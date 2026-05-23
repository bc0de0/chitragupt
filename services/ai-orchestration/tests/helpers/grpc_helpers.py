"""Pre-built gRPC channels and stub factories for integration tests.

Provides:
  - state_machine_stub(): gRPC stub for the Rust state machine
  - orchestration_stub(): gRPC stub for the Python orchestration service

Addresses and credentials are read from environment variables (set by Docker Compose
test profile). Falls back to localhost defaults for local dev.

Usage:
    stub = state_machine_stub()
    resp = stub.CreateSession(CreateSessionRequest(...))
"""
from __future__ import annotations

import os


_STATE_MACHINE_ADDR = os.environ.get("STATE_MACHINE_ADDR", "localhost:50051")
_ORCHESTRATION_ADDR = os.environ.get("GRPC_PORT", "localhost:50052")


def state_machine_stub():
    """Return a gRPC stub for the Rust state machine service."""
    try:
        import grpc
        from ai_orchestration.grpc import state_machine_pb2_grpc as sm_grpc
    except ImportError as e:
        raise ImportError(
            f"gRPC stubs not available: {e}. "
            "Run `python -m grpc_tools.protoc` to regenerate from proto files."
        )

    channel = grpc.insecure_channel(_STATE_MACHINE_ADDR)
    return sm_grpc.StateMachineStub(channel)


def orchestration_stub():
    """Return a gRPC stub for the Python AI orchestration service."""
    try:
        import grpc
        from ai_orchestration.grpc import orchestration_pb2_grpc as orch_grpc
    except ImportError as e:
        raise ImportError(
            f"gRPC stubs not available: {e}. "
            "Run `python -m grpc_tools.protoc` to regenerate from proto files."
        )

    channel = grpc.insecure_channel(_ORCHESTRATION_ADDR)
    return orch_grpc.OrchestrationStub(channel)
