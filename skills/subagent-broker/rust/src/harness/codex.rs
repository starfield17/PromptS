//! Codex CLI stream adapter.
//!
//! Capability mapping: V3 keeps stock `sandbox read-only` for read_only mode.
//! Patch/write elevation is intentionally not auto-enabled from capabilities
//! (vendor sandbox is not an OS boundary; parent reviews patches).

use std::path::Path;

use serde_json::Value;

use crate::event::{BoundedChunk, HarnessEvent, HarnessTerminalClaim, SafeToolName, ToolId};
use crate::harness::{ParserDiagnostics, StreamParser};
use crate::identity::{bounded_identity_label, IdentityEvidence, ObservedIdentity};
use crate::task::{AgentSpec, BoundedText};

#[derive(Debug, Clone)]
pub struct CodexAdapter {
    pub model: Option<String>,
}

impl CodexAdapter {
    pub fn new(model: Option<String>) -> Self {
        Self { model }
    }

    pub fn build_argv(&self, agent: &AgentSpec, work_dir: &Path) -> Vec<String> {
        let mut argv = vec![
            "codex".into(),
            "exec".into(),
            "--json".into(),
            "--cd".into(),
            work_dir.display().to_string(),
            "--sandbox".into(),
            match agent.mode {
                crate::task::Mode::ReadOnly => "read-only".into(),
                crate::task::Mode::PatchOnly => "workspace-write".into(),
            },
            "--ephemeral".into(),
        ];
        if let Some(ref m) = self.model {
            argv.push("--model".into());
            argv.push(m.clone());
        }
        argv.push(crate::prompt::render(agent, work_dir));
        argv
    }
}

pub struct CodexParser {
    buf: Vec<u8>,
    max_result_bytes: usize,
    max_event_line_bytes: usize,
    skipping_oversized: bool,
    oversized_bytes: u64,
    saw_terminal: bool,
    diagnostics: ParserDiagnostics,
}

impl CodexParser {
    pub fn new(max_result_bytes: usize, max_event_line_bytes: usize) -> Self {
        Self {
            buf: Vec::new(),
            max_result_bytes,
            max_event_line_bytes,
            skipping_oversized: false,
            oversized_bytes: 0,
            saw_terminal: false,
            diagnostics: ParserDiagnostics::default(),
        }
    }

    fn emit_line(&mut self, line: &[u8]) -> Vec<HarnessEvent> {
        if line.is_empty() {
            return Vec::new();
        }
        let Ok(text) = std::str::from_utf8(line) else {
            self.diagnostics.invalid_json_count =
                self.diagnostics.invalid_json_count.saturating_add(1);
            return Vec::new();
        };
        let Ok(value) = serde_json::from_str::<Value>(text) else {
            self.diagnostics.invalid_json_count =
                self.diagnostics.invalid_json_count.saturating_add(1);
            return Vec::new();
        };
        let event_type = value.get("type").and_then(|v| v.as_str()).unwrap_or("");
        if !matches!(
            event_type,
            "thread.started"
                | "thread.ended"
                | "turn.started"
                | "item.completed"
                | "item.started"
                | "item.updated"
                | "turn.completed"
                | "turn.failed"
                | "error"
                | "permission_denied"
                | "tool.permission_denied"
        ) {
            self.diagnostics.unknown_event_count =
                self.diagnostics.unknown_event_count.saturating_add(1);
        }
        parse_codex_event(&value, self.max_result_bytes, &mut self.saw_terminal)
    }
}

impl StreamParser for CodexParser {
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
            } else if self.buf.len() >= self.max_event_line_bytes {
                self.skipping_oversized = true;
                self.oversized_bytes = self.buf.len() as u64 + 1;
                self.buf.clear();
            } else {
                self.buf.push(b);
            }
        }
        Ok(events)
    }

    fn finish(&mut self) -> Result<Vec<HarnessEvent>, crate::error::StreamError> {
        let mut events = Vec::new();
        if !self.buf.is_empty() {
            let line = std::mem::take(&mut self.buf);
            events.extend(self.emit_line(&line));
        }
        if !self.saw_terminal {
            events.push(HarnessEvent::HarnessResult(HarnessTerminalClaim::Error));
        }
        Ok(events)
    }

    fn diagnostics(&self) -> ParserDiagnostics {
        self.diagnostics
    }
}

fn parse_codex_event(
    value: &Value,
    max_result_bytes: usize,
    saw_terminal: &mut bool,
) -> Vec<HarnessEvent> {
    let mut events = Vec::new();
    let ty = value.get("type").and_then(|v| v.as_str()).unwrap_or("");

    if matches!(ty, "permission_denied" | "tool.permission_denied")
        || value.get("permission_denied").and_then(|v| v.as_bool()) == Some(true)
    {
        let name = value
            .get("tool_name")
            .or_else(|| value.get("tool"))
            .and_then(|v| v.as_str())
            .unwrap_or("unknown");
        let id = value
            .get("tool_use_id")
            .or_else(|| value.get("id"))
            .and_then(|v| v.as_str());
        events.push(HarnessEvent::PermissionDenied {
            id: id.map(ToolId::new),
            name: Some(SafeToolName::new(name)),
        });
    }

    match ty {
        "thread.started" => {
            if let Some(model) = value.get("model").and_then(|v| v.as_str()) {
                events.push(HarnessEvent::IdentityObserved(ObservedIdentity {
                    provider: value
                        .get("provider")
                        .and_then(|v| v.as_str())
                        .map(bounded_identity_label),
                    model: Some(bounded_identity_label(model)),
                    api_key_source: None,
                    evidence: Some(IdentityEvidence::StreamClaim),
                }));
            }
        }
        "item.completed" => {
            let item_type = value
                .get("item")
                .and_then(|i| i.get("type"))
                .and_then(|v| v.as_str())
                .unwrap_or("");
            if item_type == "agent_message" {
                if let Some(t) = value
                    .get("item")
                    .and_then(|i| i.get("text").or_else(|| i.get("content")))
                    .and_then(|v| v.as_str())
                {
                    events.push(HarnessEvent::FinalResult(BoundedChunk {
                        text: BoundedText::with_limit_from_str(t, max_result_bytes),
                    }));
                }
            }
        }
        "turn.completed" => {
            *saw_terminal = true;
            events.push(HarnessEvent::HarnessResult(HarnessTerminalClaim::Success));
        }
        "turn.failed" | "error" => {
            *saw_terminal = true;
            let msg = value
                .get("error")
                .or_else(|| value.get("message"))
                .and_then(|v| v.as_str())
                .unwrap_or("turn failed");
            events.push(HarnessEvent::HarnessError(
                BoundedText::with_limit_from_str(msg, 512),
            ));
            events.push(HarnessEvent::HarnessResult(HarnessTerminalClaim::Error));
        }
        _ => {}
    }
    events
}
