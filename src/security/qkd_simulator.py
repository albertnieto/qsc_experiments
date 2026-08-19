# Copyright © 2026 PricewaterhouseCoopers LLP (PwC US).
# This file is the property of PwC US. Licensed under the MIT License.

"""QKD link-key model for the experimental framework.

This module never claims to implement physical QKD. It produces test key
material and records the modeled establishment latency so cloud results can
separate measured PQC-TLS time from a hypothetical QKD contribution.
"""
from __future__ import annotations

import secrets
import logging
import time
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class QKDSimulator:
    """Simulates QKD for establishing shared encryption keys."""

    measurement_type = "Model-QKD"

    def __init__(self, establishment_latency_ms: float = 10.0):
        self._shared_keys = {}
        self.establishment_latency_ms = establishment_latency_ms
        logger.info(
            "QKDSimulator: Initialized (modeled latency=%s ms)",
            establishment_latency_ms,
        )

    def establish_key(
        self,
        agent_a: str,
        agent_b: str,
        *,
        epoch: Optional[str] = None,
    ) -> bytes:
        """Simulate QKD key establishment between two agents."""
        key_id = (tuple(sorted([agent_a, agent_b])), epoch or "default")
        
        if key_id not in self._shared_keys:
            # The sleep is a model parameter, not a physical QKD measurement.
            time.sleep(self.establishment_latency_ms / 1000)
            shared_key = secrets.token_bytes(32)
            self._shared_keys[key_id] = shared_key
            logger.info(f"QKDSimulator: Established key between {agent_a} and {agent_b}")
        
        return self._shared_keys[key_id]

    def get_shared_key(self, agent_a: str, agent_b: str) -> bytes:
        """Retrieve existing shared key."""
        key_id = (tuple(sorted([agent_a, agent_b])), "default")
        return self._shared_keys.get(key_id)

    def metadata(self) -> Dict[str, object]:
        return {
            "measurement_type": self.measurement_type,
            "provider": "qkd-simulator",
            "establishment_latency_ms": self.establishment_latency_ms,
            "physical_qkd": False,
        }
