# Copyright © 2026 PricewaterhouseCoopers LLP (PwC US).
# This file is the property of PwC US. Licensed under the MIT License.

"""
Scalability benchmark: Fan-out testing with N worker agents.
"""
import asyncio
import json
import time
from pathlib import Path
import sys
from typing import List
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.pqc_agents.orchestrator_agent import OrchestratorAgent
from src.pqc_agents.secure_search_agent import SecureSearchAgent
from src.pqc_agents.classical_orchestrator import ClassicalOrchestrator
from src.pqc_agents.classical_search_agent import ClassicalSearchAgent
from src.security.benchmark_metadata import run_metadata
from results_paths import result_path


async def benchmark_pqc_fanout(num_workers: int, queries_per_worker: int = 1) -> dict:
    """Benchmark authenticated ML-KEM/AEAD fan-out (no network I/O)."""
    orchestrator = OrchestratorAgent(f"pqc_orch_{num_workers}")
    workers = []
    
    # Create and register workers
    for i in range(num_workers):
        worker = SecureSearchAgent(f"pqc_worker_{num_workers}_{i}")
        orchestrator.register_worker(worker.agent_id, worker.get_public_key())
        workers.append(worker)
    
    # Measure fan-out crypto operations
    start_time = time.perf_counter()
    
    tasks = []
    for i, worker in enumerate(workers):
        async def establish_exchange_teardown(worker_agent, idx):
            result = await orchestrator.delegate_search(
                worker_agent,
                [f"test query {idx}"],
                {"search_api": "mock"},
                max_results=2,
                teardown=True,
            )
            return result.get("status") == "success"
        
        tasks.append(establish_exchange_teardown(worker, i))
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    end_time = time.perf_counter()
    total_time = (end_time - start_time) * 1000
    
    return {
        "num_workers": num_workers,
        "total_time_ms": total_time,
        "avg_time_per_worker_ms": total_time / num_workers,
        "successful": sum(1 for r in results if r is True),
        "failed": sum(1 for r in results if r is not True)
    }


async def benchmark_classical_fanout(num_workers: int, queries_per_worker: int = 1) -> dict:
    """Benchmark classical system with N workers (crypto only, no network)."""
    orchestrator = ClassicalOrchestrator(f"classical_orch_{num_workers}")
    workers = []
    
    # Create and register workers
    for i in range(num_workers):
        worker = ClassicalSearchAgent(f"classical_worker_{num_workers}_{i}")
        orchestrator.register_worker(worker.agent_id, worker.get_public_key())
        workers.append(worker)
    
    # Measure fan-out crypto operations
    start_time = time.perf_counter()
    
    tasks = []
    for i, worker in enumerate(workers):
        async def sign_and_verify(worker_agent, idx):
            import secrets
            payload = {
                "query_id": secrets.token_hex(16),
                "queries": [f"test query {idx}"],
                "max_results": 2,
                "date_range": None
            }
            signed = orchestrator.message_handler.sign_message(payload)
            verified = worker_agent.message_handler.verify_message(
                signed,
                orchestrator.identity.get_public_key()
            )
            return verified
        
        tasks.append(sign_and_verify(worker, i))
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    end_time = time.perf_counter()
    total_time = (end_time - start_time) * 1000
    
    return {
        "num_workers": num_workers,
        "total_time_ms": total_time,
        "avg_time_per_worker_ms": total_time / num_workers,
        "successful": sum(1 for r in results if r is True),
        "failed": sum(1 for r in results if r is not True)
    }


async def run_scalability_tests(worker_counts: List[int], iterations: int = 3):
    """Run scalability tests for different worker counts."""
    pqc_results = []
    classical_results = []
    
    for num_workers in worker_counts:
        print(f"\n[PQC] Testing with {num_workers} workers...")
        pqc_times = []
        for i in range(iterations):
            result = await benchmark_pqc_fanout(num_workers)
            pqc_times.append(result["total_time_ms"])
            print(f"  Iteration {i+1}: {result['total_time_ms']:.2f}ms")
        
        pqc_results.append({
            "num_workers": num_workers,
            "mean_time_ms": sum(pqc_times) / len(pqc_times),
            "min_time_ms": min(pqc_times),
            "max_time_ms": max(pqc_times)
        })
        
        print(f"\n[Classical] Testing with {num_workers} workers...")
        classical_times = []
        for i in range(iterations):
            result = await benchmark_classical_fanout(num_workers)
            classical_times.append(result["total_time_ms"])
            print(f"  Iteration {i+1}: {result['total_time_ms']:.2f}ms")
        
        classical_results.append({
            "num_workers": num_workers,
            "mean_time_ms": sum(classical_times) / len(classical_times),
            "min_time_ms": min(classical_times),
            "max_time_ms": max(classical_times)
        })
    
    return pqc_results, classical_results


def generate_scalability_report(pqc_results: List[dict], classical_results: List[dict]):
    """Generate scalability analysis report."""
    print("\n" + "="*60)
    print("SCALABILITY ANALYSIS RESULTS")
    print("="*60)
    
    print("\n## Fan-Out Performance\n")
    print("| Workers | PQC Time (ms) | Classical Time (ms) | PQC Overhead |")
    print("|---------|---------------|---------------------|--------------|")
    
    for pqc, classical in zip(pqc_results, classical_results):
        overhead = ((pqc["mean_time_ms"] / classical["mean_time_ms"]) - 1) * 100
        print(
            f"| {pqc['num_workers']:7d} | {pqc['mean_time_ms']:13.2f} | "
            f"{classical['mean_time_ms']:19.2f} | {overhead:+11.1f}% |"
        )
    
    print("\n## Scalability Metrics\n")
    print("| Workers | PQC Throughput (req/s) | Classical Throughput (req/s) |")
    print("|---------|------------------------|------------------------------|")
    
    for pqc, classical in zip(pqc_results, classical_results):
        pqc_throughput = (pqc["num_workers"] * 1000) / pqc["mean_time_ms"]
        classical_throughput = (classical["num_workers"] * 1000) / classical["mean_time_ms"]
        print(f"| {pqc['num_workers']:7d} | {pqc_throughput:22.2f} | {classical_throughput:28.2f} |")
    
    print("\n## Scaling Efficiency\n")
    print("| Workers | PQC Time/Worker (ms) | Classical Time/Worker (ms) |")
    print("|---------|----------------------|----------------------------|")
    
    for pqc, classical in zip(pqc_results, classical_results):
        pqc_per_worker = pqc["mean_time_ms"] / pqc["num_workers"]
        classical_per_worker = classical["mean_time_ms"] / classical["num_workers"]
        print(f"| {pqc['num_workers']:7d} | {pqc_per_worker:20.2f} | {classical_per_worker:26.2f} |")


def generate_plot_data(pqc_results: List[dict], classical_results: List[dict]):
    """Generate data for plotting."""
    plot_data = {
        "worker_counts": [r["num_workers"] for r in pqc_results],
        "pqc_times": [r["mean_time_ms"] for r in pqc_results],
        "classical_times": [r["mean_time_ms"] for r in classical_results],
        "pqc_throughput": [(r["num_workers"] * 1000) / r["mean_time_ms"] for r in pqc_results],
        "classical_throughput": [(r["num_workers"] * 1000) / r["mean_time_ms"] for r in classical_results]
    }
    return plot_data


async def main():
    """Run scalability benchmarks."""
    print("="*60)
    print("SCALABILITY BENCHMARK: Fan-Out Testing")
    print("="*60)
    
    worker_counts = [1, 5, 10, 25, 50]
    iterations = 3
    
    print(f"\nTesting worker counts: {worker_counts}")
    print(f"Iterations per configuration: {iterations}\n")
    
    pqc_results, classical_results = await run_scalability_tests(worker_counts, iterations)
    
    generate_scalability_report(pqc_results, classical_results)
    
    # Save results
    output = {
        "measurement_type": "M-local",
        "provenance": "Phase I local scalability fan-out benchmark",
        "run_metadata": run_metadata(repetitions=iterations),
        "pqc_results": pqc_results,
        "classical_results": classical_results,
        "plot_data": generate_plot_data(pqc_results, classical_results)
    }
    
    output_file = result_path("scalability_results.json")
    with output_file.open("w") as f:
        json.dump(output, f, indent=2)
    
    print(f"\n\nResults saved to: {output_file}")


if __name__ == "__main__":
    asyncio.run(main())
