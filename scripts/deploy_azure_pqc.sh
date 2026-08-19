#!/bin/bash
# Copyright © 2026 PricewaterhouseCoopers LLP (PwC US).
# This file is the property of PwC US. Licensed under the MIT License.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# Configuration
RESOURCE_GROUP="${AZURE_RESOURCE_GROUP:?Set AZURE_RESOURCE_GROUP to the approved resource group}"
LOCATION="${AZURE_LOCATION:-eastus}"
ACR_NAME="${AZURE_ACR_NAME:-qscExperimentRegistry}"
IMAGE_TAG="${IMAGE_TAG:-qsc-experiments}"
OWNER_TAG="${AZURE_OWNER_TAG:?Set AZURE_OWNER_TAG to satisfy the subscription Owner-tag policy}"
PROJECT_TAG="${AZURE_PROJECT_TAG:-qsc-experiments}"
BOOTSTRAP_TOKEN="${QSC_BOOTSTRAP_TOKEN:-$(openssl rand -hex 32)}"

# FQDNs (Must be unique in the region)
DNS_LABEL_ORCH="qsc-orch-${RANDOM}"
DNS_LABEL_W1="qsc-w1-${RANDOM}"
DNS_LABEL_W2="qsc-w2-${RANDOM}"
ORCHESTRATOR_FQDN="${DNS_LABEL_ORCH}.${LOCATION}.azurecontainer.io"
WORKER1_FQDN="${DNS_LABEL_W1}.${LOCATION}.azurecontainer.io"
WORKER2_FQDN="${DNS_LABEL_W2}.${LOCATION}.azurecontainer.io"
DEPLOY_DIR="$(mktemp -d)"
trap 'rm -rf "$DEPLOY_DIR"' EXIT

QSC_CERTS_DIR="$ROOT/certs" \
ORCHESTRATOR_DNS_NAMES="$ORCHESTRATOR_FQDN" \
WORKER_DNS_NAMES="$WORKER1_FQDN,$WORKER2_FQDN" \
    "$ROOT/deployment/scripts/generate_certs.sh"

echo "=== Azure PQC Deployment (Sidecar Architecture) ==="
echo "Resource Group: $RESOURCE_GROUP"
echo "ACR: $ACR_NAME"
echo "DNS Labels: $DNS_LABEL_ORCH, $DNS_LABEL_W1, $DNS_LABEL_W2"

# 1. Create Resource Group (if not exists)
az group create --name "$RESOURCE_GROUP" --location "$LOCATION" \
  --tags Owner="$OWNER_TAG" Project="$PROJECT_TAG"

# 2. Create/Get ACR
echo "Checking ACR..."
if ! az acr show --name "$ACR_NAME" --resource-group "$RESOURCE_GROUP" > /dev/null 2>&1; then
    echo "Creating ACR..."
    az acr create --resource-group "$RESOURCE_GROUP" --name "$ACR_NAME" --sku Basic --admin-enabled true
else
    echo "ACR exists."
fi

# 3. Build images in ACR (does not require a local Docker daemon)
ACR_LOGIN_SERVER=$(az acr show --name "$ACR_NAME" --query loginServer --output tsv)
ACR_USERNAME=$(az acr credential show --name "$ACR_NAME" --query username --output tsv)
ACR_PASSWORD=$(az acr credential show --name "$ACR_NAME" --query passwords[0].value --output tsv)

if [ "${SKIP_ACR_BUILD:-false}" != "true" ]; then
echo "Building Agent Image..."
az acr build --registry "$ACR_NAME" --image "qsc-agent:$IMAGE_TAG" --file Dockerfile .

echo "Building Proxy Image..."
az acr build --registry "$ACR_NAME" --image "qsc-proxy:$IMAGE_TAG" --file deployment/azure/nginx/Dockerfile .
else
echo "Skipping ACR build (SKIP_ACR_BUILD=true)."
fi

# 4. Deploy Worker 1
echo "Deploying Worker 1..."
cat <<EOF > "$DEPLOY_DIR/worker1.yaml"
apiVersion: 2019-12-01
location: $LOCATION
name: worker1-group
properties:
  containers:
  - name: worker1-agent
    properties:
      image: $ACR_LOGIN_SERVER/qsc-agent:$IMAGE_TAG
      command:
      - python
      - -m
      - src.pqc_agents.worker_server
      ports:
      - port: 8001
      resources:
        requests:
          cpu: 1.0
          memoryInGB: 2.0
      environmentVariables:
      - name: AGENT_TYPE
        value: worker
      - name: AGENT_ID
        value: worker_agent_1
      - name: AGENT_PORT
        value: '8001'
      - name: SEARCH_API
        value: mock
      - name: QSC_BOOTSTRAP_TOKEN
        secureValue: $BOOTSTRAP_TOKEN
  - name: worker1-proxy
    properties:
      image: $ACR_LOGIN_SERVER/qsc-proxy:$IMAGE_TAG
      ports:
      - port: 8443
      resources:
        requests:
          cpu: 1.0
          memoryInGB: 2.0
      environmentVariables:
      - name: ROLE
        value: worker1
  osType: Linux
  ipAddress:
    type: Public
    ports:
    - protocol: TCP
      port: 8443
    dnsNameLabel: $DNS_LABEL_W1
  imageRegistryCredentials:
  - server: $ACR_LOGIN_SERVER
    username: $ACR_USERNAME
    password: $ACR_PASSWORD
EOF

az container create --resource-group "$RESOURCE_GROUP" --file "$DEPLOY_DIR/worker1.yaml"

# 5. Deploy Worker 2
echo "Deploying Worker 2..."
cat <<EOF > "$DEPLOY_DIR/worker2.yaml"
apiVersion: 2019-12-01
location: $LOCATION
name: worker2-group
properties:
  containers:
  - name: worker2-agent
    properties:
      image: $ACR_LOGIN_SERVER/qsc-agent:$IMAGE_TAG
      command:
      - python
      - -m
      - src.pqc_agents.worker_server
      ports:
      - port: 8002
      resources:
        requests:
          cpu: 1.0
          memoryInGB: 2.0
      environmentVariables:
      - name: AGENT_TYPE
        value: worker
      - name: AGENT_ID
        value: worker_agent_2
      - name: AGENT_PORT
        value: '8002'
      - name: SEARCH_API
        value: mock
      - name: QSC_BOOTSTRAP_TOKEN
        secureValue: $BOOTSTRAP_TOKEN
  - name: worker2-proxy
    properties:
      image: $ACR_LOGIN_SERVER/qsc-proxy:$IMAGE_TAG
      ports:
      - port: 8443
      resources:
        requests:
          cpu: 1.0
          memoryInGB: 2.0
      environmentVariables:
      - name: ROLE
        value: worker2
  osType: Linux
  ipAddress:
    type: Public
    ports:
    - protocol: TCP
      port: 8443
    dnsNameLabel: $DNS_LABEL_W2
  imageRegistryCredentials:
  - server: $ACR_LOGIN_SERVER
    username: $ACR_USERNAME
    password: $ACR_PASSWORD
EOF

az container create --resource-group "$RESOURCE_GROUP" --file "$DEPLOY_DIR/worker2.yaml"

# 6. Deploy Orchestrator
WORKER_URLS="https://${DNS_LABEL_W1}.${LOCATION}.azurecontainer.io:8443,https://${DNS_LABEL_W2}.${LOCATION}.azurecontainer.io:8443"
echo "Deploying Orchestrator (Workers: $WORKER_URLS)..."

cat <<EOF > "$DEPLOY_DIR/orchestrator.yaml"
apiVersion: 2019-12-01
location: $LOCATION
name: orchestrator-group
properties:
  containers:
  - name: orchestrator-agent
    properties:
      image: $ACR_LOGIN_SERVER/qsc-agent:$IMAGE_TAG
      command:
      - python
      - -m
      - src.pqc_agents.orchestrator_server
      ports:
      - port: 8000
      resources:
        requests:
          cpu: 1.0
          memoryInGB: 2.0
      environmentVariables:
      - name: AGENT_TYPE
        value: orchestrator
      - name: AGENT_ID
        value: orchestrator_agent
      - name: AGENT_PORT
        value: '8000'
      - name: WORKER_ENDPOINTS
        value: $WORKER_URLS
      - name: SEARCH_API
        value: mock
      - name: QSC_BOOTSTRAP_TOKEN
        secureValue: $BOOTSTRAP_TOKEN
      - name: QSC_CA_BUNDLE
        value: /app/certs/ca.crt
  - name: orchestrator-proxy
    properties:
      image: $ACR_LOGIN_SERVER/qsc-proxy:$IMAGE_TAG
      ports:
      - port: 8443
      resources:
        requests:
          cpu: 1.0
          memoryInGB: 2.0
      environmentVariables:
      - name: ROLE
        value: orchestrator
  osType: Linux
  ipAddress:
    type: Public
    ports:
    - protocol: TCP
      port: 8443
    dnsNameLabel: $DNS_LABEL_ORCH
  imageRegistryCredentials:
  - server: $ACR_LOGIN_SERVER
    username: $ACR_USERNAME
    password: $ACR_PASSWORD
EOF

az container create --resource-group "$RESOURCE_GROUP" --file "$DEPLOY_DIR/orchestrator.yaml"


echo ""
echo "=== Deployment Started ==="
echo "Orchestrator URL: https://${DNS_LABEL_ORCH}.${LOCATION}.azurecontainer.io:8443"
echo "Worker 1 URL: https://${DNS_LABEL_W1}.${LOCATION}.azurecontainer.io:8443"
echo "Worker 2 URL: https://${DNS_LABEL_W2}.${LOCATION}.azurecontainer.io:8443"
echo ""
echo "Monitor deployment with:"
echo "az container show --resource-group $RESOURCE_GROUP --name orchestrator-group --query instanceView.state"
