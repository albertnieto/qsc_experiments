# Copyright © 2026 PricewaterhouseCoopers LLP (PwC US).
# This file is the property of PwC US. Licensed under the MIT License.

"""
Orchestrator Agent - Enhanced with PQC security for delegating to Secure Search Agent.
"""
import logging
import asyncio
from typing import Dict, Any, List, Optional
from src.security.pqc_identity import PQCIdentity
from src.security.message_handler import MessageHandler
from src.security.agent_registry import AgentRegistry
from src.security.qrng_simulator import QRNGSimulator
from src.security.audit_log import AuditLog
from src.security.hybrid_session_key import (
    SessionKey,
    derive_session_key,
    session_auth_message,
)
from src.security.qkd_simulator import QKDSimulator

logger = logging.getLogger(__name__)


class OrchestratorAgent:
    """Orchestrator agent with PQC security for delegating search tasks."""

    def __init__(self, agent_id: str = "orchestrator_agent"):
        self.agent_id = agent_id
        self.identity = PQCIdentity(agent_id)
        self.message_handler = MessageHandler(self.identity)
        self.registry = AgentRegistry()
        self.qrng = QRNGSimulator()
        self.qkd = QKDSimulator()
        self.audit_log = AuditLog(self.identity)
        self.sessions: Dict[str, SessionKey] = {}
        logger.info(f"OrchestratorAgent initialized with ID: {agent_id}")

    def establish_session(
        self,
        worker_agent,
        *,
        session_context: bytes,
        use_qkd: bool = False,
        qkd_epoch: Optional[str] = None,
    ) -> tuple[SessionKey, bytes]:
        """Establish a transcript-bound ML-KEM/AES-256-GCM session.

        The sender encapsulates to the receiver's public key. The receiver
        decapsulates the returned ciphertext; neither side decapsulates its own
        encapsulation. The returned ciphertext is included in the derivation
        transcript and is also returned for transport-layer evidence.
        """
        worker_agent.register_orchestrator(
            self.agent_id,
            self.identity.get_public_key(),
        )
        ciphertext, pqc_secret_sender = self.identity.encapsulate(
            worker_agent.identity.get_kem_public_key()
        )
        if use_qkd:
            qkd_epoch = qkd_epoch or self.qrng.generate_query_id()
        qkd_secret = (
            self.qkd.establish_key(
                self.agent_id,
                worker_agent.agent_id,
                epoch=qkd_epoch,
            )
            if use_qkd
            else None
        )
        qrng_entropy = self.qrng.generate_bytes(32)
        session = derive_session_key(
            pqc_secret=pqc_secret_sender,
            pqc_ciphertext=ciphertext,
            sender_id=self.agent_id,
            receiver_id=worker_agent.agent_id,
            session_context=session_context,
            qrng_entropy=qrng_entropy,
            qkd_secret=qkd_secret,
            qkd_epoch=qkd_epoch,
        )
        signature = self.identity.sign(
            session_auth_message(
                sender_id=self.agent_id,
                receiver_id=worker_agent.agent_id,
                session_context=session_context,
                ciphertext=ciphertext,
                qrng_entropy=qrng_entropy,
                qkd_epoch=qkd_epoch,
            )
        )
        worker_agent.accept_session(
            sender_id=self.agent_id,
            session_context=session_context,
            ciphertext=ciphertext,
            qrng_entropy=qrng_entropy,
            qkd_secret=qkd_secret,
            qkd_epoch=qkd_epoch,
            signature=signature,
            session_key=session,
        )
        self.sessions[worker_agent.agent_id] = session
        self.audit_log.log_event(
            "SESSION_ESTABLISHED",
            {
                "agent_id": self.agent_id,
                "worker_id": worker_agent.agent_id,
                "session_id": session.transcript_hash,
                "mode": session.mode,
            },
        )
        return session, ciphertext

    def teardown_session(self, worker_agent) -> bool:
        """Invalidate both peers' session state after task completion."""
        session = self.sessions.pop(worker_agent.agent_id, None)
        if session is None:
            return False
        worker_agent.teardown_session(session.transcript_hash)
        self.audit_log.log_event(
            "SESSION_TORN_DOWN",
            {
                "agent_id": self.agent_id,
                "worker_id": worker_agent.agent_id,
                "session_id": session.transcript_hash,
            },
        )
        return True

    def register_worker(self, worker_agent_id: str, worker_public_key: bytes) -> None:
        """Register a worker agent in the trusted registry."""
        self.registry.register_agent(worker_agent_id, worker_public_key)
        self.audit_log.log_event("AGENT_REGISTERED", {
            "agent_id": self.agent_id,
            "worker_id": worker_agent_id
        })

    async def perform_handshake(self, worker_agent) -> bool:
        """Perform authentication handshake with worker agent."""
        nonce = self.qrng.generate_nonce()
        
        self.audit_log.log_event("HANDSHAKE_INITIATED", {
            "agent_id": self.agent_id,
            "worker_id": worker_agent.agent_id,
            "nonce": nonce
        })
        
        response = await worker_agent.handle_handshake(nonce)
        
        # Verify signature
        worker_public_key = self.registry.get_public_key(worker_agent.agent_id)
        if not worker_public_key:
            logger.error(f"OrchestratorAgent: Worker {worker_agent.agent_id} not registered")
            return False
        
        signature = bytes.fromhex(response["signature"])
        verified = self.identity.verify(nonce.encode(), signature, worker_public_key)
        
        self.audit_log.log_event("HANDSHAKE_VERIFIED" if verified else "HANDSHAKE_FAILED", {
            "agent_id": self.agent_id,
            "worker_id": worker_agent.agent_id,
            "verified": verified
        })
        
        return verified

    async def delegate_search(
        self,
        worker_agent,
        queries: List[str],
        search_config: Dict[str, Any],
        max_results: int = 5,
        date_range: Optional[Dict[str, str]] = None,
        teardown: bool = True,
    ) -> Dict[str, Any]:
        """Delegate a routine search task over the authenticated AEAD session."""
        
        query_id = self.qrng.generate_query_id()
        
        payload = {
            "query_id": query_id,
            "queries": queries,
            "max_results": max_results,
            "date_range": date_range,
            "search_config": search_config,
        }
        
        session_key = self.sessions.get(worker_agent.agent_id)
        if session_key is None:
            session_key, _ = self.establish_session(
                worker_agent,
                session_context=f"search:{query_id}".encode(),
            )
        encrypted_payload = self.message_handler.encrypt_payload(
            payload,
            session_key,
            aad=f"qsc-task:{query_id}".encode(),
        )
        
        self.audit_log.log_event("QUERY_ENCRYPTED", {
            "agent_id": self.agent_id,
            "query_id": query_id,
            "queries": queries
        })
        
        try:
            encrypted_response = await worker_agent.execute_search(
                encrypted_payload,
                self.identity.get_public_key(),
                {},
            )
            try:
                response_payload = self.message_handler.decrypt_payload(
                    encrypted_response,
                    session_key,
                    aad=f"qsc-result:{query_id}".encode(),
                )
                if response_payload.get("query_id") != query_id:
                    raise ValueError("worker response query identifier mismatch")
            except (KeyError, ValueError, TypeError) as exc:
                logger.error("OrchestratorAgent: Invalid worker response: %s", exc)
                self.audit_log.log_event("RESULTS_VERIFICATION_FAILED", {
                    "agent_id": self.agent_id,
                    "query_id": query_id
                })
                return {"error": "Response authentication failed"}

            self.audit_log.log_event("RESULTS_AUTHENTICATED", {
                "agent_id": self.agent_id,
                "query_id": query_id,
                "status": response_payload.get("status")
            })

            return response_payload
        finally:
            if teardown:
                self.teardown_session(worker_agent)
