# PQC Benchmarking Suite

See `docs/README_QUANTUM_SECURITY.md` for the framework overview.

## Overview

This benchmarking suite provides comprehensive performance analysis comparing Post-Quantum Cryptography (PQC) with classical cryptography for secure agent communication.

## Framework lifecycle benchmark

`benchmark_framework_lifecycle.py` maps selected measurements to the paper's
operational workflow. It is an integration report, not a replacement for the
canonical primitive, security, scalability, and seven-channel artifacts.

See `benchmark_framework_lifecycle.py` and the top-level `docs/REPRODUCTION.md`
for the lifecycle benchmark and reproducibility procedure.

### Quick Start

```bash
# Run the unified lifecycle benchmark
python tests/benchmarks/benchmark_framework_lifecycle.py

# Output: ./results/lifecycle_benchmark_results.json
```

### Why use the lifecycle benchmark?

- **Paper-aligned**: metrics map to selected operational steps
- **Protocol-level**: measures complete workflows in addition to primitives
- **Cross-referenced**: invokes the canonical security and scalability
  simulations rather than defining competing evidence

---

## Canonical benchmark components

The individual outputs remain authoritative for their named measurement scope.

### 1. PQC Benchmark (`benchmark_pqc.py`)
Measures performance of the PQC implementation using ML-DSA-65:
- Key generation
- Message signing and verification
- QRNG operations
- QKD simulation
- Full query delegation workflow

### 2. Comparative Benchmark (`benchmark_comparative.py`)
Direct comparison between PQC and classical Ed25519:
- **Cryptographic Primitives**: Key generation, signing, verification
- **End-to-End Performance**: Complete query delegation workflow
- **Artifact Sizes**: Public keys and signatures
- **System Throughput**: Queries per second

### 3. Paper Results Generator (`generate_paper_results.py`)
Generates publication-ready results:
- LaTeX tables
- Markdown tables
- Key findings summary
- Comparative analysis

## Running Benchmarks

### Unified Lifecycle Benchmark (Recommended)

```bash
# Run the unified benchmark
python tests/benchmarks/benchmark_framework_lifecycle.py

# Results saved to:
# - ./results/lifecycle_benchmark_results.json
```

### Individual benchmark scripts

```bash
# Run the component scripts that feed the frozen results/
./scripts/run_all_benchmarks.sh
```

## Implementation Details

### PQC Implementation
- **Algorithm**: ML-DSA-65 (FIPS 204)
- **Library**: liboqs-python
- **Components**:
  - `PQCIdentity`: Key management
  - `MessageHandler`: Signing/verification
  - `QRNG`: Quantum random number generation
  - `QKD`: Quantum key distribution simulation

### Classical Baseline
- **Algorithm**: Ed25519
- **Library**: PyNaCl
- **Components**:
  - `ClassicalIdentity`: Key management
  - `ClassicalMessageHandler`: Signing/verification
  - Standard PRNG for nonces

## Key Metrics

### Performance Metrics
- **Latency**: Mean, min, max execution time (ms)
- **Throughput**: Operations per second
- **Overhead**: PQC vs Classical percentage increase

### Size Metrics
- **Public Key Size**: Bytes
- **Signature Size**: Bytes
- **Message Overhead**: Signed vs unsigned payload size

## Interpreting results

Do not substitute expected cryptographic sizes or timing estimates for measured
outputs. Use the JSON files in `results/`, whose run metadata records the host,
software versions, repetitions, warm-up policy, and confidence-interval method.

## Output Files

- `benchmark_results.json`: Raw PQC metrics
- `comparative_results.json`: Raw comparative metrics
- `paper_results.txt`: Formatted results for publication

## Docker Environment

The `Dockerfile` pins liboqs 0.14.0 and liboqs-python Git tag `v0.14` for the
sidecar image. Local Phase I JSON in `results/` was captured on the host
recorded in `docs/REPRODUCTION.md` (liboqs-python 0.12.0); do not assume the
Docker image and the frozen local numbers are the same environment.
