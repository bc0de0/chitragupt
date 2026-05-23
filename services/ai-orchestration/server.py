"""AI Orchestration gRPC server entry point.

Usage:
    python server.py

Environment variables:
    GRPC_PORT       — port to listen on (default: 50052)
    DATABASE_URL    — asyncpg connection string
    REDIS_URL       — Redis connection string (optional; disables budget persistence if absent)

Proto stubs must be generated before starting the server:
    bash scripts/generate_proto.sh
"""
from __future__ import annotations

import asyncio
import logging
import os
import signal
import sys
from concurrent import futures

logger = logging.getLogger(__name__)


async def serve() -> None:
    try:
        import grpc
        import grpc.aio as aio_grpc
    except ImportError:
        logger.error("grpcio not installed — run: pip install grpcio grpcio-tools")
        sys.exit(1)

    from src.ai_orchestration.config import OrchestrationConfig
    from src.ai_orchestration.db.pool import close_pool, init_pool
    from src.ai_orchestration.grpc.servicer import AiOrchestrationServicer

    # Load config
    config = OrchestrationConfig.default()

    # Database pool
    database_url = os.environ.get("DATABASE_URL")
    if database_url:
        await init_pool(dsn=database_url)
        logger.info("Database pool initialised")
    else:
        logger.warning("DATABASE_URL not set — RAG retrieval and ingestion will be unavailable")

    # Redis client
    redis = None
    redis_url = os.environ.get("REDIS_URL")
    if redis_url:
        try:
            import redis.asyncio as aioredis  # type: ignore[import]
            redis = aioredis.from_url(redis_url, decode_responses=True)
            logger.info("Redis client connected")
        except ImportError:
            logger.warning("redis[hiredis] not installed — budget persistence disabled")

    # Build servicer
    servicer = AiOrchestrationServicer(config=config, redis=redis)

    # Try to import generated stubs for server registration
    try:
        from src.ai_orchestration.grpc import ai_orchestration_pb2_grpc as pb2_grpc  # type: ignore[import]
        stubs_available = True
    except ImportError:
        logger.error(
            "Proto stubs not found — run scripts/generate_proto.sh before starting the server"
        )
        stubs_available = False

    port = int(os.environ.get("GRPC_PORT", "50052"))
    server = aio_grpc.server(futures.ThreadPoolExecutor(max_workers=10))

    if stubs_available:
        pb2_grpc.add_AiOrchestrationServicer_to_server(servicer, server)  # type: ignore[name-defined]

    server.add_insecure_port(f"[::]:{port}")
    await server.start()
    logger.info("AiOrchestration gRPC server listening on [::]:%d", port)

    # Graceful shutdown on SIGTERM / SIGINT
    loop = asyncio.get_running_loop()

    async def _shutdown() -> None:
        logger.info("Shutting down gRPC server...")
        await server.stop(grace=5.0)
        await close_pool()
        if redis:
            await redis.aclose()

    loop.add_signal_handler(signal.SIGTERM, lambda: asyncio.create_task(_shutdown()))
    loop.add_signal_handler(signal.SIGINT,  lambda: asyncio.create_task(_shutdown()))

    await server.wait_for_termination()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    )
    asyncio.run(serve())


if __name__ == "__main__":
    main()
