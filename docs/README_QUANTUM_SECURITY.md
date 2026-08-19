# Quantum-Resistant Security Framework for Agentic AI

This implementation demonstrates a quantum-resistant security framework for multi-agent systems, based on the principles of Post-Quantum Cryptography (PQC), Quantum Random Number Generation (QRNG), and Quantum Key Distribution (QKD).

## Architecture

### Agents

1. **Orchestrator Agent** (`orchestrator_agent.py`)
   - Main research planning agent
   - Delegates search tasks to worker agents
   - Manages agent registry and authentication
   - Authenticates session transcripts with ML-DSA and encrypts routine traffic

2. **Secure Search Agent** (`secure_search_agent.py`)
   - Worker agent for web search operations
   - Verifies the pinned orchestrator identity during session setup
   - Authenticates routine results with AES-256-GCM
   - Enforces per-session nonce and query-ID replay state

### Security Components

Located in `src/security/`:

- **pqc_identity.py**: PQC key pair generation and signing using **ML-DSA-65** (NIST PQC standard, formerly Dilithium3)
- **message_handler.py**: AES-256-GCM envelopes and selective artifact signatures
- **hybrid_session_key.py**: Context-bound ML-KEM/QKD/QRNG session derivation
- **bootstrap_auth.py**: HMAC bootstrap proofs for remote trust and teardown
- **agent_registry.py**: Trusted agent public key registry
- **qrng_simulator.py**: Quantum random number generation for nonces and query IDs
- **qkd_simulator.py**: Quantum key distribution simulation for confidential queries
- **audit_log.py**: ML-DSA-signed, hash-chained security-event log

## Implementation Phases

### Phase 0: Setup (Current)
- ✅ Worker Agent (Secure Search Agent) created
- ✅ Orchestrator Agent with PQC capabilities
- ✅ Security infrastructure in place
- ✅ **Real ML-DSA-65 PQC implementation via liboqs**

### Phase 1: Foundation - Quantum-Resistant Identity
**Objective**: Establish verifiable agent identities using PQC

**Experiments**:
- 1.1: Agent Identity Generation - Both agents generate ML-DSA-65 key pairs
- 1.2: Authenticated Handshake - Challenge-response authentication

**Run Tests**:
```bash
pytest tests/test_phase1_identity.py -v
```

### Phase 2: Secure Delegated Research Workflow
**Objective**: End-to-end secure query delegation with cryptographic guarantees

**Experiments**:
- 2.1: Secure Query Delegation - Orchestrator encrypts routine queries with AES-256-GCM
- 2.2: Secure Search Execution & Result Authentication - Worker returns AES-256-GCM-authenticated results
- 2.3: Secure Result Ingestion & Auditing - Complete chain of custody

**Run Tests**:
```bash
pytest tests/test_phase2_workflow.py -v
```

### Phase 3: Resilience Testing & Advanced Security
**Objective**: Demonstrate robustness against attacks and advanced primitives

**Experiments**:
- 3.1: QRNG Simulation for Replay Attack Prevention
- 3.2: Integrity Attack (Tampering) Simulation
- 3.3: QKD Simulation for Confidential Queries

**Run Tests**:
```bash
pytest tests/test_phase3_resilience.py -v
```

## Quick Start

### Local Installation

```bash
# Install liboqs
git clone --depth=1 https://github.com/open-quantum-safe/liboqs
cmake -S liboqs -B liboqs/build -DBUILD_SHARED_LIBS=ON
cmake --build liboqs/build --parallel 8
sudo cmake --build liboqs/build --target install

# Set library path
export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:/usr/local/lib

# Install liboqs-python
git clone --depth=1 https://github.com/open-quantum-safe/liboqs-python
cd liboqs-python
pip install .
cd ..

# Install project
pip install .
```

### Docker Installation

```bash
# Build Docker image (includes liboqs and liboqs-python)
docker build -t qsc-experiments:local .

# Run container
docker run -it qsc-experiments:local
```

### Run Phase 0 Demo
```bash
python tests/demos/phase0_demo.py
```

### Run All Tests
```bash
pytest tests/test_phase1_identity.py tests/test_phase2_workflow.py tests/test_phase3_resilience.py -v
```

## Security Features

### Defense-in-Depth Layers

1. **PQC (Post-Quantum Cryptography)**
   - **ML-DSA-65** digital signatures (NIST PQC standard, formerly Dilithium3)
   - Quantum-resistant authentication
   - Message integrity verification
   - Public key size: 1952 bytes
   - Signature size: 3293 bytes

2. **QRNG (Quantum Random Number Generator)**
   - Cryptographically secure random values
   - Unique query IDs for replay prevention
   - Challenge nonces for handshakes

3. **QKD (Quantum Key Distribution)**
   - Optional modeled link-key input
   - Not a physical QKD deployment in this package
   - Does not replace endpoint authentication

### Audit Trail

Security events are logged with:
- Timestamp
- Event type (QUERY_ENCRYPTED, RESULTS_AUTHENTICATED, and artifact-signing events)
- Agent identities
- Query IDs and status
- Previous-record hash, event hash, signer public key, and ML-DSA signature

The verifier detects modified or reordered records. Detecting valid suffix
deletion requires an externally retained chain-head checkpoint; this is a
tamper-evident log, not immutable storage.

View audit log:
```python
from src.security.audit_log import AuditLog
from src.security.pqc_identity import PQCIdentity

signer = PQCIdentity("orchestrator")
log = AuditLog(signer, "fresh_audit_log.jsonl")
log.log_event("VERIFICATION_EXAMPLE", {"agent_id": signer.agent_id})
trusted = {signer.agent_id: signer.get_public_key()}
assert log.verify_chain(trusted)
```

For a persisted deployment log, load the separately pinned signer keys rather
than generating a new identity. Archive and externally checkpoint the chain
head before `QSC_AUDIT_MAX_BYTES` is reached.

## Dependencies

The Dockerfile automatically installs:
- **liboqs**: Open Quantum Safe C library
- **liboqs-python**: Python bindings for liboqs
- Python dependencies from `requirements.txt` (or the hashed
  `requirements.lock` for local reproduction)

## PQC Algorithms Available

Via liboqs-python, you can use:
- **ML-DSA-44, ML-DSA-65, ML-DSA-87** (default: ML-DSA-65, formerly Dilithium2/3/5)
- Falcon-512, Falcon-1024
- SPHINCS+-SHA2/SHAKE variants

Change algorithm:
```python
orchestrator = OrchestratorAgent("orch", algorithm="ML-DSA-87")
```

## Future Enhancements

1. ✅ Real ML-DSA implementation (COMPLETE)
2. Integrate real QRNG hardware/API
3. Implement actual QKD network protocols
4. ✅ Add encrypted communication channels (COMPLETE)
5. ✅ Implement authenticated session establishment and teardown (COMPLETE)
6. Add multi-agent coordination protocols

## Remote bootstrap

Remote orchestrator and worker services must share a high-entropy
`QSC_BOOTSTRAP_TOKEN` through the deployment secret store. Bootstrap proofs are
HMACs over canonical request fields and nonces; this includes the public
`/delegate_search` request digest, and the token itself is never sent. TLS
verification defaults to enabled. Set `QSC_CA_BUNDLE` to the generated or
managed CA file for private certificates; only disable `QSC_TLS_VERIFY`
explicitly in an isolated test.

## References

- NIST Post-Quantum Cryptography Standards
- ML-DSA Digital Signature Algorithm (NIST standard, formerly CRYSTALS-Dilithium)
- Open Quantum Safe Project
- Quantum Key Distribution Protocols
- Defense-in-Depth Security Architecture
