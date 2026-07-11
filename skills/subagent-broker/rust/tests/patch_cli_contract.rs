//! CLI-level patch invariants: terminal success is mandatory and new files are included.

#![cfg(unix)]
#![allow(clippy::unwrap_used, clippy::expect_used)]

use std::fs;
use std::os::unix::fs::PermissionsExt;
use std::process::Command;

use assert_cmd::cargo::CommandCargoExt;
use tempfile::tempdir;

fn init_repo(root: &std::path::Path) {
    fs::write(root.join("base.txt"), "base\n").unwrap();
    for args in [
        &["init", "-q"][..],
        &["config", "user.email", "test@example.invalid"][..],
        &["config", "user.name", "test"][..],
        &["add", "-A"][..],
        &["commit", "-q", "-m", "base"][..],
    ] {
        assert!(Command::new("git")
            .args(args)
            .current_dir(root)
            .status()
            .unwrap()
            .success());
    }
}

fn write_harness(path: &std::path::Path, terminal: &str) {
    fs::write(
        path,
        format!(
            "#!/bin/sh\nprintf 'new file\\n' > added.txt\nprintf '%s\\n' '{}'\n",
            terminal.replace('\'', "'\\''")
        ),
    )
    .unwrap();
    let mut permissions = fs::metadata(path).unwrap().permissions();
    permissions.set_mode(0o755);
    fs::set_permissions(path, permissions).unwrap();
}

fn run_packet(root: &std::path::Path, run_id: &str, harness: &std::path::Path) -> i32 {
    let packet = serde_json::json!({
        "schema_version": 3,
        "run_id": run_id,
        "agents": [{
            "id": "worker",
            "goal": "add a file",
            "harness": {
                "kind": "custom",
                "executable": harness,
                "stream_family": "claude_stream_json"
            },
            "mode": "patch_only",
            "capabilities": ["repo_read", "patch"],
            "allowed_paths": ["**"]
        }]
    });
    let tasks = root.join(format!("{run_id}.json"));
    fs::write(&tasks, serde_json::to_vec_pretty(&packet).unwrap()).unwrap();
    Command::cargo_bin("subagent-broker")
        .unwrap()
        .args([
            "run",
            tasks.to_str().unwrap(),
            "--cwd",
            root.to_str().unwrap(),
        ])
        .status()
        .unwrap()
        .code()
        .unwrap_or(-1)
}

#[test]
fn invalid_terminal_never_persists_patch() {
    let dir = tempdir().unwrap();
    init_repo(dir.path());
    let harness = dir.path().join("failed-harness.sh");
    write_harness(
        &harness,
        r#"{"type":"result","subtype":"error","is_error":true,"result":"failed"}"#,
    );
    assert_eq!(run_packet(dir.path(), "failed-patch", &harness), 1);
    let agent = dir.path().join(".subagents/failed-patch/worker");
    assert!(!agent.join("patch.diff").exists());
    assert!(!agent.join("patch.diff.sha256").exists());
}

#[test]
fn successful_new_file_patch_is_complete_and_checks() {
    let dir = tempdir().unwrap();
    init_repo(dir.path());
    let harness = dir.path().join("success-harness.sh");
    write_harness(
        &harness,
        r#"{"type":"result","subtype":"success","is_error":false,"result":"done"}"#,
    );
    let code = run_packet(dir.path(), "success-patch", &harness);
    let agent = dir.path().join(".subagents/success-patch/worker");
    assert_eq!(
        code,
        0,
        "{}",
        fs::read_to_string(agent.join("result.json")).unwrap_or_default()
    );
    let patch = agent.join("patch.diff");
    let bytes = fs::read(&patch).unwrap();
    assert!(String::from_utf8_lossy(&bytes).contains("added.txt"));
    assert!(Command::cargo_bin("subagent-broker")
        .unwrap()
        .args(["patch", "check", patch.to_str().unwrap()])
        .status()
        .unwrap()
        .success());
    assert!(Command::cargo_bin("subagent-broker")
        .unwrap()
        .args([
            "patch",
            "apply",
            patch.to_str().unwrap(),
            "--repo",
            dir.path().to_str().unwrap(),
        ])
        .status()
        .unwrap()
        .success());
    assert_eq!(
        fs::read_to_string(dir.path().join("added.txt")).unwrap(),
        "new file\n"
    );

    let result_path = agent.join("result.json");
    let original_result = fs::read(&result_path).unwrap();
    let mut result: serde_json::Value = serde_json::from_slice(&original_result).unwrap();
    result["patch"]["sha256"] = serde_json::json!("00");
    fs::write(&result_path, serde_json::to_vec_pretty(&result).unwrap()).unwrap();
    assert!(!Command::cargo_bin("subagent-broker")
        .unwrap()
        .args(["patch", "check", patch.to_str().unwrap()])
        .status()
        .unwrap()
        .success());
    fs::write(&result_path, original_result).unwrap();

    let manifest_path = agent.join("baseline_manifest.json");
    let original_manifest = fs::read(&manifest_path).unwrap();
    let mut manifest: serde_json::Value = serde_json::from_slice(&original_manifest).unwrap();
    manifest["source_visible_sha256"] = serde_json::json!("00");
    fs::write(
        &manifest_path,
        serde_json::to_vec_pretty(&manifest).unwrap(),
    )
    .unwrap();
    assert!(!Command::cargo_bin("subagent-broker")
        .unwrap()
        .args(["patch", "check", patch.to_str().unwrap()])
        .status()
        .unwrap()
        .success());
    fs::write(&manifest_path, original_manifest).unwrap();

    let bundle_path = agent.join("baseline.bundle");
    let mut bundle = fs::read(&bundle_path).unwrap();
    bundle.extend_from_slice(b"tamper");
    fs::write(&bundle_path, bundle).unwrap();
    assert!(!Command::cargo_bin("subagent-broker")
        .unwrap()
        .args(["patch", "check", patch.to_str().unwrap()])
        .status()
        .unwrap()
        .success());
}
