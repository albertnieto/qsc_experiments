# Quantis QRNG evidence

This directory contains the small provenance inputs used to create
`results/qrng_quantis_mqrng.json`. The 1 GiB capture itself is not duplicated
in this repository; its SHA-256 and size are recorded in the manifest.

The live probe was performed on 2026-07-07 with an ID Quantique Quantis USB
device through EasyQuantis 1.4 under Rosetta 2. The 16 MiB / 34.185 s capture
corresponds to 0.468 MiB/s, 3.744 Mibit/s, or 3.926 decimal Mbit/s, against the
4.0 decimal Mbit/s device specification. The approximately 479 device-limited
256-bit key derivations per second assumes 1,024 captured source bytes per
derived key under the documented conditioning budget.

The USB output is vendor-postprocessed. It must not be described as raw
detector-level entropy. The probe and manifest are therefore evidence for an
`M-QRNG` provider observation, not a certification of the physical entropy
source.

Regenerate the normalized QSC artifact with:

```bash
python3 scripts/import_qrng_device_report.py \
  --probe-report docs/qrng/quantis_probe_report.json \
  --capture-manifest docs/qrng/quantis_conditioned.bin.manifest.json \
  --measurement-date 2026-07-07T10:59:00Z \
  --source-repository Quantum_QRNG_Assessment \
  --source-commit 679f46a4796de7f5d88f9eade8279cc9c9d83adf \
  --source-git-dirty \
  --operator collaborator \
  --serial 206406A410 \
  --output results/qrng_quantis_mqrng.json
```
