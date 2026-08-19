# Copyright © 2026 PricewaterhouseCoopers LLP (PwC US).
# This file is the property of PwC US. Licensed under the MIT License.

"""
Phase 3 Tests: Resilience Testing & Advanced Security Layers
"""
import pytest
import asyncio
from src.pqc_agents.orchestrator_agent import OrchestratorAgent
from src.pqc_agents.secure_search_agent import SecureSearchAgent


class TestPhase3Resilience:
    """Test replay attack prevention, tampering detection, and QKD."""

    @pytest.fixture
    def orchestrator(self):
        return OrchestratorAgent("orchestrator_resilience")

    @pytest.fixture
    def search_agent(self):
        return SecureSearchAgent("search_agent_resilience")

    @pytest.fixture
    def search_config(self):
        return {
            "search_api": "exa",
            "fallback_apis": [],
            "timeout": 30,
            "max_retries": 1,
            "summarize_content": False
        }

    @pytest.mark.asyncio
    async def test_replay_attack_prevention(self, orchestrator, search_agent, search_config):
        """Experiment 3.1: Reject a replayed AEAD nonce within one session."""
        orchestrator.register_worker(search_agent.agent_id, search_agent.get_public_key())
        query_id = orchestrator.qrng.generate_query_id()
        session, _ = orchestrator.establish_session(
            search_agent,
            session_context=b"replay-resilience-test",
        )
        payload = {
            "query_id": query_id,
            "queries": ["replay test"],
            "max_results": 5,
            "date_range": None
        }
        envelope = orchestrator.message_handler.encrypt_payload(
            payload,
            session,
            aad=f"qsc-task:{query_id}".encode(),
        )

        first = await search_agent.execute_search(
            envelope,
            orchestrator.identity.get_public_key(),
            search_config,
        )
        assert orchestrator.message_handler.decrypt_payload(
            first,
            session,
            aad=f"qsc-result:{query_id}".encode(),
        )["status"] == "success"

        replay = await search_agent.execute_search(
            envelope,
            orchestrator.identity.get_public_key(),
            search_config,
        )
        replay_payload = orchestrator.message_handler.decrypt_payload(
            replay,
            session,
            aad=f"qsc-result:{query_id}".encode(),
        )
        assert replay_payload["error"] == "Message authentication failed"
        orchestrator.teardown_session(search_agent)

    @pytest.mark.asyncio
    async def test_tampering_detection(self, orchestrator, search_agent, search_config):
        """Experiment 3.2: Reject ciphertext modification under AES-GCM."""
        orchestrator.register_worker(search_agent.agent_id, search_agent.get_public_key())
        query_id = orchestrator.qrng.generate_query_id()
        session, _ = orchestrator.establish_session(
            search_agent,
            session_context=b"tamper-resilience-test",
        )
        payload = {
            "query_id": query_id,
            "queries": ["original query"],
            "max_results": 5,
            "date_range": None
        }
        envelope = orchestrator.message_handler.encrypt_payload(
            payload,
            session,
            aad=f"qsc-task:{query_id}".encode(),
        )
        ciphertext = bytearray.fromhex(envelope["ciphertext"])
        ciphertext[0] ^= 1
        envelope["ciphertext"] = ciphertext.hex()

        result = await search_agent.execute_search(
            envelope,
            orchestrator.identity.get_public_key(),
            search_config,
        )
        result_payload = orchestrator.message_handler.decrypt_payload(
            result,
            session,
            aad=f"qsc-result:{query_id}".encode(),
        )
        assert result_payload["error"] == "Message authentication failed"
        orchestrator.teardown_session(search_agent)

    def test_qrng_uniqueness(self, orchestrator):
        """Experiment 3.1: Verify QRNG generates unique query IDs."""
        query_ids = set()
        
        for _ in range(100):
            query_id = orchestrator.qrng.generate_query_id()
            assert query_id not in query_ids
            query_ids.add(query_id)
        
        assert len(query_ids) == 100
