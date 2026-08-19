# Copyright © 2026 PricewaterhouseCoopers LLP (PwC US).
# This file is the property of PwC US. Licensed under the MIT License.

"""Hash-chained, ML-DSA-authenticated security audit logging."""

import hashlib
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Mapping, Optional

logger = logging.getLogger(__name__)


class AuditLog:
    """Append-only audit log with chained hashes and signer authentication."""

    def __init__(self, identity, log_file: Optional[str] = None):
        if identity is None:
            raise ValueError("an ML-DSA identity is required for audit signing")
        self.identity = identity
        self.log_file = Path(
            log_file or os.environ.get("QSC_AUDIT_LOG", "audit_log.jsonl")
        )
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        self.max_bytes = int(
            os.environ.get("QSC_AUDIT_MAX_BYTES", str(50 * 1024 * 1024))
        )
        if self.max_bytes < 1:
            raise ValueError("QSC_AUDIT_MAX_BYTES must be positive")
        self._lock = Lock()
        self._previous_hash = self._load_chain_head()
        logger.info(f"AuditLog: Initialized at {self.log_file}")

    @staticmethod
    def _canonical_bytes(event: Mapping[str, Any]) -> bytes:
        unsigned = {
            key: value
            for key, value in event.items()
            if key not in {"event_hash", "signature"}
        }
        return json.dumps(
            unsigned,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")

    def _load_chain_head(self) -> str:
        """Load the final chain hash without scanning the complete log."""
        if not self.log_file.exists():
            return "0" * 64
        with self.log_file.open("rb") as audit_file:
            audit_file.seek(0, os.SEEK_END)
            position = audit_file.tell()
            buffer = b""
            raw_line = b""
            while position > 0:
                block_size = min(8192, position)
                position -= block_size
                audit_file.seek(position)
                buffer = audit_file.read(block_size) + buffer
                stripped = buffer.rstrip(b"\r\n")
                line_start = stripped.rfind(b"\n")
                if line_start >= 0 or position == 0:
                    raw_line = stripped[line_start + 1 :]
                    break
        if not raw_line.strip():
            return "0" * 64
        try:
            event = json.loads(raw_line)
        except json.JSONDecodeError as exc:
            raise ValueError("audit log has an invalid final record") from exc
        return event.get(
            "event_hash",
            hashlib.sha256(raw_line).hexdigest(),
        )

    def log_event(
        self,
        event_type: str,
        details: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Append a chained event signed by this process identity."""
        with self._lock:
            return self._log_event(event_type, details)

    def _log_event(
        self,
        event_type: str,
        details: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Append one event while the writer lock is held."""
        event: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "details": details,
            "signer_id": self.identity.agent_id,
            "signer_public_key": self.identity.get_public_key().hex(),
            "previous_hash": self._previous_hash,
        }
        event_hash = hashlib.sha256(self._canonical_bytes(event)).hexdigest()
        event["event_hash"] = event_hash
        event["signature"] = self.identity.sign(
            bytes.fromhex(event_hash)
        ).hex()

        serialized = (
            json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n"
        )
        current_size = (
            self.log_file.stat().st_size if self.log_file.exists() else 0
        )
        if current_size + len(serialized.encode("utf-8")) > self.max_bytes:
            raise RuntimeError(
                "audit log size limit reached; archive and checkpoint it "
                "before continuing"
            )

        with self.log_file.open("a", encoding="utf-8") as audit_file:
            audit_file.write(serialized)
            audit_file.flush()
            os.fsync(audit_file.fileno())

        self._previous_hash = event_hash
        logger.info(f"AuditLog: {event_type} - {details.get('agent_id', 'unknown')}")
        return event

    def get_events(self, event_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retrieve audit events, optionally filtered by type."""
        events: List[Dict[str, Any]] = []
        if not self.log_file.exists():
            return events

        with self.log_file.open("r", encoding="utf-8") as audit_file:
            for line in audit_file:
                event = json.loads(line)
                if event_type is None or event["event_type"] == event_type:
                    events.append(event)
        return events

    def verify_chain(
        self,
        trusted_public_keys: Mapping[str, bytes],
    ) -> bool:
        """Verify hashes, continuity, and every ML-DSA event signature."""
        previous_hash = "0" * 64
        for event in self.get_events():
            required = {
                "event_hash",
                "signature",
                "signer_id",
                "signer_public_key",
                "previous_hash",
            }
            if not required.issubset(event):
                return False
            if event["previous_hash"] != previous_hash:
                return False
            expected_hash = hashlib.sha256(
                self._canonical_bytes(event)
            ).hexdigest()
            if event["event_hash"] != expected_hash:
                return False
            trusted_key = trusted_public_keys.get(event["signer_id"])
            if (
                trusted_key is None
                or event["signer_public_key"] != trusted_key.hex()
                or not self.identity.verify(
                    bytes.fromhex(expected_hash),
                    bytes.fromhex(event["signature"]),
                    trusted_key,
                )
            ):
                return False
            previous_hash = expected_hash
        return True
