//! Single-writer run state. No shared Arc<Mutex<RunState>>.

use std::collections::HashMap;
use std::time::{Duration, SystemTime, UNIX_EPOCH};

use serde::{Deserialize, Serialize};

use crate::event::{HarnessEvent, HarnessTerminalClaim, StateEvent};
use crate::identity::{
    evaluate_identity_gate, ExecutableIdentity, IdentityGateResult, IdentityRequirement,
    ObservedIdentity, RequestedIdentity,
};
use crate::task::{AgentId, BoundedText, IsolationMode, Mode, RunId};

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Phase {
    Queued,
    Preparing,
    Running,
    Finished,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum OutcomeKind {
    Success,
    Blocked,
    Failed,
    Cancelled,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum BlockReason {
    PermissionDenied,
    ProviderMismatch,
    PatchPolicy,
}

impl BlockReason {
    pub fn as_str(self) -> &'static str {
        match self {
            BlockReason::PermissionDenied => "permission_denied",
            BlockReason::ProviderMismatch => "provider_mismatch",
            BlockReason::PatchPolicy => "patch_policy",
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum FailureReason {
    Timeout,
    IdleTimeout,
    InvalidStream,
    HarnessExit,
    CommandNotFound,
    WorkspaceViolation,
    ReadOnlyWrite,
    ResponseTruncated,
    VerificationFailed,
    Internal,
}

impl FailureReason {
    pub fn as_str(self) -> &'static str {
        match self {
            FailureReason::Timeout => "timeout",
            FailureReason::IdleTimeout => "idle_timeout",
            FailureReason::InvalidStream => "invalid_stream",
            FailureReason::HarnessExit => "harness_exit",
            FailureReason::CommandNotFound => "command_not_found",
            FailureReason::WorkspaceViolation => "workspace_violation",
            FailureReason::ReadOnlyWrite => "read_only_write",
            FailureReason::ResponseTruncated => "response_truncated",
            FailureReason::VerificationFailed => "verification_failed",
            FailureReason::Internal => "internal",
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct PermissionDenial {
    pub tool_name: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub tool_id: Option<String>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, Default)]
pub struct ResponseRecord {
    pub summary: String,
    pub truncated: bool,
    pub original_bytes: u64,
    pub tests: TestsRecord,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct TestsRecord {
    pub verification: String,
    pub items: Vec<String>,
    #[serde(default)]
    pub results: Vec<VerificationResult>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct VerificationResult {
    pub command: String,
    pub exit_code: Option<i32>,
    pub timed_out: bool,
    pub stdout_bytes: u64,
    pub stderr_bytes: u64,
    pub output_truncated: bool,
}

impl Default for TestsRecord {
    fn default() -> Self {
        Self {
            verification: "self_reported".into(),
            items: Vec::new(),
            results: Vec::new(),
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, Default)]
pub struct Diagnostics {
    pub raw_stdout_truncated: bool,
    pub raw_stderr_truncated: bool,
    pub stdout_total_bytes: u64,
    pub stderr_total_bytes: u64,
    pub stdout_persisted_bytes: u64,
    pub stderr_persisted_bytes: u64,
    pub descendants_terminated: bool,
    pub exit_code: Option<i32>,
    pub exit_signal: Option<i32>,
    pub timed_out: bool,
    pub idle_timed_out: bool,
    pub cancelled: bool,
    pub duration_ms: Option<u64>,
    pub unknown_event_count: u64,
    pub invalid_json_count: u64,
    pub oversized_event_count: u64,
    pub events_dropped: u64,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct EnvironmentRecord {
    pub home: String,
    pub allowed_env_names: Vec<String>,
    pub host_configuration_exposed: bool,
    pub reproducibility: String,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct PolicyGateRecord {
    pub evaluated: bool,
    pub satisfied: bool,
    pub reason: Option<String>,
}

/// Opaque proof that identity, denial, response and harness terminal gates passed.
pub struct PatchAuthorization {
    _private: (),
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct PatchRecord {
    pub(crate) path: String,
    pub(crate) sha256: String,
    pub(crate) files_changed: Vec<String>,
    pub(crate) baseline_manifest_sha256: Option<String>,
    pub(crate) baseline_bundle_sha256: Option<String>,
}

impl PatchRecord {
    pub fn path(&self) -> &str {
        &self.path
    }

    pub fn sha256(&self) -> &str {
        &self.sha256
    }

    pub fn files_changed(&self) -> &[String] {
        &self.files_changed
    }
}

/// Terminal outcome — only Success may ever hold a patch.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Outcome {
    Success {
        patch: Option<PatchRecord>,
    },
    Blocked {
        reason: BlockReason,
    },
    Failed {
        reason: FailureReason,
        detail: Option<String>,
    },
    Cancelled {
        detail: Option<String>,
    },
}

impl Outcome {
    pub fn kind(&self) -> OutcomeKind {
        match self {
            Outcome::Success { .. } => OutcomeKind::Success,
            Outcome::Blocked { .. } => OutcomeKind::Blocked,
            Outcome::Failed { .. } => OutcomeKind::Failed,
            Outcome::Cancelled { .. } => OutcomeKind::Cancelled,
        }
    }

    pub fn reason_str(&self) -> Option<&str> {
        match self {
            Outcome::Success { .. } => None,
            Outcome::Blocked { reason } => Some(reason.as_str()),
            Outcome::Failed { reason, .. } => Some(reason.as_str()),
            Outcome::Cancelled { .. } => Some("cancelled"),
        }
    }

    pub fn patch(&self) -> Option<&PatchRecord> {
        match self {
            Outcome::Success { patch } => patch.as_ref(),
            _ => None,
        }
    }
}

#[derive(Debug, Clone)]
pub struct AgentRuntime {
    pub(crate) agent_id: AgentId,
    pub(crate) mode: Mode,
    pub(crate) isolation: IsolationMode,
    pub(crate) phase: Phase,
    pub(crate) requested: RequestedIdentity,
    pub(crate) executable: Option<ExecutableIdentity>,
    pub(crate) observed: ObservedIdentity,
    pub(crate) identity_req: IdentityRequirement,
    pub(crate) identity_gate: Option<IdentityGateResult>,
    pub(crate) permission_denials: Vec<PermissionDenial>,
    pub(crate) harness_completed: bool,
    pub(crate) response: ResponseRecord,
    pub(crate) diagnostics: Diagnostics,
    pub(crate) environment: Option<EnvironmentRecord>,
    pub(crate) policy_gate: Option<PolicyGateRecord>,
    pub(crate) files_changed: Vec<String>,
    pub(crate) outcome: Option<Outcome>,
    pub(crate) started_at: Option<String>,
    pub(crate) ended_at: Option<String>,
    max_result_bytes: usize,
    assistant: BoundedText,
    terminal_claim: Option<HarnessTerminalClaim>,
    response_truncated_hard: bool,
    started_mono: Option<std::time::Instant>,
}

impl AgentRuntime {
    pub fn new(
        agent_id: AgentId,
        mode: Mode,
        requested: RequestedIdentity,
        identity_req: IdentityRequirement,
        max_result_bytes: usize,
    ) -> Self {
        Self::new_with_isolation(
            agent_id,
            mode,
            requested,
            identity_req,
            max_result_bytes,
            IsolationMode::CopyIsolation,
        )
    }

    pub fn new_with_isolation(
        agent_id: AgentId,
        mode: Mode,
        requested: RequestedIdentity,
        identity_req: IdentityRequirement,
        max_result_bytes: usize,
        isolation: IsolationMode,
    ) -> Self {
        Self {
            agent_id,
            mode,
            isolation,
            phase: Phase::Queued,
            requested,
            executable: None,
            observed: ObservedIdentity::default(),
            identity_req,
            identity_gate: None,
            permission_denials: Vec::new(),
            harness_completed: false,
            response: ResponseRecord::default(),
            diagnostics: Diagnostics::default(),
            environment: None,
            policy_gate: None,
            files_changed: Vec::new(),
            outcome: None,
            started_at: None,
            ended_at: None,
            max_result_bytes,
            assistant: BoundedText::new(max_result_bytes),
            terminal_claim: None,
            response_truncated_hard: false,
            started_mono: None,
        }
    }

    pub fn prepare(&mut self) {
        if self.phase == Phase::Queued {
            self.phase = Phase::Preparing;
        }
    }

    pub fn start(&mut self, executable: ExecutableIdentity) {
        self.phase = Phase::Running;
        self.executable = Some(executable);
        self.started_at = Some(now_rfc3339());
        self.started_mono = Some(std::time::Instant::now());
    }

    pub fn apply_harness_event(&mut self, ev: HarnessEvent) {
        match ev {
            HarnessEvent::AssistantText(chunk) => {
                self.assistant
                    .push_bounded(&chunk.text, self.max_result_bytes);
            }
            HarnessEvent::FinalResult(chunk) => {
                if chunk.text.truncated() {
                    self.response_truncated_hard = true;
                }
                self.assistant = chunk.text;
            }
            HarnessEvent::ToolStarted { .. } | HarnessEvent::ToolFinished { .. } => {}
            HarnessEvent::PermissionDenied { id, name } => {
                let tool_name = name
                    .map(|n| n.as_str().to_string())
                    .unwrap_or_else(|| "unknown".into());
                let denial = PermissionDenial {
                    tool_name,
                    tool_id: id.map(|i| i.as_str().to_string()),
                };
                if !self
                    .permission_denials
                    .iter()
                    .any(|d| d.tool_name == denial.tool_name && d.tool_id == denial.tool_id)
                {
                    self.permission_denials.push(denial);
                }
            }
            HarnessEvent::IdentityObserved(obs) => {
                if obs.provider.is_some() {
                    self.observed.provider = obs.provider;
                }
                if obs.model.is_some() {
                    self.observed.model = obs.model;
                }
                if obs.api_key_source.is_some() {
                    self.observed.api_key_source = obs.api_key_source;
                }
                self.observed.evidence = obs
                    .evidence
                    .or(Some(crate::identity::IdentityEvidence::StreamClaim));
            }
            HarnessEvent::HarnessResult(claim) => {
                self.terminal_claim = Some(claim);
                self.harness_completed = true;
            }
            HarnessEvent::HarnessError(text) => {
                self.terminal_claim = Some(HarnessTerminalClaim::Error);
                if self.assistant.is_empty() {
                    self.assistant = BoundedText::with_limit_from_str(
                        &text.to_string_lossy(),
                        self.max_result_bytes,
                    );
                }
            }
            HarnessEvent::OversizedEventSkipped { .. } => {}
        }
    }

    /// Compute terminal outcome. Denial and identity gates always win over Success.
    pub(crate) fn finish(
        &mut self,
        forced: Option<Outcome>,
        patch: Option<PatchRecord>,
    ) -> Outcome {
        if self.phase == Phase::Finished {
            if let Some(ref o) = self.outcome {
                return o.clone();
            }
        }

        self.ended_at = Some(now_rfc3339());
        self.diagnostics.duration_ms = self
            .started_mono
            .map(|started| started.elapsed().as_millis().min(u128::from(u64::MAX)) as u64);
        self.response.summary = self.assistant.to_string_lossy();
        self.response.truncated = self.assistant.truncated();
        self.response.original_bytes = self.assistant.original_bytes();

        let gate =
            evaluate_identity_gate(&self.identity_req, &self.observed, self.executable.as_ref());
        self.identity_gate = Some(gate.clone());

        let outcome = if let Some(o) = forced {
            enforce_gates(o, &self.permission_denials, &gate, patch)
        } else {
            decide_outcome(
                &self.permission_denials,
                &gate,
                self.terminal_claim.as_ref(),
                self.response_truncated_hard,
                self.diagnostics.exit_code,
                patch,
            )
        };

        self.outcome = Some(outcome.clone());
        self.phase = Phase::Finished;
        outcome
    }

    pub fn finish_without_patch(&mut self, forced: Option<Outcome>) -> Outcome {
        self.finish(forced, None)
    }

    pub fn denial_count(&self) -> usize {
        self.permission_denials.len()
    }

    pub fn last_denied_tool(&self) -> Option<&str> {
        self.permission_denials.last().map(|d| d.tool_name.as_str())
    }

    /// True only when every non-policy gate required before patch persistence passes.
    fn patch_gate_ready(&self, forced: Option<&Outcome>) -> bool {
        if forced.is_some() || !self.permission_denials.is_empty() {
            return false;
        }
        let identity =
            evaluate_identity_gate(&self.identity_req, &self.observed, self.executable.as_ref());
        (!identity.required || identity.satisfied)
            && self.executable.as_ref().map_or(true, |executable| {
                executable.trust == crate::identity::ExecutableTrust::Custom
                    || executable.version_verified
            })
            && self.diagnostics.exit_code == Some(0)
            && !self.response_truncated_hard
            && self.diagnostics.unknown_event_count == 0
            && self.diagnostics.invalid_json_count == 0
            && self.diagnostics.oversized_event_count == 0
            && matches!(self.terminal_claim, Some(HarnessTerminalClaim::Success))
    }

    pub fn patch_authorization(&self, forced: Option<&Outcome>) -> Option<PatchAuthorization> {
        self.patch_gate_ready(forced)
            .then_some(PatchAuthorization { _private: () })
    }

    pub fn record_process_exit(&mut self, code: Option<i32>) {
        self.diagnostics.exit_code = code;
    }

    pub fn record_verification(&mut self, results: Vec<VerificationResult>, passed: bool) {
        self.response.tests.verification = if passed {
            "broker_verified".into()
        } else {
            "broker_failed".into()
        };
        self.response.tests.items = results
            .iter()
            .map(|result| {
                format!(
                    "{}: exit={:?} timeout={} truncated={}",
                    result.command, result.exit_code, result.timed_out, result.output_truncated
                )
            })
            .collect();
        self.response.tests.results = results;
    }
}

fn enforce_gates(
    outcome: Outcome,
    denials: &[PermissionDenial],
    gate: &IdentityGateResult,
    patch: Option<PatchRecord>,
) -> Outcome {
    if !denials.is_empty() {
        return Outcome::Blocked {
            reason: BlockReason::PermissionDenied,
        };
    }
    if gate.required && !gate.satisfied {
        return Outcome::Blocked {
            reason: BlockReason::ProviderMismatch,
        };
    }
    match outcome {
        Outcome::Success { .. } => Outcome::Success { patch },
        other => other,
    }
}

fn decide_outcome(
    denials: &[PermissionDenial],
    gate: &IdentityGateResult,
    claim: Option<&HarnessTerminalClaim>,
    response_truncated_hard: bool,
    exit_code: Option<i32>,
    patch: Option<PatchRecord>,
) -> Outcome {
    if !denials.is_empty() {
        return Outcome::Blocked {
            reason: BlockReason::PermissionDenied,
        };
    }
    if gate.required && !gate.satisfied {
        return Outcome::Blocked {
            reason: BlockReason::ProviderMismatch,
        };
    }
    if response_truncated_hard {
        return Outcome::Failed {
            reason: FailureReason::ResponseTruncated,
            detail: None,
        };
    }
    match claim {
        Some(HarnessTerminalClaim::Success) => {
            if exit_code.is_some_and(|c| c != 0) {
                Outcome::Failed {
                    reason: FailureReason::HarnessExit,
                    detail: exit_code.map(|c| format!("exit {c}")),
                }
            } else {
                Outcome::Success { patch }
            }
        }
        Some(HarnessTerminalClaim::Cancelled)
        | Some(HarnessTerminalClaim::MaxTurns)
        | Some(HarnessTerminalClaim::MaxTokens)
        | Some(HarnessTerminalClaim::Refusal) => Outcome::Cancelled {
            detail: claim.map(|c| format!("{c:?}")),
        },
        Some(HarnessTerminalClaim::Error) | Some(HarnessTerminalClaim::Other(_)) => {
            Outcome::Failed {
                reason: FailureReason::InvalidStream,
                detail: None,
            }
        }
        None => {
            if exit_code == Some(0) {
                Outcome::Failed {
                    reason: FailureReason::InvalidStream,
                    detail: Some("missing terminal result event".into()),
                }
            } else {
                Outcome::Failed {
                    reason: FailureReason::HarnessExit,
                    detail: exit_code.map(|c| format!("exit {c}")),
                }
            }
        }
    }
}

#[derive(Debug, Clone)]
pub struct RunState {
    pub(crate) schema_version: u32,
    pub(crate) revision: u64,
    pub(crate) run_id: RunId,
    pub(crate) phase: Phase,
    pub(crate) outcome: Option<OutcomeKind>,
    pub(crate) reason: Option<String>,
    pub(crate) started_at: String,
    pub(crate) ended_at: Option<String>,
    agents: HashMap<String, AgentRuntime>,
    agent_order: Vec<String>,
}

impl RunState {
    pub fn new(run_id: RunId) -> Self {
        Self {
            schema_version: 3,
            revision: 0,
            run_id,
            phase: Phase::Queued,
            outcome: None,
            reason: None,
            started_at: now_rfc3339(),
            ended_at: None,
            agents: HashMap::new(),
            agent_order: Vec::new(),
        }
    }

    pub fn bump_revision(&mut self) {
        self.revision = self.revision.saturating_add(1);
    }

    pub fn insert_agent(&mut self, agent: AgentRuntime) {
        let id = agent.agent_id.as_str().to_string();
        self.agent_order.push(id.clone());
        self.agents.insert(id, agent);
        self.phase = Phase::Running;
        self.bump_revision();
    }

    pub fn agent(&self, id: &str) -> Option<&AgentRuntime> {
        self.agents.get(id)
    }

    pub fn agent_mut(&mut self, id: &str) -> Option<&mut AgentRuntime> {
        self.agents.get_mut(id)
    }

    pub fn agents_in_order(&self) -> impl Iterator<Item = &AgentRuntime> {
        self.agent_order.iter().filter_map(|id| self.agents.get(id))
    }

    pub fn apply_agent_event(&mut self, agent_id: &str, ev: StateEvent) {
        let Some(agent) = self.agents.get_mut(agent_id) else {
            return;
        };
        match ev {
            StateEvent::AgentStarted { .. } => {}
            StateEvent::Harness(h) => agent.apply_harness_event(h),
            StateEvent::ProcessExited { code, .. } => {
                agent.diagnostics.exit_code = code;
            }
            StateEvent::DescendantsTerminated => {
                agent.diagnostics.descendants_terminated = true;
            }
            StateEvent::IdleTimeout => {
                let _ = agent.finish(
                    Some(Outcome::Failed {
                        reason: FailureReason::IdleTimeout,
                        detail: None,
                    }),
                    None,
                );
            }
            StateEvent::TotalTimeout => {
                let _ = agent.finish(
                    Some(Outcome::Failed {
                        reason: FailureReason::Timeout,
                        detail: None,
                    }),
                    None,
                );
            }
            StateEvent::Cancelled => {
                let _ = agent.finish(
                    Some(Outcome::Cancelled {
                        detail: Some("SIGINT".into()),
                    }),
                    None,
                );
            }
            StateEvent::InternalError(msg) => {
                let _ = agent.finish(
                    Some(Outcome::Failed {
                        reason: FailureReason::Internal,
                        detail: Some(msg),
                    }),
                    None,
                );
            }
            StateEvent::Activity => {}
        }
        self.bump_revision();
    }

    pub fn finish_agent(&mut self, agent_id: &str, patch: Option<PatchRecord>) {
        if let Some(agent) = self.agents.get_mut(agent_id) {
            if agent.phase != Phase::Finished {
                let _ = agent.finish(None, patch);
            }
        }
        self.recompute_run_outcome();
        self.bump_revision();
    }

    pub fn recompute_run_outcome(&mut self) {
        let all_finished = self.agents.values().all(|a| a.phase == Phase::Finished);
        if !all_finished || self.agents.is_empty() {
            return;
        }
        self.phase = Phase::Finished;
        self.ended_at = Some(now_rfc3339());

        let mut any_cancelled = false;
        let mut any_blocked = false;
        let mut any_failed = false;
        let mut block_reason = None;
        let mut fail_reason = None;

        for a in self.agents.values() {
            match a.outcome.as_ref() {
                Some(Outcome::Cancelled { .. }) => any_cancelled = true,
                Some(Outcome::Blocked { reason }) => {
                    any_blocked = true;
                    block_reason = Some(*reason);
                }
                Some(Outcome::Failed { reason, .. }) => {
                    any_failed = true;
                    fail_reason = Some(*reason);
                }
                Some(Outcome::Success { .. }) | None => {}
            }
        }

        if any_cancelled {
            self.outcome = Some(OutcomeKind::Cancelled);
            self.reason = Some("cancelled".into());
        } else if any_blocked {
            self.outcome = Some(OutcomeKind::Blocked);
            self.reason = block_reason.map(|r| r.as_str().to_string());
        } else if any_failed {
            self.outcome = Some(OutcomeKind::Failed);
            self.reason = fail_reason.map(|r| r.as_str().to_string());
        } else {
            self.outcome = Some(OutcomeKind::Success);
            self.reason = None;
        }
    }

    pub fn is_success(&self) -> bool {
        self.outcome == Some(OutcomeKind::Success)
    }
}

pub fn now_rfc3339() -> String {
    let dur = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or(Duration::from_secs(0));
    let secs = dur.as_secs();
    let days = secs / 86400;
    let time = secs % 86400;
    let hour = time / 3600;
    let min = (time % 3600) / 60;
    let sec = time % 60;
    let (year, month, day) = civil_from_days(days as i64);
    format!("{year:04}-{month:02}-{day:02}T{hour:02}:{min:02}:{sec:02}Z")
}

fn civil_from_days(days: i64) -> (i32, u32, u32) {
    let z = days + 719_468;
    let era = if z >= 0 { z } else { z - 146_096 } / 146_097;
    let doe = (z - era * 146_097) as u64;
    let yoe = (doe - doe / 1460 + doe / 36524 - doe / 146_096) / 365;
    let y = yoe as i64 + era * 400;
    let doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
    let mp = (5 * doy + 2) / 153;
    let d = doy - (153 * mp + 2) / 5 + 1;
    let m = if mp < 10 { mp + 3 } else { mp - 9 };
    let y = if m <= 2 { y + 1 } else { y };
    (y as i32, m as u32, d as u32)
}

#[cfg(test)]
#[allow(
    clippy::unwrap_used,
    clippy::expect_used,
    clippy::field_reassign_with_default
)]
mod tests {
    use super::*;
    use crate::event::{BoundedChunk, SafeToolName, ToolId};
    use crate::identity::IdentityEvidence;

    fn agent_with_req(required: bool, provider: Option<&str>) -> AgentRuntime {
        let mut req = IdentityRequirement::default();
        req.required = required;
        req.expected_provider = provider.map(str::to_string);
        AgentRuntime::new(
            AgentId::new("a1").unwrap(),
            Mode::ReadOnly,
            RequestedIdentity {
                harness: "claude_code".into(),
                model: Some("claude-x".into()),
            },
            req,
            1024,
        )
    }

    #[test]
    fn denial_forces_blocked_not_success() {
        let mut a = agent_with_req(false, None);
        a.apply_harness_event(HarnessEvent::PermissionDenied {
            id: Some(ToolId::new("t1")),
            name: Some(SafeToolName::new("Bash")),
        });
        a.apply_harness_event(HarnessEvent::HarnessResult(HarnessTerminalClaim::Success));
        a.apply_harness_event(HarnessEvent::FinalResult(BoundedChunk {
            text: BoundedText::with_limit_from_str("ok", 1024),
        }));
        let o = a.finish(
            None,
            Some(PatchRecord {
                path: "p".into(),
                sha256: "x".into(),
                files_changed: vec![],
                baseline_manifest_sha256: None,
                baseline_bundle_sha256: None,
            }),
        );
        assert!(matches!(
            o,
            Outcome::Blocked {
                reason: BlockReason::PermissionDenied
            }
        ));
        assert!(o.patch().is_none());
    }

    #[test]
    fn identity_mismatch_blocks_no_patch() {
        let mut a = agent_with_req(true, Some("anthropic"));
        a.apply_harness_event(HarnessEvent::IdentityObserved(ObservedIdentity {
            provider: Some("xai".into()),
            model: Some("grok".into()),
            api_key_source: None,
            evidence: Some(IdentityEvidence::StreamClaim),
        }));
        a.apply_harness_event(HarnessEvent::HarnessResult(HarnessTerminalClaim::Success));
        let o = a.finish(
            None,
            Some(PatchRecord {
                path: "p".into(),
                sha256: "x".into(),
                files_changed: vec![],
                baseline_manifest_sha256: None,
                baseline_bundle_sha256: None,
            }),
        );
        assert!(matches!(
            o,
            Outcome::Blocked {
                reason: BlockReason::ProviderMismatch
            }
        ));
        assert!(o.patch().is_none());
    }

    #[test]
    fn success_can_hold_patch() {
        let mut a = agent_with_req(false, None);
        a.apply_harness_event(HarnessEvent::HarnessResult(HarnessTerminalClaim::Success));
        a.apply_harness_event(HarnessEvent::FinalResult(BoundedChunk {
            text: BoundedText::with_limit_from_str("done", 1024),
        }));
        let o = a.finish(
            None,
            Some(PatchRecord {
                path: "patch.diff".into(),
                sha256: "abc".into(),
                files_changed: vec!["src/a.rs".into()],
                baseline_manifest_sha256: None,
                baseline_bundle_sha256: None,
            }),
        );
        assert!(matches!(o, Outcome::Success { patch: Some(_) }));
    }
}
