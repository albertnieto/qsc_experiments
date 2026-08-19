# Copyright © 2026 PricewaterhouseCoopers LLP (PwC US).
# This file is the property of PwC US. Licensed under the MIT License.

"""
Phase 1 Tests: Foundation - Establishing Quantum-Resistant Identity
"""
import pytest
import asyncio
from src.pqc_agents.orchestrator_agent import OrchestratorAgent
from src.pqc_agents.secure_search_agent import SecureSearchAgent


class TestPhase1Identity:
    """Test PQC identity generation and authenticated handshake."""

    @pytest.fixture
    def orchestrator(self):
        """Create orchestrator agent."""
        return OrchestratorAgent("orchestrator_test")

    @pytest.fixture
    def search_agent(self):
        """Create secure search agent."""
        return SecureSearchAgent("search_agent_test")

    def test_identity_generation(self, orchestrator, search_agent):
        """Experiment 1.1: Verify both agents generate PQC key pairs."""
        # Verify orchestrator has identity
        assert orchestrator.identity is not None
        assert orchestrator.identity.agent_id == "orchestrator_test"
        orchestrator_pubkey = orchestrator.identity.get_public_key()
        assert orchestrator_pubkey is not None
        assert len(orchestrator_pubkey) == 1952  # ML-DSA-65 public key size
        
        # Verify search agent has identity
        assert search_agent.identity is not None
        assert search_agent.identity.agent_id == "search_agent_test"
        search_pubkey = search_agent.get_public_key()
        assert search_pubkey is not None
        assert len(search_pubkey) == 1952
        
        # Verify keys are different
        assert orchestrator_pubkey != search_pubkey

    def test_agent_registry(self, orchestrator, search_agent):
        """Experiment 1.1: Verify agent registry stores public keys."""
        # Register search agent
        search_pubkey = search_agent.get_public_key()
        orchestrator.register_worker(search_agent.agent_id, search_pubkey)
        
        # Verify registration
        assert orchestrator.registry.is_registered(search_agent.agent_id)
        retrieved_key = orchestrator.registry.get_public_key(search_agent.agent_id)
        assert retrieved_key == search_pubkey

    @pytest.mark.asyncio
    async def test_authenticated_handshake(self, orchestrator, search_agent):
        """Experiment 1.2: Verify authenticated handshake between agents."""
        # Register search agent
        orchestrator.register_worker(search_agent.agent_id, search_agent.get_public_key())
        
        # Perform handshake
        handshake_result = await orchestrator.perform_handshake(search_agent)
        
        # Verify handshake succeeded
        assert handshake_result is True
        
        # Verify audit log entries
        events = orchestrator.audit_log.get_events()
        assert len(events) >= 3  # AGENT_REGISTERED, HANDSHAKE_INITIATED, HANDSHAKE_VERIFIED
        assert any(e["event_type"] == "HANDSHAKE_VERIFIED" for e in events)
