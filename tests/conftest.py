# Copyright © 2026 PricewaterhouseCoopers LLP (PwC US).
# This file is the property of PwC US. Licensed under the MIT License.

"""Ensure qsc_experiments root is on sys.path for src.* imports."""
import sys
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture(autouse=True)
def isolated_audit_log(monkeypatch, tmp_path):
    """Keep tests independent from benchmark audit output."""
    monkeypatch.setenv("QSC_AUDIT_LOG", str(tmp_path / "audit_log.jsonl"))
