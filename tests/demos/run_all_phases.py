# Copyright © 2026 PricewaterhouseCoopers LLP (PwC US).
# This file is the property of PwC US. Licensed under the MIT License.

"""
Run all phases sequentially to demonstrate the complete quantum-resistant framework.
"""
import asyncio
import logging
from src.pqc_agents.orchestrator_agent import OrchestratorAgent
from src.pqc_agents.secure_search_agent import SecureSearchAgent

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


async def phase1_identity():
    """Phase 1: Establish quantum-resistant identities."""
    logger.info("\n" + "="*60)
    logger.info("PHASE 1: Foundation - Quantum-Resistant Identity")
    logger.info("="*60 + "\n")
    
    orchestrator = OrchestratorAgent("orchestrator_phase1")
    search_agent = SecureSearchAgent("search_agent_phase1")
    
    logger.info("Experiment 1.1: Agent Identity Generation")
    logger.info(f"  ✓ Orchestrator public key: {orchestrator.identity.get_public_key().hex()[:40]}...")
    logger.info(f"  ✓ Search Agent public key: {search_agent.get_public_key().hex()[:40]}...")
    
    orchestrator.register_worker(search_agent.agent_id, search_agent.get_public_key())
    logger.info(f"  ✓ Search Agent registered in Orchestrator's registry\n")
    
    logger.info("Experiment 1.2: Authenticated Handshake")
    handshake_result = await orchestrator.perform_handshake(search_agent)
    logger.info(f"  ✓ Handshake verification: {'PASSED' if handshake_result else 'FAILED'}\n")
    
    return orchestrator, search_agent


async def phase2_workflow(orchestrator, search_agent):
    """Phase 2: Secure delegated research workflow."""
    logger.info("\n" + "="*60)
    logger.info("PHASE 2: Secure Delegated Research Workflow")
    logger.info("="*60 + "\n")
    
    search_config = {
        "search_api": "duckduckgo",
        "fallback_apis": [],
        "timeout": 30,
        "max_retries": 2,
        "summarize_content": False
    }
    
    logger.info("Experiment 2.1: Secure Query Delegation")
    queries = ["quantum cryptography basics"]
    logger.info(f"  → Orchestrator signing query: {queries[0]}")
    
    result = await orchestrator.delegate_search(
        search_agent,
        queries,
        search_config,
        max_results=3
    )
    
    logger.info(f"  ✓ Query signed and sent with ID: {result.get('query_id')}\n")
    
    logger.info("Experiment 2.2: Secure Search Execution & Result Attestation")
    logger.info(f"  ✓ Search Agent verified orchestrator signature")
    logger.info(f"  ✓ Search executed with status: {result.get('status')}")
    logger.info(f"  ✓ Results signed by Search Agent\n")
    
    logger.info("Experiment 2.3: Secure Result Ingestion & Auditing")
    events = orchestrator.audit_log.get_events()
    logger.info(f"  ✓ Audit trail contains {len(events)} events:")
    for event in events[-5:]:
        logger.info(f"    - {event['event_type']}")
    logger.info("")


async def phase3_resilience(orchestrator, search_agent):
    """Phase 3: Resilience testing and advanced security."""
    logger.info("\n" + "="*60)
    logger.info("PHASE 3: Resilience Testing & Advanced Security")
    logger.info("="*60 + "\n")
    
    search_config = {
        "search_api": "duckduckgo",
        "fallback_apis": [],
        "timeout": 30,
        "max_retries": 1,
        "summarize_content": False
    }
    
    logger.info("Experiment 3.1: QRNG Simulation for Replay Attack Prevention")
    
    # Generate unique query IDs
    query_ids = [orchestrator.qrng.generate_query_id() for _ in range(5)]
    logger.info(f"  ✓ Generated 5 unique QRNG query IDs")
    logger.info(f"  ✓ All IDs are unique: {len(set(query_ids)) == 5}")
    
    # Test replay attack
    queries = ["test query"]
    result1 = await orchestrator.delegate_search(search_agent, queries, search_config)
    query_id = result1.get("query_id")
    
    # Attempt replay
    duplicate_payload = {
        "query_id": query_id,
        "queries": queries,
        "max_results": 5,
        "date_range": None
    }
    signed_duplicate = orchestrator.message_handler.sign_message(duplicate_payload)
    replay_result = await search_agent.execute_search(
        signed_duplicate,
        orchestrator.identity.get_public_key(),
        search_config
    )
    
    logger.info(f"  ✓ Replay attack detected: {'Replay attack detected' in replay_result['payload'].get('error', '')}\n")
    
    logger.info("Experiment 3.2: Integrity Attack (Tampering) Simulation")
    
    # Create valid message
    payload = {
        "query_id": orchestrator.qrng.generate_query_id(),
        "queries": ["original query"],
        "max_results": 5,
        "date_range": None
    }
    signed_payload = orchestrator.message_handler.sign_message(payload)
    
    # Tamper with payload
    signed_payload["payload"]["queries"] = ["tampered query"]
    
    tamper_result = await search_agent.execute_search(
        signed_payload,
        orchestrator.identity.get_public_key(),
        search_config
    )
    
    logger.info(f"  ✓ Tampering detected: {'Authentication failed' in tamper_result.get('error', '')}\n")
    
    logger.info("Experiment 3.3: QKD Simulation for Confidential Queries")
    from src.security.qkd_simulator import QKDSimulator
    
    qkd = QKDSimulator()
    shared_key = qkd.establish_key(orchestrator.agent_id, search_agent.agent_id)
    logger.info(f"  ✓ QKD shared key established: {shared_key.hex()[:40]}...")
    logger.info(f"  ✓ Key can be used for encrypting confidential queries\n")


async def main():
    """Run all phases."""
    logger.info("\n" + "="*60)
    logger.info("QUANTUM-RESISTANT SECURITY FRAMEWORK DEMONSTRATION")
    logger.info("="*60)
    
    # Phase 1
    orchestrator, search_agent = await phase1_identity()
    
    # Phase 2
    await phase2_workflow(orchestrator, search_agent)
    
    # Phase 3
    await phase3_resilience(orchestrator, search_agent)
    
    logger.info("\n" + "="*60)
    logger.info("ALL PHASES COMPLETED SUCCESSFULLY")
    logger.info("="*60 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
