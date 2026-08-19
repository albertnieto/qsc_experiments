#!/bin/bash
# Copyright © 2026 PricewaterhouseCoopers LLP (PwC US).
# This file is the property of PwC US. Licensed under the MIT License.

# Run PQC experimentation tests in Docker

echo "=== Running PQC Multi-Agent Tests ==="
echo ""

echo "Running the complete collected test suite"
docker exec orchestrator-agent bash -c \
  "cd /app && PYTHONPATH=/app python -m pytest tests -v --tb=short"

echo ""
echo "=== All Tests Complete ==="
