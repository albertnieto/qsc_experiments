# Reproduction record

This document records the accepted 2026-08-18 evidence freeze that ships in
`results/`. The software tag for this deposit is `v1.0.0`.

## What a rerun will and will not do

This package is enough to re-run protocol tests, regenerate Phase I
micro-benchmarks, and redeploy the sidecar stack. It is **not** a
bit-identical reproduction kit.

- Timing JSON depends on CPU, thermal state, OS, liboqs build, and cloud
  placement. A new machine will not reproduce the SHA-256 hashes in
  `results/PROVENANCE.md`.
- The committed `results/` files are the accepted evidence. Compare a new run
  by measurement class and qualitative ranking, not by byte-identical JSON.
- Local Phase I numbers were captured on the host below (liboqs-python 0.12.0,
  dirty worktree). The Docker image pins liboqs / liboqs-python 0.14.0. Those
  are different environments.
- `qrng_simulated.json` is the accepted 11 Aug record and was not re-run
  against the 18 Aug host revision. M-QRNG and M-cloud files are external
  acquisitions; `run_all_benchmarks.sh` does not regenerate them.

## Software

- Repository tag: `v1.0.0`
- Frozen-result capture revision: `b3442b7af146e873945363d010c183d3a3a29fc9`
  (dirty worktree; recorded in run metadata). This release packages those
  accepted files; HEAD is not that revision.
- Python: 3.11.5
- Operating system: macOS 26.4.1, arm64
- Local `liboqs` / `liboqs-python`: liboqs 0.12.1-dev / liboqs-python 0.12.0
  (the warning is retained in the run log)
- Docker `liboqs` / `liboqs-python`: pinned build defaults 0.14.0 / 0.14.0
- PQC-TLS proxy image: `openquantumsafe/nginx` at digest
  `sha256:4fe9d9c284ecfa561d668ea312ac5c448894fec532e5e5e4bfd7b4d823947d2e`
  (Docker Hub `latest` index as of 2026-08-17). The accepted Azure JSON does
  not record the proxy digest used at capture time.
- Python-linked OpenSSL: 3.0.10 (1 Aug 2023), as recorded by `ssl`
- Host `openssl` CLI: 3.6.3 (9 Jun 2026)
- Dependency lock: `requirements.lock` (direct Python package versions)

## Local hardware

- CPU/model: Apple M3 Pro
- Physical cores: 12
- RAM: 36 GiB
- Python architecture: arm64
- Thermal/power mode: not controlled
- Background load: not instrumented; report if materially different

## Workloads and statistics

- Synthetic workload description: fixed mock queries; no private dataset
- Random seed: 20260811 for lifecycle/security conformance
- Repetitions per primitive: 50--1000, recorded per metric in JSON
- Repetitions per channel: recorded per metric in JSON
- Security-conformance vector count: 100,000
- Attack probability and classes: 5%; 2.5% tampering and 2.5% stale replay
- Warm-up policy: no separate warm-up phase
- Summary statistic: arithmetic mean with minimum and maximum
- Confidence interval method: normal approximation,
  `1.96 * sample standard deviation / sqrt(n)` where reported

## Measurement labels

- `M-local`: wall-clock observation from the declared local host
- `M-cloud`: wall-clock observation from an Azure endpoint
- `M-QRNG`: real QRNG-provider output with device metadata
- `Model-QKD`: parameterized QKD or infrastructure contribution
- `S-simulation`: software provider or fault-injection behavior

## QRNG hardware run

The real-device evidence is preserved separately from the deterministic local
protocol benchmark. The benchmark uses the explicitly labeled
`S-simulation` provider; the following artifact records an independent
`M-QRNG` live probe:

- Artifact: `results/qrng_quantis_mqrng.json`
- Device: ID Quantique Quantis USB, device 0, serial `206406A410`
- SDK/firmware: EasyQuantis 1.4 (x86_64 via Rosetta 2), core `0x060b1c01`
- Output mode: vendor-postprocessed USB output; no detector-level raw mode
- Live sample: 16 MiB in 34.185 s
- Measured device rate: 0.468 MiB/s, 3.744 Mibit/s, or 3.926 decimal Mbit/s
  (4.0 decimal Mbit/s specification)
- Device-limited rate: approximately 479 256-bit key derivations/second,
  assuming 1,024 captured source bytes per derived key
- Operator: collaborator
- Capture SHA-256: `d2f3a0de24f046c1167313625b6986749145e3448c057bbe50e4b34702de7c18`
- Source revision: `Quantum_QRNG_Assessment` at
  `679f46a4796de7f5d88f9eade8279cc9c9d83adf`

The evidence is a real provider observation, not a certification of the
inaccessible detector-level entropy source. The bundled probe and manifest
under `docs/qrng/` are sufficient to regenerate the normalized artifact.

The software fallback uses `python.secrets` and must be labeled S-simulation. It
must not be described as a physical QRNG measurement.

## Azure Phase II

- Subscription (record only if permitted): omitted
- Resource group: `quantum-sandbox`
- Region: East US
- Container/VM SKU: Azure Container Instances; per-service SKU is not retained in the sanitized artifact
- CPU and memory per service: not retained in the sanitized artifact
- Container image digest: not retained in the sanitized artifact
- PQC-TLS proxy version: not retained in the sanitized artifact
- Endpoint roles: orchestrator, worker1, worker2 health endpoints
- Number of repetitions: 20 per endpoint
- Network conditions: public Azure endpoint RTT; status code 200 for every repetition

The Azure harness measures PQC-TLS transport behavior. The accepted artifact is
`results/azure_channel_results.json`; it reports role-level health-endpoint RTTs,
not complete seven-channel application transactions. The accepted run validates
the private-CA chain against `QSC_CA_BUNDLE` and is measured from an in-region
Azure client so the genuine QSC certificate is presented rather than a re-signed
certificate from an external TLS-inspection proxy. Physical QKD is not available in this deployment; QKD values
are modeled separately.

## Commands

```bash
python3 -m pip install -r requirements.lock
python3 -m pytest tests -v   # protocol tests only; does not write results/
AUDIT_FILE="$(mktemp /tmp/qsc-benchmark-audit.XXXXXX)"
trap 'rm -f "$AUDIT_FILE"' EXIT
QSC_AUDIT_LOG="$AUDIT_FILE" QSC_AUDIT_MAX_BYTES=209715200 \
  ./scripts/run_all_benchmarks.sh
python3 scripts/collect_qrng_measurement.py \
  --mode simulated --samples 100 --bytes 32 \
  --output results/qrng_simulated.json
python3 scripts/import_qrng_device_report.py \
  --probe-report docs/qrng/quantis_probe_report.json \
  --capture-manifest docs/qrng/quantis_conditioned.bin.manifest.json \
  --measurement-date 2026-07-07T10:59:00Z \
  --source-repository Quantum_QRNG_Assessment \
  --source-commit 679f46a4796de7f5d88f9eade8279cc9c9d83adf \
  --source-git-dirty --operator collaborator --serial 206406A410 \
  --output results/qrng_quantis_mqrng.json
QSC_CA_BUNDLE=certs/ca.crt python3 scripts/benchmark_azure_channels.py \
  --output results/azure_channel_results.json
```

The local benchmark runner produces `lifecycle_benchmark_results.json`,
`comparative_results.json`, `benchmark_results.json`,
`kem_benchmark_results.json`, `scalability_results.json`,
`security_results.json`, `full_framework_results.json`, formatted paper output,
and plots. `qrng_simulated.json` uses its explicit collection command above.
The M-QRNG and M-cloud files are external acquisitions and are never silently
regenerated by `run_all_benchmarks.sh`. Before a release, record the exact
command, date, environment, and output hashes in `results/PROVENANCE.md`.

`full_framework_results.json` is canonical only for the seven local channel
measurements. It references, but does not copy, the canonical
`security_results.json` and `scalability_results.json` outputs.

## Zenodo deposit

This repository is intended to be archived on Zenodo with a citable DOI.

Suggested deposit metadata:

- **Title:** QSC Multi-Agent Security Experiments — Phase I micro-benchmarks and
  Phase II Azure sidecar deployment
- **Resource type:** Software
- **License:** MIT (see `LICENSE`)
- **Copyright:** PricewaterhouseCoopers LLP (PwC US)
- **Authors:** as listed in `CITATION.cff`
- **Related publication:** A. K. Bishwas, M. Sen, A. Nieto-Morales,
  and J. J. Varghese, *Quantum-Secure-By-Construction (QSC): A Paradigm
  Shift For Post-Quantum Agentic Intelligence*, arXiv:2603.15668,
  https://arxiv.org/abs/2603.15668

Before depositing:

1. Confirm the author list and affiliations in `CITATION.cff` with all co-authors.
2. Verify no secrets are tracked (`.env`, private keys, certificates, subscription
   identifiers); these are excluded via `.gitignore`.
3. Confirm the committed `results/` artifacts match their hashes in
   `results/PROVENANCE.md` and are labeled with the correct evidence class
   (`M-local`, `M-cloud`, `M-QRNG`, `Model-QKD`, `S-simulation`). Never present a
   modeled or simulated value as a physical measurement.
4. This release is tagged `v1.0.0`. After Zenodo assigns the DOI, add it as the
   top-level `doi` value in `CITATION.cff`.
