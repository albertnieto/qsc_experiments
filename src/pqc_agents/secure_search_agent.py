# Copyright © 2026 PricewaterhouseCoopers LLP (PwC US).
# This file is the property of PwC US. Licensed under the MIT License.

"""
Secure Search Agent - Worker Agent for quantum-resistant web search operations.
"""
import logging
import asyncio
from typing import Dict, Any, List, Optional
from src.security.pqc_identity import PQCIdentity
from src.security.message_handler import MessageHandler
from src.security.hybrid_session_key import (
    SessionKey,
    derive_session_key,
    session_auth_message,
)
from src.security.replay_cache import ReplayCache

logger = logging.getLogger(__name__)


class SecureSearchAgent:
    """Worker agent that performs web searches with PQC authentication."""

    def __init__(self, agent_id: str = "secure_search_agent"):
        self.agent_id = agent_id
        self.identity = PQCIdentity(agent_id)
        self.message_handler = MessageHandler(self.identity)
        self.sessions = {}
        self.trusted_orchestrators: Dict[str, bytes] = {}
        self.accepted_session_ids = ReplayCache()
        self.processed_artifact_ids = set()
        logger.info(f"SecureSearchAgent initialized with ID: {agent_id}")

    def get_public_key(self) -> bytes:
        """Return agent's public key for registration."""
        return self.identity.get_public_key()

    def register_orchestrator(
        self,
        sender_id: str,
        public_key: bytes,
    ) -> None:
        """Pin a trusted orchestrator key and reject silent replacement."""
        existing = self.trusted_orchestrators.get(sender_id)
        if existing is not None and existing != public_key:
            raise ValueError(
                f"refusing public-key replacement for {sender_id}"
            )
        self.trusted_orchestrators[sender_id] = public_key

    def accept_session(
        self,
        *,
        sender_id: str,
        session_context: bytes,
        ciphertext: bytes,
        qrng_entropy: bytes,
        qkd_secret: Optional[bytes],
        qkd_epoch: Optional[str],
        signature: bytes,
        session_key: Optional[SessionKey] = None,
    ) -> SessionKey:
        """Authenticate the sender, decapsulate, and record a new session."""
        trusted_key = self.trusted_orchestrators.get(sender_id)
        if trusted_key is None:
            raise ValueError(f"untrusted session sender: {sender_id}")
        authenticated_request = session_auth_message(
            sender_id=sender_id,
            receiver_id=self.agent_id,
            session_context=session_context,
            ciphertext=ciphertext,
            qrng_entropy=qrng_entropy,
            qkd_epoch=qkd_epoch,
        )
        if not self.identity.verify(
            authenticated_request,
            signature,
            trusted_key,
        ):
            raise ValueError("invalid session-establishment signature")
        receiver_secret = self.identity.decapsulate(ciphertext)
        receiver_session = derive_session_key(
            pqc_secret=receiver_secret,
            pqc_ciphertext=ciphertext,
            sender_id=sender_id,
            receiver_id=self.agent_id,
            session_context=session_context,
            qrng_entropy=qrng_entropy,
            qkd_secret=qkd_secret,
            qkd_epoch=qkd_epoch,
        )
        # Sender and receiver derive from the same transcript. The sender ID
        # is carried by the session context in the current in-process harness.
        if session_key is not None and receiver_session.key != session_key.key:
            raise ValueError("session key mismatch during receiver acceptance")
        if not self.accepted_session_ids.accept(
            receiver_session.transcript_hash
        ):
            raise ValueError("replayed session-establishment transcript")
        self.sessions[receiver_session.transcript_hash] = {
            "sender_id": sender_id,
            "context": session_context,
            "ciphertext": ciphertext,
            "qkd_secret": qkd_secret,
            "qkd_epoch": qkd_epoch,
            "receiver_secret": receiver_secret,
            "session_key": receiver_session,
            "processed_query_ids": set(),
            "processed_nonces": set(),
        }
        return receiver_session

    def teardown_session(
        self,
        session_id: str,
        sender_id: Optional[str] = None,
    ) -> bool:
        """Invalidate a session and release its replay-tracking state."""
        session = self.sessions.get(session_id)
        if session is None:
            return False
        if sender_id is not None and session["sender_id"] != sender_id:
            return False
        return self.sessions.pop(session_id, None) is not None

    async def handle_handshake(self, challenge: str) -> Dict[str, Any]:
        """Handle authentication handshake by signing challenge."""
        signature = self.identity.sign(challenge.encode())
        return {
            "agent_id": self.agent_id,
            "signature": signature.hex(),
            "public_key": self.identity.get_public_key().hex()
        }

    async def execute_search(
        self,
        message: Dict[str, Any],
        orchestrator_public_key: bytes,
        search_config: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Execute a routine AEAD request or trusted signed artifact.

        New delegation uses an authenticated session envelope. The signed
        branch is limited to independently verifiable artifacts and resolves
        its verification key from the worker's trusted registry. The
        ``orchestrator_public_key`` argument is ignored and retained only for
        source compatibility with older in-process harnesses.
        """
        session_key: Optional[SessionKey] = None
        session_record: Optional[Dict[str, Any]] = None
        routine_message = message.get("mode") == "aead"
        if routine_message:
            session_id = message.get("session_id")
            session_record = self.sessions.get(session_id)
            if not session_record:
                logger.error("SecureSearchAgent: Unknown session")
                return {"error": "Session authentication failed", "results": []}
            session_key = session_record["session_key"]
            try:
                nonce = message["nonce"]
                if nonce in session_record["processed_nonces"]:
                    raise ValueError("replayed message nonce")
                aad = bytes.fromhex(message["aad"])
                if not aad.startswith(b"qsc-task:"):
                    raise ValueError("unexpected task metadata")
                payload = self.message_handler.decrypt_payload(
                    message, session_key, aad=aad
                )
                session_record["processed_nonces"].add(nonce)
            except (KeyError, ValueError, TypeError) as exc:
                logger.error("SecureSearchAgent: Invalid AEAD request: %s", exc)
                if session_key is not None:
                    try:
                        task_aad = bytes.fromhex(message["aad"])
                        query_id = task_aad.removeprefix(b"qsc-task:")
                        return self.message_handler.encrypt_payload(
                            {
                                "error": "Message authentication failed",
                                "status": "failed",
                            },
                            session_key,
                            aad=b"qsc-result:" + query_id,
                        )
                    except (KeyError, ValueError, TypeError):
                        pass
                return {"error": "Message authentication failed", "results": []}
        else:
            sender_id = message.get("agent_id")
            trusted_key = self.trusted_orchestrators.get(sender_id)
            if trusted_key is None or not self.message_handler.verify_message(
                message,
                trusted_key,
            ):
                logger.error("SecureSearchAgent: Invalid orchestrator signature")
                return {"error": "Authentication failed", "results": []}
            payload = message["payload"]
        query_id = payload.get("query_id")

        replay_set = (
            session_record["processed_query_ids"]
            if session_record is not None
            else self.processed_artifact_ids
        )
        # Replay attack prevention
        if query_id in replay_set:
            logger.warning(f"SecureSearchAgent: Duplicate query_id detected: {query_id}")
            error_payload = {
                "query_id": query_id,
                "error": "Replay attack detected",
                "results": []
            }
            if session_key is not None:
                return self.message_handler.encrypt_payload(
                    error_payload,
                    session_key,
                    aad=f"qsc-result:{query_id}".encode(),
                )
            return self.message_handler.sign_message(error_payload)

        if session_record is not None:
            session_record["processed_query_ids"].add(query_id)
        else:
            self.processed_artifact_ids.add(query_id)
        
        # Extract search parameters
        query_list = payload.get("queries", [])
        max_results = payload.get("max_results", 5)
        date_range = payload.get("date_range")
        
        logger.info(f"SecureSearchAgent: Executing search for {len(query_list)} queries")
        
        try:
            # Mock search results for PQC testing
            # In production, integrate with actual search API
            response_payload = {
                "query_id": query_id,
                "results": [{"query": q, "mock": True} for q in query_list],
                "status": "success"
            }
            
            if session_key is not None:
                signed_response = self.message_handler.encrypt_payload(
                    response_payload,
                    session_key,
                    aad=f"qsc-result:{query_id}".encode(),
                )
            else:
                signed_response = self.message_handler.sign_message(response_payload)
            
            logger.info(f"SecureSearchAgent: Search completed successfully for query_id: {query_id}")
            return signed_response
            
        except Exception as e:
            logger.error(f"SecureSearchAgent: Search failed: {e}")
            error_payload = {
                "query_id": query_id,
                "error": str(e),
                "status": "failed"
            }
            if session_key is not None:
                return self.message_handler.encrypt_payload(
                    error_payload,
                    session_key,
                    aad=f"qsc-result:{query_id}".encode(),
                )
            return self.message_handler.sign_message(error_payload)
