pub mod service;

// Re-export the generated proto modules so callers can use chitragupt_state_machine::grpc::proto::*.
pub mod proto {
    pub mod state {
        tonic::include_proto!("chitragupt.state");
    }
    pub mod common {
        tonic::include_proto!("chitragupt.common");
    }
}

pub use service::StateEngineService;
pub use proto::state::state_engine_server::StateEngineServer;
