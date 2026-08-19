# Copyright © 2026 PricewaterhouseCoopers LLP (PwC US).
# This file is the property of PwC US. Licensed under the MIT License.

"""
Phase 0 Demo: Basic setup and verification of Worker Agent and Orchestrator Agent.
"""
import asyncio
import logging
from src.pqc_agents.orchestrator_agent import OrchestratorAgent
from src.pqc_agents.secure_search_agent import SecureSearchAgent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    """Demonstrate basic agent setup and communication."""
    
    logger.info("=== Phase 0: Agent Setup Demo ===\n")
    
    # Step 1: Create agents
    logger.info("Step 1: Creating Orchestrator and Secure Search Agent...")
    orchestrator = OrchestratorAgent("orchestrator_demo")
    search_agent = SecureSearchAgent("search_agent_demo")
    logger.info(f"✓ Orchestrator ID: {orchestrator.agent_id}")
    logger.info(f"✓ Search Agent ID: {search_agent.agent_id}\n")
    
    # Step 2: Verify PQC identities
    logger.info("Step 2: Verifying PQC identities...")
    orch_pubkey = orchestrator.identity.get_public_key()
    search_pubkey = search_agent.get_public_key()
    logger.info(f"✓ Orchestrator public key: {orch_pubkey.hex()[:32]}...")
    logger.info(f"✓ Search Agent public key: {search_pubkey.hex()[:32]}...\n")
    
    # Step 3: Register search agent
    logger.info("Step 3: Registering Search Agent in Orchestrator's registry...")
    orchestrator.register_worker(search_agent.agent_id, search_pubkey)
    logger.info(f"✓ Search Agent registered\n")
    
    # Step 4: Perform handshake
    logger.info("Step 4: Performing authenticated handshake...")
    handshake_success = await orchestrator.perform_handshake(search_agent)
    logger.info(f"✓ Handshake {'succeeded' if handshake_success else 'failed'}\n")
    
    # Step 5: Delegate a simple search
    logger.info("Step 5: Delegating search query...")
    search_config = {
        "search_api": "exa",
        "fallback_apis": [],
        "timeout": 30,
        "max_retries": 2,
        "summarize_content": False
    }
    
    queries = ["quantum computing"]
    result = await orchestrator.delegate_search(
        search_agent,
        queries,
        search_config,
        max_results=3
    )
    
    logger.info(f"✓ Search completed with status: {result.get('status')}")
    logger.info(f"✓ Query ID: {result.get('query_id')}\n")
    
    # Step 6: Review audit log
    logger.info("Step 6: Reviewing audit log...")
    events = orchestrator.audit_log.get_events()
    logger.info(f"✓ Total audit events: {len(events)}")
    for event in events:
        logger.info(f"  - {event['event_type']}: {event['timestamp']}")
    
    logger.info("\n=== Phase 0 Demo Complete ===")


if __name__ == "__main__":
    asyncio.run(main())
