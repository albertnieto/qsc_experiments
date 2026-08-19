# Copyright © 2026 PricewaterhouseCoopers LLP (PwC US).
# This file is the property of PwC US. Licensed under the MIT License.

"""
Unified Framework Lifecycle Benchmark
Maps directly to research paper's operational steps and three-layer security architecture.
"""
import asyncio
import json
import logging
import time
import random
import os
from typing import Dict, List, Tuple
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.pqc_agents.orchestrator_agent import OrchestratorAgent
from src.pqc_agents.secure_search_agent import SecureSearchAgent
from src.pqc_agents.classical_orchestrator import ClassicalOrchestrator
from src.pqc_agents.classical_search_agent import ClassicalSearchAgent
from src.security.performance_metrics import PerformanceMetrics
from src.security.qkd_simulator import QKDSimulator
from src.security.benchmark_metadata import run_metadata
from results_paths import result_path


class LifecycleMetrics:
    """Enhanced metrics aligned with paper's operational steps."""
    
    def __init__(self):
        self.pqc_metrics = PerformanceMetrics()
        self.classical_metrics = PerformanceMetrics()
        self.security_stats = {
            "tampered_injected": 0,
            "tampered_detected": 0,
            "replay_injected": 0,
            "replay_detected": 0,
            "legitimate_success": 0,
            "legitimate_failed": 0
        }


async def benchmark_secure_session_bootstrap(metrics: LifecycleMetrics, iterations: int = 50):
    """
    Operational Step 1: Quantum-Secured Session Bootstrap
    Tests ML-DSA-authenticated ML-KEM session establishment.
    """
    print(f"\n[Step 1] Secure Session Bootstrap ({iterations} iterations)...")
    
    # PQC System
    for i in range(iterations):
        orchestrator = OrchestratorAgent(f"orch_pqc_{i}")
        worker = SecureSearchAgent(f"worker_pqc_{i}")
        orchestrator.register_worker(worker.agent_id, worker.get_public_key())
        
        with metrics.pqc_metrics.measure("bootstrap_session"):
            session, _ = orchestrator.establish_session(
                worker,
                session_context=f"lifecycle-bootstrap:{i}".encode(),
            )
            if session.transcript_hash not in worker.sessions:
                raise ValueError("receiver session establishment failed")
        orchestrator.teardown_session(worker)
    
    # Classical System
    for i in range(iterations):
        orchestrator = ClassicalOrchestrator(f"orch_classical_{i}")
        worker = ClassicalSearchAgent(f"worker_classical_{i}")
        orchestrator.register_worker(worker.agent_id, worker.get_public_key())
        
        with metrics.classical_metrics.measure("bootstrap_session"):
            import secrets
            nonce = secrets.token_hex(32)
            response = await worker.handle_handshake(nonce)
            signature = bytes.fromhex(response["signature"])
            orchestrator.identity.verify(nonce.encode(), signature, worker.get_public_key())


async def benchmark_secure_task_graph_construction(metrics: LifecycleMetrics, iterations: int = 100):
    """
    Operational Step 3: Secure Task Graph Construction
    Tests signing of task graph structures with PQC.
    """
    print(f"\n[Step 3] Task Graph Construction ({iterations} iterations)...")
    
    task_graph = {
        "nodes": [
            {"id": "node_1", "task": "search", "query": "quantum computing"},
            {"id": "node_2", "task": "analyze", "depends_on": ["node_1"]},
            {"id": "node_3", "task": "synthesize", "depends_on": ["node_2"]}
        ],
        "edges": [
            {"from": "node_1", "to": "node_2"},
            {"from": "node_2", "to": "node_3"}
        ]
    }
    
    # PQC System
    orchestrator_pqc = OrchestratorAgent("orch_pqc_graph")
    task_graph_bytes = json.dumps(task_graph).encode()
    
    for _ in range(iterations):
        with metrics.pqc_metrics.measure("task_graph_construction_sign"):
            orchestrator_pqc.identity.sign(task_graph_bytes)
    
    # Classical System
    orchestrator_classical = ClassicalOrchestrator("orch_classical_graph")
    
    for _ in range(iterations):
        with metrics.classical_metrics.measure("task_graph_construction_sign"):
            orchestrator_classical.identity.sign(task_graph_bytes)


async def benchmark_agent_communication(metrics: LifecycleMetrics, iterations: int = 100):
    """
    Operational Step 4: Secure Agent Execution & Communication
    Tests routine AEAD traffic after ML-DSA/ML-KEM + modeled-QKD setup.
    """
    print(f"\n[Step 4] Agent Communication ({iterations} iterations)...")
    
    # PQC System
    orchestrator_pqc = OrchestratorAgent("orch_pqc_comm")
    worker_pqc = SecureSearchAgent("worker_pqc_comm")
    orchestrator_pqc.register_worker(worker_pqc.agent_id, worker_pqc.get_public_key())
    with metrics.pqc_metrics.measure("qkd_key_establishment_sim"):
        session, _ = orchestrator_pqc.establish_session(
            worker_pqc,
            session_context=b"lifecycle-agent-communication",
            use_qkd=True,
            qkd_epoch="lifecycle-communication",
        )
    
    for i in range(iterations):
        with metrics.pqc_metrics.measure("agent_communication_e2e"):
            with metrics.pqc_metrics.measure("qrng_nonce_generation"):
                query_id = orchestrator_pqc.qrng.generate_query_id()
            payload = {
                "query_id": query_id,
                "queries": [f"test_{i}"],
                "max_results": 2,
                "date_range": None,
            }
            with metrics.pqc_metrics.measure("agent_communication_encrypt"):
                envelope = orchestrator_pqc.message_handler.encrypt_payload(
                    payload,
                    session,
                    aad=f"qsc-task:{query_id}".encode(),
                )
            encrypted_response = await worker_pqc.execute_search(
                envelope,
                orchestrator_pqc.identity.get_public_key(),
                {"search_api": "mock"},
            )
            with metrics.pqc_metrics.measure("agent_communication_decrypt"):
                response = orchestrator_pqc.message_handler.decrypt_payload(
                    encrypted_response,
                    session,
                    aad=f"qsc-result:{query_id}".encode(),
                )
            if response.get("status") != "success":
                raise ValueError("lifecycle AEAD exchange failed")
    orchestrator_pqc.teardown_session(worker_pqc)
    
    # Classical System
    orchestrator_classical = ClassicalOrchestrator("orch_classical_comm")
    worker_classical = ClassicalSearchAgent("worker_classical_comm")
    orchestrator_classical.register_worker(worker_classical.agent_id, worker_classical.get_public_key())
    
    for i in range(iterations):
        with metrics.classical_metrics.measure("agent_communication_e2e"):
            import secrets
            nonce = secrets.token_hex(32)
            shared_key = secrets.token_bytes(32)
            
            message = {"query": f"test_{i}", "nonce": nonce}
            message_bytes = json.dumps(message).encode()
            
            signature = orchestrator_classical.identity.sign(message_bytes)
            orchestrator_classical.identity.verify(message_bytes, signature, orchestrator_classical.identity.get_public_key())


async def benchmark_scalability_fanout(metrics: LifecycleMetrics, worker_counts: List[int], iterations: int = 3):
    """
    Scalability Test: Full agent communication protocol with N workers.
    Tests how the complete three-layer security scales.
    """
    print(f"\n[Scalability] Testing worker counts: {worker_counts}")
    from benchmark_scalability import (
        benchmark_classical_fanout,
        benchmark_pqc_fanout,
    )
    
    pqc_results = []
    classical_results = []
    
    for num_workers in worker_counts:
        print(f"\n  Testing {num_workers} workers...")
        
        pqc_times = []
        for iteration in range(iterations):
            result = await benchmark_pqc_fanout(num_workers)
            pqc_times.append(result["total_time_ms"])
        
        pqc_results.append({
            "num_workers": num_workers,
            "mean_time_ms": sum(pqc_times) / len(pqc_times),
            "min_time_ms": min(pqc_times),
            "max_time_ms": max(pqc_times)
        })
        
        classical_times = []
        for iteration in range(iterations):
            result = await benchmark_classical_fanout(num_workers)
            classical_times.append(result["total_time_ms"])
        
        classical_results.append({
            "num_workers": num_workers,
            "mean_time_ms": sum(classical_times) / len(classical_times),
            "min_time_ms": min(classical_times),
            "max_time_ms": max(classical_times)
        })
    
    return pqc_results, classical_results


async def benchmark_security_resilience(metrics: LifecycleMetrics, num_transactions: int = 100000):
    """Reuse the canonical AEAD tamper/replay conformance simulation."""
    print(f"\n[Security] Running {num_transactions} transactions with attack injection...")
    from benchmark_security import run_security_simulation

    canonical = await run_security_simulation(
        num_transactions=num_transactions,
        attack_probability=0.05,
    )
    data = canonical.to_dict()
    for key in metrics.security_stats:
        metrics.security_stats[key] = data[key]


def generate_lifecycle_report(metrics: LifecycleMetrics, pqc_scale: List[dict], classical_scale: List[dict]):
    """Generate comprehensive lifecycle benchmark report."""
    
    print("\n" + "="*70)
    print("FRAMEWORK LIFECYCLE BENCHMARK RESULTS")
    print("="*70)
    
    pqc_summary = metrics.pqc_metrics.get_summary()
    classical_summary = metrics.classical_metrics.get_summary()
    
    # Protocol-Centric Table (for paper)
    print("\n## Operational Step Performance\n")
    print("| Operational Step                 | Security Layers | PQC (ms) | Classical (ms) | Overhead (%) |")
    print("|----------------------------------|-----------------|----------|----------------|--------------|")
    
    steps = [
        (
            "1. Secure Session Bootstrap",
            "ML-KEM, ML-DSA, QRNG",
            "bootstrap_session",
        ),
        (
            "2. Task Graph Signing",
            "ML-DSA",
            "task_graph_construction_sign",
        ),
        (
            "3. Secure Agent Communication",
            "AES-GCM, QRNG, Model-QKD",
            "agent_communication_e2e",
        ),
    ]
    
    for label, layers, metric_key in steps:
        if metric_key in pqc_summary and metric_key in classical_summary:
            pqc_val = pqc_summary[metric_key]["mean_ms"]
            classical_val = classical_summary[metric_key]["mean_ms"]
            overhead = ((pqc_val / classical_val) - 1) * 100
            print(
                f"| {label:32s} | {layers:15s} | {pqc_val:8.2f} | "
                f"{classical_val:14.2f} | {overhead:+11.1f}% |"
            )
    
    # Layer-Specific Performance
    print("\n## Security Layer Performance\n")
    print("| Layer | Operation | PQC (ms) | Classical (ms) |")
    print("|-------|-----------|----------|----------------|")
    
    layer_metrics = [
        ("Routine AEAD", "Encrypt", "agent_communication_encrypt"),
        ("Routine AEAD", "Decrypt", "agent_communication_decrypt"),
        ("Layer 2 (QRNG)", "Nonce Gen", "qrng_nonce_generation"),
        ("Layer 3 (QKD)", "Key Establish", "qkd_key_establishment_sim")
    ]
    
    for layer, op, metric_key in layer_metrics:
        if metric_key in pqc_summary:
            pqc_val = pqc_summary[metric_key]["mean_ms"]
            classical_val = classical_summary.get(metric_key, {}).get("mean_ms", 0)
            if classical_val > 0:
                print(f"| {layer:13s} | {op:9s} | {pqc_val:8.3f} | {classical_val:14.3f} |")
            else:
                print(f"| {layer:13s} | {op:9s} | {pqc_val:8.3f} | N/A            |")
    
    # Scalability Results
    print("\n## Scalability Analysis\n")
    print("| Workers | PQC Time (ms) | Classical Time (ms) | Overhead (%) |")
    print("|---------|---------------|---------------------|--------------|")
    
    for pqc, classical in zip(pqc_scale, classical_scale):
        overhead = ((pqc["mean_time_ms"] / classical["mean_time_ms"]) - 1) * 100
        print(
            f"| {pqc['num_workers']:7d} | {pqc['mean_time_ms']:13.2f} | "
            f"{classical['mean_time_ms']:19.2f} | {overhead:+11.1f}% |"
        )
    
    # Security Resilience
    stats = metrics.security_stats
    total_attacks = stats["tampered_injected"] + stats["replay_injected"]
    total_detected = stats["tampered_detected"] + stats["replay_detected"]
    
    print("\n## Security Resilience\n")
    print(f"Tampered payloads detected: {stats['tampered_detected']}/{stats['tampered_injected']} " +
          f"(AES-256-GCM authentication)")
    print(f"Replay attacks detected: {stats['replay_detected']}/{stats['replay_injected']} " +
          f"(per-session nonce replay state)")
    print(f"\nOverall detection rate: {total_detected}/{total_attacks} " +
          f"({total_detected/total_attacks*100 if total_attacks > 0 else 0:.1f}%)")
    
    print("\n" + "="*70 + "\n")


async def main():
    """Execute unified framework lifecycle benchmark."""
    
    print("="*70)
    print("QUANTUM-SECURED AGENTIC AI FRAMEWORK LIFECYCLE BENCHMARK")
    print("="*70)
    print("\nMapping to Research Paper:")
    print("  - Identity and artifacts: ML-DSA-65")
    print("  - Session establishment: ML-KEM-768 + QRNG input")
    print("  - Routine traffic: AES-256-GCM")
    print("  - Optional modeled input: QKD")
    print("="*70)
    
    random.seed(20260811)
    metrics = LifecycleMetrics()
    
    # Core Operational Steps
    await benchmark_secure_session_bootstrap(metrics, iterations=50)
    await benchmark_secure_task_graph_construction(metrics, iterations=100)
    await benchmark_agent_communication(metrics, iterations=100)
    
    # Scalability Testing
    worker_counts = [1, 5, 10, 25, 50]
    pqc_scale, classical_scale = await benchmark_scalability_fanout(metrics, worker_counts, iterations=3)
    
    # Security Resilience
    num_transactions = int(os.environ.get("QSC_SECURITY_TRANSACTIONS", "100000"))
    await benchmark_security_resilience(metrics, num_transactions=num_transactions)
    
    # Generate Report
    generate_lifecycle_report(metrics, pqc_scale, classical_scale)
    
    # Export Results
    output = {
        "operational_steps": {
            "pqc": metrics.pqc_metrics.get_summary(),
            "classical": metrics.classical_metrics.get_summary()
        },
        "scalability": {
            "pqc_results": pqc_scale,
            "classical_results": classical_scale,
            "scope": (
                "non-canonical integration snapshot; use "
                "scalability_results.json for manuscript claims"
            ),
        },
        "security_resilience": metrics.security_stats,
        "canonical_related_artifacts": {
            "scalability": "scalability_results.json",
            "security": "security_results.json",
        },
    }
    
    output["measurement_type"] = "mixed"
    output["provenance"] = (
        "M-local lifecycle benchmark with Model-QKD timing and S-simulation attacks"
    )
    output["run_metadata"] = run_metadata(repetitions=num_transactions)
    output_file = result_path("lifecycle_benchmark_results.json")
    with output_file.open("w") as f:
        json.dump(output, f, indent=2)
    
    print(f"Results exported to: {output_file}\n")


if __name__ == "__main__":
    asyncio.run(main())
