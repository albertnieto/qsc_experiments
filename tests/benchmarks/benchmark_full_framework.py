# Copyright © 2026 PricewaterhouseCoopers LLP (PwC US).
# This file is the property of PwC US. Licensed under the MIT License.

"""
Unified Framework Benchmark: 7 Critical Communication Channels
Validates the Quantum-Secured Agentic AI architecture from the research paper.
"""
import asyncio
import json
import time
import secrets
from typing import Dict, List, Any
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

CLASSICAL_PRNG_TIME_MS = 0.000001  # 1 nanosecond
QKD_ENC_DEC_TIME_MS = 0.005  # 5 microseconds per encrypt/decrypt

from src.pqc_agents.orchestrator_agent import OrchestratorAgent
from src.pqc_agents.secure_search_agent import SecureSearchAgent
from src.pqc_agents.classical_orchestrator import ClassicalOrchestrator
from src.pqc_agents.classical_search_agent import ClassicalSearchAgent
from src.security.qkd_simulator import QKDSimulator
from src.security.qrng_simulator import QRNGSimulator
from src.security.hybrid_session_key import (
    SessionKey,
    decrypt_aes256_gcm,
    derive_session_key,
    encrypt_aes256_gcm,
    session_auth_message,
)
from src.security.message_handler import MessageHandler
from src.security.pqc_identity import PQCIdentity
from src.security.benchmark_metadata import run_metadata
from results_paths import result_path


CHANNEL_METADATA = {
    "channel_1": {
        "label": "1. User -> Orchestrator",
        "layers": ["ML-KEM", "ML-DSA", "AES-256-GCM", "QRNG"],
        "qrng_in_timing": True,
        "model_qkd_in_timing": False,
        "scope": "routine exchange plus amortized session setup",
    },
    "channel_2": {
        "label": "2. Orchestrator <-> Agent Handshake",
        "layers": ["ML-KEM", "ML-DSA", "QRNG"],
        "qrng_in_timing": True,
        "model_qkd_in_timing": False,
        "scope": "complete authenticated session setup",
    },
    "channel_3": {
        "label": "3. Orchestrator -> MCP Server",
        "layers": ["ML-KEM", "ML-DSA", "AES-256-GCM", "QRNG", "Model-QKD"],
        "qrng_in_timing": True,
        "model_qkd_in_timing": True,
        "scope": "routine exchange plus amortized session setup",
    },
    "channel_4": {
        "label": "4. Agent <- MCP Server (Fetch)",
        "layers": ["ML-KEM", "ML-DSA", "AES-256-GCM", "QRNG", "Model-QKD"],
        "qrng_in_timing": True,
        "model_qkd_in_timing": True,
        "scope": "fetch plus amortized session setup",
    },
    "channel_5": {
        "label": "5. Agent -> MCP Server (Publish)",
        "layers": ["ML-KEM", "ML-DSA", "AES-256-GCM", "QRNG", "Model-QKD"],
        "qrng_in_timing": True,
        "model_qkd_in_timing": True,
        "scope": "routine exchange plus amortized session setup",
    },
    "channel_6": {
        "label": "6. Agent <-> Agent (via Shared Memory)",
        "layers": ["ML-KEM", "ML-DSA", "AES-256-GCM", "QRNG", "Model-QKD"],
        "qrng_in_timing": True,
        "model_qkd_in_timing": True,
        "scope": "routine exchange plus amortized session setup",
    },
    "channel_7": {
        "label": "7. Orchestrator <- MCP (Aggregation)",
        "layers": ["ML-DSA", "AES-256-GCM"],
        "qrng_in_timing": False,
        "model_qkd_in_timing": False,
        "scope": "aggregation only; setup and publication are excluded",
    },
}


class MCP_Server_Simulator:
    """Simulates Multi-agent Control Protocol Server."""
    
    def __init__(self):
        self.task_queue = {}
        self.results_store = {}
        self.task_graph = None
    
    def publish_task_graph(self, signed_graph: dict):
        """Publish task graph from orchestrator."""
        self.task_graph = signed_graph
        payload = signed_graph.get("payload", {})
        tasks = payload.get("tasks", [])
        for task in tasks:
            agent_id = task.get("agent_id")
            if agent_id:
                self.task_queue[agent_id] = task
    
    def get_agent_task(self, agent_id: str) -> dict:
        """Agent fetches its assigned task."""
        return self.task_queue.get(agent_id, {})
    
    def submit_agent_result(self, result: dict, agent_id: str = ""):
        """Agent submits completed result."""
        resolved_agent_id = agent_id or result.get("agent_id")
        if resolved_agent_id:
            self.results_store[resolved_agent_id] = result
    
    def get_all_results(self) -> List[dict]:
        """Orchestrator retrieves all results."""
        return list(self.results_store.values())


class Shared_Memory_Simulator:
    """Simulates shared memory for inter-agent communication."""
    
    def __init__(self):
        self.memory = {}
    
    def write(self, key: str, signed_data: dict):
        """Write data to shared memory."""
        self.memory[key] = signed_data
    
    def read(self, key: str) -> dict:
        """Read data from shared memory."""
        return self.memory.get(key, {})


class User:
    """Simulates user with PQC identity."""
    
    def __init__(self):
        from src.security.pqc_identity import PQCIdentity
        from src.security.message_handler import MessageHandler
        self.agent_id = "user"
        self.identity = PQCIdentity(self.agent_id)
        self.message_handler = MessageHandler(self.identity)
        self.qrng = QRNGSimulator()


class BenchmarkEndpoint:
    """Minimal PQC endpoint used by the in-memory MCP transport."""

    def __init__(self, endpoint_id: str):
        self.agent_id = endpoint_id
        self.identity = PQCIdentity(endpoint_id)
        self.message_handler = MessageHandler(self.identity)


def establish_benchmark_session(
    sender,
    receiver,
    *,
    context: bytes,
    qrng: QRNGSimulator,
    qkd: QKDSimulator | None = None,
    qkd_epoch: str | None = None,
) -> tuple[SessionKey, SessionKey, float]:
    """Establish matching ML-KEM sessions and return measured setup time."""
    started = time.perf_counter()
    ciphertext, sender_secret = sender.identity.encapsulate(
        receiver.identity.get_kem_public_key()
    )
    receiver_secret = receiver.identity.decapsulate(ciphertext)
    if sender_secret != receiver_secret:
        raise ValueError("ML-KEM endpoint secrets differ")
    epoch = qkd_epoch if qkd is not None else None
    qkd_secret = (
        qkd.establish_key(
            sender.agent_id,
            receiver.agent_id,
            epoch=epoch,
        )
        if qkd is not None
        else None
    )
    entropy = qrng.generate_bytes(32)
    session_auth = session_auth_message(
        sender_id=sender.agent_id,
        receiver_id=receiver.agent_id,
        session_context=context,
        ciphertext=ciphertext,
        qrng_entropy=entropy,
        qkd_epoch=epoch,
    )
    signature = sender.identity.sign(session_auth)
    if not receiver.identity.verify(
        session_auth,
        signature,
        sender.identity.get_public_key(),
    ):
        raise ValueError("session-establishment signature failed")
    session_args = {
        "pqc_ciphertext": ciphertext,
        "sender_id": sender.agent_id,
        "receiver_id": receiver.agent_id,
        "session_context": context,
        "qrng_entropy": entropy,
        "qkd_secret": qkd_secret,
        "qkd_epoch": epoch,
    }
    sender_session = derive_session_key(
        pqc_secret=sender_secret,
        **session_args,
    )
    receiver_session = derive_session_key(
        pqc_secret=receiver_secret,
        **session_args,
    )
    if sender_session != receiver_session:
        raise ValueError("hybrid session derivation mismatch")
    elapsed_ms = (time.perf_counter() - started) * 1000
    return sender_session, receiver_session, elapsed_ms


def encrypt_with_qkd(data: bytes, key: bytes) -> bytes:
    """Encrypt data using AES-256-GCM and a modeled QKD-derived key."""
    time.sleep(QKD_ENC_DEC_TIME_MS / 1000)
    nonce, ciphertext = encrypt_aes256_gcm(key, data)
    return nonce + ciphertext


def decrypt_with_qkd(encrypted: bytes, key: bytes) -> bytes:
    """Decrypt and authenticate AES-256-GCM data."""
    time.sleep(QKD_ENC_DEC_TIME_MS / 1000)
    return decrypt_aes256_gcm(key, encrypted[:12], encrypted[12:])


def encrypted_envelope(agent_id: str, encrypted: bytes) -> dict:
    """Represent encrypted bytes in the in-memory transport simulator."""
    return {"agent_id": agent_id, "encrypted": encrypted.hex()}


def decode_envelope(envelope: dict, key: bytes) -> dict:
    """Decrypt an envelope and restore the signed JSON object."""
    plaintext = decrypt_with_qkd(bytes.fromhex(envelope["encrypted"]), key)
    return json.loads(plaintext.decode())


async def benchmark_user_to_orchestrator(iterations: int = 100) -> Dict[str, float]:
    """Channel 1: routine user request over ML-KEM/AES-GCM + QRNG."""
    
    # PQC version
    user = User()
    orchestrator = OrchestratorAgent("orch_1")
    sender_session, receiver_session, key_time = establish_benchmark_session(
        user,
        orchestrator,
        context=b"channel-1-user-request",
        qrng=user.qrng,
    )
    
    start = time.perf_counter()
    for i in range(iterations):
        request = {"query": "research quantum computing", "nonce": user.qrng.generate_nonce()}
        aad = f"channel-1:{i}".encode()
        envelope = user.message_handler.encrypt_payload(
            request,
            sender_session,
            aad=aad,
        )
        recovered = orchestrator.message_handler.decrypt_payload(
            envelope,
            receiver_session,
            aad=aad,
        )
        if recovered != request:
            raise ValueError("channel 1 request mismatch")
    pqc_time = (
        (time.perf_counter() - start) * 1000 / iterations
        + (key_time / iterations)
    )
    
    # Classical version
    from src.security.classical_identity import ClassicalIdentity
    from src.security.classical_message_handler import ClassicalMessageHandler
    
    user_classical = ClassicalIdentity("user_classical")
    user_handler = ClassicalMessageHandler(user_classical)
    orch_classical = ClassicalOrchestrator("orch_classical_1")
    
    start = time.perf_counter()
    for _ in range(iterations):
        time.sleep(CLASSICAL_PRNG_TIME_MS / 1000)
        request = {"query": "research quantum computing", "nonce": secrets.token_hex(32)}
        signed = user_handler.sign_message(request)
        verified = orch_classical.message_handler.verify_message(signed, user_classical.get_public_key())
    classical_time = (time.perf_counter() - start) * 1000 / iterations
    
    return {"pqc": pqc_time, "classical": classical_time}


async def benchmark_orchestrator_to_agent_handshake(iterations: int = 50) -> Dict[str, float]:
    """Channel 2: mutually bound ML-DSA/ML-KEM session establishment."""
    
    # PQC version
    pqc_times = []
    for i in range(iterations):
        orchestrator = OrchestratorAgent(f"orch_hs_{i}")
        agent = SecureSearchAgent(f"agent_hs_{i}")
        orchestrator.register_worker(agent.agent_id, agent.get_public_key())
        
        start = time.perf_counter()
        session, _ = orchestrator.establish_session(
            agent,
            session_context=f"channel-2:{i}".encode(),
        )
        pqc_times.append((time.perf_counter() - start) * 1000)
        if session.transcript_hash not in agent.sessions:
            raise ValueError("channel 2 receiver session missing")
        orchestrator.teardown_session(agent)
    
    # Classical version
    classical_times = []
    for i in range(iterations):
        orchestrator = ClassicalOrchestrator(f"orch_hs_c_{i}")
        agent = ClassicalSearchAgent(f"agent_hs_c_{i}")
        orchestrator.register_worker(agent.agent_id, agent.get_public_key())
        
        start = time.perf_counter()
        result = await orchestrator.perform_handshake(agent)
        classical_times.append((time.perf_counter() - start) * 1000)
    
    return {"pqc": sum(pqc_times) / len(pqc_times), "classical": sum(classical_times) / len(classical_times)}


async def benchmark_orchestrator_to_mcp(iterations: int = 100) -> Dict[str, float]:
    """Channel 3: signed task artifacts over ML-KEM/AES-GCM + modeled QKD."""
    
    mcp = MCP_Server_Simulator()
    qkd = QKDSimulator()
    
    # PQC version
    orchestrator = OrchestratorAgent("orch_mcp")
    mcp_endpoint = BenchmarkEndpoint("mcp_server")
    sender_session, receiver_session, key_time = establish_benchmark_session(
        orchestrator,
        mcp_endpoint,
        context=b"channel-3-task-publication",
        qrng=orchestrator.qrng,
        qkd=qkd,
        qkd_epoch="channel-3",
    )
    
    start = time.perf_counter()
    for i in range(iterations):
        task_graph = {
            "graph_id": orchestrator.qrng.generate_query_id(),
            "tasks": [{"agent_id": f"agent_{i}", "task": "search"}]
        }
        signed = orchestrator.message_handler.sign_message(task_graph)
        aad = f"channel-3:{task_graph['graph_id']}".encode()
        envelope = orchestrator.message_handler.encrypt_payload(
            signed,
            sender_session,
            aad=aad,
        )
        recovered = mcp_endpoint.message_handler.decrypt_payload(
            envelope,
            receiver_session,
            aad=aad,
        )
        if not mcp_endpoint.message_handler.verify_message(
            recovered,
            orchestrator.identity.get_public_key(),
        ):
            raise ValueError("channel 3 task-graph signature failed")
        mcp.publish_task_graph(recovered)
    pqc_time = (time.perf_counter() - start) * 1000 / iterations + (key_time / iterations)
    
    # Classical version
    orchestrator_c = ClassicalOrchestrator("orch_mcp_c")
    key_c = secrets.token_bytes(32)
    
    start = time.perf_counter()
    for i in range(iterations):
        time.sleep(CLASSICAL_PRNG_TIME_MS / 1000)
        task_graph = {
            "graph_id": secrets.token_hex(16),
            "tasks": [{"agent_id": f"agent_{i}", "task": "search"}]
        }
        signed = orchestrator_c.message_handler.sign_message(task_graph)
        encrypted = encrypt_with_qkd(json.dumps(signed).encode(), key_c)
        mcp.publish_task_graph(
            json.loads(decrypt_with_qkd(encrypted, key_c).decode())
        )
    classical_time = (time.perf_counter() - start) * 1000 / iterations
    
    return {"pqc": pqc_time, "classical": classical_time}


async def benchmark_agent_fetch_from_mcp(iterations: int = 100) -> Dict[str, float]:
    """Channel 4: agent fetches signed tasks over ML-KEM/AES-GCM."""
    
    mcp = MCP_Server_Simulator()
    qkd = QKDSimulator()
    
    # PQC version
    orchestrator = OrchestratorAgent("orch_fetch")
    agent = SecureSearchAgent("agent_fetch")
    sender_session, receiver_session, key_time = establish_benchmark_session(
        orchestrator,
        agent,
        context=b"channel-4-task-fetch",
        qrng=orchestrator.qrng,
        qkd=qkd,
        qkd_epoch="channel-4",
    )
    
    # Pre-populate MCP
    for i in range(iterations):
        task = {"task_id": f"task_{i}", "query": f"query_{i}"}
        signed = orchestrator.message_handler.sign_message(task)
        aad = f"channel-4:task_{i}".encode()
        envelope = orchestrator.message_handler.encrypt_payload(
            signed,
            sender_session,
            aad=aad,
        )
        mcp.task_queue[f"agent_fetch_{i}"] = {
            "aad": aad,
            "envelope": envelope,
        }
    
    start = time.perf_counter()
    for i in range(iterations):
        task = mcp.get_agent_task(f"agent_fetch_{i}")
        if task:
            decrypted = agent.message_handler.decrypt_payload(
                task["envelope"],
                receiver_session,
                aad=task["aad"],
            )
            verified = agent.message_handler.verify_message(
                decrypted, orchestrator.identity.get_public_key()
            )
            if not verified:
                raise ValueError("channel 4 task signature failed")
    pqc_time = (
        (time.perf_counter() - start) * 1000 / iterations
        + (key_time / iterations)
    )
    
    # Classical version
    orchestrator_c = ClassicalOrchestrator("orch_fetch_c")
    agent_c = ClassicalSearchAgent("agent_fetch_c")
    key_c = secrets.token_bytes(32)
    
    mcp_c = MCP_Server_Simulator()
    for i in range(iterations):
        task = {"task_id": f"task_{i}", "query": f"query_{i}"}
        signed = orchestrator_c.message_handler.sign_message(task)
        encrypted = encrypt_with_qkd(json.dumps(signed).encode(), key_c)
        mcp_c.task_queue[f"agent_fetch_c_{i}"] = encrypted_envelope(
            orchestrator_c.agent_id, encrypted
        )
    
    start = time.perf_counter()
    for i in range(iterations):
        task = mcp_c.get_agent_task(f"agent_fetch_c_{i}")
        if task:
            decrypted = decode_envelope(task, key_c)
            verified = agent_c.message_handler.verify_message(
                decrypted, orchestrator_c.identity.get_public_key()
            )
    classical_time = (time.perf_counter() - start) * 1000 / iterations
    
    return {"pqc": pqc_time, "classical": classical_time}


async def benchmark_agent_publish_to_mcp(iterations: int = 100) -> Dict[str, float]:
    """Channel 5: signed result artifacts over ML-KEM/AES-GCM."""
    
    mcp = MCP_Server_Simulator()
    qkd = QKDSimulator()
    
    # PQC version
    agent = SecureSearchAgent("agent_pub")
    mcp_endpoint = BenchmarkEndpoint("mcp_server")
    qrng_pub = QRNGSimulator()
    sender_session, receiver_session, key_time = establish_benchmark_session(
        agent,
        mcp_endpoint,
        context=b"channel-5-result-publication",
        qrng=qrng_pub,
        qkd=qkd,
        qkd_epoch="channel-5",
    )
    
    start = time.perf_counter()
    for i in range(iterations):
        result = {
            "result_id": qrng_pub.generate_query_id(),
            "data": f"result_{i}"
        }
        signed = agent.message_handler.sign_message(result)
        aad = f"channel-5:{result['result_id']}".encode()
        envelope = agent.message_handler.encrypt_payload(
            signed,
            sender_session,
            aad=aad,
        )
        recovered = mcp_endpoint.message_handler.decrypt_payload(
            envelope,
            receiver_session,
            aad=aad,
        )
        if not mcp_endpoint.message_handler.verify_message(
            recovered,
            agent.get_public_key(),
        ):
            raise ValueError("channel 5 result signature failed")
        mcp.submit_agent_result(recovered)
    pqc_time = (
        (time.perf_counter() - start) * 1000 / iterations
        + (key_time / iterations)
    )
    
    # Classical version
    agent_c = ClassicalSearchAgent("agent_pub_c")
    key_c = secrets.token_bytes(32)
    mcp_c = MCP_Server_Simulator()
    
    start = time.perf_counter()
    for i in range(iterations):
        time.sleep(CLASSICAL_PRNG_TIME_MS / 1000)
        result = {"result_id": secrets.token_hex(16), "data": f"result_{i}"}
        signed = agent_c.message_handler.sign_message(result)
        encrypted = encrypt_with_qkd(json.dumps(signed).encode(), key_c)
        mcp_c.submit_agent_result(encrypted_envelope(agent_c.agent_id, encrypted))
    classical_time = (time.perf_counter() - start) * 1000 / iterations
    
    return {"pqc": pqc_time, "classical": classical_time}


async def benchmark_agent_to_agent_via_shared_memory(iterations: int = 100) -> Dict[str, float]:
    """Channel 6: routine agent traffic over ML-KEM/AES-GCM."""
    
    shared_mem = Shared_Memory_Simulator()
    qkd = QKDSimulator()
    qrng = QRNGSimulator()
    
    # PQC version
    agent_a = SecureSearchAgent("agent_a")
    agent_b = SecureSearchAgent("agent_b")
    sender_session, receiver_session, key_time = establish_benchmark_session(
        agent_a,
        agent_b,
        context=b"channel-6-shared-memory",
        qrng=qrng,
        qkd=qkd,
        qkd_epoch="channel-6",
    )
    
    start = time.perf_counter()
    for i in range(iterations):
        message = {"nonce": qrng.generate_nonce(), "data": f"message_{i}"}
        aad = f"channel-6:{i}".encode()
        encrypted = agent_a.message_handler.encrypt_payload(
            message,
            sender_session,
            aad=aad,
        )
        shared_mem.write(
            f"key_{i}", {"aad": aad, "envelope": encrypted}
        )
        
        read_data = shared_mem.read(f"key_{i}")
        if read_data:
            decrypted = agent_b.message_handler.decrypt_payload(
                read_data["envelope"],
                receiver_session,
                aad=read_data["aad"],
            )
            if decrypted != message:
                raise ValueError("channel 6 routine payload mismatch")
    pqc_time = (
        (time.perf_counter() - start) * 1000 / iterations
        + (key_time / iterations)
    )
    
    # Classical version
    agent_a_c = ClassicalSearchAgent("agent_a_c")
    agent_b_c = ClassicalSearchAgent("agent_b_c")
    key_c = secrets.token_bytes(32)
    shared_mem_c = Shared_Memory_Simulator()
    
    start = time.perf_counter()
    for i in range(iterations):
        time.sleep(CLASSICAL_PRNG_TIME_MS / 1000)
        message = {"nonce": secrets.token_hex(32), "data": f"message_{i}"}
        signed = agent_a_c.message_handler.sign_message(message)
        encrypted = encrypt_with_qkd(json.dumps(signed).encode(), key_c)
        shared_mem_c.write(
            f"key_{i}", encrypted_envelope(agent_a_c.agent_id, encrypted)
        )
        
        read_data = shared_mem_c.read(f"key_{i}")
        if read_data:
            decrypted = decode_envelope(read_data, key_c)
            verified = agent_b_c.message_handler.verify_message(
                decrypted, agent_a_c.get_public_key()
            )
    classical_time = (time.perf_counter() - start) * 1000 / iterations
    
    return {"pqc": pqc_time, "classical": classical_time}


async def benchmark_orchestrator_aggregation(num_agents: int = 10) -> Dict[str, float]:
    """Channel 7: decrypt and verify signed result artifacts."""
    
    mcp = MCP_Server_Simulator()
    qkd = QKDSimulator()
    
    # PQC version
    orchestrator = OrchestratorAgent("orch_agg")
    agents = [SecureSearchAgent(f"agent_agg_{i}") for i in range(num_agents)]
    receiver_sessions = {}
    
    # Pre-populate results (key establishment happens here, not measured in aggregation)
    for i, agent in enumerate(agents):
        sender_session, receiver_session, _ = establish_benchmark_session(
            agent,
            orchestrator,
            context=f"channel-7-agent-{i}".encode(),
            qrng=orchestrator.qrng,
            qkd=qkd,
            qkd_epoch=f"channel-7-{i}",
        )
        receiver_sessions[agent.agent_id] = receiver_session
        result = {"agent_id": agent.agent_id, "result": f"data_{i}"}
        signed = agent.message_handler.sign_message(result)
        aad = f"channel-7:{agent.agent_id}".encode()
        encrypted = agent.message_handler.encrypt_payload(
            signed,
            sender_session,
            aad=aad,
        )
        mcp.submit_agent_result(
            {"aad": aad, "envelope": encrypted},
            agent.agent_id,
        )
    
    # Measure aggregation time (verify + decrypt per agent)
    start = time.perf_counter()
    all_results = mcp.get_all_results()
    for i, result in enumerate(all_results):
        agent = agents[i]
        decrypted = orchestrator.message_handler.decrypt_payload(
            result["envelope"],
            receiver_sessions[agent.agent_id],
            aad=result["aad"],
        )
        verified = orchestrator.message_handler.verify_message(
            decrypted, agent.get_public_key()
        )
        if not verified:
            raise ValueError("channel 7 result signature failed")
    pqc_time = (time.perf_counter() - start) * 1000
    
    # Classical version
    orchestrator_c = ClassicalOrchestrator("orch_agg_c")
    agents_c = [ClassicalSearchAgent(f"agent_agg_c_{i}") for i in range(num_agents)]
    mcp_c = MCP_Server_Simulator()
    classical_keys = []
    
    for i, agent in enumerate(agents_c):
        key_c = secrets.token_bytes(32)
        classical_keys.append(key_c)
        result = {"agent_id": agent.agent_id, "result": f"data_{i}"}
        signed = agent.message_handler.sign_message(result)
        encrypted = encrypt_with_qkd(json.dumps(signed).encode(), key_c)
        mcp_c.submit_agent_result(encrypted_envelope(agent.agent_id, encrypted))
    
    start = time.perf_counter()
    all_results = mcp_c.get_all_results()
    for i, result in enumerate(all_results):
        decrypted = decode_envelope(result, classical_keys[i])
        verified = orchestrator_c.message_handler.verify_message(
            decrypted, agents_c[i].get_public_key()
        )
    classical_time = (time.perf_counter() - start) * 1000 + (QKD_ENC_DEC_TIME_MS * num_agents)
    
    return {"pqc": pqc_time, "classical": classical_time}


def print_results_table(results: Dict[str, Any]):
    """Print final results table."""
    
    print("\n" + "="*100)
    print("QUANTUM-SECURED AGENTIC AI: FULL FRAMEWORK BENCHMARK RESULTS")
    print("="*100)
    print()
    print("| Communication Channel                 | Security Layers Used | PQC Time (ms) | Classical Time (ms) | Overhead (%) |")
    print("|---------------------------------------|--------------------|---------------|---------------------|--------------|")
    
    channels = [
        (
            metadata["label"],
            ", ".join(metadata["layers"]),
            results[channel_id],
        )
        for channel_id, metadata in CHANNEL_METADATA.items()
    ]
    
    for name, layers, data in channels:
        pqc = data["pqc"]
        classical = data["classical"]
        overhead = ((pqc / classical) - 1) * 100
        print(f"| {name:37s} | {layers:18s} | {pqc:13.2f} | {classical:19.2f} | {overhead:12.1f} |")
    
    print()
    print("="*100)
    print()


async def main():
    """Run all benchmarks."""
    
    print("Starting Full Framework Benchmark...")
    print("This validates the 7 critical communication channels from the research paper.\n")
    
    results = {}
    
    print("[1/7] Benchmarking User -> Orchestrator...")
    results["channel_1"] = await benchmark_user_to_orchestrator(100)
    
    print("[2/7] Benchmarking Orchestrator <-> Agent Handshake...")
    results["channel_2"] = await benchmark_orchestrator_to_agent_handshake(50)
    
    print("[3/7] Benchmarking Orchestrator -> MCP Server...")
    results["channel_3"] = await benchmark_orchestrator_to_mcp(100)
    
    print("[4/7] Benchmarking Agent <- MCP Server (Fetch)...")
    results["channel_4"] = await benchmark_agent_fetch_from_mcp(100)
    
    print("[5/7] Benchmarking Agent -> MCP Server (Publish)...")
    results["channel_5"] = await benchmark_agent_publish_to_mcp(100)
    
    print("[6/7] Benchmarking Agent <-> Agent (Shared Memory)...")
    results["channel_6"] = await benchmark_agent_to_agent_via_shared_memory(100)
    
    print("[7/7] Benchmarking Orchestrator <- MCP (Aggregation)...")
    results["channel_7"] = await benchmark_orchestrator_aggregation(10)
    
    # Print results table
    print_results_table(results)
    
    # Save to JSON
    results["measurement_type"] = "mixed"
    results["provenance"] = (
        "M-local seven-channel protocol benchmark with Model-QKD latency; "
        "security and scalability use their dedicated canonical artifacts"
    )
    results["canonical_related_artifacts"] = {
        "security": "security_results.json",
        "scalability": "scalability_results.json",
    }
    results["channel_metadata"] = CHANNEL_METADATA
    results["run_metadata"] = run_metadata()
    output_file = result_path("full_framework_results.json")
    with output_file.open("w") as f:
        json.dump(results, f, indent=2)
    
    print(f"Results saved to: {output_file}\n")


if __name__ == "__main__":
    asyncio.run(main())
