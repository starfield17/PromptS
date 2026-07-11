//! Single-writer StateOwner: only component that mutates RunState and persists.

use std::time::{Duration, Instant};

use tokio::sync::mpsc;

use crate::error::BrokerResult;
use crate::event::{HarnessEvent, StateEvent};
use crate::persistence::RunDirectory;
use crate::state::{AgentRuntime, Outcome, PatchRecord, RunState};

const ACTIVITY_THROTTLE: Duration = Duration::from_millis(500);
const CHANNEL_CAP: usize = 256;

/// Messages sent to the StateOwner (never shared Arc<Mutex<RunState>>).
#[derive(Debug)]
#[allow(clippy::large_enum_variant)]
pub enum OwnerMsg {
    /// Insert/replace agent runtime snapshot (from worker completion path).
    UpsertAgent(AgentRuntime),
    /// Apply a stream/process event to an agent.
    Event { agent_id: String, event: StateEvent },
    /// Finish agent with optional patch.
    FinishAgent {
        agent_id: String,
        forced: Option<Outcome>,
        patch: Option<PatchRecord>,
    },
    /// Low-value activity; may be dropped under backpressure.
    Activity { agent_id: String },
    /// Stop owner loop after draining.
    Shutdown,
}

pub struct StateOwner {
    state: RunState,
    run_dir: RunDirectory,
    last_persist: Instant,
    dirty: bool,
    max_events_log_bytes: u64,
    event_budget_marker_written: bool,
}

impl StateOwner {
    pub fn new(state: RunState, run_dir: RunDirectory, max_events_log_bytes: u64) -> Self {
        Self {
            state,
            run_dir,
            last_persist: Instant::now(),
            dirty: false,
            max_events_log_bytes,
            event_budget_marker_written: false,
        }
    }

    pub fn channel() -> (mpsc::Sender<OwnerMsg>, mpsc::Receiver<OwnerMsg>) {
        mpsc::channel(CHANNEL_CAP)
    }

    /// Send critical message; await capacity. Activity uses try_send and may drop.
    pub async fn send_critical(tx: &mpsc::Sender<OwnerMsg>, msg: OwnerMsg) {
        let _ = tx.send(msg).await;
    }

    pub fn try_send_activity(tx: &mpsc::Sender<OwnerMsg>, agent_id: &str) {
        let _ = tx.try_send(OwnerMsg::Activity {
            agent_id: agent_id.to_string(),
        });
    }

    pub fn into_state(self) -> RunState {
        self.state
    }

    pub fn run_dir(&self) -> &RunDirectory {
        &self.run_dir
    }

    pub async fn run(
        mut self,
        mut rx: mpsc::Receiver<OwnerMsg>,
    ) -> BrokerResult<(RunState, RunDirectory)> {
        while let Some(msg) = rx.recv().await {
            match msg {
                OwnerMsg::Shutdown => break,
                OwnerMsg::UpsertAgent(agent) => {
                    let id = agent.agent_id.as_str().to_string();
                    let phase = crate::render::phase_str(agent.phase);
                    if self.state.agent(&id).is_some() {
                        // replace finished snapshot
                        if let Some(slot) = self.state.agent_mut(&id) {
                            *slot = agent;
                        }
                        self.state.bump_revision();
                    } else {
                        self.state.insert_agent(agent);
                    }
                    self.state.recompute_run_outcome();
                    self.append_event(&serde_json::json!({
                        "revision": self.state.revision,
                        "agent_id": id,
                        "event": "agent_snapshot",
                        "phase": phase,
                    }))?;
                    self.dirty = true;
                    if self.state.phase != crate::state::Phase::Finished {
                        self.run_dir.persist_live(&self.state)?;
                    }
                    self.last_persist = Instant::now();
                    self.dirty = false;
                }
                OwnerMsg::Event { agent_id, event } => {
                    let critical = is_critical(&event);
                    let label = event_label(&event);
                    self.state.apply_agent_event(&agent_id, event);
                    self.append_event(&serde_json::json!({
                        "revision": self.state.revision,
                        "agent_id": agent_id,
                        "event": label,
                    }))?;
                    self.dirty = true;
                    if critical || self.last_persist.elapsed() >= ACTIVITY_THROTTLE {
                        self.run_dir.persist_live(&self.state)?;
                        self.last_persist = Instant::now();
                        self.dirty = false;
                    }
                }
                OwnerMsg::FinishAgent {
                    agent_id,
                    forced,
                    patch,
                } => {
                    if let Some(agent) = self.state.agent_mut(&agent_id) {
                        let _ = agent.finish(forced, patch);
                    }
                    self.state.recompute_run_outcome();
                    self.dirty = true;
                    if self.state.phase != crate::state::Phase::Finished {
                        self.run_dir.persist_live(&self.state)?;
                    }
                    self.last_persist = Instant::now();
                    self.dirty = false;
                }
                OwnerMsg::Activity { agent_id } => {
                    self.state
                        .apply_agent_event(&agent_id, StateEvent::Activity);
                    self.dirty = true;
                    if self.last_persist.elapsed() >= ACTIVITY_THROTTLE {
                        self.run_dir.persist_live(&self.state)?;
                        self.last_persist = Instant::now();
                        self.dirty = false;
                    }
                }
            }
        }
        if self.dirty {
            self.run_dir.persist_live(&self.state)?;
        }
        Ok((self.state, self.run_dir))
    }

    fn append_event(&mut self, value: &serde_json::Value) -> BrokerResult<()> {
        if self
            .run_dir
            .append_event_with_limit(value, self.max_events_log_bytes)?
        {
            return Ok(());
        }
        if !self.event_budget_marker_written {
            let marker = serde_json::json!({
                "revision": self.state.revision,
                "event": "events_truncated",
                "reason": "max_events_log_bytes"
            });
            self.event_budget_marker_written = self
                .run_dir
                .append_event_with_limit(&marker, self.max_events_log_bytes)?;
        }
        Ok(())
    }
}

fn event_label(event: &StateEvent) -> &'static str {
    match event {
        StateEvent::AgentStarted { .. } => "agent_started",
        StateEvent::Harness(HarnessEvent::PermissionDenied { .. }) => "permission_denied",
        StateEvent::Harness(HarnessEvent::IdentityObserved(_)) => "identity_observed",
        StateEvent::Harness(HarnessEvent::FinalResult(_)) => "final_result",
        StateEvent::Harness(HarnessEvent::HarnessResult(_)) => "harness_result",
        StateEvent::Harness(HarnessEvent::HarnessError(_)) => "harness_error",
        StateEvent::Harness(_) => "harness_activity",
        StateEvent::ProcessExited { .. } => "process_exited",
        StateEvent::DescendantsTerminated => "descendants_terminated",
        StateEvent::IdleTimeout => "idle_timeout",
        StateEvent::TotalTimeout => "total_timeout",
        StateEvent::Cancelled => "cancelled",
        StateEvent::InternalError(_) => "internal_error",
        StateEvent::Activity => "activity",
    }
}

fn is_critical(ev: &StateEvent) -> bool {
    match ev {
        StateEvent::ProcessExited { .. }
        | StateEvent::Cancelled
        | StateEvent::IdleTimeout
        | StateEvent::TotalTimeout
        | StateEvent::InternalError(_)
        | StateEvent::DescendantsTerminated => true,
        StateEvent::Harness(h) => matches!(
            h,
            HarnessEvent::PermissionDenied { .. }
                | HarnessEvent::IdentityObserved(_)
                | HarnessEvent::FinalResult(_)
                | HarnessEvent::HarnessResult(_)
                | HarnessEvent::HarnessError(_)
        ),
        StateEvent::AgentStarted { .. } | StateEvent::Activity => false,
    }
}

/// Capacity used by tests.
pub fn channel_capacity() -> usize {
    CHANNEL_CAP
}
