#!/usr/bin/env bash
# generate_proto.sh — Generate gRPC stubs for all three languages.
#
# Prerequisites:
#   protoc           (brew install protobuf  /  apt install protobuf-compiler)
#   protoc-gen-go    (go install google.golang.org/protobuf/cmd/protoc-gen-go@latest)
#   protoc-gen-go-grpc (go install google.golang.org/grpc/cmd/protoc-gen-go-grpc@latest)
#   grpcio-tools     (pip install grpcio-tools)
#
# Run from the repo root:
#   bash scripts/generate_proto.sh

set -euo pipefail

PROTO_DIR="services/state-machine/proto"
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "▶ Generating Python stubs..."
PYTHON_OUT="services/ai-orchestration/src/ai_orchestration/grpc"
mkdir -p "$PYTHON_OUT"
python -m grpc_tools.protoc \
  -I "$PROTO_DIR" \
  --python_out="$PYTHON_OUT" \
  --grpc_python_out="$PYTHON_OUT" \
  "$PROTO_DIR/common.proto" \
  "$PROTO_DIR/ai_orchestration.proto"

# Fix relative imports produced by grpc_tools (needed for Python package layout).
for f in "$PYTHON_OUT"/*_pb2*.py; do
  sed -i 's/^import common_pb2/from . import common_pb2/' "$f" 2>/dev/null || true
  sed -i 's/^import ai_orchestration_pb2/from . import ai_orchestration_pb2/' "$f" 2>/dev/null || true
done
echo "  Python stubs written to $PYTHON_OUT"

echo "▶ Generating Go stubs..."
GO_OUT="services/api-gateway/proto"
mkdir -p "$GO_OUT/state" "$GO_OUT/common" "$GO_OUT/orchestration"

protoc \
  -I "$PROTO_DIR" \
  --go_out="$GO_OUT/common"        --go_opt=paths=source_relative \
  --go-grpc_out="$GO_OUT/common"   --go-grpc_opt=paths=source_relative \
  "$PROTO_DIR/common.proto"

protoc \
  -I "$PROTO_DIR" \
  --go_out="$GO_OUT/state"         --go_opt=paths=source_relative \
  --go-grpc_out="$GO_OUT/state"    --go-grpc_opt=paths=source_relative \
  "$PROTO_DIR/state_engine.proto"  \
  "$PROTO_DIR/common.proto"

protoc \
  -I "$PROTO_DIR" \
  --go_out="$GO_OUT/orchestration"       --go_opt=paths=source_relative \
  --go-grpc_out="$GO_OUT/orchestration"  --go-grpc_opt=paths=source_relative \
  "$PROTO_DIR/ai_orchestration.proto"    \
  "$PROTO_DIR/common.proto"

echo "  Go stubs written to $GO_OUT"

echo "✓ Proto generation complete."
echo "  Remember to run: cd services/api-gateway && go mod tidy"
