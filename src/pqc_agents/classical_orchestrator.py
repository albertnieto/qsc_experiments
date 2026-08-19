# Copyright © 2026 PricewaterhouseCoopers LLP (PwC US).
# This file is the property of PwC US. Licensed under the MIT License.

"""
Classical orchestrator using Ed25519 for baseline comparison.
"""
import logging
import secrets
from typing import Dict, Any, List
from src.security.classical_identity import ClassicalIdentity
from src.security.classical_message_handler import ClassicalMessageHandler

logger = logging.getLogger(__name__)


class ClassicalOrchestrator:
    """Orchestrator using classical Ed25519 cryptography."""

    def __init__(self, agent_id: str = "classical_orchestrator"):
        self.agent_id = agent_id
        self.identity = ClassicalIdentity(agent_id)
        self.message_handler = ClassicalMessageHandler(self.identity)
        self.registered_workers = {}

    def register_worker(self, worker_id: str, public_key: bytes):
        """Register a worker agent."""
        self.registered_workers[worker_id] = public_key

    async def perform_handshake(self, worker_agent) -> bool:
        """Perform authentication handshake."""
        challenge = secrets.token_hex(32)
        response = await worker_agent.handle_handshake(challenge)
        
        signature = bytes.fromhex(response["signature"])
        public_key = bytes.fromhex(response["public_key"])
        
        return self.identity.verify(challenge.encode(), signature, public_key)

    async def delegate_search(
        self,
        worker_agent,
        queries: List[str],
        search_config: Dict[str, Any],
        max_results: int = 5
    ) -> Dict[str, Any]:
        """Delegate search to worker with classical crypto."""
        query_id = secrets.token_hex(16)
        
        payload = {
            "query_id": query_id,
            "queries": queries,
            "max_results": max_results,
            "date_range": None
        }
        
        signed_payload = self.message_handler.sign_message(payload)
        
        result = await worker_agent.execute_search(
            signed_payload,
            self.identity.get_public_key(),
            search_config
        )
        
        if "payload" in result:
            return result["payload"]
        return result
