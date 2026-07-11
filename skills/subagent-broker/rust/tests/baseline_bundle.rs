//! Baseline bundle for patch_only workspaces.

#![allow(clippy::unwrap_used, clippy::expect_used)]

use std::fs;
use std::process::Command;

use subagent_broker::task::Mode;
use subagent_broker::workspace::{
    create_agent_baseline_bundle, prepare_workspace, write_baseline_manifest,
};
use tempfile::tempdir;

#[test]
fn patch_only_writes_baseline_bundle_and_manifest_hash() {
    let dir = tempdir().unwrap();
    let src = dir.path().join("src");
    fs::create_dir_all(&src).unwrap();
    fs::write(src.join("a.txt"), "hi\n").unwrap();
    Command::new("git")
        .args(["init", "-q"])
        .current_dir(&src)
        .status()
        .unwrap();
    Command::new("git")
        .args(["config", "user.email", "t@t"])
        .current_dir(&src)
        .status()
        .unwrap();
    Command::new("git")
        .args(["config", "user.name", "t"])
        .current_dir(&src)
        .status()
        .unwrap();
    Command::new("git")
        .args(["add", "-A"])
        .current_dir(&src)
        .status()
        .unwrap();
    Command::new("git")
        .args(["commit", "-q", "-m", "i"])
        .current_dir(&src)
        .status()
        .unwrap();

    let agent = dir.path().join("agent");
    fs::create_dir_all(&agent).unwrap();
    let mut ws = prepare_workspace(
        &src,
        &agent.join("workspace"),
        Mode::PatchOnly,
        1000,
        10_000_000,
    )
    .unwrap();
    create_agent_baseline_bundle(&mut ws, &agent).unwrap();
    write_baseline_manifest(&agent, &ws).unwrap();

    assert!(agent.join("baseline.bundle").is_file());
    assert!(ws.baseline_bundle_sha256.is_some());
    let manifest: serde_json::Value =
        serde_json::from_str(&fs::read_to_string(agent.join("baseline_manifest.json")).unwrap())
            .unwrap();
    assert_eq!(
        manifest["baseline_bundle_sha256"].as_str(),
        ws.baseline_bundle_sha256.as_deref()
    );
    assert_eq!(manifest["baseline_bundle"], "baseline.bundle");
}
