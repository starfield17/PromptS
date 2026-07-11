//! Custom harness — never auto-bound to stock parsers.

use std::path::{Path, PathBuf};

use crate::error::{BrokerResult, TaskError};
use crate::event::{BoundedChunk, HarnessEvent, HarnessTerminalClaim};
use crate::harness::{claude, StreamParser};
use crate::task::{AgentSpec, BoundedText};

#[derive(Debug, Clone)]
pub struct CustomAdapter {
    pub executable: PathBuf,
    pub args: Vec<String>,
    pub stream_family: Option<String>,
}

impl CustomAdapter {
    pub fn new(
        executable: PathBuf,
        args: Vec<String>,
        stream_family: Option<String>,
    ) -> BrokerResult<Self> {
        if !executable.is_absolute() {
            return Err(
                TaskError::Other("custom harness executable must be absolute".into()).into(),
            );
        }
        if let Some(ref fam) = stream_family {
            match fam.as_str() {
                "plain" | "claude_stream_json" => {}
                other => {
                    return Err(TaskError::Other(format!(
                        "unsupported custom stream_family: {other} (use plain or claude_stream_json)"
                    ))
                    .into());
                }
            }
        }
        Ok(Self {
            executable,
            args,
            stream_family,
        })
    }

    pub fn executable_display(&self) -> &str {
        self.executable.to_str().unwrap_or("custom-harness")
    }

    pub fn build_argv(&self, agent: &AgentSpec, work_dir: &Path) -> Vec<String> {
        let mut argv = vec![self.executable.display().to_string()];
        argv.extend(self.args.iter().cloned());
        // The full canonical prompt is passed as one argument; validation
        // rejects packets large enough to threaten ARG_MAX.
        argv.push(crate::prompt::render(agent, work_dir));
        argv
    }

    pub fn new_parser(
        &self,
        max_result_bytes: usize,
        max_event_line_bytes: usize,
    ) -> Box<dyn StreamParser> {
        match self.stream_family.as_deref() {
            Some("claude_stream_json") => Box::new(claude::ClaudeParser::new(
                max_result_bytes,
                max_event_line_bytes,
            )),
            _ => Box::new(PlainParser::new(max_result_bytes)),
        }
    }
}

struct PlainParser {
    buf: Vec<u8>,
    max_result_bytes: usize,
    total: u64,
}

impl PlainParser {
    fn new(max_result_bytes: usize) -> Self {
        Self {
            buf: Vec::new(),
            max_result_bytes,
            total: 0,
        }
    }
}

impl StreamParser for PlainParser {
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
        Ok(vec![
            HarnessEvent::FinalResult(BoundedChunk {
                text: BoundedText::from_captured_bytes(
                    &self.buf,
                    self.total,
                    self.max_result_bytes,
                ),
            }),
            HarnessEvent::HarnessResult(HarnessTerminalClaim::Success),
        ])
    }
}
