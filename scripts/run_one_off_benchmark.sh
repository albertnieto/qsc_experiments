#!/bin/bash
# Copyright © 2026 PricewaterhouseCoopers LLP (PwC US).
# This file is the property of PwC US. Licensed under the MIT License.

set -euo pipefail

# Non-canonical probe helper. Results from this script are not publication
# evidence: it uses curl -k (TLS verification disabled). The accepted Azure
# artifact is produced by scripts/benchmark_azure_channels.py with QSC_CA_BUNDLE.

# Config
RG="${AZURE_RESOURCE_GROUP:?Set AZURE_RESOURCE_GROUP to the approved resource group}"
ACR_NAME="${AZURE_ACR_NAME:-qscExperimentRegistry}"
CONTAINER_NAME="${AZURE_BENCHMARK_CONTAINER:-probe-benchmark}"
SERVER_HOST="${AZURE_BENCHMARK_HOST:?Set AZURE_BENCHMARK_HOST to the deployed service host}"

# Get ACR Creds
ACR_LOGIN_SERVER=$(az acr show --name $ACR_NAME --query loginServer --output tsv)
ACR_USERNAME=$(az acr credential show --name $ACR_NAME --query username --output tsv)
ACR_PASSWORD=$(az acr credential show --name $ACR_NAME --query passwords[0].value --output tsv)

# Command
CMD="echo BENCHMARK_START; for i in \$(seq 1 20); do curl -k -w \"%{time_total}\\n\" -o /dev/null -s https://$SERVER_HOST:8443/health; sleep 0.2; done; echo BENCHMARK_END"

echo "Deploying one-off benchmark container..."
az container create \
  --resource-group $RG \
  --name $CONTAINER_NAME \
  --image "$ACR_LOGIN_SERVER/curl:latest" \
  --registry-login-server $ACR_LOGIN_SERVER \
  --registry-username $ACR_USERNAME \
  --registry-password $ACR_PASSWORD \
  --restart-policy Never \
  --command-line "/bin/sh -c '$CMD'" \
  --cpu 1 --memory 1

echo "Waiting for container to finish..."
while [ "$(az container show --resource-group $RG --name $CONTAINER_NAME --query instanceView.state -o tsv)" == "Running" ] || [ "$(az container show --resource-group $RG --name $CONTAINER_NAME --query instanceView.state -o tsv)" == "Pending" ]; do
  echo "Still running..."
  sleep 5
done

echo "Container finished. Fetching logs..."
az container logs --resource-group $RG --name $CONTAINER_NAME
