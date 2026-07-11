//! Grok Build stream adapter.

use std::path::Path;

use serde_json::Value;

use crate::event::{BoundedChunk, HarnessEvent, HarnessTerminalClaim, SafeToolName, ToolId};
use crate::harness::{ParserDiagnostics, StreamParser};
use crate::identity::{bounded_identity_label, IdentityEvidence, ObservedIdentity};
use crate::task::{AgentSpec, BoundedText};

#[derive(Debug, Clone)]
pub struct GrokAdapter {
    pub model: Option<String>,
}

impl GrokAdapter {
    pub fn new(model: Option<String>) -> Self {
        Self { model }
    }

    /// Fixed argv — headless single-turn with streaming-json.
    pub fn build_argv(&self, agent: &AgentSpec, work_dir: &Path) -> Vec<String> {
        use crate::capability::grok_allow_rules;

        let mut argv = vec![
            "grok".into(),
            "--cwd".into(),
            work_dir.display().to_string(),
            "--output-format".into(),
            "streaming-json".into(),
            "--permission-mode".into(),
            "dontAsk".into(),
        ];
        for rule in grok_allow_rules(&agent.capabilities) {
            argv.push("--allow".into());
            argv.push(rule);
        }
        if let Some(ref m) = self.model {
            argv.push("--model".into());
            argv.push(m.clone());
        }
        argv.push("--single".into());
        argv.push(crate::prompt::render(agent, work_dir));
        argv
    }
}

pub struct GrokParser {
    buf: Vec<u8>,
    max_result_bytes: usize,
    max_event_line_bytes: usize,
    skipping_oversized: bool,
    oversized_bytes: u64,
    saw_end: bool,
    diagnostics: ParserDiagnostics,
}

impl GrokParser {
    pub fn new(max_result_bytes: usize, max_event_line_bytes: usize) -> Self {
        Self {
            buf: Vec::new(),
            max_result_bytes,
            max_event_line_bytes,
            skipping_oversized: false,
            oversized_bytes: 0,
            saw_end: false,
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
            "thought"
                | "thinking"
                | "text"
                | "message"
                | "tool_use"
                | "tool_result"
                | "permission_denied"
                | "tool_permission_denied"
                | "error"
                | "end"
        ) {
            self.diagnostics.unknown_event_count =
                self.diagnostics.unknown_event_count.saturating_add(1);
        }
        parse_grok_event(&value, self.max_result_bytes, &mut self.saw_end)
    }
}

impl StreamParser for GrokParser {
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
        if !self.saw_end {
            // Missing end is not success.
            events.push(HarnessEvent::HarnessResult(HarnessTerminalClaim::Error));
        }
        Ok(events)
    }

    fn diagnostics(&self) -> ParserDiagnostics {
        self.diagnostics
    }
}

fn parse_grok_event(
    value: &Value,
    max_result_bytes: usize,
    saw_end: &mut bool,
) -> Vec<HarnessEvent> {
    let mut events = Vec::new();
    let ty = value.get("type").and_then(|v| v.as_str()).unwrap_or("");

    if matches!(ty, "permission_denied" | "tool_permission_denied")
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

    if let Some(provider) = value.get("provider").and_then(|v| v.as_str()) {
        events.push(HarnessEvent::IdentityObserved(ObservedIdentity {
            provider: Some(bounded_identity_label(provider)),
            model: value
                .get("model")
                .and_then(|v| v.as_str())
                .map(bounded_identity_label),
            api_key_source: None,
            evidence: Some(IdentityEvidence::StreamClaim),
        }));
    }

    match ty {
        // Never retain thought/thinking content in normalized events.
        "thought" | "thinking" => {}
        "text" | "message" => {
            // Real Grok streaming-json uses {"type":"text","data":"..."}.
            if let Some(t) = value
                .get("data")
                .or_else(|| value.get("text"))
                .or_else(|| value.get("content"))
                .and_then(|v| v.as_str())
            {
                events.push(HarnessEvent::AssistantText(BoundedChunk {
                    text: BoundedText::with_limit_from_str(t, max_result_bytes),
                }));
            }
        }
        "error" => {
            let msg = value
                .get("message")
                .or_else(|| value.get("data"))
                .and_then(|v| v.as_str())
                .unwrap_or("harness error");
            events.push(HarnessEvent::HarnessError(
                BoundedText::with_limit_from_str(msg, 512),
            ));
            events.push(HarnessEvent::HarnessResult(HarnessTerminalClaim::Error));
            *saw_end = true;
        }
        "end" => {
            *saw_end = true;
            if let Some(t) = value
                .get("text")
                .or_else(|| value.get("data"))
                .and_then(|v| v.as_str())
            {
                events.push(HarnessEvent::FinalResult(BoundedChunk {
                    text: BoundedText::with_limit_from_str(t, max_result_bytes),
                }));
            }
            let stop = value
                .get("stopReason")
                .or_else(|| value.get("stop_reason"))
                .and_then(|v| v.as_str())
                .unwrap_or("end");
            let stop_l = bounded_identity_label(stop)
                .to_ascii_lowercase()
                .replace(['_', '-'], "");
            let claim = match stop_l.as_str() {
                "end" | "endturn" | "stop" | "completed" | "success" => {
                    HarnessTerminalClaim::Success
                }
                "cancelled" | "canceled" => HarnessTerminalClaim::Cancelled,
                "maxturn" | "maxturns" => HarnessTerminalClaim::MaxTurns,
                "maxtoken" | "maxtokens" => HarnessTerminalClaim::MaxTokens,
                "refusal" => HarnessTerminalClaim::Refusal,
                other => HarnessTerminalClaim::Other(other.to_string()),
            };
            events.push(HarnessEvent::HarnessResult(claim));
        }
        _ => {}
    }
    events
}

#[cfg(test)]
#[allow(clippy::unwrap_used, clippy::expect_used)]
mod tests {
    use super::*;
    use crate::harness::StreamParser;
    use std::fs;

    #[test]
    fn parses_real_streaming_json_endturn() {
        let path = "tests/fixtures/streams/grok_endturn_success.jsonl";
        let data = fs::read_to_string(path)
            .unwrap_or_else(|_| fs::read_to_string(format!("rust/{path}")).unwrap());
        let mut p = GrokParser::new(4096, 1 << 20);
        let mut evs = p.push(data.as_bytes()).unwrap();
        evs.extend(p.finish().unwrap());
        assert!(evs
            .iter()
            .any(|e| matches!(e, HarnessEvent::AssistantText(_))));
        assert!(evs.iter().any(|e| matches!(
            e,
            HarnessEvent::HarnessResult(HarnessTerminalClaim::Success)
        )));
        // thought content must not surface as assistant/final text with "user wants"
        for e in &evs {
            if let HarnessEvent::AssistantText(c) = e {
                assert!(!c.text.to_string_lossy().contains("user wants"));
            }
        }
    }
}
