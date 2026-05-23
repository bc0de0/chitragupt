use std::net::SocketAddr;

use anyhow::Context;
use tracing::info;

use chitragupt_state_machine::grpc::{StateEngineServer, StateEngineService};

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    tracing_subscriber::fmt()
        .with_env_filter(
            tracing_subscriber::EnvFilter::try_from_default_env()
                .unwrap_or_else(|_| tracing_subscriber::EnvFilter::new("info")),
        )
        .init();

    let addr: SocketAddr = std::env::var("GRPC_ADDR")
        .unwrap_or_else(|_| "[::]:50051".to_string())
        .parse()
        .context("invalid GRPC_ADDR")?;

    let service = StateEngineService::new();

    info!(%addr, "StateEngine gRPC server listening");

    tonic::transport::Server::builder()
        .add_service(StateEngineServer::new(service))
        .serve(addr)
        .await
        .context("gRPC server error")?;

    Ok(())
}
