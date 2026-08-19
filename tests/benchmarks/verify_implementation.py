#!/usr/bin/env python3
# Copyright © 2026 PricewaterhouseCoopers LLP (PwC US).
# This file is the property of PwC US. Licensed under the MIT License.

"""Verify that all required components for the lifecycle benchmark are in place."""

import sys
from pathlib import Path

def check_file(filepath, description):
    """Check if a file exists."""
    if Path(filepath).exists():
        print(f"✅ {description}")
        return True
    else:
        print(f"❌ {description} - MISSING: {filepath}")
        return False

def main():
    print("="*70)
    print("LIFECYCLE BENCHMARK IMPLEMENTATION VERIFICATION")
    print("="*70)
    
    all_good = True
    
    # Core benchmark file
    print("\n📦 Core Implementation:")
    all_good &= check_file(
        "tests/benchmarks/benchmark_framework_lifecycle.py",
        "Main benchmark script"
    )
    
    # Documentation
    print("\n📚 Documentation:")
    docs = [
        ("README.md", "Experiment README"),
        ("docs/REPRODUCTION.md", "Reproduction record"),
        ("docs/THREAT_MODEL.md", "Threat model"),
        ("results/PROVENANCE.md", "Results provenance"),
    ]
    for filepath, desc in docs:
        all_good &= check_file(filepath, desc)
    
    # Supporting scripts
    print("\n🔧 Supporting Scripts:")
    all_good &= check_file(
        "scripts/benchmark_scripts/run_lifecycle_benchmark.sh",
        "Execution script"
    )
    
    # Required agent files
    print("\n🤖 Required Agent Components:")
    agents = [
        ("src/pqc_agents/orchestrator_agent.py", "PQC Orchestrator"),
        ("src/pqc_agents/secure_search_agent.py", "PQC Worker"),
        ("src/pqc_agents/classical_orchestrator.py", "Classical Orchestrator"),
        ("src/pqc_agents/classical_search_agent.py", "Classical Worker"),
    ]
    for filepath, desc in agents:
        all_good &= check_file(filepath, desc)
    
    # Security components
    print("\n🔒 Security Components:")
    security = [
        ("src/security/pqc_identity.py", "PQC Identity"),
        ("src/security/classical_identity.py", "Classical Identity"),
        ("src/security/message_handler.py", "PQC Message Handler"),
        ("src/security/classical_message_handler.py", "Classical Message Handler"),
        ("src/security/qrng_simulator.py", "QRNG Simulator"),
        ("src/security/qkd_simulator.py", "QKD Simulator"),
        ("src/security/performance_metrics.py", "Performance Metrics"),
        ("src/security/hybrid_session_key.py", "Hybrid session key"),
        ("src/security/benchmark_metadata.py", "Benchmark metadata"),
    ]
    for filepath, desc in security:
        all_good &= check_file(filepath, desc)
    
    # Summary
    print("\n" + "="*70)
    if all_good:
        print("✅ ALL COMPONENTS VERIFIED - IMPLEMENTATION COMPLETE!")
        print("="*70)
        print("\n🚀 Ready to run:")
        print("   python tests/benchmarks/benchmark_framework_lifecycle.py")
        return 0
    else:
        print("❌ SOME COMPONENTS MISSING - SEE ABOVE")
        print("="*70)
        return 1

if __name__ == "__main__":
    sys.exit(main())
