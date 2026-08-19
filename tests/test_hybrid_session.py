# Copyright © 2026 PricewaterhouseCoopers LLP (PwC US).
# This file is the property of PwC US. Licensed under the MIT License.

from src.pqc_agents.orchestrator_agent import OrchestratorAgent
from src.pqc_agents.secure_search_agent import SecureSearchAgent
from src.security.hybrid_session_key import (
    decrypt_aes256_gcm,
    derive_session_key,
    encrypt_aes256_gcm,
)


def test_hybrid_session_matches_at_receiver():
    orchestrator = OrchestratorAgent("hybrid-orchestrator")
    worker = SecureSearchAgent("hybrid-worker")
    session, ciphertext = orchestrator.establish_session(
        worker,
        session_context=b"test-session-1",
        use_qkd=True,
        qkd_epoch="epoch-1",
    )
    receiver_session = worker.sessions[session.transcript_hash]["session_key"]
    assert ciphertext
    assert session.key == receiver_session.key
    assert len(session.key) == 32


def test_combiner_binds_mode_and_context():
    args = {
        "pqc_secret": b"pqc-secret",
        "pqc_ciphertext": b"kem-ciphertext",
        "sender_id": "sender",
        "receiver_id": "receiver",
        "session_context": b"context-a",
        "qrng_entropy": b"entropy",
    }
    first = derive_session_key(**args)
    second = derive_session_key(**{**args, "session_context": b"context-b"})
    assert first.key != second.key
    assert first.mode == "pqc+qrng"


def test_aes256_gcm_round_trip_and_authentication():
    key = b"k" * 32
    nonce, ciphertext = encrypt_aes256_gcm(key, b"payload", aad=b"metadata")
    assert decrypt_aes256_gcm(key, nonce, ciphertext, aad=b"metadata") == b"payload"
