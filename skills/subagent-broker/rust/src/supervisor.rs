//! Process supervisor: spawn, drain, timeout, TERM/KILL/reap.

use std::path::Path;
use std::process::Stdio;
use std::time::Duration;

use nix::sys::signal::Signal;
use tokio::io::{AsyncReadExt, AsyncWriteExt};
use tokio::process::Command;
use tokio::time::Instant;

use crate::environment::{apply_to_command, PreparedEnvironment};
use crate::error::{BrokerResult, SpawnError};
use crate::event::{HarnessEvent, StateEvent};
use crate::harness::{ParserDiagnostics, StreamParser};
use crate::platform::{self, configure_command, kill_process_group, pgid_alive, pid_exists};
use crate::task::Limits;

#[derive(Debug)]
pub struct SupervisedRun {
    pub exit_code: Option<i32>,
    pub exit_signal: Option<i32>,
    pub descendants_terminated: bool,
    pub stdout_total_bytes: u64,
    pub stderr_total_bytes: u64,
    pub stdout_persisted_bytes: u64,
    pub stderr_persisted_bytes: u64,
    pub raw_stdout_truncated: bool,
    pub raw_stderr_truncated: bool,
    pub timed_out: bool,
    pub idle_timed_out: bool,
    pub cancelled: bool,
    pub stream_error: bool,
    pub leader_pid: Option<u32>,
    pub events: Vec<HarnessEvent>,
    pub parser_diagnostics: ParserDiagnostics,
    pub events_dropped: u64,
}

/// RAII guard: best-effort kill if not reaped.
pub struct ChildGuard {
    pgid: Option<i32>,
    reaped: bool,
}

pub type OwnerEventSink = (
    tokio::sync::mpsc::Sender<crate::state_owner::OwnerMsg>,
    String,
);

impl ChildGuard {
    pub fn new(pgid: i32) -> Self {
        Self {
            pgid: Some(pgid),
            reaped: false,
        }
    }

    pub fn mark_reaped(&mut self) {
        self.reaped = true;
    }

    pub fn pgid(&self) -> Option<i32> {
        self.pgid
    }
}

impl Drop for ChildGuard {
    fn drop(&mut self) {
        if self.reaped {
            return;
        }
        if let Some(pgid) = self.pgid {
            let _ = kill_process_group(pgid, Signal::SIGKILL);
        }
    }
}

/// Run an external harness with full lifecycle management (argv array, never shell).
#[allow(clippy::too_many_arguments)]
pub async fn run_external_harness(
    argv: &[String],
    work_dir: &Path,
    env: &PreparedEnvironment,
    limits: &Limits,
    parser: Box<dyn StreamParser>,
    stdout_log: Option<&Path>,
    stderr_log: Option<&Path>,
    mut cancel: Option<tokio::sync::watch::Receiver<bool>>,
) -> BrokerResult<SupervisedRun> {
    run_external_harness_with_sink(
        argv,
        work_dir,
        env,
        limits,
        parser,
        stdout_log,
        stderr_log,
        cancel.take(),
        None,
    )
    .await
}

#[allow(clippy::too_many_arguments)]
pub async fn run_external_harness_with_sink(
    argv: &[String],
    work_dir: &Path,
    env: &PreparedEnvironment,
    limits: &Limits,
    parser: Box<dyn StreamParser>,
    stdout_log: Option<&Path>,
    stderr_log: Option<&Path>,
    cancel: Option<tokio::sync::watch::Receiver<bool>>,
    event_sink: Option<OwnerEventSink>,
) -> BrokerResult<SupervisedRun> {
    run_external_harness_with_sink_budget(
        argv, work_dir, env, limits, parser, stdout_log, stderr_log, cancel, event_sink, 4096,
    )
    .await
}

#[allow(clippy::too_many_arguments)]
pub async fn run_external_harness_with_sink_budget(
    argv: &[String],
    work_dir: &Path,
    env: &PreparedEnvironment,
    limits: &Limits,
    mut parser: Box<dyn StreamParser>,
    stdout_log: Option<&Path>,
    stderr_log: Option<&Path>,
    mut cancel: Option<tokio::sync::watch::Receiver<bool>>,
    event_sink: Option<OwnerEventSink>,
    max_normalized_events: usize,
) -> BrokerResult<SupervisedRun> {
    if !platform::platform_supported() {
        return Err(crate::error::BrokerError::UnsupportedPlatform);
    }
    if argv.is_empty() {
        return Err(SpawnError::Failed("empty argv".into()).into());
    }

    let mut cmd = Command::new(&argv[0]);
    if argv.len() > 1 {
        cmd.args(&argv[1..]);
    }
    cmd.current_dir(work_dir)
        .stdin(Stdio::null())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .kill_on_drop(true);
    apply_to_command(&mut cmd, env);
    configure_command(&mut cmd)?;

    let mut child = cmd.spawn().map_err(|e| {
        if e.kind() == std::io::ErrorKind::NotFound {
            SpawnError::NotFound(argv[0].clone())
        } else {
            SpawnError::Failed(e.to_string())
        }
    })?;

    let pid = child.id().unwrap_or(0);
    let pgid = pid as i32;
    let mut guard = ChildGuard::new(pgid);

    let mut stdout = child
        .stdout
        .take()
        .ok_or_else(|| SpawnError::Failed("missing stdout".into()))?;
    let mut stderr = child
        .stderr
        .take()
        .ok_or_else(|| SpawnError::Failed("missing stderr".into()))?;

    let mut stdout_file = match stdout_log {
        Some(p) => {
            crate::persistence::refuse_symlink(p)?;
            Some(tokio::fs::File::create(p).await.map_err(|e| {
                crate::error::PersistenceError::Io(format!("create {}: {e}", p.display()))
            })?)
        }
        None => None,
    };
    let mut stderr_file = match stderr_log {
        Some(p) => {
            crate::persistence::refuse_symlink(p)?;
            Some(tokio::fs::File::create(p).await.map_err(|e| {
                crate::error::PersistenceError::Io(format!("create {}: {e}", p.display()))
            })?)
        }
        None => None,
    };

    let max_raw = limits.max_raw_log_bytes;
    let pipe_grace = Duration::from_millis(limits.pipe_grace_ms.max(1));
    let term_grace = Duration::from_millis(limits.term_grace_ms.max(1));
    let total_deadline = Instant::now() + Duration::from_millis(limits.timeout_ms.max(1));
    let idle_dur = Duration::from_millis(limits.idle_timeout_ms.max(1));

    let mut stdout_total: u64 = 0;
    let mut stderr_total: u64 = 0;
    let mut stdout_persisted: u64 = 0;
    let mut stderr_persisted: u64 = 0;
    let mut raw_stdout_truncated = false;
    let mut raw_stderr_truncated = false;
    let mut events: Vec<HarnessEvent> = Vec::new();
    let mut events_dropped: u64 = 0;
    let mut out_buf = vec![0u8; 8192];
    let mut err_buf = vec![0u8; 8192];
    let mut stdout_done = false;
    let mut stderr_done = false;
    let mut child_done = false;
    let mut exit_code = None;
    let mut exit_signal = None;
    let mut descendants_terminated = false;
    let mut timed_out = false;
    let mut idle_timed_out = false;
    let mut cancelled = false;
    let mut stream_error = false;
    let mut last_activity = Instant::now();
    let mut shutting_down = false;
    let mut kill_phase = 0u8;
    let mut term_deadline: Option<Instant> = None;
    let mut pipe_deadline: Option<Instant> = None;

    loop {
        if child_done && stdout_done && stderr_done {
            break;
        }

        let now = Instant::now();

        if let Some(ref mut rx) = cancel {
            if *rx.borrow() {
                cancelled = true;
                shutting_down = true;
            }
        }

        if !shutting_down && now >= total_deadline {
            timed_out = true;
            shutting_down = true;
        }

        if !shutting_down && !child_done && last_activity.elapsed() >= idle_dur {
            idle_timed_out = true;
            shutting_down = true;
        }

        if stream_error {
            shutting_down = true;
        }

        if shutting_down && !child_done {
            if kill_phase == 0 {
                let _ = kill_process_group(pgid, Signal::SIGTERM);
                kill_phase = 1;
                term_deadline = Some(now + term_grace);
            } else if kill_phase == 1 && term_deadline.is_some_and(|d| now >= d) {
                let _ = kill_process_group(pgid, Signal::SIGKILL);
                kill_phase = 2;
                descendants_terminated = true;
            }
        }

        if child_done && pipe_deadline.is_none() {
            pipe_deadline = Some(now + pipe_grace);
        }
        if let Some(pd) = pipe_deadline {
            if now >= pd && (!stdout_done || !stderr_done) {
                if pgid_alive(pgid) {
                    let _ = kill_process_group(pgid, Signal::SIGTERM);
                    tokio::time::sleep(term_grace).await;
                    if pgid_alive(pgid) {
                        let _ = kill_process_group(pgid, Signal::SIGKILL);
                        descendants_terminated = true;
                    }
                }
                break;
            }
        }

        let idle_left = idle_dur.saturating_sub(last_activity.elapsed());
        let total_left = total_deadline.saturating_duration_since(now);
        let wait_slice = Duration::from_millis(50)
            .min(idle_left)
            .min(total_left)
            .max(Duration::from_millis(1));

        tokio::select! {
            biased;
            status = child.wait(), if !child_done => {
                child_done = true;
                match status {
                    Ok(st) => {
                        exit_code = st.code();
                        #[cfg(unix)]
                        {
                            use std::os::unix::process::ExitStatusExt;
                            exit_signal = st.signal();
                        }
                    }
                    Err(_) => {
                        exit_code = None;
                    }
                }
                if let Some((ref tx, ref agent_id)) = event_sink {
                    crate::state_owner::StateOwner::send_critical(
                        tx,
                        crate::state_owner::OwnerMsg::Event {
                            agent_id: agent_id.clone(),
                            event: StateEvent::ProcessExited { code: exit_code, signal: exit_signal },
                        },
                    ).await;
                }
                guard.mark_reaped();
            }
            n = stdout.read(&mut out_buf), if !stdout_done => {
                match n {
                    Ok(0) => stdout_done = true,
                    Ok(n) => {
                        last_activity = Instant::now();
                        stdout_total += n as u64;
                        let chunk = &out_buf[..n];
                        match parser.push(chunk) {
                            Ok(evs) => {
                                forward_events(event_sink.as_ref(), &evs).await;
                                record_events(
                                    &mut events,
                                    evs,
                                    limits.max_result_bytes as usize,
                                    max_normalized_events,
                                    &mut events_dropped,
                                );
                            }
                            Err(_) => {
                                stream_error = true;
                                shutting_down = true;
                                stdout_done = true;
                            }
                        }
                        if let Some((ref tx, ref agent_id)) = event_sink {
                            crate::state_owner::StateOwner::try_send_activity(tx, agent_id);
                        }
                        if let Some(ref mut f) = stdout_file {
                            if stdout_persisted == 0 {
                                let marker = b"[stdout content redacted; normalized output is in result.json]\n";
                                let take = marker.len().min(max_raw as usize);
                                if f.write_all(&marker[..take]).await.is_err() {
                                    stream_error = true;
                                }
                                stdout_persisted = take as u64;
                            }
                            if stdout_total > max_raw && !raw_stdout_truncated {
                                let marker = b"[raw log budget exceeded]\n";
                                if f.write_all(marker).await.is_err() {
                                    stream_error = true;
                                } else {
                                    stdout_persisted = stdout_persisted
                                        .saturating_add(marker.len() as u64);
                                }
                                raw_stdout_truncated = true;
                            }
                        }
                    }
                    Err(_) => {
                        stream_error = true;
                        shutting_down = true;
                        stdout_done = true;
                    }
                }
            }
            n = stderr.read(&mut err_buf), if !stderr_done => {
                match n {
                    Ok(0) => stderr_done = true,
                    Ok(n) => {
                        last_activity = Instant::now();
                        stderr_total += n as u64;
                        if let Some(ref mut f) = stderr_file {
                            if stderr_persisted == 0 {
                                let marker = b"[stderr content redacted; byte counts are in result.json]\n";
                                let take = marker.len().min(max_raw as usize);
                                if f.write_all(&marker[..take]).await.is_err() {
                                    stream_error = true;
                                }
                                stderr_persisted = take as u64;
                            }
                            if stderr_total > max_raw && !raw_stderr_truncated {
                                let marker = b"[raw log budget exceeded]\n";
                                if f.write_all(marker).await.is_err() {
                                    stream_error = true;
                                } else {
                                    stderr_persisted = stderr_persisted
                                        .saturating_add(marker.len() as u64);
                                }
                                raw_stderr_truncated = true;
                            }
                        }
                    }
                    Err(_) => stderr_done = true,
                }
            }
            _ = tokio::time::sleep(wait_slice) => {}
        }
    }

    if !guard.reaped {
        let _ = kill_process_group(pgid, Signal::SIGKILL);
        match child.wait().await {
            Ok(st) => {
                exit_code = st.code();
                #[cfg(unix)]
                {
                    use std::os::unix::process::ExitStatusExt;
                    exit_signal = st.signal();
                }
                guard.mark_reaped();
            }
            Err(error) => {
                return Err(SpawnError::Failed(format!("wait after SIGKILL: {error}")).into())
            }
        }
        descendants_terminated = true;
    } else if pgid_alive(pgid) {
        let _ = kill_process_group(pgid, Signal::SIGTERM);
        tokio::time::sleep(term_grace).await;
        if pgid_alive(pgid) {
            let _ = kill_process_group(pgid, Signal::SIGKILL);
        }
        descendants_terminated = true;
    }

    match parser.finish() {
        Ok(evs) => {
            forward_events(event_sink.as_ref(), &evs).await;
            record_events(
                &mut events,
                evs,
                limits.max_result_bytes as usize,
                max_normalized_events,
                &mut events_dropped,
            );
        }
        Err(_) => stream_error = true,
    }

    if pid > 0 && pid_exists(pid) {
        let _ = kill_process_group(pgid, Signal::SIGKILL);
        descendants_terminated = true;
    }

    let parser_diagnostics = parser.diagnostics();

    Ok(SupervisedRun {
        exit_code,
        exit_signal,
        descendants_terminated,
        stdout_total_bytes: stdout_total,
        stderr_total_bytes: stderr_total,
        stdout_persisted_bytes: stdout_persisted,
        stderr_persisted_bytes: stderr_persisted,
        raw_stdout_truncated,
        raw_stderr_truncated,
        timed_out,
        idle_timed_out,
        cancelled,
        stream_error,
        leader_pid: if pid > 0 { Some(pid) } else { None },
        events,
        parser_diagnostics,
        events_dropped,
    })
}

async fn forward_events(sink: Option<&OwnerEventSink>, events: &[HarnessEvent]) {
    let Some((tx, agent_id)) = sink else {
        return;
    };
    for event in events {
        let message = crate::state_owner::OwnerMsg::Event {
            agent_id: agent_id.clone(),
            event: StateEvent::Harness(clone_event(event)),
        };
        if matches!(
            event,
            HarnessEvent::PermissionDenied { .. }
                | HarnessEvent::IdentityObserved(_)
                | HarnessEvent::FinalResult(_)
                | HarnessEvent::HarnessResult(_)
                | HarnessEvent::HarnessError(_)
        ) {
            crate::state_owner::StateOwner::send_critical(tx, message).await;
        } else {
            let _ = tx.try_send(message);
        }
    }
}

fn record_events(
    destination: &mut Vec<HarnessEvent>,
    incoming: Vec<HarnessEvent>,
    max_result_bytes: usize,
    max_normalized_events: usize,
    events_dropped: &mut u64,
) {
    for event in incoming {
        match event {
            HarnessEvent::AssistantText(chunk) => {
                if let Some(HarnessEvent::AssistantText(existing)) = destination
                    .iter_mut()
                    .find(|e| matches!(e, HarnessEvent::AssistantText(_)))
                {
                    existing.text.push_bounded(&chunk.text, max_result_bytes);
                } else if destination.len() < max_normalized_events {
                    destination.push(HarnessEvent::AssistantText(chunk));
                } else {
                    *events_dropped = events_dropped.saturating_add(1);
                }
            }
            HarnessEvent::IdentityObserved(identity) => {
                if let Some(slot) = destination
                    .iter_mut()
                    .rev()
                    .find(|e| matches!(e, HarnessEvent::IdentityObserved(_)))
                {
                    *slot = HarnessEvent::IdentityObserved(identity);
                } else {
                    make_room_for_critical(destination, max_normalized_events);
                    destination.push(HarnessEvent::IdentityObserved(identity));
                }
            }
            HarnessEvent::FinalResult(result) => {
                destination.retain(|e| !matches!(e, HarnessEvent::FinalResult(_)));
                make_room_for_critical(destination, max_normalized_events);
                destination.push(HarnessEvent::FinalResult(result));
            }
            HarnessEvent::HarnessResult(claim) => {
                destination.retain(|e| !matches!(e, HarnessEvent::HarnessResult(_)));
                make_room_for_critical(destination, max_normalized_events);
                destination.push(HarnessEvent::HarnessResult(claim));
            }
            HarnessEvent::PermissionDenied { id, name } => {
                make_room_for_critical(destination, max_normalized_events);
                destination.push(HarnessEvent::PermissionDenied { id, name });
            }
            other if destination.len() < max_normalized_events => destination.push(other),
            _ => *events_dropped = events_dropped.saturating_add(1),
        }
    }
}

fn make_room_for_critical(events: &mut Vec<HarnessEvent>, max_normalized_events: usize) {
    if events.len() < max_normalized_events {
        return;
    }
    if let Some(index) = events.iter().position(|e| {
        matches!(
            e,
            HarnessEvent::ToolStarted { .. }
                | HarnessEvent::ToolFinished { .. }
                | HarnessEvent::OversizedEventSkipped { .. }
                | HarnessEvent::AssistantText(_)
        )
    }) {
        events.remove(index);
    } else {
        events.remove(0);
    }
}

pub fn enforce_normalized_event_budget(
    run: &mut SupervisedRun,
    max_normalized_events: usize,
    max_result_bytes: usize,
) {
    if run.events.len() <= max_normalized_events {
        return;
    }
    let incoming = std::mem::take(&mut run.events);
    let mut dropped = 0u64;
    record_events(
        &mut run.events,
        incoming,
        max_result_bytes,
        max_normalized_events,
        &mut dropped,
    );
    run.events_dropped = run.events_dropped.saturating_add(dropped);
}

/// In-process fake harness (no spawn) for vertical slice.
#[cfg(feature = "dev-harness")]
pub async fn run_fake_harness(
    adapter: &crate::harness::FakeAdapter,
    limits: &Limits,
    stdout_log: Option<&Path>,
    mut cancel: Option<tokio::sync::watch::Receiver<bool>>,
) -> BrokerResult<SupervisedRun> {
    let sleep_ms = adapter.sleep_ms;
    if sleep_ms > 0 {
        let mut remaining = sleep_ms;
        while remaining > 0 {
            if let Some(ref mut rx) = cancel {
                if *rx.borrow() {
                    return Ok(SupervisedRun {
                        exit_code: None,
                        exit_signal: Some(2),
                        descendants_terminated: false,
                        stdout_total_bytes: 0,
                        stderr_total_bytes: 0,
                        stdout_persisted_bytes: 0,
                        stderr_persisted_bytes: 0,
                        raw_stdout_truncated: false,
                        raw_stderr_truncated: false,
                        timed_out: false,
                        idle_timed_out: false,
                        cancelled: true,
                        stream_error: false,
                        leader_pid: None,
                        events: Vec::new(),
                        parser_diagnostics: ParserDiagnostics::default(),
                        events_dropped: 0,
                    });
                }
            }
            let step = remaining.min(50);
            tokio::time::sleep(Duration::from_millis(step)).await;
            remaining = remaining.saturating_sub(step);
        }
    }

    if let Some(ref rx) = cancel {
        if *rx.borrow() {
            return Ok(SupervisedRun {
                exit_code: None,
                exit_signal: Some(2),
                descendants_terminated: false,
                stdout_total_bytes: 0,
                stderr_total_bytes: 0,
                stdout_persisted_bytes: 0,
                stderr_persisted_bytes: 0,
                raw_stdout_truncated: false,
                raw_stderr_truncated: false,
                timed_out: false,
                idle_timed_out: false,
                cancelled: true,
                stream_error: false,
                leader_pid: None,
                events: Vec::new(),
                parser_diagnostics: ParserDiagnostics::default(),
                events_dropped: 0,
            });
        }
    }

    let mut events = Vec::new();

    if let Some(ref fixture_path) = adapter.stream_fixture {
        let data = tokio::fs::read(fixture_path)
            .await
            .map_err(|e| SpawnError::Failed(format!("read fixture: {e}")))?;
        if let Some(path) = stdout_log {
            crate::persistence::refuse_symlink(path)?;
            let marker = b"[fixture stdout redacted; normalized output is in result.json]\n";
            let take = marker.len().min(limits.max_raw_log_bytes as usize);
            let mut f = tokio::fs::File::create(path)
                .await
                .map_err(|e| SpawnError::Failed(e.to_string()))?;
            f.write_all(&marker[..take])
                .await
                .map_err(|e| SpawnError::Failed(e.to_string()))?;
            if data.len() as u64 > limits.max_raw_log_bytes {
                f.write_all(b"[raw log budget exceeded]\n")
                    .await
                    .map_err(|e| SpawnError::Failed(e.to_string()))?;
            }
        }
        let mut parser = crate::harness::claude::ClaudeParser::new(
            limits.max_result_bytes as usize,
            limits.max_event_line_bytes as usize,
        );
        let mut events_dropped = 0u64;
        let parsed = parser.push(&data).unwrap_or_else(|_| Vec::new());
        record_events(
            &mut events,
            parsed,
            limits.max_result_bytes as usize,
            4096,
            &mut events_dropped,
        );
        let finished = parser.finish().unwrap_or_else(|_| Vec::new());
        record_events(
            &mut events,
            finished,
            limits.max_result_bytes as usize,
            4096,
            &mut events_dropped,
        );
        let total = data.len() as u64;
        return Ok(SupervisedRun {
            exit_code: Some(adapter.exit_code),
            exit_signal: None,
            descendants_terminated: false,
            stdout_total_bytes: total,
            stderr_total_bytes: 0,
            stdout_persisted_bytes:
                (b"[fixture stdout redacted; normalized output is in result.json]\n".len() as u64)
                    .min(limits.max_raw_log_bytes)
                    .saturating_add(if total > limits.max_raw_log_bytes {
                        b"[raw log budget exceeded]\n".len() as u64
                    } else {
                        0
                    }),
            stderr_persisted_bytes: 0,
            raw_stdout_truncated: total > limits.max_raw_log_bytes,
            raw_stderr_truncated: false,
            timed_out: false,
            idle_timed_out: false,
            cancelled: false,
            stream_error: false,
            leader_pid: None,
            events,
            parser_diagnostics: ParserDiagnostics::default(),
            events_dropped,
        });
    }

    events.extend(adapter.synthesize_events(limits.max_result_bytes as usize));
    let fake_marker = b"[fake stdout redacted; see result.json]\n";
    let fake_persisted = fake_marker.len().min(limits.max_raw_log_bytes as usize);
    if let Some(path) = stdout_log {
        crate::persistence::refuse_symlink(path)?;
        tokio::fs::write(path, &fake_marker[..fake_persisted])
            .await
            .map_err(|e| SpawnError::Failed(e.to_string()))?;
    }
    Ok(SupervisedRun {
        exit_code: Some(adapter.exit_code),
        exit_signal: None,
        descendants_terminated: false,
        stdout_total_bytes: adapter.response_summary.len() as u64,
        stderr_total_bytes: 0,
        stdout_persisted_bytes: fake_persisted as u64,
        stderr_persisted_bytes: 0,
        raw_stdout_truncated: adapter.response_summary.len() as u64 > limits.max_raw_log_bytes,
        raw_stderr_truncated: false,
        timed_out: false,
        idle_timed_out: false,
        cancelled: false,
        stream_error: false,
        leader_pid: None,
        events,
        parser_diagnostics: ParserDiagnostics::default(),
        events_dropped: 0,
    })
}

pub fn apply_supervised_to_agent(agent: &mut crate::state::AgentRuntime, run: &SupervisedRun) {
    for e in &run.events {
        agent.apply_harness_event(clone_event(e));
    }
    agent.diagnostics.exit_code = run.exit_code;
    agent.diagnostics.exit_signal = run.exit_signal;
    agent.diagnostics.stdout_total_bytes = run.stdout_total_bytes;
    agent.diagnostics.stderr_total_bytes = run.stderr_total_bytes;
    agent.diagnostics.stdout_persisted_bytes = run.stdout_persisted_bytes;
    agent.diagnostics.stderr_persisted_bytes = run.stderr_persisted_bytes;
    agent.diagnostics.raw_stdout_truncated = run.raw_stdout_truncated;
    agent.diagnostics.raw_stderr_truncated = run.raw_stderr_truncated;
    agent.diagnostics.descendants_terminated = run.descendants_terminated;
    agent.diagnostics.timed_out = run.timed_out;
    agent.diagnostics.idle_timed_out = run.idle_timed_out;
    agent.diagnostics.cancelled = run.cancelled;
    agent.diagnostics.unknown_event_count = run.parser_diagnostics.unknown_event_count;
    agent.diagnostics.invalid_json_count = run.parser_diagnostics.invalid_json_count;
    agent.diagnostics.oversized_event_count = run.parser_diagnostics.oversized_event_count;
    agent.diagnostics.events_dropped = run.events_dropped;
}

pub fn forced_outcome_from_run(run: &SupervisedRun) -> Option<crate::state::Outcome> {
    use crate::state::{FailureReason, Outcome};
    if run.cancelled {
        return Some(Outcome::Cancelled {
            detail: Some("SIGINT".into()),
        });
    }
    if run.idle_timed_out {
        return Some(Outcome::Failed {
            reason: FailureReason::IdleTimeout,
            detail: None,
        });
    }
    if run.timed_out {
        return Some(Outcome::Failed {
            reason: FailureReason::Timeout,
            detail: None,
        });
    }
    if run.stream_error {
        return Some(Outcome::Failed {
            reason: FailureReason::InvalidStream,
            detail: Some("stream parser or reader failure".into()),
        });
    }
    None
}

fn clone_event(e: &HarnessEvent) -> HarnessEvent {
    match e {
        HarnessEvent::AssistantText(c) => HarnessEvent::AssistantText(crate::event::BoundedChunk {
            text: c.text.clone(),
        }),
        HarnessEvent::FinalResult(c) => HarnessEvent::FinalResult(crate::event::BoundedChunk {
            text: c.text.clone(),
        }),
        HarnessEvent::ToolStarted { id, name } => HarnessEvent::ToolStarted {
            id: crate::event::ToolId::new(id.as_str()),
            name: crate::event::SafeToolName::new(name.as_str()),
        },
        HarnessEvent::ToolFinished { id, is_error } => HarnessEvent::ToolFinished {
            id: crate::event::ToolId::new(id.as_str()),
            is_error: *is_error,
        },
        HarnessEvent::PermissionDenied { id, name } => HarnessEvent::PermissionDenied {
            id: id.as_ref().map(|i| crate::event::ToolId::new(i.as_str())),
            name: name
                .as_ref()
                .map(|n| crate::event::SafeToolName::new(n.as_str())),
        },
        HarnessEvent::IdentityObserved(o) => HarnessEvent::IdentityObserved(o.clone()),
        HarnessEvent::HarnessResult(c) => HarnessEvent::HarnessResult(c.clone()),
        HarnessEvent::HarnessError(t) => HarnessEvent::HarnessError(
            crate::task::BoundedText::with_limit_from_str(&t.to_string_lossy(), t.len().max(1)),
        ),
        HarnessEvent::OversizedEventSkipped { bytes } => {
            HarnessEvent::OversizedEventSkipped { bytes: *bytes }
        }
    }
}

#[allow(dead_code)]
fn _state_event_placeholder() -> StateEvent {
    StateEvent::Activity
}

/// Test helper: spawn long-running process, drop guard, assert reaped.
#[cfg(test)]
#[allow(clippy::unwrap_used)]
mod tests {
    use super::*;
    use crate::environment::{build_environment, ensure_isolated_dirs};
    use crate::task::EnvironmentSpec;
    use tempfile::tempdir;

    #[tokio::test]
    async fn child_guard_drop_kills_pgid() {
        let dir = tempdir().unwrap();
        let home = dir.path().join("home");
        ensure_isolated_dirs(&home).unwrap();
        let env = build_environment(&EnvironmentSpec::default(), dir.path(), &home);

        let mut cmd = Command::new("/bin/sh");
        cmd.args(["-c", "sleep 60"]);
        cmd.current_dir(dir.path())
            .stdin(Stdio::null())
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .kill_on_drop(true);
        apply_to_command(&mut cmd, &env);
        configure_command(&mut cmd).unwrap();
        let child = cmd.spawn().unwrap();
        let pid = child.id().unwrap();
        let pgid = pid as i32;
        {
            let _guard = ChildGuard::new(pgid);
            // drop kills
        }
        tokio::time::sleep(Duration::from_millis(200)).await;
        // Reap zombie by waiting on child if still joinable — drop of child also kills
        drop(child);
        tokio::time::sleep(Duration::from_millis(100)).await;
        assert!(
            !pid_exists(pid) || !pgid_alive(pgid),
            "process should be gone after ChildGuard drop"
        );
    }
}
