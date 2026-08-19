# Copyright © 2026 PricewaterhouseCoopers LLP (PwC US).
# This file is the property of PwC US. Licensed under the MIT License.

"""Agent Registry for managing trusted agent identities."""
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class AgentRegistry:
    """Registry for storing and retrieving trusted agent public keys."""

    def __init__(self):
        self._registry: Dict[str, bytes] = {}
        logger.info("AgentRegistry: Initialized")

    def register_agent(self, agent_id: str, public_key: bytes) -> None:
        """Register an agent key once and reject silent key substitution."""
        existing = self._registry.get(agent_id)
        if existing is not None and existing != public_key:
            raise ValueError(
                f"refusing public-key replacement for trusted agent {agent_id}"
            )
        self._registry[agent_id] = public_key
        logger.info(f"AgentRegistry: Registered agent {agent_id}")

    def get_public_key(self, agent_id: str) -> Optional[bytes]:
        """Retrieve an agent's public key."""
        return self._registry.get(agent_id)

    def is_registered(self, agent_id: str) -> bool:
        """Check if an agent is registered."""
        return agent_id in self._registry

    def list_agents(self) -> list:
        """List all registered agent IDs."""
        return list(self._registry.keys())
