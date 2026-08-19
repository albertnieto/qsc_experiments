# Copyright © 2026 PricewaterhouseCoopers LLP (PwC US).
# This file is the property of PwC US. Licensed under the MIT License.

import requests
import sys
import os

ORCHESTRATOR_URL = os.environ.get("QSC_ORCHESTRATOR_URL")
WORKER1_URL = os.environ.get("QSC_WORKER1_URL")
WORKER2_URL = os.environ.get("QSC_WORKER2_URL")
TLS_VERIFY = os.environ.get("QSC_CA_BUNDLE") or True

def check_url(url, name):
    if not url:
        print(f"Skipping {name}: set its environment URL first")
        return False
    print(f"Checking {name} at {url}...")
    try:
        response = requests.get(url, verify=TLS_VERIFY, timeout=10)
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text}")
        return True
    except requests.RequestException as e:
        print(f"Error connecting to {name}: {e}")
        return False

print("=== Verifying Azure PQC Deployment ===")
o_ok = check_url(ORCHESTRATOR_URL, "Orchestrator")
w1_ok = check_url(WORKER1_URL, "Worker 1")
w2_ok = check_url(WORKER2_URL, "Worker 2")

if o_ok and w1_ok and w2_ok:
    print("\nSUCCESS: All agents are reachable!")
    sys.exit(0)
else:
    print("\nFAILURE: Some agents are unreachable.")
    sys.exit(1)
