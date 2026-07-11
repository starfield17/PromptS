//! SIGINT and cancel lifecycle CLI tests.

#![cfg(feature = "dev-harness")]
#![allow(clippy::unwrap_used, clippy::expect_used)]
#![cfg(target_os = "linux")]

use std::fs;
use std::os::unix::process::ExitStatusExt;
use std::process::{Command, Stdio};
use std::time::Duration;

use assert_cmd::cargo::CommandCargoExt;
use nix::sys::signal::{kill, Signal};
use nix::unistd::Pid;
use tempfile::tempdir;

#[test]
fn sigint_during_fake_sleep_exits_130_and_persists_cancelled() {
    let dir = tempdir().unwrap();
    fs::write(dir.path().join("README.md"), "x").unwrap();
    let tasks = dir.path().join("tasks.json");
    fs::write(
        &tasks,
        r#"{
          "schema_version": 3,
          "run_id": "sigint-run",
          "agents": [{
            "id": "worker",
            "goal": "sleep",
            "harness": {
              "kind": "fake",
              "sleep_ms": 30000,
              "response_summary": "should not finish"
            },
            "mode": "read_only",
            "capabilities": ["repo_read"],
            "limits": {
              "timeout_ms": 60000,
              "idle_timeout_ms": 60000,
              "max_workspace_files": 1000,
              "max_workspace_bytes": 10485760
            }
          }]
        }"#,
    )
    .unwrap();

    let mut child = Command::cargo_bin("subagent-broker")
        .unwrap()
        .arg("run")
        .arg(&tasks)
        .arg("--cwd")
        .arg(dir.path())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .unwrap();

    std::thread::sleep(Duration::from_millis(500));
    let pid = child.id() as i32;
    kill(Pid::from_raw(pid), Signal::SIGINT).expect("send SIGINT");

    let status = wait_timeout(&mut child, Duration::from_secs(15)).expect("child should exit");
    let code = status.code();
    let result_path = dir.path().join(".subagents/sigint-run/result.json");
    for _ in 0..40 {
        if result_path.exists() {
            break;
        }
        std::thread::sleep(Duration::from_millis(50));
    }
    assert!(
        result_path.exists(),
        "result.json missing after SIGINT; exit={code:?} signal={:?}",
        status.signal()
    );
    let v: serde_json::Value =
        serde_json::from_str(&fs::read_to_string(&result_path).unwrap()).unwrap();
    assert_eq!(v["outcome"], "cancelled");
    assert!(v["agents"][0]["patch"].is_null());
    assert!(!dir
        .path()
        .join(".subagents/sigint-run/worker/patch.diff")
        .exists());
    assert_eq!(
        code,
        Some(130),
        "soft-cancel path must exit 130, got {code:?}"
    );
}

fn wait_timeout(
    child: &mut std::process::Child,
    dur: Duration,
) -> Result<std::process::ExitStatus, String> {
    let start = std::time::Instant::now();
    loop {
        match child.try_wait() {
            Ok(Some(st)) => return Ok(st),
            Ok(None) if start.elapsed() >= dur => {
                let _ = child.kill();
                let _ = child.wait();
                return Err("timeout waiting for child".into());
            }
            Ok(None) => std::thread::sleep(Duration::from_millis(20)),
            Err(e) => return Err(e.to_string()),
        }
    }
}
