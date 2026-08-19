# Copyright © 2026 PricewaterhouseCoopers LLP (PwC US).
# This file is the property of PwC US. Licensed under the MIT License.

"""Portable paths shared by benchmark entry points."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RESULTS_DIR = PROJECT_ROOT / "results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)


def result_path(filename: str) -> Path:
    path = RESULTS_DIR / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    return path
