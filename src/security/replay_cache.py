# Copyright © 2026 PricewaterhouseCoopers LLP (PwC US).
# This file is the property of PwC US. Licensed under the MIT License.

"""Thread-safe bounded replay cache for one-time protocol values."""

from __future__ import annotations

from collections import OrderedDict
from threading import Lock


class ReplayCache:
    """Remember a bounded number of values and reject duplicates atomically."""

    def __init__(self, max_entries: int = 100_000):
        if max_entries < 1:
            raise ValueError("max_entries must be positive")
        self.max_entries = max_entries
        self._entries: OrderedDict[str, None] = OrderedDict()
        self._lock = Lock()

    def accept(self, value: str) -> bool:
        """Return true only when ``value`` was not already retained."""
        with self._lock:
            if value in self._entries:
                return False
            if len(self._entries) >= self.max_entries:
                return False
            self._entries[value] = None
            return True

    def clear(self) -> None:
        """Clear retained values, primarily for isolated tests."""
        with self._lock:
            self._entries.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._entries)
