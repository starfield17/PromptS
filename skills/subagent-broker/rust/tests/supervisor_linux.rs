//! Supervisor Linux blackbox tests — real subprocesses.

#![cfg(target_os = "linux")]
#![allow(clippy::unwrap_used, clippy::expect_used)]

use std::time::Duration;

use tempfile::tempdir;
use tokio::time::timeout;

use subagent_broker::environment::{build_environment, ensure_isolated_dirs};
use subagent_broker::harness::claude::ClaudeParser;
use subagent_broker::harness::StreamParser;
use subagent_broker::platform::pid_exists;
use subagent_broker::supervisor::run_external_harness;
use subagent_broker::task::{EnvironmentSpec, Limits};

fn limits_short() -> Limits {
    Limits {
        timeout_ms: 5_000,
        idle_timeout_ms: 2_000,
        term_grace_ms: 200,
        pipe_grace_ms: 300,
        max_result_bytes: 65_536,
        max_raw_log_bytes: 4_096,
        max_event_line_bytes: 1_048_576,
        max_workspace_files: 1000,
        max_workspace_bytes: 10_000_000,
        max_files_changed: 50,
    }
}

fn env_for(dir: &std::path::Path) -> subagent_broker::environment::PreparedEnvironment {
    let home = dir.join("home");
    ensure_isolated_dirs(&home).unwrap();
    build_environment(&EnvironmentSpec::default(), dir, &home)
}

fn write_script(path: &std::path::Path, body: &str) {
    std::fs::write(path, body).unwrap();
}

fn sh_argv(script: &std::path::Path) -> Vec<String> {
    // Invoke via /bin/sh to avoid ETXTBSY races on freshly written executables.
    vec!["/bin/sh".into(), script.display().to_string()]
}

#[tokio::test]
async fn slow_harness_waits_for_completion() {
    let dir = tempdir().unwrap();
    let script = dir.path().join("slow.sh");
    write_script(&script, "sleep 0.3\necho done\n");

    let limits = limits_short();
    let env = env_for(dir.path());
    let parser: Box<dyn StreamParser> = Box::new(ClaudeParser::new(1024, 1 << 20));
    let argv = sh_argv(&script);
    let start = std::time::Instant::now();
    let run = run_external_harness(&argv, dir.path(), &env, &limits, parser, None, None, None)
        .await
        .unwrap();
    assert!(start.elapsed() >= Duration::from_millis(250));
    assert_eq!(run.exit_code, Some(0));
}

#[tokio::test]
async fn leader_exit_child_holds_pipe_reaped_quickly() {
    let dir = tempdir().unwrap();
    let script = dir.path().join("hold_pipe.sh");
    write_script(
        &script,
        r#"( sleep 30 ) &
sleep 0.1
exit 0
"#,
    );

    let mut limits = limits_short();
    limits.timeout_ms = 30_000;
    limits.pipe_grace_ms = 200;
    limits.term_grace_ms = 200;
    let env = env_for(dir.path());
    let parser: Box<dyn StreamParser> = Box::new(ClaudeParser::new(1024, 1 << 20));
    let argv = sh_argv(&script);
    let start = std::time::Instant::now();
    let run = timeout(
        Duration::from_secs(5),
        run_external_harness(&argv, dir.path(), &env, &limits, parser, None, None, None),
    )
    .await
    .expect("should not hit total timeout wait")
    .unwrap();
    assert!(
        start.elapsed() < Duration::from_secs(4),
        "took too long: {:?}",
        start.elapsed()
    );
    assert!(run.exit_code.is_some());
}

#[tokio::test]
async fn child_ignores_term_then_kill() {
    let dir = tempdir().unwrap();
    let script = dir.path().join("ignore_term.sh");
    write_script(
        &script,
        r#"trap '' TERM
sleep 60
"#,
    );

    let mut limits = limits_short();
    limits.timeout_ms = 800;
    limits.term_grace_ms = 150;
    limits.idle_timeout_ms = 60_000;
    let env = env_for(dir.path());
    let parser: Box<dyn StreamParser> = Box::new(ClaudeParser::new(1024, 1 << 20));
    let argv = sh_argv(&script);
    let run = run_external_harness(&argv, dir.path(), &env, &limits, parser, None, None, None)
        .await
        .unwrap();
    assert!(run.timed_out || run.exit_code.is_some());
    let _ = pid_exists(0);
}

#[tokio::test]
async fn idle_timeout_fires() {
    let dir = tempdir().unwrap();
    let script = dir.path().join("idle.sh");
    write_script(&script, "sleep 30\n");
    let mut limits = limits_short();
    limits.idle_timeout_ms = 400;
    limits.timeout_ms = 30_000;
    limits.term_grace_ms = 100;
    let env = env_for(dir.path());
    let parser: Box<dyn StreamParser> = Box::new(ClaudeParser::new(1024, 1 << 20));
    let argv = sh_argv(&script);
    let run = run_external_harness(&argv, dir.path(), &env, &limits, parser, None, None, None)
        .await
        .unwrap();
    assert!(run.idle_timed_out, "expected idle timeout");
}

#[tokio::test]
async fn raw_log_truncated_still_gets_output() {
    let dir = tempdir().unwrap();
    let script = dir.path().join("verbose.sh");
    write_script(
        &script,
        r#"dd if=/dev/zero bs=1024 count=20 2>/dev/null | tr '\0' 'a'
echo
echo '{"type":"result","subtype":"success","is_error":false,"result":"FINAL_OK"}'
"#,
    );
    let mut limits = limits_short();
    limits.max_raw_log_bytes = 2048;
    limits.idle_timeout_ms = 10_000;
    let env = env_for(dir.path());
    let log = dir.path().join("stdout.log");
    let parser: Box<dyn StreamParser> = Box::new(ClaudeParser::new(65_536, 1 << 22));
    let argv = sh_argv(&script);
    let run = run_external_harness(
        &argv,
        dir.path(),
        &env,
        &limits,
        parser,
        Some(&log),
        None,
        None,
    )
    .await
    .unwrap();
    assert!(run.raw_stdout_truncated);
    assert!(run.stdout_total_bytes > limits.max_raw_log_bytes);
    let log_bytes = std::fs::metadata(&log).unwrap().len();
    assert!(log_bytes <= limits.max_raw_log_bytes + 64);
    assert!(run
        .events
        .iter()
        .any(|e| matches!(e, subagent_broker::event::HarnessEvent::FinalResult(_))));
}

#[tokio::test]
async fn continuous_stdout_avoids_idle_timeout() {
    let dir = tempdir().unwrap();
    let script = dir.path().join("stream.sh");
    write_script(
        &script,
        r#"i=0
while [ $i -lt 10 ]; do
  echo tick
  sleep 0.15
  i=$((i+1))
done
"#,
    );
    let mut limits = limits_short();
    limits.idle_timeout_ms = 500;
    limits.timeout_ms = 10_000;
    let env = env_for(dir.path());
    let parser: Box<dyn StreamParser> = Box::new(ClaudeParser::new(1024, 1 << 20));
    let argv = sh_argv(&script);
    let run = run_external_harness(&argv, dir.path(), &env, &limits, parser, None, None, None)
        .await
        .unwrap();
    assert!(!run.idle_timed_out, "idle should not fire while streaming");
    assert_eq!(run.exit_code, Some(0));
}

#[tokio::test]
async fn total_timeout_fires_and_reaps() {
    let dir = tempdir().unwrap();
    let script = dir.path().join("long.sh");
    write_script(&script, "sleep 30\n");
    let mut limits = limits_short();
    limits.timeout_ms = 400;
    limits.idle_timeout_ms = 60_000;
    limits.term_grace_ms = 100;
    let env = env_for(dir.path());
    let parser: Box<dyn StreamParser> = Box::new(ClaudeParser::new(1024, 1 << 20));
    let argv = sh_argv(&script);
    let run = run_external_harness(&argv, dir.path(), &env, &limits, parser, None, None, None)
        .await
        .unwrap();
    assert!(run.timed_out, "expected total timeout");
    if let Some(pid) = run.leader_pid {
        tokio::time::sleep(Duration::from_millis(100)).await;
        assert!(!pid_exists(pid), "leader should be reaped");
    }
}

struct FailingParser;

impl StreamParser for FailingParser {
    fn push(
        &mut self,
        _data: &[u8],
    ) -> Result<Vec<subagent_broker::event::HarnessEvent>, subagent_broker::error::StreamError>
    {
        Err(subagent_broker::error::StreamError::Invalid(
            "injected parser failure".into(),
        ))
    }
    fn finish(
        &mut self,
    ) -> Result<Vec<subagent_broker::event::HarnessEvent>, subagent_broker::error::StreamError>
    {
        Ok(Vec::new())
    }
}

#[tokio::test]
async fn parser_failure_terminates_process_group() {
    let dir = tempdir().unwrap();
    let script = dir.path().join("talk.sh");
    write_script(
        &script,
        r#"i=0
while [ $i -lt 100 ]; do
  echo line$i
  sleep 0.05
  i=$((i+1))
done
"#,
    );
    let mut limits = limits_short();
    limits.timeout_ms = 10_000;
    limits.idle_timeout_ms = 10_000;
    limits.term_grace_ms = 100;
    let env = env_for(dir.path());
    let parser: Box<dyn StreamParser> = Box::new(FailingParser);
    let argv = sh_argv(&script);
    let run = run_external_harness(&argv, dir.path(), &env, &limits, parser, None, None, None)
        .await
        .unwrap();
    assert!(run.stream_error);
    if let Some(pid) = run.leader_pid {
        tokio::time::sleep(Duration::from_millis(150)).await;
        assert!(
            !pid_exists(pid),
            "leader should be reaped after parser fail"
        );
    }
}
