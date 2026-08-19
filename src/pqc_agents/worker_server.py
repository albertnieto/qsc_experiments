# Copyright © 2026 PricewaterhouseCoopers LLP (PwC US).
# This file is the property of PwC US. Licensed under the MIT License.

"""
HTTP server for Worker Agent with PQC security.
"""
import os
import logging
from flask import Flask, request, jsonify
from src.pqc_agents.secure_search_agent import SecureSearchAgent
from src.security.bootstrap_auth import (
    create_bootstrap_proof,
    require_bootstrap_secret,
    verify_bootstrap_proof,
)
from src.security.replay_cache import ReplayCache

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Initialize worker agent
AGENT_ID = os.getenv("AGENT_ID", "worker_agent")
BOOTSTRAP_TOKEN = os.getenv("QSC_BOOTSTRAP_TOKEN", "")
BOOTSTRAP_NONCES = ReplayCache(
    int(os.getenv("QSC_REPLAY_CACHE_SIZE", "100000"))
)
worker = SecureSearchAgent(AGENT_ID)

logger.info(f"Worker agent initialized: {AGENT_ID}")


@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint."""
    return jsonify({"status": "healthy", "agent_id": AGENT_ID}), 200


@app.route("/public_key", methods=["GET"])
def get_public_key():
    """Return worker's public key for registration."""
    return jsonify({
        "agent_id": AGENT_ID,
        "public_key": worker.get_public_key().hex(),
        "kem_public_key": worker.identity.get_kem_public_key().hex(),
    }), 200


@app.route("/handshake", methods=["POST"])
def handshake():
    """Prove the worker's deployment membership and ML-DSA identity."""
    data = request.get_json(silent=True) or {}
    challenge = data.get("challenge")
    
    if not challenge:
        return jsonify({"error": "Missing challenge"}), 400
    
    try:
        import asyncio
        response = asyncio.run(worker.handle_handshake(challenge))
        response["kem_public_key"] = worker.identity.get_kem_public_key().hex()
        proof_fields = {
            "challenge": challenge,
            "agent_id": response["agent_id"],
            "public_key": response["public_key"],
            "kem_public_key": response["kem_public_key"],
        }
        response["bootstrap_proof"] = create_bootstrap_proof(
            BOOTSTRAP_TOKEN,
            "worker-handshake",
            proof_fields,
        )
        return jsonify(response), 200
    except (RuntimeError, TypeError, ValueError) as e:
        logger.error(f"Handshake failed: {e}")
        return jsonify({"error": "Worker authentication unavailable"}), 503


@app.route("/execute_search", methods=["POST"])
def execute_search():
    """Execute a routine request only through an authenticated AEAD session."""
    data = request.get_json(silent=True) or {}

    encrypted_payload = data.get("encrypted_payload")

    required_envelope_fields = {
        "mode",
        "session_id",
        "nonce",
        "ciphertext",
    }
    if (
        not isinstance(encrypted_payload, dict)
        or encrypted_payload.get("mode") != "aead"
        or not required_envelope_fields.issubset(encrypted_payload)
    ):
        return jsonify({"error": "Valid AEAD envelope required"}), 400
    
    try:
        import asyncio
        response = asyncio.run(
            worker.execute_search(
                encrypted_payload,
                b"",
                {},
            )
        )
        if not isinstance(response, dict) or response.get("mode") != "aead":
            return jsonify({"error": "Authenticated session required"}), 401
        return jsonify({"encrypted_response": response}), 200
        
    except Exception as e:
        logger.error(f"Search execution failed: {e}")
        return jsonify({"error": "Search execution failed"}), 400


@app.route("/trust/orchestrator", methods=["POST"])
def trust_orchestrator():
    """Pin an orchestrator identity proven by the deployment trust anchor."""
    data = request.json or {}
    required = ("sender_id", "public_key", "nonce", "bootstrap_proof")
    if any(not data.get(field) for field in required):
        return jsonify({"error": "Missing registration field"}), 400
    fields = {
        "sender_id": data["sender_id"],
        "public_key": data["public_key"],
        "nonce": data["nonce"],
    }
    try:
        if not verify_bootstrap_proof(
            BOOTSTRAP_TOKEN,
            "orchestrator-registration",
            fields,
            data["bootstrap_proof"],
        ) or not BOOTSTRAP_NONCES.accept(data["nonce"]):
            return jsonify({"error": "Orchestrator authentication failed"}), 401
        worker.register_orchestrator(
            data["sender_id"],
            bytes.fromhex(data["public_key"]),
        )
        return jsonify(
            {"status": "trusted", "sender_id": data["sender_id"]}
        ), 200
    except (RuntimeError, TypeError, ValueError) as exc:
        logger.error("Orchestrator registration failed: %s", exc)
        return jsonify({"error": "Orchestrator registration failed"}), 400


@app.route("/session", methods=["POST"])
def session():
    """Verify and accept the orchestrator's signed ML-KEM encapsulation."""
    data = request.json or {}
    required = (
        "sender_id",
        "session_context",
        "ciphertext",
        "qrng_entropy",
        "signature",
    )
    if any(not data.get(field) for field in required):
        return jsonify({"error": "Missing session establishment field"}), 400
    try:
        ciphertext = bytes.fromhex(data["ciphertext"])
        session_context = bytes.fromhex(data["session_context"])
        qrng_entropy = bytes.fromhex(data["qrng_entropy"])
        receiver_session = worker.accept_session(
            sender_id=data["sender_id"],
            session_context=session_context,
            ciphertext=ciphertext,
            qrng_entropy=qrng_entropy,
            qkd_secret=None,
            qkd_epoch=None,
            signature=bytes.fromhex(data["signature"]),
        )
        return jsonify(
            {"status": "established", "session_id": receiver_session.transcript_hash}
        ), 200
    except (KeyError, TypeError, ValueError) as exc:
        logger.error("Session establishment failed: %s", exc)
        return jsonify({"error": "Session establishment failed"}), 400


@app.route("/session/teardown", methods=["POST"])
def teardown_session():
    """Invalidate a session after an authenticated teardown request."""
    data = request.json or {}
    required = ("sender_id", "session_id", "nonce", "bootstrap_proof")
    if any(not data.get(field) for field in required):
        return jsonify({"error": "Missing teardown field"}), 400
    fields = {
        "sender_id": data["sender_id"],
        "session_id": data["session_id"],
        "nonce": data["nonce"],
    }
    try:
        session = worker.sessions.get(data["session_id"])
        if (
            data["sender_id"] not in worker.trusted_orchestrators
            or (
                session is not None
                and session["sender_id"] != data["sender_id"]
            )
            or not verify_bootstrap_proof(
                BOOTSTRAP_TOKEN,
                "session-teardown",
                fields,
                data["bootstrap_proof"],
            )
            or not BOOTSTRAP_NONCES.accept(data["nonce"])
        ):
            return jsonify({"error": "Teardown authentication failed"}), 401
        removed = worker.teardown_session(
            data["session_id"],
            sender_id=data["sender_id"],
        )
        return jsonify(
            {
                "status": "torn_down" if removed else "already_absent",
                "session_id": data["session_id"],
            }
        ), 200
    except (RuntimeError, TypeError, ValueError) as exc:
        logger.error("Session teardown failed: %s", exc)
        return jsonify({"error": "Session teardown failed"}), 400


if __name__ == "__main__":
    require_bootstrap_secret(BOOTSTRAP_TOKEN)
    port = int(os.getenv("AGENT_PORT", 8001))
    app.run(host="0.0.0.0", port=port, debug=False)
