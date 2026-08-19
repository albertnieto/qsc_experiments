# PQC Multi-Agent Deployment Guide

This guide covers deploying the PQC-secured multi-agent system locally and on Azure.

## Architecture

```
┌─────────────────┐      PQC-TLS       ┌─────────────────┐
│  Orchestrator   │◄──────────────────►│   Worker 1      │
│     Agent       │                     │     Agent       │
│  + nginx-oqs    │      PQC-TLS       │  + nginx-oqs    │
└─────────────────┘◄──────────────────►└─────────────────┘
                                                 │
                                        PQC-TLS  │
                                                 ▼
                                        ┌─────────────────┐
                                        │   Worker 2      │
                                        │     Agent       │
                                        │  + nginx-oqs    │
                                        └─────────────────┘
```

## Security Layers

1. **Application Layer**: ML-DSA-65 signatures on independently verifiable artifacts
2. **Transport Layer**: PQC-TLS with ML-KEM support via nginx-oqs
3. **Network Layer**: Azure VNet/NSG or Docker network isolation

## Local Deployment

### Prerequisites

- Docker and Docker Compose
- OpenSSL (for certificate generation)

### Steps

1. **Generate certificates**:
```bash
./deployment/scripts/generate_certs.sh
```

2. **Start all services**:
```bash
export QSC_BOOTSTRAP_TOKEN="$(openssl rand -hex 32)"
docker compose -f deployment/docker-compose.yml up -d
```

3. **Verify deployment**:
```bash
# Check orchestrator
curl --cacert certs/ca.crt https://localhost:8443/health

# Check worker 1
curl --cacert certs/ca.crt https://localhost:8444/health

# Check worker 2
curl --cacert certs/ca.crt https://localhost:8445/health
```

4. **View logs**:
```bash
docker compose -f deployment/docker-compose.yml logs -f orchestrator
docker compose -f deployment/docker-compose.yml logs -f worker1
```

5. **Stop services**:
```bash
docker compose -f deployment/docker-compose.yml down
```

## Azure Deployment

### Option 1: Azure Container Instances (Simplest)

**Prerequisites**:
- Azure CLI installed and logged in
- Azure subscription

**Deploy**:
```bash
AZURE_RESOURCE_GROUP="my-rg" \
AZURE_LOCATION="eastus" \
AZURE_ACR_NAME="myacr" \
AZURE_OWNER_TAG="owner@example.com" \
./scripts/deploy_azure_pqc.sh
./scripts/verify_azure_pqc.py
```

That script is the only Azure publication path. `deployment/azure/deploy.sh`
forwards to it.

**Access**:
- Orchestrator: `https://<orchestrator-dns-label>.<region>.azurecontainer.io:8443`
- Worker 1: `https://<worker-1-dns-label>.<region>.azurecontainer.io:8443`
- Worker 2: `https://<worker-2-dns-label>.<region>.azurecontainer.io:8443`

### Option 2: Azure Kubernetes Service (optional)

These manifests are provided for operators who want AKS. They were **not**
the source of `results/azure_channel_results.json`. The nginx-oqs image is
pinned by digest in the YAML.

**Prerequisites**:
- Azure CLI
- kubectl

**Deploy**:
```bash
kubectl apply -f deployment/azure/k8s/
```

**Create TLS secrets**:
```bash
# Generate certs first
./deployment/scripts/generate_certs.sh

# Create Kubernetes secrets
kubectl create secret tls tls-certs \
  --cert=certs/orchestrator.crt \
  --key=certs/orchestrator.key
```

**Check status**:
```bash
kubectl get pods
kubectl get svc
kubectl logs -l app=orchestrator
```

**Scale workers**:
```bash
kubectl scale deployment worker-agent --replicas=5
```

**Access**:
```bash
# Get external IP
kubectl get svc orchestrator-service
```

### Option 3: Azure VMs (Manual)

**Create 3 VMs**:
```bash
# VM1: Orchestrator
az vm create \
  --resource-group "${AZURE_RESOURCE_GROUP:?set approved resource group}" \
  --name orchestrator-vm \
  --image Ubuntu2204 \
  --size Standard_D4s_v3 \
  --admin-username azureuser \
  --generate-ssh-keys

# VM2: Worker 1
az vm create \
  --resource-group "${AZURE_RESOURCE_GROUP:?set approved resource group}" \
  --name worker1-vm \
  --image Ubuntu2204 \
  --size Standard_D4s_v3 \
  --admin-username azureuser \
  --generate-ssh-keys

# VM3: Worker 2
az vm create \
  --resource-group "${AZURE_RESOURCE_GROUP:?set approved resource group}" \
  --name worker2-vm \
  --image Ubuntu2204 \
  --size Standard_D4s_v3 \
  --admin-username azureuser \
  --generate-ssh-keys
```

**On each VM**:
```bash
# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Clone repo
git clone <repo-url>
cd qsc_experiments

# Generate certs
./deployment/scripts/generate_certs.sh

# Run orchestrator (VM1)
docker run -d -p 8000:8000 -p 8443:8443 \
  -e AGENT_TYPE=orchestrator \
  -e AGENT_ID=orchestrator_agent \
  -e QSC_BOOTSTRAP_TOKEN="$QSC_BOOTSTRAP_TOKEN" \
  -e QSC_CA_BUNDLE=/app/certs/ca.crt \
  -v $(pwd)/certs:/app/certs \
  qsc-experiments:local

# Run worker (VM2, VM3)
docker run -d -p 8001:8001 -p 8443:8443 \
  -e AGENT_TYPE=worker \
  -e AGENT_ID=worker_agent_1 \
  -e QSC_BOOTSTRAP_TOKEN="$QSC_BOOTSTRAP_TOKEN" \
  -v $(pwd)/certs:/app/certs \
  qsc-experiments:local
```

## Testing PQC Communication

### Delegate Search

Worker discovery, mutual identity pinning, and session establishment are
performed by the orchestrator. The public delegation ingress first requires a
nonce and request-bound bootstrap proof; it does not expose the removed
`/register_worker` API.

```bash
export QSC_BOOTSTRAP_TOKEN="<same deployment secret>"
./test_local.sh
```

## Monitoring

### Local
```bash
docker-compose logs -f
```

### Azure Container Instances
```bash
az container logs --resource-group "${AZURE_RESOURCE_GROUP:?set approved resource group}" --name orchestrator-agent
```

### AKS
```bash
kubectl logs -l app=orchestrator -f
kubectl top pods
```

## Cost Estimates

### Azure Container Instances
- 3 containers × 2 vCPU × 4GB RAM
- ~$150-200/month (24/7 operation)

### AKS
- 3-node cluster (Standard_D4s_v3)
- ~$400-500/month
- Auto-scaling can reduce costs

### VMs
- 3 × Standard_D4s_v3
- ~$450/month

## Security Best Practices

1. **Certificates**: Use Azure Key Vault for production certs
2. **Secrets**: Store API keys in Azure Key Vault
3. **Network**: Use Azure Private Link for internal communication
4. **Monitoring**: Enable Azure Monitor and Application Insights
5. **Updates**: Regularly update liboqs and nginx-oqs images

## Troubleshooting

### nginx-oqs not starting
```bash
# Check nginx config
docker exec orchestrator-proxy nginx -t

# Check certificates
docker exec orchestrator-proxy ls -la /etc/nginx/certs/
```

### PQC signature verification fails
```bash
# Check liboqs installation
docker exec orchestrator python -c "import oqs; print(oqs.get_enabled_sig_mechanisms())"
```

### Network connectivity issues
```bash
# Test connectivity
docker exec orchestrator ping worker1
docker exec orchestrator curl http://worker1:8001/health
```

## Cleanup

### Local
```bash
docker-compose down -v
rm -rf certs/
```

### Azure
```bash
az group delete --name "${AZURE_RESOURCE_GROUP:?set approved resource group}" --yes --no-wait
```
