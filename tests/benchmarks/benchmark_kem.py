# Copyright © 2026 PricewaterhouseCoopers LLP (PwC US).
# This file is the property of PwC US. Licensed under the MIT License.

"""
 KEM Benchmark: ML-KEM-768 vs ECDH (P-256)
"""
import time
import json
import resource
import statistics
import math
from pathlib import Path
import sys
import oqs
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.security.benchmark_metadata import run_metadata
from results_paths import result_path

ITERATIONS = 1000

def benchmark_kyber():
    """Benchmark ML-KEM-768 using the liboqs Kyber768 identifier."""
    results = {
        "encapsulation_times": [],
        "decapsulation_times": [],
        "public_key_size": 0,
        "ciphertext_size": 0
    }
    
    try:
        kem_algorithm = "ML-KEM-768"
        kem = oqs.KeyEncapsulation(kem_algorithm)
    except Exception:
        kem_algorithm = "Kyber768"
        kem = oqs.KeyEncapsulation(kem_algorithm)
    
    # Key generation (Bob)
    public_key = kem.generate_keypair()
    results["public_key_size"] = len(public_key)
    
    for _ in range(ITERATIONS):
        # Encapsulation (Alice)
        start = time.perf_counter()
        ciphertext, shared_secret_alice = kem.encap_secret(public_key)
        results["encapsulation_times"].append((time.perf_counter() - start) * 1000)
        
        # Decapsulation (Bob)
        start = time.perf_counter()
        shared_secret_bob = kem.decap_secret(ciphertext)
        results["decapsulation_times"].append((time.perf_counter() - start) * 1000)
    
    results["ciphertext_size"] = len(ciphertext)
    results["algorithm"] = kem_algorithm
    raw_peak_rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    # macOS reports bytes; Linux reports KiB. Normalize the publication field.
    results["peak_rss_bytes"] = (
        raw_peak_rss
        if sys.platform == "darwin"
        else raw_peak_rss * 1024
    )
    results["peak_rss_source_unit"] = (
        "bytes" if sys.platform == "darwin" else "KiB"
    )
    results["wire_bytes_per_exchange"] = (
        results["public_key_size"] + results["ciphertext_size"] + len(shared_secret_alice)
    )
    return results

def benchmark_ecdh():
    """Benchmark ECDH P-256"""
    results = {
        "key_exchange_times": [],
        "public_key_size": 0
    }
    
    for _ in range(ITERATIONS):
        start = time.perf_counter()
        
        # Alice generates key pair
        alice_private = ec.generate_private_key(ec.SECP256R1(), default_backend())
        alice_public = alice_private.public_key()
        
        # Bob generates key pair
        bob_private = ec.generate_private_key(ec.SECP256R1(), default_backend())
        bob_public = bob_private.public_key()
        
        # Derive shared secret
        alice_private.exchange(ec.ECDH(), bob_public)
        
        results["key_exchange_times"].append((time.perf_counter() - start) * 1000)
    
    # Get public key size
    from cryptography.hazmat.primitives import serialization
    pub_bytes = alice_public.public_bytes(
        encoding=serialization.Encoding.X962,
        format=serialization.PublicFormat.UncompressedPoint
    )
    results["public_key_size"] = len(pub_bytes)
    
    return results


def mean_ci(values: list[float]) -> tuple[float, float]:
    mean = statistics.mean(values)
    if len(values) < 2:
        return mean, 0.0
    return mean, 1.96 * statistics.stdev(values) / math.sqrt(len(values))

def main():
    print("="*60)
    print("KEM BENCHMARK: ML-KEM-768 vs ECDH (P-256)")
    print("="*60)
    print(f"Iterations: {ITERATIONS}\n")
    
    print("Benchmarking ML-KEM-768...")
    kyber_results = benchmark_kyber()
    
    print("Benchmarking ECDH...")
    ecdh_results = benchmark_ecdh()
    
    # Calculate means
    kyber_encap_mean, kyber_encap_ci = mean_ci(kyber_results["encapsulation_times"])
    kyber_decap_mean, kyber_decap_ci = mean_ci(kyber_results["decapsulation_times"])
    ecdh_mean, ecdh_ci = mean_ci(ecdh_results["key_exchange_times"])
    
    # Output table
    print("\n" + "="*60)
    print("RESULTS")
    print("="*60)
    
    print("\n| Metric | PQC Mean (ms) | Classical Mean (ms) | PQC Size (bytes) | Classical Size (bytes) |")
    print("|--------|---------------|---------------------|------------------|------------------------|")
    print(f"| Key Encapsulation | {kyber_encap_mean:.4f} | {ecdh_mean:.4f} | N/A | N/A |")
    print(f"| Key Decapsulation | {kyber_decap_mean:.4f} | N/A | N/A | N/A |")
    print(f"| Public Key Size | N/A | N/A | {kyber_results['public_key_size']} | {ecdh_results['public_key_size']} |")
    print(f"| Ciphertext Size | N/A | N/A | {kyber_results['ciphertext_size']} | N/A |")
    
    # Export JSON
    output = {
        "measurement_type": "M-local",
        "provenance": "Phase I local KEM benchmark",
        "run_metadata": run_metadata(repetitions=ITERATIONS),
        "kem": {
            "algorithm": kyber_results["algorithm"],
            "encapsulation_mean_ms": kyber_encap_mean,
            "encapsulation_ci95_ms": kyber_encap_ci,
            "decapsulation_mean_ms": kyber_decap_mean,
            "decapsulation_ci95_ms": kyber_decap_ci,
            "public_key_size_bytes": kyber_results["public_key_size"],
            "ciphertext_size_bytes": kyber_results["ciphertext_size"],
            "peak_rss_bytes": kyber_results["peak_rss_bytes"],
            "peak_rss_source_unit": kyber_results["peak_rss_source_unit"],
            "wire_bytes_per_exchange": kyber_results["wire_bytes_per_exchange"],
        },
        "ecdh": {
            "key_exchange_mean_ms": ecdh_mean,
            "key_exchange_ci95_ms": ecdh_ci,
            "public_key_size_bytes": ecdh_results["public_key_size"]
        }
    }
    
    output_file = result_path("kem_benchmark_results.json")
    with output_file.open("w") as f:
        json.dump(output, f, indent=2)
    
    print(f"\n✓ Results saved to: {output_file}")

if __name__ == "__main__":
    main()
