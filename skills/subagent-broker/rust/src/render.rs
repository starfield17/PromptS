//! Pure render functions for summary.md and status text.

use crate::state::{Outcome, OutcomeKind, Phase, RunState};

pub fn render_summary(state: &RunState) -> String {
    let mut out = String::new();
    out.push_str("# Subagent Broker Run Summary\n\n");
    out.push_str(&format!("- **run_id**: `{}`\n", state.run_id));
    out.push_str(&format!("- **revision**: {}\n", state.revision));
    out.push_str(&format!("- **phase**: `{}`\n", phase_str(state.phase)));
    out.push_str(&format!(
        "- **outcome**: `{}`\n",
        state.outcome.map(outcome_kind_str).unwrap_or("in_progress")
    ));
    if let Some(ref r) = state.reason {
        out.push_str(&format!("- **reason**: `{r}`\n"));
    }
    out.push_str(&format!("- **started_at**: {}\n", state.started_at));
    if let Some(ref e) = state.ended_at {
        out.push_str(&format!("- **ended_at**: {e}\n"));
    }
    if state.phase != Phase::Finished {
        out.push_str("\n> Status: **in-progress** (not final).\n");
    }
    out.push_str("\n## Agents\n");
    for agent in state.agents_in_order() {
        out.push_str(&format!("\n### `{}`\n\n", agent.agent_id));
        out.push_str(&format!("- phase: `{}`\n", phase_str(agent.phase)));
        out.push_str(&format!("- mode: `{:?}`\n", agent.mode));
        out.push_str(&format!(
            "- isolation: `{}`\n",
            match agent.isolation {
                crate::task::IsolationMode::CopyIsolation => "copy_isolation",
                crate::task::IsolationMode::Strict => "strict",
            }
        ));
        let (oc, reason) = match &agent.outcome {
            Some(o) => (outcome_kind_str(o.kind()), o.reason_str().unwrap_or("-")),
            None => ("in_progress", "-"),
        };
        out.push_str(&format!("- outcome: `{oc}`\n"));
        out.push_str(&format!("- reason: `{reason}`\n"));
        out.push_str(&format!(
            "- requested: harness=`{}` model=`{}`\n",
            agent.requested.harness,
            agent.requested.model.as_deref().unwrap_or("-")
        ));
        if let Some(ref ex) = agent.executable {
            out.push_str(&format!(
                "- executable: path=`{}` realpath=`{}` version=`{}` trust=`{:?}` hash=`{}`\n",
                ex.path.as_deref().unwrap_or("-"),
                ex.realpath.as_deref().unwrap_or("-"),
                ex.version.as_deref().unwrap_or("-"),
                ex.trust,
                ex.sha256.as_deref().unwrap_or("-")
            ));
        }
        out.push_str(&format!(
            "- observed (claimed/stream): provider=`{}` model=`{}` evidence=`{:?}`\n",
            agent.observed.provider.as_deref().unwrap_or("-"),
            agent.observed.model.as_deref().unwrap_or("-"),
            agent.observed.evidence
        ));
        if let Some(ref g) = agent.identity_gate {
            out.push_str(&format!(
                "- identity_gate: required={} satisfied={} reason=`{}`\n",
                g.required,
                g.satisfied,
                g.reason.as_deref().unwrap_or("-")
            ));
        }
        out.push_str(&format!(
            "- permission_denials: {} (last_tool=`{}`)\n",
            agent.denial_count(),
            agent.last_denied_tool().unwrap_or("-")
        ));
        out.push_str(&format!(
            "- harness_completed: {}\n",
            agent.harness_completed
        ));
        if let Some(ref env) = agent.environment {
            out.push_str(&format!(
                "- environment: home=`{}` host_configuration_exposed={} reproducibility=`{}` allowed_env={:?}\n",
                env.home,
                env.host_configuration_exposed,
                env.reproducibility,
                env.allowed_env_names
            ));
        }
        if let Some(ref gate) = agent.policy_gate {
            out.push_str(&format!(
                "- policy_gate: evaluated={} satisfied={} reason=`{}`\n",
                gate.evaluated,
                gate.satisfied,
                gate.reason.as_deref().unwrap_or("-")
            ));
        }
        out.push_str(&format!(
            "- response truncated: {} (original_bytes={})\n",
            agent.response.truncated, agent.response.original_bytes
        ));
        out.push_str(&format!(
            "- tests: verification=`{}` (self_reported, not verified)\n",
            agent.response.tests.verification
        ));
        out.push_str(&format!(
            "- diagnostics: raw_stdout_truncated={} raw_stderr_truncated={} stdout_total_bytes={} stdout_persisted_bytes={} stderr_total_bytes={} stderr_persisted_bytes={} exit={:?} signal={:?} timeout={} idle_timeout={} cancelled={} duration_ms={:?} descendants_terminated={} unknown_events={} invalid_json={} oversized_events={} events_dropped={}\n",
            agent.diagnostics.raw_stdout_truncated,
            agent.diagnostics.raw_stderr_truncated,
            agent.diagnostics.stdout_total_bytes,
            agent.diagnostics.stdout_persisted_bytes,
            agent.diagnostics.stderr_total_bytes,
            agent.diagnostics.stderr_persisted_bytes,
            agent.diagnostics.exit_code,
            agent.diagnostics.exit_signal,
            agent.diagnostics.timed_out,
            agent.diagnostics.idle_timed_out,
            agent.diagnostics.cancelled,
            agent.diagnostics.duration_ms,
            agent.diagnostics.descendants_terminated,
            agent.diagnostics.unknown_event_count,
            agent.diagnostics.invalid_json_count,
            agent.diagnostics.oversized_event_count,
            agent.diagnostics.events_dropped
        ));
        out.push_str(&format!("- files_changed: {:?}\n", agent.files_changed));
        match &agent.outcome {
            Some(Outcome::Success { patch: Some(p) }) => {
                out.push_str(&format!(
                    "- patch: path=`{}` sha256=`{}`\n",
                    p.path, p.sha256
                ));
            }
            _ => {
                out.push_str("- patch: none\n");
            }
        }
        if !agent.response.summary.is_empty() {
            out.push_str("\n**Response summary**\n\n");
            out.push_str("```\n");
            out.extend(agent.response.summary.chars().take(4000));
            out.push_str("\n```\n");
        }
        out.push_str(
            "\n**Next step**: review result.json; apply patches only after human/parent review.\n",
        );
    }
    out
}

pub fn render_status(state: &RunState) -> String {
    let mut out = String::new();
    out.push_str(&format!(
        "run_id={} revision={} phase={} outcome={}\n",
        state.run_id,
        state.revision,
        phase_str(state.phase),
        state.outcome.map(outcome_kind_str).unwrap_or("in_progress")
    ));
    for agent in state.agents_in_order() {
        let oc = agent
            .outcome
            .as_ref()
            .map(|o| outcome_kind_str(o.kind()))
            .unwrap_or("in_progress");
        out.push_str(&format!(
            "  agent={} phase={} outcome={} denials={} last_denied={}\n",
            agent.agent_id,
            phase_str(agent.phase),
            oc,
            agent.denial_count(),
            agent.last_denied_tool().unwrap_or("-")
        ));
    }
    out
}

pub fn phase_str(p: Phase) -> &'static str {
    match p {
        Phase::Queued => "queued",
        Phase::Preparing => "preparing",
        Phase::Running => "running",
        Phase::Finished => "finished",
    }
}

pub fn outcome_kind_str(o: OutcomeKind) -> &'static str {
    match o {
        OutcomeKind::Success => "success",
        OutcomeKind::Blocked => "blocked",
        OutcomeKind::Failed => "failed",
        OutcomeKind::Cancelled => "cancelled",
    }
}

/// Serialize run state to V3 result.json value.
pub fn run_state_to_json(state: &RunState) -> serde_json::Value {
    let agents: Vec<serde_json::Value> = state
        .agents_in_order()
        .map(|a| {
            let (outcome, reason) = match &a.outcome {
                Some(o) => (
                    Some(outcome_kind_str(o.kind())),
                    o.reason_str().map(str::to_string),
                ),
                None => (None, None),
            };
            let patch = a.outcome.as_ref().and_then(|o| o.patch()).map(|p| {
                serde_json::json!({
                    "path": p.path,
                    "sha256": p.sha256,
                    "files_changed": p.files_changed,
                    "baseline_manifest_sha256": p.baseline_manifest_sha256,
                    "baseline_bundle_sha256": p.baseline_bundle_sha256,
                })
            });
            serde_json::json!({
                "revision": state.revision,
                "agent_id": a.agent_id.as_str(),
                "phase": phase_str(a.phase),
                "mode": match a.mode {
                    crate::task::Mode::ReadOnly => "read_only",
                    crate::task::Mode::PatchOnly => "patch_only",
                },
                "isolation": match a.isolation {
                    crate::task::IsolationMode::CopyIsolation => "copy_isolation",
                    crate::task::IsolationMode::Strict => "strict",
                },
                "outcome": outcome,
                "reason": reason,
                "requested": {
                    "harness": a.requested.harness,
                    "model": a.requested.model,
                },
                "executable": a.executable.as_ref().map(|e| serde_json::json!({
                    "argv0": e.argv0,
                    "path": e.path,
                    "realpath": e.realpath,
                    "sha256": e.sha256,
                    "version": e.version,
                    "version_verified": e.version_verified,
                    "trust": match e.trust {
                        crate::identity::ExecutableTrust::StockAdapter => "stock_adapter",
                        crate::identity::ExecutableTrust::Custom => "custom",
                    },
                })),
                "observed": {
                    "provider": a.observed.provider,
                    "model": a.observed.model,
                    "api_key_source": a.observed.api_key_source,
                    "evidence": a.observed.evidence.map(|e| match e {
                        crate::identity::IdentityEvidence::StreamClaim => "stream_claim",
                        crate::identity::IdentityEvidence::Missing => "missing",
                    }),
                },
                "identity_gate": a.identity_gate.as_ref().map(|g| serde_json::json!({
                    "required": g.required,
                    "satisfied": g.satisfied,
                    "reason": g.reason,
                })),
                "permission_denials": a.permission_denials,
                "harness_completed": a.harness_completed,
                "response": {
                    "summary": a.response.summary,
                    "truncated": a.response.truncated,
                    "original_bytes": a.response.original_bytes,
                    "tests": {
                        "verification": a.response.tests.verification,
                        "items": a.response.tests.items,
                        "results": a.response.tests.results,
                    }
                },
                "workspace": {
                    "files_changed": a.files_changed,
                },
                "environment": a.environment.as_ref().map(|e| serde_json::json!({
                    "home": e.home,
                    "allowed_env_names": e.allowed_env_names,
                    "host_configuration_exposed": e.host_configuration_exposed,
                    "reproducibility": e.reproducibility,
                })),
                "policy_gate": a.policy_gate.as_ref().map(|g| serde_json::json!({
                    "evaluated": g.evaluated,
                    "satisfied": g.satisfied,
                    "reason": g.reason,
                })),
                "patch": patch,
                "diagnostics": {
                    "raw_stdout_truncated": a.diagnostics.raw_stdout_truncated,
                    "raw_stderr_truncated": a.diagnostics.raw_stderr_truncated,
                    "stdout_total_bytes": a.diagnostics.stdout_total_bytes,
                    "stderr_total_bytes": a.diagnostics.stderr_total_bytes,
                    "stdout_persisted_bytes": a.diagnostics.stdout_persisted_bytes,
                    "stderr_persisted_bytes": a.diagnostics.stderr_persisted_bytes,
                    "descendants_terminated": a.diagnostics.descendants_terminated,
                    "exit_code": a.diagnostics.exit_code,
                    "exit_signal": a.diagnostics.exit_signal,
                    "timed_out": a.diagnostics.timed_out,
                    "idle_timed_out": a.diagnostics.idle_timed_out,
                    "cancelled": a.diagnostics.cancelled,
                    "duration_ms": a.diagnostics.duration_ms,
                    "unknown_event_count": a.diagnostics.unknown_event_count,
                    "invalid_json_count": a.diagnostics.invalid_json_count,
                    "oversized_event_count": a.diagnostics.oversized_event_count,
                    "events_dropped": a.diagnostics.events_dropped,
                },
                "started_at": a.started_at,
                "ended_at": a.ended_at,
            })
        })
        .collect();

    serde_json::json!({
        "schema_version": state.schema_version,
        "revision": state.revision,
        "run_id": state.run_id.as_str(),
        "phase": phase_str(state.phase),
        "outcome": state.outcome.map(outcome_kind_str),
        "reason": state.reason,
        "started_at": state.started_at,
        "ended_at": state.ended_at,
        "agents": agents,
    })
}
