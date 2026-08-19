# Copyright © 2026 PricewaterhouseCoopers LLP (PwC US).
# This file is the property of PwC US. Licensed under the MIT License.

"""
Comparative benchmark: PQC vs Classical cryptography.
"""
import asyncio
import json
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.pqc_agents.orchestrator_agent import OrchestratorAgent
from src.pqc_agents.secure_search_agent import SecureSearchAgent
from src.pqc_agents.classical_orchestrator import ClassicalOrchestrator
from src.pqc_agents.classical_search_agent import ClassicalSearchAgent
from src.security.performance_metrics import PerformanceMetrics
from results_paths import result_path


async def benchmark_pqc_system(metrics: PerformanceMetrics, iterations: int = 100):
    """Benchmark PQC-based system (crypto only, no network)."""
    print(f"\n[PQC] Running {iterations} iterations...")
    
    orchestrator = OrchestratorAgent("pqc_orch")
    search_agent = SecureSearchAgent("pqc_search")
    orchestrator.register_worker(search_agent.agent_id, search_agent.get_public_key())
    
    for i in range(iterations):
        queries = [f"test query {i}"]
        
        with metrics.measure("pqc_message_signing"):
            payload = {
                "query_id": orchestrator.qrng.generate_query_id(),
                "queries": queries,
                "max_results": 2,
                "date_range": None
            }
            signed_payload = orchestrator.message_handler.sign_message(payload)
        
        with metrics.measure("pqc_message_verification"):
            search_agent.message_handler.verify_message(
                signed_payload,
                orchestrator.identity.get_public_key()
            )


async def benchmark_classical_system(metrics: PerformanceMetrics, iterations: int = 100):
    """Benchmark classical Ed25519-based system (crypto only, no network)."""
    print(f"\n[Classical] Running {iterations} iterations...")
    
    orchestrator = ClassicalOrchestrator("classical_orch")
    search_agent = ClassicalSearchAgent("classical_search")
    orchestrator.register_worker(search_agent.agent_id, search_agent.get_public_key())
    
    for i in range(iterations):
        queries = [f"test query {i}"]
        
        with metrics.measure("classical_message_signing"):
            import secrets
            payload = {
                "query_id": secrets.token_hex(16),
                "queries": queries,
                "max_results": 2,
                "date_range": None
            }
            signed_payload = orchestrator.message_handler.sign_message(payload)
        
        with metrics.measure("classical_message_verification"):
            search_agent.message_handler.verify_message(
                signed_payload,
                orchestrator.identity.get_public_key()
            )


def benchmark_crypto_primitives(metrics: PerformanceMetrics, iterations: int = 100):
    """Benchmark individual crypto operations."""
    print(f"\n[Primitives] Benchmarking {iterations} iterations...")
    
    # PQC primitives
    from src.security.pqc_identity import PQCIdentity
    pqc_id = PQCIdentity("bench")
    message = b"test" * 100
    
    for _ in range(iterations):
        with metrics.measure("pqc_keygen"):
            temp = PQCIdentity("temp")
            pubkey = temp.get_public_key()
        with metrics.measure("pqc_pubkey_size", size_bytes=len(pubkey)):
            pass
    
    for _ in range(iterations):
        with metrics.measure("pqc_sign"):
            sig = pqc_id.sign(message)
        with metrics.measure("pqc_sig_size", size_bytes=len(sig)):
            pass
    
    pubkey = pqc_id.get_public_key()
    sig = pqc_id.sign(message)
    for _ in range(iterations):
        with metrics.measure("pqc_verify"):
            pqc_id.verify(message, sig, pubkey)
    
    # Classical primitives
    from src.security.classical_identity import ClassicalIdentity
    classical_id = ClassicalIdentity("bench")
    
    for _ in range(iterations):
        with metrics.measure("classical_keygen"):
            temp = ClassicalIdentity("temp")
            pubkey = temp.get_public_key()
        with metrics.measure("classical_pubkey_size", size_bytes=len(pubkey)):
            pass
    
    for _ in range(iterations):
        with metrics.measure("classical_sign"):
            sig = classical_id.sign(message)
        with metrics.measure("classical_sig_size", size_bytes=len(sig)):
            pass
    
    pubkey = classical_id.get_public_key()
    sig = classical_id.sign(message)
    for _ in range(iterations):
        with metrics.measure("classical_verify"):
            classical_id.verify(message, sig, pubkey)


async def main():
    """Run comparative benchmarks."""
    print("="*60)
    print("COMPARATIVE BENCHMARK: PQC vs Classical")
    print("="*60)
    
    metrics = PerformanceMetrics()
    
    benchmark_crypto_primitives(metrics, iterations=100)
    await benchmark_pqc_system(metrics, iterations=100)
    await benchmark_classical_system(metrics, iterations=100)
    
    print("\n" + "="*60)
    print("COMPARATIVE RESULTS")
    print("="*60)
    
    summary = metrics.get_summary()
    
    # Generate comparison table
    print("\n| Operation | PQC (ms) | Classical (ms) | Overhead |")
    print("|-----------|----------|----------------|----------|")
    
    comparisons = [
        ("Key Generation", "pqc_keygen", "classical_keygen"),
        ("Signing", "pqc_sign", "classical_sign"),
        ("Verification", "pqc_verify", "classical_verify"),
        ("Message Signing", "pqc_message_signing", "classical_message_signing"),
        ("Message Verification", "pqc_message_verification", "classical_message_verification"),
    ]
    
    for label, pqc_key, classical_key in comparisons:
        if pqc_key in summary and classical_key in summary:
            pqc_val = summary[pqc_key]["mean_ms"]
            classical_val = summary[classical_key]["mean_ms"]
            overhead = ((pqc_val / classical_val) - 1) * 100
            print(
                f"| {label} | {pqc_val:.2f} | {classical_val:.2f} | "
                f"{overhead:+.1f}% |"
            )
    
    # Size comparison
    print("\n| Artifact | PQC (bytes) | Classical (bytes) | Overhead |")
    print("|----------|-------------|-------------------|----------|")
    
    size_comparisons = [
        ("Public Key", "pqc_pubkey_size", "classical_pubkey_size"),
        ("Signature", "pqc_sig_size", "classical_sig_size"),
    ]
    
    for label, pqc_key, classical_key in size_comparisons:
        if pqc_key in summary and classical_key in summary:
            pqc_val = summary[pqc_key]["total_bytes"] / summary[pqc_key]["count"]
            classical_val = summary[classical_key]["total_bytes"] / summary[classical_key]["count"]
            overhead = ((pqc_val / classical_val) - 1) * 100
            print(
                f"| {label} | {int(pqc_val)} | {int(classical_val)} | "
                f"{overhead:+.1f}% |"
            )
    
    # Throughput comparison
    print("\n| System | Throughput (msg/sec) |")
    print("|--------|----------------------|")
    
    if "pqc_message_signing" in summary:
        pqc_throughput = 1000 / summary["pqc_message_signing"]["mean_ms"]
        print(f"| PQC | {pqc_throughput:.2f} |")
    
    if "classical_message_signing" in summary:
        classical_throughput = 1000 / summary["classical_message_signing"]["mean_ms"]
        print(f"| Classical | {classical_throughput:.2f} |")
    
    # Export results
    output_file = result_path("comparative_results.json")
    metrics.export_json(str(output_file))
    print(f"\nResults exported to: {output_file}")


if __name__ == "__main__":
    asyncio.run(main())
