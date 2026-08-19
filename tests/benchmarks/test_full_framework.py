# Copyright © 2026 PricewaterhouseCoopers LLP (PwC US).
# This file is the property of PwC US. Licensed under the MIT License.

"""
Quick test to verify benchmark_full_framework.py components work correctly.
"""
import asyncio
import sys
from pathlib import Path

import pytest

# Add project root and benchmark directory to the path.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(Path(__file__).parent))

from benchmark_full_framework import (
    MCP_Server_Simulator,
    Shared_Memory_Simulator,
    User,
    encrypt_with_qkd,
    decrypt_with_qkd
)


def test_mcp_server():
    """Test MCP Server Simulator."""
    print("Testing MCP_Server_Simulator...")
    mcp = MCP_Server_Simulator()
    
    # Test task graph publishing
    task_graph = {
        "payload": {
            "graph_id": "test_123",
            "tasks": [
                {"agent_id": "agent_1", "task": "search"},
                {"agent_id": "agent_2", "task": "analyze"}
            ]
        }
    }
    mcp.publish_task_graph(task_graph)
    
    # Test task retrieval
    task = mcp.get_agent_task("agent_1")
    assert task["task"] == "search", "Task retrieval failed"
    
    # Test result submission
    result = {
        "agent_id": "agent_1",
        "payload": {"result": "completed"}
    }
    mcp.submit_agent_result(result)
    
    # Test result retrieval
    all_results = mcp.get_all_results()
    assert len(all_results) == 1, "Result retrieval failed"
    
    print("✓ MCP_Server_Simulator tests passed")


def test_shared_memory():
    """Test Shared Memory Simulator."""
    print("Testing Shared_Memory_Simulator...")
    shared_mem = Shared_Memory_Simulator()
    
    # Test write
    data = {"payload": {"message": "test"}}
    shared_mem.write("key_1", data)
    
    # Test read
    read_data = shared_mem.read("key_1")
    assert read_data["payload"]["message"] == "test", "Shared memory read/write failed"
    
    # Test non-existent key
    empty = shared_mem.read("non_existent")
    assert empty == {}, "Non-existent key should return empty dict"
    
    print("✓ Shared_Memory_Simulator tests passed")


def test_user():
    """Test User component."""
    print("Testing User component...")
    user = User()
    
    # Test identity
    assert user.identity is not None, "User identity not initialized"
    assert user.message_handler is not None, "User message handler not initialized"
    assert user.qrng is not None, "User QRNG not initialized"
    
    # Test message signing
    message = {"query": "test query"}
    signed = user.message_handler.sign_message(message)
    assert "payload" in signed, "Signed message missing payload"
    assert "signature" in signed, "Signed message missing signature"
    
    # Test nonce generation
    nonce = user.qrng.generate_nonce()
    assert len(nonce) > 0, "Nonce generation failed"
    
    print("✓ User component tests passed")


def test_encryption():
    """Test QKD encryption/decryption."""
    print("Testing QKD encryption/decryption...")
    
    import secrets
    key = secrets.token_bytes(32)
    plaintext = b"This is a test message for encryption"
    
    # Test encryption
    encrypted = encrypt_with_qkd(plaintext, key)
    assert encrypted != plaintext, "Encryption failed"
    assert len(encrypted) > len(plaintext), "Encrypted data should be larger (includes IV)"
    
    # Test decryption
    decrypted = decrypt_with_qkd(encrypted, key)
    assert decrypted == plaintext, "Decryption failed"
    
    print("✓ QKD encryption/decryption tests passed")


@pytest.mark.asyncio
async def test_integration():
    """Test basic integration flow."""
    print("Testing basic integration flow...")
    
    from src.pqc_agents.orchestrator_agent import OrchestratorAgent
    from src.pqc_agents.secure_search_agent import SecureSearchAgent
    
    # Create components
    orchestrator = OrchestratorAgent("test_orch")
    agent = SecureSearchAgent("test_agent")
    mcp = MCP_Server_Simulator()
    
    # Register agent
    orchestrator.register_worker(agent.agent_id, agent.get_public_key())
    
    # Test handshake
    handshake_result = await orchestrator.perform_handshake(agent)
    assert handshake_result is True, "Handshake failed"
    
    # Test message flow
    task = {"task_id": "task_1", "query": "test"}
    signed_task = orchestrator.message_handler.sign_message(task)
    
    # Verify by agent
    verified = agent.message_handler.verify_message(
        signed_task,
        orchestrator.identity.get_public_key()
    )
    assert verified is True, "Message verification failed"
    
    print("✓ Integration tests passed")


def main():
    """Run all tests."""
    print("="*60)
    print("FULL FRAMEWORK BENCHMARK - COMPONENT TESTS")
    print("="*60)
    print()
    
    try:
        test_mcp_server()
        test_shared_memory()
        test_user()
        test_encryption()
        asyncio.run(test_integration())
        
        print()
        print("="*60)
        print("ALL TESTS PASSED ✓")
        print("="*60)
        print()
        print("You can now run the full benchmark:")
        print("  python tests/benchmarks/benchmark_full_framework.py")
        print()
        
    except Exception as e:
        print()
        print("="*60)
        print(f"TEST FAILED: {e}")
        print("="*60)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
