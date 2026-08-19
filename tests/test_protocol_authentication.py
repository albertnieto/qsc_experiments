# Copyright © 2026 PricewaterhouseCoopers LLP (PwC US).
# This file is the property of PwC US. Licensed under the MIT License.

"""Security regression tests for peer authentication and audit integrity."""

import json
from types import SimpleNamespace

import pytest
import requests

from src.pqc_agents.secure_search_agent import SecureSearchAgent
from src.security.audit_log import AuditLog
from src.security.bootstrap_auth import (
    canonical_payload_sha256,
    create_bootstrap_proof,
)
from src.security.hybrid_session_key import (
    derive_session_key,
    session_auth_message,
)
from src.security.message_handler import MessageHandler
from src.security.pqc_identity import PQCIdentity


def test_session_rejects_untrusted_and_invalid_senders():
    sender = PQCIdentity("trusted-orchestrator")
    worker = SecureSearchAgent("authenticated-worker")
    ciphertext, _ = sender.encapsulate(worker.identity.get_kem_public_key())
    context = b"authenticated-session-test"
    entropy = b"e" * 32
    request = session_auth_message(
        sender_id=sender.agent_id,
        receiver_id=worker.agent_id,
        session_context=context,
        ciphertext=ciphertext,
        qrng_entropy=entropy,
    )

    with pytest.raises(ValueError, match="untrusted session sender"):
        worker.accept_session(
            sender_id=sender.agent_id,
            session_context=context,
            ciphertext=ciphertext,
            qrng_entropy=entropy,
            qkd_secret=None,
            qkd_epoch=None,
            signature=sender.sign(request),
        )

    worker.register_orchestrator(sender.agent_id, sender.get_public_key())
    with pytest.raises(ValueError, match="invalid session-establishment"):
        worker.accept_session(
            sender_id=sender.agent_id,
            session_context=context,
            ciphertext=ciphertext,
            qrng_entropy=entropy,
            qkd_secret=None,
            qkd_epoch=None,
            signature=b"invalid",
        )

    session = worker.accept_session(
        sender_id=sender.agent_id,
        session_context=context,
        ciphertext=ciphertext,
        qrng_entropy=entropy,
        qkd_secret=None,
        qkd_epoch=None,
        signature=sender.sign(request),
    )
    assert session.transcript_hash in worker.sessions
    assert not worker.teardown_session(
        session.transcript_hash,
        sender_id="different-orchestrator",
    )
    with pytest.raises(ValueError, match="replayed session-establishment"):
        worker.accept_session(
            sender_id=sender.agent_id,
            session_context=context,
            ciphertext=ciphertext,
            qrng_entropy=entropy,
            qkd_secret=None,
            qkd_epoch=None,
            signature=sender.sign(request),
        )
    assert worker.teardown_session(session.transcript_hash)
    assert not worker.sessions
    with pytest.raises(ValueError, match="replayed session-establishment"):
        worker.accept_session(
            sender_id=sender.agent_id,
            session_context=context,
            ciphertext=ciphertext,
            qrng_entropy=entropy,
            qkd_secret=None,
            qkd_epoch=None,
            signature=sender.sign(request),
        )


@pytest.mark.asyncio
async def test_signed_artifact_cannot_select_its_own_trust_key():
    trusted = PQCIdentity("trusted-orchestrator")
    attacker = PQCIdentity("attacker")
    worker = SecureSearchAgent("artifact-worker")
    worker.register_orchestrator(trusted.agent_id, trusted.get_public_key())
    forged = attacker.signer.sign(
        json.dumps(
            {"query_id": "forged", "queries": []},
            sort_keys=True,
        ).encode()
    )
    message = {
        "payload": {"query_id": "forged", "queries": []},
        "signature": forged.hex(),
        "agent_id": attacker.agent_id,
        "public_key": attacker.get_public_key().hex(),
    }

    result = await worker.execute_search(
        message,
        attacker.get_public_key(),
        {},
    )
    assert result["error"] == "Authentication failed"


def test_http_worker_rejects_legacy_signed_search():
    from src.pqc_agents.worker_server import app

    response = app.test_client().post(
        "/execute_search",
        json={
            "signed_payload": {"payload": {}},
            "orchestrator_public_key": "00",
        },
    )
    assert response.status_code == 400
    assert response.get_json()["error"] == "Valid AEAD envelope required"

    response = app.test_client().post(
        "/execute_search",
        json={
            "encrypted_payload": {
                "mode": "signed",
                "payload": {},
                "signature": "00",
            }
        },
    )
    assert response.status_code == 400


def test_http_session_requires_bootstrap_and_signature(monkeypatch):
    from src.pqc_agents import worker_server

    token = "bootstrap-secret-" + ("a" * 48)
    sender = PQCIdentity("http-orchestrator")
    http_worker = SecureSearchAgent("http-worker")
    monkeypatch.setattr(worker_server, "BOOTSTRAP_TOKEN", token)
    monkeypatch.setattr(worker_server, "worker", http_worker)
    worker_server.BOOTSTRAP_NONCES.clear()
    client = worker_server.app.test_client()

    registration = {
        "sender_id": sender.agent_id,
        "public_key": sender.get_public_key().hex(),
        "nonce": "registration-nonce",
    }
    registration["bootstrap_proof"] = create_bootstrap_proof(
        token,
        "orchestrator-registration",
        registration,
    )
    assert client.post(
        "/trust/orchestrator",
        json=registration,
    ).status_code == 200

    context = b"http-session-test"
    entropy = b"q" * 32
    ciphertext, sender_secret = sender.encapsulate(
        http_worker.identity.get_kem_public_key()
    )
    sender_session = derive_session_key(
        pqc_secret=sender_secret,
        pqc_ciphertext=ciphertext,
        sender_id=sender.agent_id,
        receiver_id=http_worker.agent_id,
        session_context=context,
        qrng_entropy=entropy,
    )
    auth_message = session_auth_message(
        sender_id=sender.agent_id,
        receiver_id=http_worker.agent_id,
        session_context=context,
        ciphertext=ciphertext,
        qrng_entropy=entropy,
    )
    session_request = {
        "sender_id": sender.agent_id,
        "session_context": context.hex(),
        "ciphertext": ciphertext.hex(),
        "qrng_entropy": entropy.hex(),
        "signature": sender.sign(auth_message).hex(),
    }
    assert client.post("/session", json=session_request).status_code == 200
    assert client.post("/session", json=session_request).status_code == 400

    query_id = "http-query"
    envelope = MessageHandler(sender).encrypt_payload(
        {"query_id": query_id, "queries": ["authenticated"]},
        sender_session,
        aad=f"qsc-task:{query_id}".encode(),
    )
    response = client.post(
        "/execute_search",
        json={"encrypted_payload": envelope, "search_config": {}},
    )
    assert response.status_code == 200
    result = MessageHandler(sender).decrypt_payload(
        response.get_json()["encrypted_response"],
        sender_session,
        aad=f"qsc-result:{query_id}".encode(),
    )
    assert result["status"] == "success"

    teardown = {
        "sender_id": sender.agent_id,
        "session_id": sender_session.transcript_hash,
        "nonce": "teardown-nonce",
    }
    teardown["bootstrap_proof"] = create_bootstrap_proof(
        token,
        "session-teardown",
        teardown,
    )
    assert client.post("/session/teardown", json=teardown).status_code == 200
    assert not http_worker.sessions
    replay = {
        **teardown,
        "nonce": "teardown-retry-nonce",
    }
    replay["bootstrap_proof"] = create_bootstrap_proof(
        token,
        "session-teardown",
        {
            key: replay[key]
            for key in ("sender_id", "session_id", "nonce")
        },
    )
    retry_response = client.post("/session/teardown", json=replay)
    assert retry_response.status_code == 200
    assert retry_response.get_json()["status"] == "already_absent"
    assert client.post("/session", json=session_request).status_code == 400


def test_http_delegation_requires_request_bound_client_proof(monkeypatch):
    from src.pqc_agents import orchestrator_server

    token = "delegation-secret-" + ("b" * 48)
    monkeypatch.setattr(orchestrator_server, "BOOTSTRAP_TOKEN", token)
    monkeypatch.setattr(orchestrator_server, "WORKER_ENDPOINTS", [])
    orchestrator_server.DELEGATION_NONCES.clear()
    client = orchestrator_server.app.test_client()

    payload = {
        "queries": ["authenticated request"],
        "search_config": {"search_api": "mock"},
        "max_results": 3,
        "date_range": None,
    }
    assert client.post("/delegate_search", json=payload).status_code == 401

    fields = {
        "client_id": "test-client",
        "nonce": "delegation-nonce",
        "request_sha256": canonical_payload_sha256(payload),
    }
    request_body = {
        **payload,
        **fields,
        "bootstrap_proof": create_bootstrap_proof(
            token,
            "client-delegation",
            fields,
        ),
    }
    assert client.post("/delegate_search", json=request_body).status_code == 503
    assert client.post("/delegate_search", json=request_body).status_code == 401

    tampered = {
        **request_body,
        "nonce": "tampered-nonce",
        "queries": ["changed after authentication"],
    }
    assert client.post("/delegate_search", json=tampered).status_code == 401


def test_failed_remote_teardown_retains_local_session(monkeypatch):
    from src.pqc_agents import orchestrator_server

    token = "teardown-secret-" + ("c" * 48)
    session = SimpleNamespace(transcript_hash="session-transcript")
    worker = {"agent_id": "worker", "endpoint": "https://worker.test"}
    monkeypatch.setattr(orchestrator_server, "BOOTSTRAP_TOKEN", token)
    monkeypatch.setitem(
        orchestrator_server.orchestrator.sessions,
        worker["agent_id"],
        session,
    )

    def fail_request(*args, **kwargs):
        raise requests.ConnectionError("offline")

    monkeypatch.setattr(orchestrator_server.requests, "post", fail_request)
    with pytest.raises(RuntimeError, match="not acknowledged"):
        orchestrator_server.teardown_remote_session(worker)
    assert (
        orchestrator_server.orchestrator.sessions[worker["agent_id"]]
        is session
    )


def test_audit_chain_detects_tampering(tmp_path):
    identity = PQCIdentity("audit-signer")
    log_path = tmp_path / "audit.jsonl"
    audit = AuditLog(identity, str(log_path))
    audit.log_event("SESSION_ESTABLISHED", {"agent_id": identity.agent_id})
    audit.log_event("SESSION_TORN_DOWN", {"agent_id": identity.agent_id})

    trusted = {identity.agent_id: identity.get_public_key()}
    assert audit.verify_chain(trusted)

    events = audit.get_events()
    events[0]["details"]["agent_id"] = "tampered"
    log_path.write_text(
        "\n".join(json.dumps(event) for event in events) + "\n",
        encoding="utf-8",
    )
    assert not audit.verify_chain(trusted)
