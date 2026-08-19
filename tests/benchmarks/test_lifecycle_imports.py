#!/usr/bin/env python3
# Copyright © 2026 PricewaterhouseCoopers LLP (PwC US).
# This file is the property of PwC US. Licensed under the MIT License.

"""Quick test to verify lifecycle benchmark imports work."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

try:
    from src.pqc_agents.orchestrator_agent import OrchestratorAgent
    from src.pqc_agents.secure_search_agent import SecureSearchAgent
    from src.pqc_agents.classical_orchestrator import ClassicalOrchestrator
    from src.pqc_agents.classical_search_agent import ClassicalSearchAgent
    from src.security.performance_metrics import PerformanceMetrics
    from src.security.qkd_simulator import QKDSimulator
    print("✅ All imports successful - benchmark ready to run")
except ImportError as e:
    print(f"❌ Import failed: {e}")
    sys.exit(1)
