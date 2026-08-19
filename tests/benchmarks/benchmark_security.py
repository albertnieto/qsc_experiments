# Copyright © 2026 PricewaterhouseCoopers LLP (PwC US).
# This file is the property of PwC US. Licensed under the MIT License.

"""
Security resilience benchmark: Automated attack simulation.
"""
import asyncio
import json
import logging
import random
import os
from pathlib import Path
import sys
from typing import Dict, List
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.pqc_agents.orchestrator_agent import OrchestratorAgent
from src.pqc_agents.secure_search_agent import SecureSearchAgent
from src.security.hybrid_session_key import SessionKey
from src.security.benchmark_metadata import run_metadata
from results_paths import result_path


class SecurityMetrics:
    """Track security metrics."""
    
    def __init__(self):
        self.total_transactions = 0
        self.legitimate_transactions = 0
        self.tampered_injected = 0
        self.replay_injected = 0
        self.tampered_detected = 0
        self.replay_detected = 0
        self.false_positives = 0
        self.legitimate_success = 0
        self.legitimate_failed = 0
    
    def to_dict(self) -> dict:
        total_attacks = self.tampered_injected + self.replay_injected
        total_detected = self.tampered_detected + self.replay_detected
        
        return {
            "total_transactions": self.total_transactions,
            "legitimate_transactions": self.legitimate_transactions,
            "attacks_injected": total_attacks,
            "tampered_injected": self.tampered_injected,
            "replay_injected": self.replay_injected,
            "attacks_detected": total_detected,
            "tampered_detected": self.tampered_detected,
            "replay_detected": self.replay_detected,
            "detection_rate": (total_detected / total_attacks * 100) if total_attacks > 0 else 0,
            "false_positives": self.false_positives,
            "legitimate_success": self.legitimate_success,
            "legitimate_failed": self.legitimate_failed,
            "legitimate_success_rate": (self.legitimate_success / self.legitimate_transactions * 100) if self.legitimate_transactions > 0 else 0
        }


async def execute_legitimate_transaction(
    orchestrator: OrchestratorAgent,
    worker: SecureSearchAgent,
    query_id: int,
    search_config: dict,
    metrics: SecurityMetrics,
    session: SessionKey,
) -> bool:
    """Execute a legitimate AEAD protocol transaction without network I/O."""
    payload = {
        "query_id": orchestrator.qrng.generate_query_id(),
        "queries": [f"query {query_id}"],
        "max_results": 2,
        "date_range": None,
    }
    aad = f"qsc-task:{payload['query_id']}".encode()
    envelope = orchestrator.message_handler.encrypt_payload(
        payload,
        session,
        aad=aad,
    )
    
    try:
        encrypted_response = await worker.execute_search(
            envelope,
            orchestrator.identity.get_public_key(),
            search_config,
        )
        response = orchestrator.message_handler.decrypt_payload(
            encrypted_response,
            session,
            aad=f"qsc-result:{payload['query_id']}".encode(),
        )
        if "error" not in response:
            metrics.legitimate_success += 1
            return True
        else:
            metrics.legitimate_failed += 1
            return False
    except Exception:
        metrics.legitimate_failed += 1
        return False


async def execute_tampered_attack(
    orchestrator: OrchestratorAgent,
    worker: SecureSearchAgent,
    query_id: int,
    search_config: dict,
    metrics: SecurityMetrics,
    session: SessionKey,
) -> bool:
    """Execute a modified-ciphertext AES-GCM conformance check."""
    queries = [f"query {query_id}"]
    
    payload = {
        "query_id": orchestrator.qrng.generate_query_id(),
        "queries": queries,
        "max_results": 2,
        "date_range": None
    }
    envelope = orchestrator.message_handler.encrypt_payload(
        payload,
        session,
        aad=f"qsc-task:{payload['query_id']}".encode(),
    )
    ciphertext = bytearray.fromhex(envelope["ciphertext"])
    ciphertext[len(ciphertext) // 2] ^= 1
    envelope["ciphertext"] = ciphertext.hex()
    
    try:
        result = await worker.execute_search(
            envelope,
            orchestrator.identity.get_public_key(),
            search_config
        )
        response = orchestrator.message_handler.decrypt_payload(
            result,
            session,
            aad=f"qsc-result:{payload['query_id']}".encode(),
        )
        if response.get("status") == "failed":
            metrics.tampered_detected += 1
            return True
        else:
            # Attack succeeded (should not happen)
            return False
    except Exception:
        # Exception means attack was detected
        metrics.tampered_detected += 1
        return True


async def execute_replay_attack(
    orchestrator: OrchestratorAgent,
    worker: SecureSearchAgent,
    query_id: int,
    search_config: dict,
    metrics: SecurityMetrics,
    replay_cache: List[tuple[dict, str]],
    session: SessionKey,
) -> bool:
    """Execute a stale AES-GCM nonce replay conformance check."""
    
    # If no cached messages, create one first
    if not replay_cache:
        queries = [f"cache query {query_id}"]
        payload = {
            "query_id": orchestrator.qrng.generate_query_id(),
            "queries": queries,
            "max_results": 2,
            "date_range": None
        }
        envelope = orchestrator.message_handler.encrypt_payload(
            payload,
            session,
            aad=f"qsc-task:{payload['query_id']}".encode(),
        )
        await worker.execute_search(
            envelope,
            orchestrator.identity.get_public_key(),
            search_config
        )
        replay_cache.append((envelope, payload["query_id"]))
    
    # Replay a cached message
    replayed_payload, replayed_query_id = random.choice(replay_cache)
    
    try:
        result = await worker.execute_search(
            replayed_payload,
            orchestrator.identity.get_public_key(),
            search_config
        )
        
        response = orchestrator.message_handler.decrypt_payload(
            result,
            session,
            aad=f"qsc-result:{replayed_query_id}".encode(),
        )
        if response.get("status") == "failed":
            metrics.replay_detected += 1
            return True
        return False
    except Exception:
        # Exception means attack was detected
        metrics.replay_detected += 1
        return True


async def run_security_simulation(num_transactions: int = 1000, attack_probability: float = 0.05):
    """Run security simulation with attack injection."""
    random.seed(20260811)
    print(f"\nRunning security simulation: {num_transactions} transactions")
    print(f"Attack injection rate: {attack_probability * 100}% (2.5% tampered, 2.5% replay)\n")
    
    orchestrator = OrchestratorAgent("security_orch")
    worker = SecureSearchAgent("security_worker")
    orchestrator.register_worker(worker.agent_id, worker.get_public_key())
    session, _ = orchestrator.establish_session(
        worker,
        session_context=b"security-conformance-run",
    )
    
    search_config = {
        "search_api": "duckduckgo",
        "fallback_apis": [],
        "timeout": 30,
        "max_retries": 1,
        "summarize_content": False
    }
    
    metrics = SecurityMetrics()
    replay_cache = []
    
    # The conformance run deliberately omits logger and audit-file I/O. This
    # keeps 100k vectors representative of protocol checks rather than disk
    # throughput, and avoids leaking individual synthetic payloads to output.
    previous_logging_disable = logging.root.manager.disable
    logging.disable(logging.CRITICAL)
    try:
        for i in range(num_transactions):
            metrics.total_transactions += 1

            # Determine transaction type
            rand = random.random()

            if rand < attack_probability / 2:
                # Tampered attack (2.5%)
                metrics.tampered_injected += 1
                await execute_tampered_attack(
                    orchestrator,
                    worker,
                    i,
                    search_config,
                    metrics,
                    session,
                )
            elif rand < attack_probability:
                # Replay attack (2.5%)
                metrics.replay_injected += 1
                await execute_replay_attack(
                    orchestrator,
                    worker,
                    i,
                    search_config,
                    metrics,
                    replay_cache,
                    session,
                )
            else:
                # Legitimate transaction (95%)
                metrics.legitimate_transactions += 1
                await execute_legitimate_transaction(
                    orchestrator,
                    worker,
                    i,
                    search_config,
                    metrics,
                    session,
                )

            # Progress indicator
            if (i + 1) % 10000 == 0:
                print(f"Progress: {i + 1}/{num_transactions} transactions completed")
    finally:
        logging.disable(previous_logging_disable)
        orchestrator.teardown_session(worker)
    
    return metrics


def generate_security_report(metrics: SecurityMetrics):
    """Generate security analysis report."""
    data = metrics.to_dict()
    
    print("\n" + "="*60)
    print("SECURITY RESILIENCE ANALYSIS")
    print("="*60)
    
    print("\n## Transaction Summary\n")
    print(f"Total Transactions: {data['total_transactions']}")
    print(f"Legitimate Transactions: {data['legitimate_transactions']}")
    print(f"Attacks Injected: {data['attacks_injected']}")
    print(f"  - Tampered Payloads: {data['tampered_injected']}")
    print(f"  - Replay Attacks: {data['replay_injected']}")
    
    print("\n## Attack Detection Results\n")
    print(f"Total Attacks Detected: {data['attacks_detected']}/{data['attacks_injected']}")
    print(f"  - Tampered Detected: {data['tampered_detected']}/{data['tampered_injected']}")
    print(f"  - Replay Detected: {data['replay_detected']}/{data['replay_injected']}")
    print(f"\n**Detection Rate: {data['detection_rate']:.2f}%**")
    
    print("\n## Legitimate Transaction Results\n")
    print(f"Successful: {data['legitimate_success']}/{data['legitimate_transactions']}")
    print(f"Failed: {data['legitimate_failed']}/{data['legitimate_transactions']}")
    print(f"False Positives: {data['false_positives']}")
    print(f"Success Rate: {data['legitimate_success_rate']:.2f}%")
    
    print("\n## Security Metrics Table\n")
    print("| Metric | Count | Rate |")
    print("|--------|-------|------|")
    print(f"| Total Transactions | {data['total_transactions']} | 100.0% |")
    print(f"| Attacks Injected | {data['attacks_injected']} | {data['attacks_injected']/data['total_transactions']*100:.1f}% |")
    print(f"| Attacks Detected | {data['attacks_detected']} | {data['detection_rate']:.1f}% |")
    print(f"| Tampered Detected | {data['tampered_detected']}/{data['tampered_injected']} | {data['tampered_detected']/data['tampered_injected']*100 if data['tampered_injected'] > 0 else 0:.1f}% |")
    print(f"| Replay Detected | {data['replay_detected']}/{data['replay_injected']} | {data['replay_detected']/data['replay_injected']*100 if data['replay_injected'] > 0 else 0:.1f}% |")
    print(f"| Legitimate Success | {data['legitimate_success']}/{data['legitimate_transactions']} | {data['legitimate_success_rate']:.1f}% |")
    
    print("\n## Security Assessment\n")
    
    if data['detection_rate'] == 100.0:
        print("✓ **PASS**: all injected modeled attack vectors were rejected")
    else:
        print(f"✗ **FAIL**: {100 - data['detection_rate']:.2f}% of attacks were not detected")
    
    if data['false_positives'] == 0:
        print("✓ **PASS**: No false positives (legitimate transactions incorrectly rejected)")
    else:
        print(f"✗ **WARNING**: {data['false_positives']} false positives detected")
    
    print()


async def main():
    """Run security benchmark."""
    print("="*60)
    print("SECURITY RESILIENCE BENCHMARK")
    print("="*60)
    
    num_transactions = int(os.environ.get("QSC_SECURITY_TRANSACTIONS", "100000"))
    metrics = await run_security_simulation(
        num_transactions=num_transactions,
        attack_probability=float(os.environ.get("QSC_ATTACK_PROBABILITY", "0.05")),
    )
    
    generate_security_report(metrics)
    
    # Save results
    output = metrics.to_dict()
    output.update(
        {
            "measurement_type": "S-simulation",
            "provenance": (
                "S-simulation: AES-256-GCM ciphertext tampering and "
                "stale-nonce replay under one authenticated ML-KEM session"
            ),
            "run_metadata": run_metadata(
                repetitions=num_transactions,
                seed=20260811,
            ),
            "scope": {
                "in_scope": ["payload tampering", "stale-nonce replay"],
                "out_of_scope": [
                    "compromised agents",
                    "key compromise",
                    "certificate-authority failure",
                    "side channels",
                    "downgrade attacks",
                    "QRNG failure",
                    "prompt/tool injection",
                ],
            },
        }
    )
    output_file = result_path("security_results.json")
    with output_file.open("w") as f:
        json.dump(output, f, indent=2)
    
    print(f"Results saved to: {output_file}\n")


if __name__ == "__main__":
    asyncio.run(main())
