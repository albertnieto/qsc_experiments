#!/bin/bash
# Copyright © 2026 PricewaterhouseCoopers LLP (PwC US).
# This file is the property of PwC US. Licensed under the MIT License.

# Compatibility wrapper. The publication Azure path is scripts/deploy_azure_pqc.sh.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
exec "$ROOT/scripts/deploy_azure_pqc.sh" "$@"
