# Results provenance

This directory holds the accepted frozen outputs for the public experiment
package. Do not replace them with older unpublished runs.

| Output | Generator | Measurement class | Paper use |
|---|---|---|---|
| `benchmark_results.json` | `tests/benchmarks/benchmark_pqc.py` | mixed (`M-local`, `Model-QKD`, `S-simulation`) | Primitive/workflow latency |
| `comparative_results.json` | `tests/benchmarks/benchmark_comparative.py` | mixed (`M-local`, `S-simulation`, `Model-QKD`) | PQC vs Ed25519 |
| `kem_benchmark_results.json` | `tests/benchmarks/benchmark_kem.py` | M-local | ML-KEM vs ECDH sizes/timing |
| `scalability_results.json` | `tests/benchmarks/benchmark_scalability.py` | M-local | Fan-out and throughput |
| `full_framework_results.json` | `tests/benchmarks/benchmark_full_framework.py` | mixed (`M-local`, `Model-QKD`, `S-simulation`) | Seven-channel local protocol |
| `lifecycle_benchmark_results.json` | `tests/benchmarks/benchmark_framework_lifecycle.py` | mixed (`M-local`, `Model-QKD`, `S-simulation`) | Lifecycle benchmark |
| `security_results.json` | `tests/benchmarks/benchmark_security.py` | S-simulation | Narrow tamper/replay conformance |
| `azure_channel_results.json` | `scripts/benchmark_azure_channels.py` | M-cloud + Model-QKD | Azure transport RTT |
| `qrng_*.json` | `scripts/collect_qrng_measurement.py` | M-QRNG or S-simulation | QRNG provider evidence |
| `qrng_quantis_mqrng.json` | `scripts/import_qrng_device_report.py` | M-QRNG | Quantis live-provider throughput and provenance |

Each JSON file must contain `measurement_type`, `provenance`, and
`run_metadata`. A file is not publication-ready if those fields are absent or
if a modeled value is presented as measured.

## Final local run record

- Command: `QSC_CPU_MODEL="Apple M3 Pro" QSC_PHYSICAL_CORES=12 QSC_RAM_BYTES=38654705664 QSC_SECURITY_TRANSACTIONS=100000 QSC_AUDIT_LOG="<fresh temporary file>" QSC_AUDIT_MAX_BYTES=209715200 bash scripts/run_all_benchmarks.sh`
- Audit policy during benchmarking: a fresh bounded temporary JSONL file was
  used and removed after the run; signing, append, flush, and `fsync` remained
  active, while prior-run log length could not distort initialization timing.
- QRNG command: `python3 scripts/collect_qrng_measurement.py --mode simulated --samples 100 --bytes 32 --output results/qrng_simulated.json`
- Host: Apple M3 Pro, 12 physical cores, 36 GiB RAM, macOS 26.4.1 arm64
- Git revision at run: `b3442b7af146e873945363d010c183d3a3a29fc9`
- Security conformance: 100,000 vectors; 4,866 attacks; 100% detected; 0 false positives
- Publication curation: machine hostnames were replaced with `redacted`; no
  timing, count, device, or cryptographic value was changed. The accepted
  Azure artifact was further sanitized after capture so `url_role` stores
  only `orchestrator` / `worker1` / `worker2` (no FQDNs) and
  `azure_resource_group` is `quantum-sandbox`; timings and status codes were
  not changed.
- Local freeze `git_dirty` is recorded as `true` on the 18 Aug host run and
  was not rewritten.
- QRNG S-simulation: `qrng_simulated.json` is the accepted 11 Aug record
  (`949d7ef6e82a6399d9f84f225e91b2f50558c2c8`). It was retained so the
  published 0.00115 ms / 27.90 MB/s means stay exact; it was not re-run
  against the 18 Aug revision.
- Azure M-cloud: captured 2026-08-18 in `quantum-sandbox` (East US ACI sidecar deployment); 20 health-endpoint repetitions per role, all HTTP 200; mean RTTs 23.99 ms (orchestrator), 19.63 ms (worker 1), 16.85 ms (worker 2). The accepted run validates the private-CA chain against `QSC_CA_BUNDLE`; it was executed from an in-region Azure client (East US ACI) so the genuine QSC certificate is presented and validated rather than a re-signed certificate injected by an external corporate TLS-inspection proxy, and the reported values are intra-region transport reachability.
- Azure command:
  `AZURE_RESOURCE_GROUP=quantum-sandbox QSC_ORCHESTRATOR_URL=... QSC_WORKER1_URL=... QSC_WORKER2_URL=... python3 scripts/benchmark_azure_channels.py --output results/azure_channel_results.json`
- QRNG hardware: `qrng_quantis_mqrng.json`; Quantis USB live probe at 0.468
  MiB/s, 3.744 Mibit/s, or 3.926 decimal Mbit/s; approximately 479
  device-limited keys/second assuming 1,024 source bytes per key; output is
  vendor-postprocessed
- QRNG source: `Quantum_QRNG_Assessment` revision
  `679f46a4796de7f5d88f9eade8279cc9c9d83adf`, with probe and capture-manifest
  hashes retained in the M-QRNG artifact

SHA-256 hashes from the final local rerun:

```text
38fe4482670f9ba42a09a9570613c8f25aba0e797ed7109f14fe2e9350f18105  benchmark_results.json
ecb027af8937d29bfcb0c7b715ccf688ff4d537cbfc7504dffb2d7cf6cfd6702  comparative_results.json
83f024ea702cc22e86e9e3a7c8a82dc2bbc492da53ac106ceda1c0e928d539cf  full_framework_results.json
00f45c23e679431933215a134e0ddce84bf7ce1ceb18fc12074ed34790bc0def  kem_benchmark_results.json
4f03c3d3919b4d697dd9cc69e4b05faa3b23fcc72352a6ca1d003404609d89f9  lifecycle_benchmark_results.json
6e5a4458eff7c61b7c6d01fd5aa5b1de6f1975c2e1834ec924cf8c1a0f9c9747  qrng_simulated.json
dc82c7517b68888e683e5379c2c4262e15a3c62bc09cd36bbf9479c7e1f23f1d  qrng_quantis_mqrng.json
6d254c4645c301e565d1f5a95f75390ca26cab3ec8d56fdc7435facee330d4ec  scalability_results.json
6291dd290535d018d14b3c152e2cb35f458479a8851a5d07b49370d5e11577e0  security_results.json
d4f046e888dc8314407bc38ed66da2d96f96039ab489c68cc8f74effdea7c8e7  azure_channel_results.json
5a9be250e5d63d68c1a1f0f1268a461ff733fb714a5719238bd628deed9b94be  plot_combined.png
b3b04cd6598a7bee74fa01b8a5cb3c6dd69e4cfc0362914fdcd91b1f37a4d97d  plot_overhead.png
03066cc556f797ab74b7cdc8ac827b360ac7d483807a92bd54143da4359d31db  plot_throughput.png
3f22cf92dd0d594853b31f8513431e228c60919f3f353c6a3ac3c0cbd0a4a340  plot_time_per_worker.png
a81b3a2a5e794a24b927e656c39e200e5601f7dd8e96700a4c79342d991dfa06  plot_total_time.png
067b75d58222e993e143554794518e756845caffab11d2ce3acb21384c6f4dbd  paper_results.txt
```

`scripts/benchmark_scripts/plots.py` can regenerate the two local-evidence
figures from `full_framework_results.json` and `scalability_results.json`.
It writes to `results/` by default.
