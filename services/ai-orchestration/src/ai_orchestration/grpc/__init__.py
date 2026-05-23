"""gRPC servicer and server entry point for the AI Orchestration service.

Generated proto stubs are produced by scripts/generate_proto.sh:
  python -m grpc_tools.protoc \\
    -I ../../services/state-machine/proto \\
    --python_out=. --grpc_python_out=. \\
    ../../services/state-machine/proto/ai_orchestration.proto \\
    ../../services/state-machine/proto/common.proto

The generated *_pb2.py and *_pb2_grpc.py files are committed to this package.
"""
