# Copyright © 2026 PricewaterhouseCoopers LLP (PwC US).
# This file is the property of PwC US. Licensed under the MIT License.

"""
Classical search agent using Ed25519 for baseline comparison.
"""
import logging
from typing import Dict, Any, List
from src.security.classical_identity import ClassicalIdentity
from src.security.classical_message_handler import ClassicalMessageHandler

logger = logging.getLogger(__name__)


class ClassicalSearchAgent:
    """Worker agent using classical Ed25519 cryptography."""

    def __init__(self, agent_id: str = "classical_search_agent"):
        self.agent_id = agent_id
        self.identity = ClassicalIdentity(agent_id)
        self.message_handler = ClassicalMessageHandler(self.identity)
        self.processed_query_ids = set()

    def get_public_key(self) -> bytes:
        """Return agent's public key."""
        return self.identity.get_public_key()

    async def handle_handshake(self, challenge: str) -> Dict[str, Any]:
        """Handle authentication handshake."""
        signature = self.identity.sign(challenge.encode())
        return {
            "agent_id": self.agent_id,
            "signature": signature.hex(),
            "public_key": self.identity.get_public_key().hex()
        }

    async def execute_search(
        self,
        signed_payload: Dict[str, Any],
        orchestrator_public_key: bytes,
        search_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute search with signature verification."""
        
        if not self.message_handler.verify_message(signed_payload, orchestrator_public_key):
            return {"error": "Authentication failed", "results": []}

        payload = signed_payload["payload"]
        query_id = payload.get("query_id")
        
        if query_id in self.processed_query_ids:
            error_payload = {
                "query_id": query_id,
                "error": "Replay attack detected",
                "results": []
            }
            return self.message_handler.sign_message(error_payload)
        
        self.processed_query_ids.add(query_id)
        
        query_list = payload.get("queries", [])
        max_results = payload.get("max_results", 5)
        date_range = payload.get("date_range")
        
        try:
            # Mock search results for crypto benchmarking (no external search API required).
            response_payload = {
                "query_id": query_id,
                "results": [{"query": q, "mock": True} for q in query_list],
                "status": "success"
            }
            
            return self.message_handler.sign_message(response_payload)
            
        except Exception as e:
            error_payload = {
                "query_id": query_id,
                "error": str(e),
                "status": "failed"
            }
            return self.message_handler.sign_message(error_payload)
