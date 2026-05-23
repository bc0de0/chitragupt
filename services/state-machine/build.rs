use std::path::PathBuf;

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let proto_dir = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("proto");

    tonic_build::configure()
        .build_server(true)
        .build_client(false) // clients live in Go and Python
        .compile(
            &[
                proto_dir.join("state_engine.proto"),
                proto_dir.join("common.proto"),
            ],
            &[&proto_dir],
        )?;

    // Re-run build script when any proto file changes.
    println!("cargo:rerun-if-changed=proto/state_engine.proto");
    println!("cargo:rerun-if-changed=proto/common.proto");

    Ok(())
}
