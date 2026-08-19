# Copyright © 2026 PricewaterhouseCoopers LLP (PwC US).
# This file is the property of PwC US. Licensed under the MIT License.

"""
Phase 2 Tests: Secure, Delegated Research Workflow
"""
import pytest
import asyncio
from src.pqc_agents.orchestrator_agent import OrchestratorAgent
from src.pqc_agents.secure_search_agent import SecureSearchAgent


class TestPhase2Workflow:
    """Test secure query delegation and result authentication."""

    @pytest.fixture
    def orchestrator(self):
        """Create orchestrator agent."""
        return OrchestratorAgent("orchestrator_workflow")

    @pytest.fixture
    def search_agent(self):
        """Create secure search agent."""
        return SecureSearchAgent("search_agent_workflow")

    @pytest.fixture
    def search_config(self):
        """Basic search configuration."""
        return {
            "search_api": "exa",
            "fallback_apis": [],
            "timeout": 30,
            "max_retries": 2,
            "summarize_content": False
        }

    @pytest.mark.asyncio
    async def test_secure_query_delegation(self, orchestrator, search_agent, search_config):
        """Experiment 2.1: Test AEAD-encrypted query delegation."""
        # Setup
        orchestrator.register_worker(search_agent.agent_id, search_agent.get_public_key())
        await orchestrator.perform_handshake(search_agent)
        
        # Delegate search
        queries = ["quantum computing basics"]
        result = await orchestrator.delegate_search(
            search_agent,
            queries,
            search_config,
            max_results=3
        )
        
        # Verify result structure
        assert "query_id" in result
        assert result.get("status") in ["success", "failed"]
        
        # Verify audit trail
        events = orchestrator.audit_log.get_events("QUERY_ENCRYPTED")
        assert len(events) >= 1
        assert events[-1]["details"]["queries"] == queries

    @pytest.mark.asyncio
    async def test_result_attestation(self, orchestrator, search_agent, search_config):
        """Experiment 2.2: Test search agent returns an authenticated result."""
        orchestrator.register_worker(search_agent.agent_id, search_agent.get_public_key())
        
        queries = ["test query"]
        result = await orchestrator.delegate_search(
            search_agent,
            queries,
            search_config,
            max_results=2
        )
        
        # Verify results were verified
        verify_events = orchestrator.audit_log.get_events("RESULTS_AUTHENTICATED")
        assert len(verify_events) >= 1

    @pytest.mark.asyncio
    async def test_audit_trail(self, orchestrator, search_agent, search_config):
        """Experiment 2.3: Verify complete audit trail."""
        orchestrator.register_worker(search_agent.agent_id, search_agent.get_public_key())
        
        queries = ["audit test"]
        await orchestrator.delegate_search(search_agent, queries, search_config)
        
        # Verify complete chain of custody
        events = orchestrator.audit_log.get_events()
        event_types = [e["event_type"] for e in events]
        
        assert "AGENT_REGISTERED" in event_types
        assert "QUERY_ENCRYPTED" in event_types
        assert "RESULTS_AUTHENTICATED" in event_types
