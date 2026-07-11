//! Claude Code stream-json adapter and incremental parser.

use std::path::Path;

use serde_json::Value;

use crate::event::{BoundedChunk, HarnessEvent, HarnessTerminalClaim, SafeToolName, ToolId};
use crate::harness::{ParserDiagnostics, StreamParser};
use crate::identity::{bounded_identity_label, IdentityEvidence, ObservedIdentity};
use crate::task::{AgentSpec, BoundedText};

#[derive(Debug, Clone)]
pub struct ClaudeAdapter {
    pub model: Option<String>,
}

impl ClaudeAdapter {
    pub fn new(model: Option<String>) -> Self {
        Self { model }
    }

    /// Fixed argv — no caller override of stock adapter.
    pub fn build_argv(&self, agent: &AgentSpec, work_dir: &Path) -> Vec<String> {
        use crate::capability::{claude_tool_names, claude_tool_rules};

        let tools = claude_tool_names(&agent.capabilities);
        let allowed = claude_tool_rules(&agent.capabilities);
        let mut argv = vec![
            "claude".into(),
            "--print".into(),
            "--output-format".into(),
            "stream-json".into(),
            "--verbose".into(),
            "--permission-mode".into(),
            "acceptEdits".into(),
            "--tools".into(),
            tools.join(","),
            "--allowedTools".into(),
            allowed.join(","),
        ];
        if let Some(ref m) = self.model {
            argv.push("--model".into());
            argv.push(m.clone());
        }
        argv.push(crate::prompt::render(agent, work_dir));
        argv
    }
}

pub struct ClaudeParser {
    buf: Vec<u8>,
    max_result_bytes: usize,
    max_event_line_bytes: usize,
    skipping_oversized: bool,
    oversized_bytes: u64,
    diagnostics: ParserDiagnostics,
}

impl ClaudeParser {
    pub fn new(max_result_bytes: usize, max_event_line_bytes: usize) -> Self {
        Self {
            buf: Vec::new(),
            max_result_bytes,
            max_event_line_bytes,
            skipping_oversized: false,
            oversized_bytes: 0,
            diagnostics: ParserDiagnostics::default(),
        }
    }

    fn emit_line(&mut self, line: &[u8]) -> Vec<HarnessEvent> {
        if line.is_empty() {
            return Vec::new();
        }
        let text = match std::str::from_utf8(line) {
            Ok(t) => t,
            Err(_) => {
                return vec![HarnessEvent::HarnessError(
                    BoundedText::with_limit_from_str("invalid utf-8 in stream line", 256),
                )];
            }
        };
        let value: Value = match serde_json::from_str(text) {
            Ok(v) => v,
            Err(_) => {
                self.diagnostics.invalid_json_count =
                    self.diagnostics.invalid_json_count.saturating_add(1);
                // Invalid JSON line — record but continue (fixture: invalid line).
                return Vec::new();
            }
        };
        let event_type = value.get("type").and_then(|v| v.as_str()).unwrap_or("");
        if !matches!(event_type, "system" | "assistant" | "user" | "result") {
            self.diagnostics.unknown_event_count =
                self.diagnostics.unknown_event_count.saturating_add(1);
        }
        parse_claude_event(&value, self.max_result_bytes)
    }
}

impl StreamParser for ClaudeParser {
    fn push(&mut self, data: &[u8]) -> Result<Vec<HarnessEvent>, crate::error::StreamError> {
        let mut events = Vec::new();
        for &b in data {
            if self.skipping_oversized {
                self.oversized_bytes += 1;
                if b == b'\n' {
                    events.push(HarnessEvent::OversizedEventSkipped {
                        bytes: self.oversized_bytes,
                    });
                    self.diagnostics.oversized_event_count =
                        self.diagnostics.oversized_event_count.saturating_add(1);
                    self.skipping_oversized = false;
                    self.oversized_bytes = 0;
                }
                continue;
            }
            if b == b'\n' {
                let line = std::mem::take(&mut self.buf);
                events.extend(self.emit_line(&line));
            } else {
                if self.buf.len() >= self.max_event_line_bytes {
                    self.skipping_oversized = true;
                    self.oversized_bytes = self.buf.len() as u64 + 1;
                    self.buf.clear();
                    continue;
                }
                self.buf.push(b);
            }
        }
        Ok(events)
    }

    fn finish(&mut self) -> Result<Vec<HarnessEvent>, crate::error::StreamError> {
        let mut events = Vec::new();
        if self.skipping_oversized {
            events.push(HarnessEvent::OversizedEventSkipped {
                bytes: self.oversized_bytes,
            });
            self.diagnostics.oversized_event_count =
                self.diagnostics.oversized_event_count.saturating_add(1);
            self.skipping_oversized = false;
        }
        if !self.buf.is_empty() {
            let line = std::mem::take(&mut self.buf);
            events.extend(self.emit_line(&line));
        }
        Ok(events)
    }

    fn diagnostics(&self) -> ParserDiagnostics {
        self.diagnostics
    }
}

fn parse_claude_event(value: &Value, max_result_bytes: usize) -> Vec<HarnessEvent> {
    let mut events = Vec::new();
    let ty = value.get("type").and_then(|v| v.as_str()).unwrap_or("");

    match ty {
        "system" => {
            let subtype = value.get("subtype").and_then(|v| v.as_str()).unwrap_or("");
            if subtype == "init" {
                let provider = value
                    .get("provider")
                    .and_then(|v| v.as_str())
                    .map(bounded_identity_label);
                let model = value
                    .get("model")
                    .and_then(|v| v.as_str())
                    .map(bounded_identity_label);
                let api_key_source = value
                    .get("apiKeySource")
                    .and_then(|v| v.as_str())
                    .map(bounded_identity_label);
                if provider.is_some() || model.is_some() {
                    events.push(HarnessEvent::IdentityObserved(ObservedIdentity {
                        provider,
                        model,
                        api_key_source,
                        evidence: Some(IdentityEvidence::StreamClaim),
                    }));
                }
            }
        }
        "assistant" => {
            if let Some(msg) = value.get("message") {
                if let Some(model) = msg.get("model").and_then(|v| v.as_str()) {
                    events.push(HarnessEvent::IdentityObserved(ObservedIdentity {
                        provider: None,
                        model: Some(bounded_identity_label(model)),
                        api_key_source: None,
                        evidence: Some(IdentityEvidence::StreamClaim),
                    }));
                }
                if let Some(content) = msg.get("content").and_then(|v| v.as_array()) {
                    for part in content {
                        let ptype = part.get("type").and_then(|v| v.as_str()).unwrap_or("");
                        match ptype {
                            "text" => {
                                if let Some(t) = part.get("text").and_then(|v| v.as_str()) {
                                    events.push(HarnessEvent::AssistantText(BoundedChunk {
                                        text: BoundedText::with_limit_from_str(t, max_result_bytes),
                                    }));
                                }
                            }
                            "tool_use" => {
                                let id =
                                    part.get("id").and_then(|v| v.as_str()).unwrap_or("unknown");
                                let name = part
                                    .get("name")
                                    .and_then(|v| v.as_str())
                                    .unwrap_or("unknown");
                                // Never retain tool input.
                                events.push(HarnessEvent::ToolStarted {
                                    id: ToolId::new(id),
                                    name: SafeToolName::new(name),
                                });
                            }
                            _ => {}
                        }
                    }
                }
            }
        }
        "user" => {
            // tool_result metadata only — drop content.
            if let Some(msg) = value.get("message") {
                if let Some(content) = msg.get("content").and_then(|v| v.as_array()) {
                    for part in content {
                        if part.get("type").and_then(|v| v.as_str()) == Some("tool_result") {
                            let id = part
                                .get("tool_use_id")
                                .and_then(|v| v.as_str())
                                .unwrap_or("unknown");
                            let is_error = part
                                .get("is_error")
                                .and_then(|v| v.as_bool())
                                .unwrap_or(false);
                            events.push(HarnessEvent::ToolFinished {
                                id: ToolId::new(id),
                                is_error,
                            });
                        }
                    }
                }
            }
        }
        "result" => {
            // permission_denials force blocked regardless of subtype success.
            if let Some(denials) = value.get("permission_denials").and_then(|v| v.as_array()) {
                for d in denials {
                    let name = d
                        .get("tool_name")
                        .and_then(|v| v.as_str())
                        .unwrap_or("unknown");
                    let id = d.get("tool_use_id").and_then(|v| v.as_str());
                    events.push(HarnessEvent::PermissionDenied {
                        id: id.map(ToolId::new),
                        name: Some(SafeToolName::new(name)),
                    });
                }
            }
            if let Some(model) = value.get("model").and_then(|v| v.as_str()) {
                events.push(HarnessEvent::IdentityObserved(ObservedIdentity {
                    provider: None,
                    model: Some(bounded_identity_label(model)),
                    api_key_source: None,
                    evidence: Some(IdentityEvidence::StreamClaim),
                }));
            }
            if let Some(result) = value.get("result").and_then(|v| v.as_str()) {
                let mut bt = BoundedText::new(max_result_bytes);
                bt.push_str(result, max_result_bytes);
                // Hard fail if final result exceeds budget.
                if bt.truncated() && bt.original_bytes() as usize > max_result_bytes {
                    events.push(HarnessEvent::FinalResult(BoundedChunk { text: bt }));
                    events.push(HarnessEvent::HarnessResult(HarnessTerminalClaim::Error));
                    return events;
                }
                events.push(HarnessEvent::FinalResult(BoundedChunk { text: bt }));
            }
            let subtype = value.get("subtype").and_then(|v| v.as_str()).unwrap_or("");
            let is_error = value
                .get("is_error")
                .and_then(|v| v.as_bool())
                .unwrap_or(false);
            let claim = if is_error {
                HarnessTerminalClaim::Error
            } else if subtype == "success" {
                HarnessTerminalClaim::Success
            } else if subtype.contains("cancel") {
                HarnessTerminalClaim::Cancelled
            } else {
                HarnessTerminalClaim::Other(bounded_identity_label(subtype))
            };
            events.push(HarnessEvent::HarnessResult(claim));
        }
        _ => {
            // unknown future event — ignore
        }
    }
    events
}

#[cfg(test)]
#[allow(clippy::unwrap_used, clippy::expect_used)]
mod tests {
    use super::*;
    use std::fs;

    fn fixture(name: &str) -> String {
        let path = format!("tests/fixtures/streams/{name}");
        fs::read_to_string(&path).unwrap_or_else(|_| {
            // when running from workspace root
            fs::read_to_string(format!("rust/tests/fixtures/streams/{name}")).unwrap()
        })
    }

    #[test]
    fn success_with_identity() {
        let data = fixture("success_with_identity.jsonl");
        let mut p = ClaudeParser::new(1 << 20, 1 << 22);
        let mut evs = p.push(data.as_bytes()).unwrap();
        evs.extend(p.finish().unwrap());
        assert!(evs
            .iter()
            .any(|e| matches!(e, HarnessEvent::IdentityObserved(_))));
        assert!(evs.iter().any(|e| matches!(
            e,
            HarnessEvent::HarnessResult(HarnessTerminalClaim::Success)
        )));
        assert!(evs
            .iter()
            .any(|e| matches!(e, HarnessEvent::FinalResult(_))));
    }

    #[test]
    fn denial_emitted_even_if_success_claim() {
        let data = fixture("denial_with_success_claim.jsonl");
        let mut p = ClaudeParser::new(1 << 20, 1 << 22);
        let mut evs = p.push(data.as_bytes()).unwrap();
        evs.extend(p.finish().unwrap());
        assert!(evs
            .iter()
            .any(|e| matches!(e, HarnessEvent::PermissionDenied { .. })));
        assert!(evs.iter().any(|e| matches!(
            e,
            HarnessEvent::HarnessResult(HarnessTerminalClaim::Success)
        )));
    }

    #[test]
    fn identity_mismatch_fixture_observes_xai() {
        let data = fixture("identity_mismatch_grok_as_claude.jsonl");
        let mut p = ClaudeParser::new(1 << 20, 1 << 22);
        let mut evs = p.push(data.as_bytes()).unwrap();
        evs.extend(p.finish().unwrap());
        let mut saw_xai = false;
        for e in &evs {
            if let HarnessEvent::IdentityObserved(o) = e {
                if o.provider.as_deref() == Some("xai") {
                    saw_xai = true;
                }
            }
        }
        assert!(saw_xai);
    }

    #[test]
    fn argv_repo_read_excludes_edit() {
        use crate::capability::Capability;
        use crate::identity::IdentityRequirement;
        use crate::task::{
            AgentId, EnvironmentSpec, HarnessSpec, IsolationMode, Limits, Mode, PatchPolicy,
        };

        let agent = AgentSpec {
            id: AgentId::new("a").unwrap(),
            goal: "g".into(),
            harness: HarnessSpec::ClaudeCode {
                model: Some("m".into()),
            },
            mode: Mode::ReadOnly,
            isolation: IsolationMode::CopyIsolation,
            source_root: ".".into(),
            allowed_paths: vec!["**".into()],
            deny_paths: vec![],
            capabilities: vec![Capability::RepoRead],
            identity: IdentityRequirement::default(),
            environment: EnvironmentSpec::default(),
            limits: Limits::default(),
            patch_policy: PatchPolicy::default(),
            require_patch: false,
            required_paths: Vec::new(),
            verification: Vec::new(),
        };
        let argv = ClaudeAdapter::new(None).build_argv(&agent, Path::new("/tmp"));
        let allowed = argv
            .windows(2)
            .find(|w| w[0] == "--allowedTools")
            .map(|w| w[1].as_str())
            .unwrap_or("");
        assert!(allowed.contains("Read"), "allowed={allowed}");
        assert!(
            !allowed.split(',').any(|t| t == "Edit" || t == "Write"),
            "allowed={allowed}"
        );
    }

    #[test]
    fn argv_patch_includes_edit() {
        use crate::capability::Capability;
        use crate::identity::IdentityRequirement;
        use crate::task::{
            AgentId, EnvironmentSpec, HarnessSpec, IsolationMode, Limits, Mode, PatchPolicy,
        };

        let agent = AgentSpec {
            id: AgentId::new("a").unwrap(),
            goal: "g".into(),
            harness: HarnessSpec::ClaudeCode { model: None },
            mode: Mode::PatchOnly,
            isolation: IsolationMode::CopyIsolation,
            source_root: ".".into(),
            allowed_paths: vec!["**".into()],
            deny_paths: vec![],
            capabilities: vec![Capability::RepoRead, Capability::Patch],
            identity: IdentityRequirement::default(),
            environment: EnvironmentSpec::default(),
            limits: Limits::default(),
            patch_policy: PatchPolicy::default(),
            require_patch: false,
            required_paths: Vec::new(),
            verification: Vec::new(),
        };
        let argv = ClaudeAdapter::new(None).build_argv(&agent, Path::new("/tmp"));
        let allowed = argv
            .windows(2)
            .find(|w| w[0] == "--allowedTools")
            .map(|w| w[1].as_str())
            .unwrap_or("");
        assert!(allowed.split(',').any(|t| t == "Edit"), "allowed={allowed}");
        assert!(
            allowed.split(',').any(|t| t == "Write"),
            "allowed={allowed}"
        );
    }
}
