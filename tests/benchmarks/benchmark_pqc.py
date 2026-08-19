# Copyright © 2026 PricewaterhouseCoopers LLP (PwC US).
# This file is the property of PwC US. Licensed under the MIT License.

"""
Benchmark PQC operations for paper results.
"""
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.pqc_agents.orchestrator_agent import OrchestratorAgent
from src.pqc_agents.secure_search_agent import SecureSearchAgent
from src.security.performance_metrics import PerformanceMetrics
from results_paths import result_path


async def benchmark_identity_generation(metrics: PerformanceMetrics, iterations: int = 100):
    """Benchmark key pair generation."""
    print(f"\nBenchmarking identity generation ({iterations} iterations)...")
    
    for i in range(iterations):
        with metrics.measure("key_generation"):
            agent = OrchestratorAgent(f"agent_{i}")
            pubkey = agent.identity.get_public_key()
        
        with metrics.measure("key_size", size_bytes=len(pubkey)):
            pass


async def benchmark_signing(metrics: PerformanceMetrics, iterations: int = 100):
    """Benchmark message signing."""
    print(f"\nBenchmarking signing operations ({iterations} iterations)...")
    
    orchestrator = OrchestratorAgent("bench_orch")
    message = b"Test message for benchmarking" * 10  # ~300 bytes
    
    for i in range(iterations):
        with metrics.measure("sign_message", size_bytes=len(message)):
            signature = orchestrator.identity.sign(message)
        
        with metrics.measure("signature_size", size_bytes=len(signature)):
            pass


async def benchmark_verification(metrics: PerformanceMetrics, iterations: int = 100):
    """Benchmark signature verification."""
    print(f"\nBenchmarking verification operations ({iterations} iterations)...")
    
    orchestrator = OrchestratorAgent("bench_orch")
    message = b"Test message for benchmarking" * 10
    signature = orchestrator.identity.sign(message)
    pubkey = orchestrator.identity.get_public_key()
    
    for i in range(iterations):
        with metrics.measure("verify_signature"):
            result = orchestrator.identity.verify(message, signature, pubkey)
            assert result is True


async def benchmark_handshake(metrics: PerformanceMetrics, iterations: int = 50):
    """Benchmark full handshake process."""
    print(f"\nBenchmarking handshake ({iterations} iterations)...")
    
    for i in range(iterations):
        orchestrator = OrchestratorAgent(f"orch_{i}")
        search_agent = SecureSearchAgent(f"search_{i}")
        orchestrator.register_worker(search_agent.agent_id, search_agent.get_public_key())
        
        with metrics.measure("handshake_full"):
            result = await orchestrator.perform_handshake(search_agent)
            assert result is True


async def benchmark_query_delegation(metrics: PerformanceMetrics, iterations: int = 20):
    """Benchmark secure query delegation."""
    print(f"\nBenchmarking query delegation ({iterations} iterations)...")
    
    orchestrator = OrchestratorAgent("bench_orch")
    search_agent = SecureSearchAgent("bench_search")
    orchestrator.register_worker(search_agent.agent_id, search_agent.get_public_key())
    
    search_config = {
        "search_api": "duckduckgo",
        "fallback_apis": [],
        "timeout": 30,
        "max_retries": 1,
        "summarize_content": False
    }
    
    for i in range(iterations):
        queries = [f"test query {i}"]
        
        with metrics.measure("query_delegation_full"):
            result = await orchestrator.delegate_search(
                search_agent,
                queries,
                search_config,
                max_results=2
            )


async def benchmark_qrng(metrics: PerformanceMetrics, iterations: int = 1000):
    """Benchmark QRNG operations."""
    print(f"\nBenchmarking QRNG ({iterations} iterations)...")
    
    orchestrator = OrchestratorAgent("bench_orch")
    
    for i in range(iterations):
        with metrics.measure("qrng_query_id"):
            query_id = orchestrator.qrng.generate_query_id()
        
        with metrics.measure("qrng_nonce"):
            nonce = orchestrator.qrng.generate_nonce()
        
        with metrics.measure("qrng_session_key"):
            key = orchestrator.qrng.generate_session_key()


async def benchmark_qkd(metrics: PerformanceMetrics, iterations: int = 100):
    """Benchmark QKD operations."""
    print(f"\nBenchmarking QKD ({iterations} iterations)...")
    
    from src.security.qkd_simulator import QKDSimulator
    qkd = QKDSimulator()
    
    for i in range(iterations):
        with metrics.measure("qkd_establish_key"):
            key = qkd.establish_key(f"agent_a_{i}", f"agent_b_{i}")
        
        with metrics.measure("qkd_retrieve_key"):
            retrieved = qkd.get_shared_key(f"agent_a_{i}", f"agent_b_{i}")


async def benchmark_message_overhead(metrics: PerformanceMetrics):
    """Measure message size overhead from PQC."""
    print("\nMeasuring message overhead...")
    
    orchestrator = OrchestratorAgent("bench_orch")
    
    # Small message
    small_payload = {"query": "test", "id": "123"}
    small_signed = orchestrator.message_handler.sign_message(small_payload)
    
    # Large message
    large_payload = {"query": "test" * 100, "data": ["item"] * 50}
    large_signed = orchestrator.message_handler.sign_message(large_payload)
    
    import json
    small_original = len(json.dumps(small_payload))
    small_with_sig = len(json.dumps(small_signed))
    large_original = len(json.dumps(large_payload))
    large_with_sig = len(json.dumps(large_signed))
    
    print(f"  Small message: {small_original} → {small_with_sig} bytes ({small_with_sig/small_original:.2f}x)")
    print(f"  Large message: {large_original} → {large_with_sig} bytes ({large_with_sig/large_original:.2f}x)")
    
    with metrics.measure("message_overhead_small", size_bytes=small_with_sig - small_original):
        pass
    with metrics.measure("message_overhead_large", size_bytes=large_with_sig - large_original):
        pass


async def main():
    """Run all benchmarks."""
    print("="*60)
    print("PQC PERFORMANCE BENCHMARKING")
    print("="*60)
    
    metrics = PerformanceMetrics()
    
    await benchmark_identity_generation(metrics, iterations=100)
    await benchmark_signing(metrics, iterations=100)
    await benchmark_verification(metrics, iterations=100)
    await benchmark_handshake(metrics, iterations=50)
    await benchmark_qrng(metrics, iterations=1000)
    await benchmark_qkd(metrics, iterations=100)
    await benchmark_message_overhead(metrics)
    await benchmark_query_delegation(metrics, iterations=10)
    
    metrics.print_summary()
    
    output_file = result_path("benchmark_results.json")
    metrics.export_json(str(output_file))
    print(f"\nResults exported to: {output_file}")


if __name__ == "__main__":
    asyncio.run(main())
