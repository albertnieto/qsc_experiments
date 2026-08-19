# Copyright © 2026 PricewaterhouseCoopers LLP (PwC US).
# This file is the property of PwC US. Licensed under the MIT License.

"""
HTTP server for Orchestrator Agent with PQC security.
"""
import os
import logging
import requests
from flask import Flask, request, jsonify
from src.pqc_agents.orchestrator_agent import OrchestratorAgent
from src.security.bootstrap_auth import (
    canonical_payload_sha256,
    create_bootstrap_proof,
    require_bootstrap_secret,
    verify_bootstrap_proof,
)
from src.security.hybrid_session_key import (
    derive_session_key,
    session_auth_message,
)
from src.security.replay_cache import ReplayCache

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Initialize orchestrator
AGENT_ID = os.getenv("AGENT_ID", "orchestrator_agent")
orchestrator = OrchestratorAgent(AGENT_ID)

# Worker endpoints from environment
WORKER_ENDPOINTS = os.getenv("WORKER_ENDPOINTS", "").split(",")
WORKER_ENDPOINTS = [endpoint.strip().rstrip("/") for endpoint in WORKER_ENDPOINTS if endpoint.strip()]


def _tls_verify_setting():
    ca_bundle = os.getenv("QSC_CA_BUNDLE")
    if ca_bundle:
        return ca_bundle
    return os.getenv("QSC_TLS_VERIFY", "true").lower() != "false"


TLS_VERIFY = _tls_verify_setting()
BOOTSTRAP_TOKEN = os.getenv("QSC_BOOTSTRAP_TOKEN", "")
DELEGATION_NONCES = ReplayCache(
    int(os.getenv("QSC_REPLAY_CACHE_SIZE", "100000"))
)
logger.info(f"Orchestrator initialized with workers: {WORKER_ENDPOINTS}")


def discover_workers() -> list[dict]:
    """Fetch candidate worker identities before authenticated pinning."""
    registered = []
    for endpoint in WORKER_ENDPOINTS:
        response = requests.get(
            f"{endpoint}/public_key",
            verify=TLS_VERIFY,
            timeout=15,
        )
        response.raise_for_status()
        identity = response.json()
        registered.append(
            {
                "endpoint": endpoint,
                "agent_id": identity["agent_id"],
                "public_key": bytes.fromhex(identity["public_key"]),
                "kem_public_key": bytes.fromhex(identity["kem_public_key"]),
            }
        )
    return registered


def establish_remote_session(worker: dict) -> None:
    """Mutually authenticate peers and establish an ML-KEM/AES-GCM session."""
    challenge = orchestrator.qrng.generate_nonce()
    response = requests.post(
        f"{worker['endpoint']}/handshake",
        json={"challenge": challenge},
        verify=TLS_VERIFY,
        timeout=30,
    )
    response.raise_for_status()
    handshake = response.json()
    proof_fields = {
        "challenge": challenge,
        "agent_id": handshake["agent_id"],
        "public_key": handshake["public_key"],
        "kem_public_key": handshake["kem_public_key"],
    }
    if (
        handshake["agent_id"] != worker["agent_id"]
        or bytes.fromhex(handshake["public_key"]) != worker["public_key"]
        or bytes.fromhex(handshake["kem_public_key"]) != worker["kem_public_key"]
        or not verify_bootstrap_proof(
            BOOTSTRAP_TOKEN,
            "worker-handshake",
            proof_fields,
            handshake["bootstrap_proof"],
        )
        or not orchestrator.identity.verify(
            challenge.encode(),
            bytes.fromhex(handshake["signature"]),
            worker["public_key"],
        )
    ):
        raise ValueError("worker handshake verification failed")
    orchestrator.register_worker(worker["agent_id"], worker["public_key"])

    registration_nonce = orchestrator.qrng.generate_nonce()
    registration_fields = {
        "sender_id": orchestrator.agent_id,
        "public_key": orchestrator.identity.get_public_key().hex(),
        "nonce": registration_nonce,
    }
    response = requests.post(
        f"{worker['endpoint']}/trust/orchestrator",
        json={
            **registration_fields,
            "bootstrap_proof": create_bootstrap_proof(
                BOOTSTRAP_TOKEN,
                "orchestrator-registration",
                registration_fields,
            ),
        },
        verify=TLS_VERIFY,
        timeout=30,
    )
    response.raise_for_status()

    session_context = (
        f"http-session:{orchestrator.agent_id}:{worker['agent_id']}".encode()
    )
    ciphertext, pqc_secret = orchestrator.identity.encapsulate(
        worker["kem_public_key"]
    )
    qrng_entropy = orchestrator.qrng.generate_bytes(32)
    session = derive_session_key(
        pqc_secret=pqc_secret,
        pqc_ciphertext=ciphertext,
        sender_id=orchestrator.agent_id,
        receiver_id=worker["agent_id"],
        session_context=session_context,
        qrng_entropy=qrng_entropy,
    )
    signature = orchestrator.identity.sign(
        session_auth_message(
            sender_id=orchestrator.agent_id,
            receiver_id=worker["agent_id"],
            session_context=session_context,
            ciphertext=ciphertext,
            qrng_entropy=qrng_entropy,
        )
    )
    response = requests.post(
        f"{worker['endpoint']}/session",
        json={
            "sender_id": orchestrator.agent_id,
            "session_context": session_context.hex(),
            "ciphertext": ciphertext.hex(),
            "qrng_entropy": qrng_entropy.hex(),
            "signature": signature.hex(),
        },
        verify=TLS_VERIFY,
        timeout=30,
    )
    response.raise_for_status()
    if response.json().get("session_id") != session.transcript_hash:
        raise ValueError("remote session transcript mismatch")
    orchestrator.sessions[worker["agent_id"]] = session


def teardown_remote_session(worker: dict) -> None:
    """Invalidate a remote session using the deployment trust anchor."""
    session = orchestrator.sessions.get(worker["agent_id"])
    if session is None:
        return
    last_error = None
    for _ in range(3):
        nonce = orchestrator.qrng.generate_nonce()
        proof_fields = {
            "sender_id": orchestrator.agent_id,
            "session_id": session.transcript_hash,
            "nonce": nonce,
        }
        try:
            response = requests.post(
                f"{worker['endpoint']}/session/teardown",
                json={
                    **proof_fields,
                    "bootstrap_proof": create_bootstrap_proof(
                        BOOTSTRAP_TOKEN,
                        "session-teardown",
                        proof_fields,
                    ),
                },
                verify=TLS_VERIFY,
                timeout=30,
            )
            response.raise_for_status()
            break
        except requests.RequestException as exc:
            last_error = exc
    else:
        raise RuntimeError(
            "remote session teardown was not acknowledged"
        ) from last_error

    orchestrator.sessions.pop(worker["agent_id"], None)
    orchestrator.audit_log.log_event(
        "SESSION_TORN_DOWN",
        {
            "agent_id": orchestrator.agent_id,
            "worker_id": worker["agent_id"],
            "session_id": session.transcript_hash,
        },
    )


@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint."""
    return jsonify({"status": "healthy", "agent_id": AGENT_ID}), 200


@app.route("/delegate_search", methods=["POST"])
def delegate_search():
    """Authenticate a client request and delegate it through an AEAD session."""
    data = request.get_json(silent=True) or {}
    required_auth = (
        "client_id",
        "nonce",
        "request_sha256",
        "bootstrap_proof",
    )
    if any(not data.get(field) for field in required_auth):
        return jsonify({"error": "Client authentication required"}), 401

    queries = data.get("queries", [])
    search_config = data.get("search_config", {})
    max_results = data.get("max_results", 5)
    date_range = data.get("date_range")
    request_payload = {
        "queries": queries,
        "search_config": search_config,
        "max_results": max_results,
        "date_range": date_range,
    }
    auth_fields = {
        "client_id": data["client_id"],
        "nonce": data["nonce"],
        "request_sha256": data["request_sha256"],
    }
    expected_digest = canonical_payload_sha256(request_payload)
    try:
        authenticated = (
            data["request_sha256"] == expected_digest
            and verify_bootstrap_proof(
                BOOTSTRAP_TOKEN,
                "client-delegation",
                auth_fields,
                data["bootstrap_proof"],
            )
            and DELEGATION_NONCES.accept(data["nonce"])
        )
    except (RuntimeError, TypeError, ValueError):
        authenticated = False
    if not authenticated:
        return jsonify({"error": "Client authentication failed"}), 401
    if (
        not isinstance(queries, list)
        or not queries
        or any(not isinstance(query, str) or not query for query in queries)
        or not isinstance(search_config, dict)
        or isinstance(max_results, bool)
        or not isinstance(max_results, int)
        or not 1 <= max_results <= 100
        or (date_range is not None and not isinstance(date_range, dict))
    ):
        return jsonify({"error": "Invalid delegation request"}), 400

    if not WORKER_ENDPOINTS:
        return jsonify({"error": "No WORKER_ENDPOINTS configured"}), 503
    try:
        registered = discover_workers()
    except (requests.RequestException, KeyError, ValueError) as exc:
        logger.error("Worker discovery failed: %s", exc)
        return jsonify({"error": "Worker discovery failed"}), 502
    if not registered:
        return jsonify({"error": "Worker discovery returned no workers"}), 502

    query_id = orchestrator.qrng.generate_query_id()
    payload = {
        "query_id": query_id,
        "queries": queries,
        "max_results": max_results,
        "search_config": search_config,
        "date_range": date_range,
    }
    
    worker = registered[0]
    result = None
    delegation_error = None
    try:
        session = orchestrator.sessions.get(worker["agent_id"])
        if session is None:
            establish_remote_session(worker)
            session = orchestrator.sessions[worker["agent_id"]]
        encrypted_payload = orchestrator.message_handler.encrypt_payload(
            payload,
            session,
            aad=f"qsc-task:{query_id}".encode(),
        )
        response = requests.post(
            f"{worker['endpoint']}/execute_search",
            json={"encrypted_payload": encrypted_payload},
            verify=TLS_VERIFY,
            timeout=120,
        )
        response.raise_for_status()
        encrypted_response = response.json()["encrypted_response"]
        result = orchestrator.message_handler.decrypt_payload(
            encrypted_response,
            session,
            aad=f"qsc-result:{query_id}".encode(),
        )
        if result.get("query_id") != query_id:
            raise ValueError("worker response query identifier mismatch")
    except (
        requests.RequestException,
        KeyError,
        RuntimeError,
        TypeError,
        ValueError,
    ) as exc:
        logger.error("Worker delegation failed: %s", exc)
        delegation_error = exc

    if orchestrator.sessions.get(worker["agent_id"]) is not None:
        try:
            teardown_remote_session(worker)
        except (requests.RequestException, RuntimeError, ValueError) as exc:
            logger.error("Remote session teardown failed: %s", exc)
            return jsonify(
                {
                    "error": "Worker session teardown was not acknowledged",
                    "result_discarded": True,
                }
            ), 502

    if delegation_error is not None or result is None:
        return jsonify({"error": "Worker delegation failed"}), 502
    return jsonify(
        {
            "authenticated": True,
            "worker_id": worker["agent_id"],
            "payload": result,
        }
    ), 200


if __name__ == "__main__":
    require_bootstrap_secret(BOOTSTRAP_TOKEN)
    port = int(os.getenv("AGENT_PORT", 8000))
    app.run(host="0.0.0.0", port=port, debug=False)
