//! OpenCode limited adapter — plain final output only.

use std::path::Path;

use crate::event::{BoundedChunk, HarnessEvent, HarnessTerminalClaim};
use crate::harness::StreamParser;
use crate::task::{AgentSpec, BoundedText};

#[derive(Debug, Clone)]
pub struct OpenCodeAdapter {
    pub model: Option<String>,
}

impl OpenCodeAdapter {
    pub fn new(model: Option<String>) -> Self {
        Self { model }
    }

    pub fn build_argv(&self, agent: &AgentSpec, work_dir: &Path) -> Vec<String> {
        let mut argv = vec![
            "opencode".into(),
            "run".into(),
            "--pure".into(),
            "--dir".into(),
            work_dir.display().to_string(),
            "--format".into(),
            "default".into(),
        ];
        if let Some(ref m) = self.model {
            argv.push("--model".into());
            argv.push(m.clone());
        }
        argv.push("--".into());
        argv.push(crate::prompt::render(agent, work_dir));
        argv
    }
}

/// Limited: accumulates plain text; no structured identity.
pub struct OpenCodeParser {
    buf: Vec<u8>,
    max_result_bytes: usize,
    total: u64,
}

impl OpenCodeParser {
    pub fn new(max_result_bytes: usize, _max_event_line_bytes: usize) -> Self {
        Self {
            buf: Vec::new(),
            max_result_bytes,
            total: 0,
        }
    }
}

impl StreamParser for OpenCodeParser {
    fn push(&mut self, data: &[u8]) -> Result<Vec<HarnessEvent>, crate::error::StreamError> {
        self.total = self.total.saturating_add(data.len() as u64);
        let remaining = self.max_result_bytes.saturating_sub(self.buf.len());
        if remaining > 0 {
            let take = remaining.min(data.len());
            self.buf.extend_from_slice(&data[..take]);
        }
        Ok(Vec::new())
    }

    fn finish(&mut self) -> Result<Vec<HarnessEvent>, crate::error::StreamError> {
        let bt = BoundedText::from_captured_bytes(&self.buf, self.total, self.max_result_bytes);
        Ok(vec![
            HarnessEvent::FinalResult(BoundedChunk { text: bt }),
            HarnessEvent::HarnessResult(HarnessTerminalClaim::Success),
        ])
    }
}
