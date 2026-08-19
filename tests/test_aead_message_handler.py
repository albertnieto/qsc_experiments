# Copyright © 2026 PricewaterhouseCoopers LLP (PwC US).
# This file is the property of PwC US. Licensed under the MIT License.

"""Tests for routine AES-256-GCM message protection."""

import pytest

from src.security.hybrid_session_key import SessionKey
from src.security.message_handler import MessageHandler
from src.pqc_agents.orchestrator_agent import OrchestratorAgent
from src.pqc_agents.secure_search_agent import SecureSearchAgent


def test_routine_payload_round_trip():
    handler = MessageHandler(object())
    session = SessionKey(b"k" * 32, "pqc+qrng", "session-1")
    envelope = handler.encrypt_payload(
        {"query_id": "q1", "queries": ["quantum"]},
        session,
        aad=b"qsc-task:q1",
    )

    assert envelope["mode"] == "aead"
    assert handler.decrypt_payload(
        envelope, session, aad=b"qsc-task:q1"
    ) == {"query_id": "q1", "queries": ["quantum"]}


def test_routine_payload_rejects_tampering():
    handler = MessageHandler(object())
    session = SessionKey(b"k" * 32, "pqc+qrng", "session-1")
    envelope = handler.encrypt_payload(
        {"query_id": "q1"},
        session,
        aad=b"qsc-task:q1",
    )
    envelope["ciphertext"] = "00" * (len(bytes.fromhex(envelope["ciphertext"])))

    with pytest.raises(Exception):
        handler.decrypt_payload(envelope, session, aad=b"qsc-task:q1")


class RecordingSearchAgent(SecureSearchAgent):
    """Capture the request envelope to assert the production path is AEAD."""

    async def execute_search(self, message, orchestrator_public_key, search_config):
        self.last_message = message
        return await super().execute_search(
            message, orchestrator_public_key, search_config
        )


@pytest.mark.asyncio
async def test_agent_delegation_uses_aead_session():
    orchestrator = OrchestratorAgent("orchestrator_aead_test")
    worker = RecordingSearchAgent("worker_aead_test")
    orchestrator.register_worker(worker.agent_id, worker.get_public_key())

    result = await orchestrator.delegate_search(
        worker,
        ["quantum security"],
        {"timeout": 5},
    )

    assert result["status"] == "success"
    assert worker.last_message["mode"] == "aead"
    assert "signature" not in worker.last_message
    assert worker.agent_id not in orchestrator.sessions
    assert not worker.sessions
    assert orchestrator.audit_log.get_events("SESSION_TORN_DOWN")
