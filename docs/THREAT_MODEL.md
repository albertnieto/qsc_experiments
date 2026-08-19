# QSC threat model

## Protected assets

- Agent identities, public-key registrations, and session establishment
- Confidentiality and integrity of inter-agent requests and responses
- Task identifiers, nonces, task graphs, audit records, and policy decisions
- Availability and correctness of the communication workflow

## Adversary capabilities

The in-scope network adversary can observe, delay, reorder, drop, replay, and
modify messages; inject messages; and attempt to impersonate an agent without
its signing key. The adversary may record ciphertext for later cryptanalysis
and may attempt downgrade or fallback manipulation when the protocol does not
bind the selected posture to the session transcript.

## Trust assumptions

- Endpoint identities and private signing keys are provisioned securely.
- The registration/authorization service is trusted to bind identities to
  public keys.
- ML-DSA-65, ML-KEM-768, HKDF-based key derivation, and AES-256-GCM are
  implemented correctly and used with unique nonces.
- A QKD key is accepted only when both endpoints authenticate the same link
  context. QKD protects key establishment on that link; it does not attest
  the endpoint.
- QRNG hardware, when selected, is an entropy provider. Its device and API
  health are outside the cryptographic proof and must be monitored.

## Security goals

The protocol aims to provide authenticated peers, confidentiality and
integrity for protected messages, replay rejection, explicit posture
negotiation, and hybrid key derivation that remains usable when QKD is
unavailable. ML-DSA signatures are retained for independently verifiable
artifacts such as task graphs and audit records; routine channel protection
uses authenticated encryption.

## Out of scope

This experiment does not establish security against compromised agents,
compromised endpoints or models, stolen private keys, certificate-authority
failure, side-channel attacks, denial of service, malicious tool outputs,
prompt/tool injection, model hallucination, policy-engine compromise, or
QRNG service compromise. It does not implement physical QKD, quantum digital
signatures, quantum secret sharing, or quantum secure direct communication.

The 100,000-vector test, when run, is a protocol-conformance and fault-
injection test for modeled payload tampering and stale-nonce replay. It is not
evidence of general adversarial robustness.
