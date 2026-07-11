//! Real harness smoke tests. Enable with SUBAGENT_REAL=1.
//!
//! Uses `environment.home=host` so local OAuth/config credentials work.
//! Values are never recorded by the broker.

#![allow(clippy::unwrap_used, clippy::expect_used, clippy::panic)]

use std::fs;
use std::path::PathBuf;
use std::process::Command;
use std::time::Duration;

use assert_cmd::cargo::CommandCargoExt;
use tempfile::tempdir;

fn real_enabled() -> bool {
    matches!(
        std::env::var("SUBAGENT_REAL").as_deref(),
        Ok("1") | Ok("true") | Ok("yes")
    )
}

fn which(name: &str) -> bool {
    Command::new("which")
        .arg(name)
        .output()
        .map(|o| o.status.success())
        .unwrap_or(false)
}

fn run_packet(harness_kind: &str, run_id: &str, goal: &str) -> (i32, serde_json::Value, PathBuf) {
    let dir = tempdir().unwrap();
    fs::write(dir.path().join("README.md"), "real harness smoke fixture\n").unwrap();
    Command::new("git")
        .args(["init", "-q"])
        .current_dir(dir.path())
        .status()
        .unwrap();
    Command::new("git")
        .args(["config", "user.email", "real@example.invalid"])
        .current_dir(dir.path())
        .status()
        .unwrap();
    Command::new("git")
        .args(["config", "user.name", "real-harness"])
        .current_dir(dir.path())
        .status()
        .unwrap();
    Command::new("git")
        .args(["add", "README.md"])
        .current_dir(dir.path())
        .status()
        .unwrap();
    Command::new("git")
        .args(["commit", "-q", "-m", "fixture"])
        .current_dir(dir.path())
        .status()
        .unwrap();
    let tasks = dir.path().join("tasks.json");
    let body = format!(
        r#"{{
          "schema_version": 3,
          "run_id": "{run_id}",
          "agents": [{{
            "id": "worker",
            "goal": {goal},
            "harness": {{ "kind": "{harness_kind}" }},
            "mode": "read_only",
            "requested_permissions": ["repo_read"],
            "environment": {{
              "home": "host",
              "allowed_env": [
                "ANTHROPIC_API_KEY",
                "ANTHROPIC_AUTH_TOKEN",
                "OPENAI_API_KEY",
                "OPENAI_BASE_URL",
                "XAI_API_KEY",
                "GROK_API_KEY",
                "CODEX_API_KEY"
              ]
            }},
            "limits": {{
              "timeout_ms": 180000,
              "idle_timeout_ms": 120000,
              "term_grace_ms": 2000,
              "pipe_grace_ms": 2000,
              "max_result_bytes": 262144,
              "max_raw_log_bytes": 1048576,
              "max_workspace_files": 5000,
              "max_workspace_bytes": 104857600
            }}
          }}]
        }}"#,
        goal = serde_json::to_string(goal).unwrap(),
    );
    fs::write(&tasks, body).unwrap();

    let output = Command::cargo_bin("subagent-broker")
        .unwrap()
        .arg("run")
        .arg(&tasks)
        .arg("--cwd")
        .arg(dir.path())
        .output()
        .unwrap();

    let code = output.status.code().unwrap_or(-1);
    let result_path = dir.path().join(format!(".subagents/{run_id}/result.json"));
    let stdout = String::from_utf8_lossy(&output.stdout);
    let stderr = String::from_utf8_lossy(&output.stderr);
    assert!(
        result_path.exists(),
        "missing result.json for {harness_kind}\nstdout={stdout}\nstderr={stderr}"
    );
    let v: serde_json::Value =
        serde_json::from_str(&fs::read_to_string(&result_path).unwrap()).unwrap();

    // Copy logs for diagnosis under /tmp when failing success
    if v["outcome"] != "success" {
        let log_dir = format!("/tmp/broker_real_{run_id}");
        let _ = fs::create_dir_all(&log_dir);
        let agent = dir.path().join(format!(".subagents/{run_id}/worker"));
        let _ = fs::copy(agent.join("stdout.log"), format!("{log_dir}/stdout.log"));
        let _ = fs::copy(agent.join("stderr.log"), format!("{log_dir}/stderr.log"));
        let _ = fs::copy(&result_path, format!("{log_dir}/result.json"));
    }

    let _ = dir;
    (code, v, result_path)
}

fn assert_broker_plumbing(v: &serde_json::Value) {
    assert_eq!(v["schema_version"], 3);
    assert!(v["agents"][0]["executable"].is_object());
    assert!(v["agents"][0]["patch"].is_null());
    assert!(v["agents"][0]["diagnostics"]["exit_code"].is_number());
    assert!(v["revision"].as_u64().unwrap_or(0) >= 1);
}

#[test]
fn doctor_lists_stock_harnesses() {
    let out = Command::cargo_bin("subagent-broker")
        .unwrap()
        .arg("doctor")
        .output()
        .unwrap();
    assert!(out.status.success());
    let s = String::from_utf8_lossy(&out.stdout);
    assert!(s.contains("claude"));
    assert!(s.contains("grok"));
    assert!(s.contains("codex"));
    println!("{s}");
}

#[test]
#[ignore = "requires SUBAGENT_REAL=1 and a logged-in Claude installation"]
fn real_claude_read_only_smoke() {
    if !real_enabled() {
        eprintln!("skip real_claude (set SUBAGENT_REAL=1)");
        return;
    }
    assert!(which("claude"), "claude not on PATH");
    let (code, v, _) = run_packet(
        "claude_code",
        "real-claude",
        "Reply with exactly the single word: pong. Do not use tools. Do not modify files.",
    );
    println!(
        "claude exit={code} outcome={} reason={} summary={}",
        v["outcome"],
        v["agents"][0]["reason"],
        v["agents"][0]["response"]["summary"]
            .as_str()
            .unwrap_or("")
            .chars()
            .take(200)
            .collect::<String>()
    );
    assert_broker_plumbing(&v);
    // Auth failures are environmental; broker must still produce structured terminal state.
    assert!(matches!(
        v["outcome"].as_str(),
        Some("success") | Some("failed") | Some("blocked") | Some("cancelled")
    ));
}

#[test]
#[ignore = "requires SUBAGENT_REAL=1 and a logged-in Grok installation"]
fn real_grok_read_only_smoke() {
    if !real_enabled() {
        eprintln!("skip real_grok (set SUBAGENT_REAL=1)");
        return;
    }
    assert!(which("grok"), "grok not on PATH");
    let (code, v, _) = run_packet(
        "grok_build",
        "real-grok",
        "Reply with exactly the single word: pong. Do not use tools. Do not modify files.",
    );
    println!(
        "grok exit={code} outcome={} reason={} summary={}",
        v["outcome"],
        v["agents"][0]["reason"],
        v["agents"][0]["response"]["summary"]
            .as_str()
            .unwrap_or("")
            .chars()
            .take(200)
            .collect::<String>()
    );
    assert_broker_plumbing(&v);
    assert!(matches!(
        v["outcome"].as_str(),
        Some("success") | Some("failed") | Some("blocked") | Some("cancelled")
    ));
}

#[test]
#[ignore = "requires SUBAGENT_REAL=1 and a logged-in Codex installation"]
fn real_codex_read_only_smoke() {
    if !real_enabled() {
        eprintln!("skip real_codex (set SUBAGENT_REAL=1)");
        return;
    }
    assert!(which("codex"), "codex not on PATH");
    let (code, v, _) = run_packet(
        "codex_cli",
        "real-codex",
        "Reply with exactly the single word: pong. Do not use tools. Do not modify files.",
    );
    println!(
        "codex exit={code} outcome={} reason={} summary={}",
        v["outcome"],
        v["agents"][0]["reason"],
        v["agents"][0]["response"]["summary"]
            .as_str()
            .unwrap_or("")
            .chars()
            .take(200)
            .collect::<String>()
    );
    assert_broker_plumbing(&v);
}

#[test]
#[ignore = "requires SUBAGENT_REAL=1 and a logged-in OpenCode installation"]
fn real_opencode_limited_smoke() {
    if !real_enabled() {
        eprintln!("skip real_opencode (set SUBAGENT_REAL=1)");
        return;
    }
    assert!(which("opencode"), "opencode not on PATH");
    let (code, v, _) = run_packet(
        "opencode",
        "real-opencode",
        "Reply with exactly the single word: pong.",
    );
    println!(
        "opencode exit={code} outcome={} reason={} summary={}",
        v["outcome"],
        v["agents"][0]["reason"],
        v["agents"][0]["response"]["summary"]
            .as_str()
            .unwrap_or("")
            .chars()
            .take(200)
            .collect::<String>()
    );
    assert_broker_plumbing(&v);
}

#[allow(dead_code)]
fn _dur() -> Duration {
    Duration::from_secs(1)
}
