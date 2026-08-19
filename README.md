# QSC Experiments — reproducible evaluation code

Self-contained experiment package for
[Quantum-Secure-By-Construction (QSC): A Paradigm Shift For Post-Quantum Agentic Intelligence](https://arxiv.org/abs/2603.15668)
(arXiv:2603.15668). It contains the Phase I micro-benchmarks, Phase II Azure
sidecar deployment, and the frozen results cited by that paper.

Please cite the paper if you use this code or these results. See [How to cite](#how-to-cite).

**Copyright © 2026 PricewaterhouseCoopers LLP (PwC US).** All contents of this
repository are the property of PwC US and are released under the MIT License.

## Architecture

```
┌─────────────────┐      PQC-TLS       ┌─────────────────┐
│  Orchestrator   │◄──────────────────►│   Worker 1      │
│     Agent       │   ML-DSA-65 Sigs   │     Agent       │
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

## Directory structure

```
qsc_experiments/
├── src/
│   ├── pqc_agents/          # Orchestrator & worker agents (+ classical baseline)
│   └── security/            # PQC, QRNG, QKD simulators, message handlers
├── tests/
│   ├── test_phase*.py       # Identity, workflow, resilience tests
│   ├── benchmarks/          # Phase I micro-benchmarks
│   └── demos/               # End-to-end phase demos
├── deployment/
│   ├── docker-compose.yml   # Local sidecar stack
│   ├── azure/               # AKS / ACI deploy scripts & k8s manifests
│   └── nginx/               # PQC-TLS proxy configs
├── scripts/                 # Deploy, verify, and benchmark runners
├── results/                 # Frozen accepted outputs (hashes in PROVENANCE.md)
├── docs/                    # Deployment, security, and reproduction docs
├── CITATION.cff             # Citation metadata
├── LICENSE
├── Dockerfile
└── pyproject.toml
```

## Quick start

Install Python dependencies from the lock file, then pick the layer you mean.
`pytest` does **not** regenerate the paper numbers.

```bash
# From the repository root
python3 -m pip install -r requirements.lock
./deployment/scripts/generate_certs.sh
```

### Protocol tests (correctness)

```bash
python3 -m pytest tests -v
```

This runs `test_*.py` only: identity, workflow, resilience, and protocol
authentication. It does not execute `tests/benchmarks/benchmark_*.py`.

### Phase I micro-benchmarks (timing)

Writes new JSON under `results/` and **will overwrite** the frozen artifacts
unless you copy them aside first. A new run will not match the committed
hashes; see [docs/REPRODUCTION.md](./docs/REPRODUCTION.md).

```bash
./scripts/run_all_benchmarks.sh
```

### Local Docker sidecar

Needs Docker. Certificates from `generate_certs.sh` are mounted at runtime.
`./test_local.sh` talks to the running `orchestrator-agent` container; it is
not a substitute for `pytest`.

```bash
export QSC_BOOTSTRAP_TOKEN="$(openssl rand -hex 32)"
docker compose -f deployment/docker-compose.yml up -d
./test_local.sh
```

### Azure Phase II

Canonical deploy is `scripts/deploy_azure_pqc.sh` (PQC-TLS sidecars).
`deployment/azure/deploy.sh` is a wrapper around that script. Optional AKS
manifests live under `deployment/azure/k8s/` and were not the source of the
frozen Azure JSON.

```bash
AZURE_RESOURCE_GROUP=YOUR_RESOURCE_GROUP \
AZURE_ACR_NAME=YOUR_ACR_NAME \
AZURE_OWNER_TAG=owner@example.com \
./scripts/deploy_azure_pqc.sh
./scripts/verify_azure_pqc.py
```

See `docs/DEPLOYMENT.md` for full instructions.

## Security components

- **PQC Identity:** ML-DSA-65 (Dilithium) digital signatures via liboqs
- **QRNG providers:** Explicit S-simulation fallback plus documented M-QRNG adapter/evidence
- **QKD Simulator:** Modeled QKD latency (not physical fiber in cloud)
- **Session protocol:** ML-KEM-768 with ML-DSA-authenticated transcripts,
  context-bound key derivation, and AES-256-GCM routine envelopes
- **Remote bootstrap:** Replay-protected HMAC proofs from an out-of-band
  `QSC_BOOTSTRAP_TOKEN`, including request-bound client ingress proofs
- **Transport validation:** TLS verification is on by default; private
  deployments trust the generated CA through `QSC_CA_BUNDLE`
- **Audit Log:** ML-DSA-signed, hash-chained security events (tamper-evident;
  suffix-deletion detection requires an external chain-head checkpoint);
  `QSC_AUDIT_MAX_BYTES` supplies a fail-closed retention bound
- **Lifecycle:** Per-session replay state and authenticated teardown

## Dependencies

- liboqs / liboqs-python
- PyNaCl (Ed25519 classical baseline)
- Flask, requests, pytest

## How to cite

If you use this experiment package or its results, please cite the paper:

```bibtex
@misc{bishwas2026quantumsecurebyconstructionqscparadigmshift,
      title={Quantum-Secure-By-Construction (QSC): A Paradigm Shift For Post-Quantum Agentic Intelligence},
      author={Arit Kumar Bishwas and Mousumi Sen and Albert Nieto-Morales and Joel Jacob Varghese},
      year={2026},
      eprint={2603.15668},
      archivePrefix={arXiv},
      primaryClass={cs.AI},
      url={https://arxiv.org/abs/2603.15668},
}
```

Please also cite this software artifact ([`CITATION.cff`](./CITATION.cff)) when referring to the code or frozen results.

## Reproduction

The committed `results/` files are the accepted evidence. Re-running
benchmarks will not reproduce those hashes. See
[docs/REPRODUCTION.md](./docs/REPRODUCTION.md) and
[results/PROVENANCE.md](./results/PROVENANCE.md).

## Copyright

Copyright © 2026 PricewaterhouseCoopers LLP (PwC US). This experiment package
and its frozen results are the property of PwC US. Permission to use, copy,
modify, and distribute is granted under the [MIT License](./LICENSE).
