//! Harness adapters: executable + parser + trust bound together.

pub mod claude;
pub mod codex;
pub mod custom;
pub mod grok;
pub mod opencode;

use std::path::{Path, PathBuf};
use std::process::Stdio;

use crate::error::{BrokerResult, SpawnError};
use crate::event::HarnessEvent;
use crate::identity::{ExecutableIdentity, ExecutableTrust};
use crate::task::{AgentSpec, HarnessSpec};

/// Bundle that binds argv construction, parser, and trust class.
pub enum AdapterBundle {
    Claude(claude::ClaudeAdapter),
    Grok(grok::GrokAdapter),
    Codex(codex::CodexAdapter),
    OpenCode(opencode::OpenCodeAdapter),
    Custom(custom::CustomAdapter),
    #[cfg(feature = "dev-harness")]
    Fake(FakeAdapter),
}

impl AdapterBundle {
    pub fn from_spec(spec: &HarnessSpec) -> BrokerResult<Self> {
        Ok(match spec {
            HarnessSpec::ClaudeCode { model } => {
                AdapterBundle::Claude(claude::ClaudeAdapter::new(model.clone()))
            }
            HarnessSpec::GrokBuild { model } => {
                AdapterBundle::Grok(grok::GrokAdapter::new(model.clone()))
            }
            HarnessSpec::CodexCli { model } => {
                AdapterBundle::Codex(codex::CodexAdapter::new(model.clone()))
            }
            HarnessSpec::OpenCode { model } => {
                AdapterBundle::OpenCode(opencode::OpenCodeAdapter::new(model.clone()))
            }
            HarnessSpec::Custom {
                executable,
                args,
                stream_family,
            } => AdapterBundle::Custom(custom::CustomAdapter::new(
                executable.clone(),
                args.clone(),
                stream_family.clone(),
            )?),
            #[cfg(feature = "dev-harness")]
            HarnessSpec::Fake { .. } => AdapterBundle::Fake(FakeAdapter::from_spec(spec)),
        })
    }

    pub fn trust(&self) -> ExecutableTrust {
        match self {
            AdapterBundle::Custom(_) => ExecutableTrust::Custom,
            #[cfg(feature = "dev-harness")]
            AdapterBundle::Fake(_) => ExecutableTrust::Custom,
            _ => ExecutableTrust::StockAdapter,
        }
    }

    pub fn executable_name(&self) -> &str {
        match self {
            AdapterBundle::Claude(_) => "claude",
            AdapterBundle::Grok(_) => "grok",
            AdapterBundle::Codex(_) => "codex",
            AdapterBundle::OpenCode(_) => "opencode",
            AdapterBundle::Custom(c) => c.executable_display(),
            #[cfg(feature = "dev-harness")]
            AdapterBundle::Fake(_) => "fake-harness",
        }
    }

    pub fn build_argv(&self, agent: &AgentSpec, work_dir: &Path) -> Vec<String> {
        match self {
            AdapterBundle::Claude(a) => a.build_argv(agent, work_dir),
            AdapterBundle::Grok(a) => a.build_argv(agent, work_dir),
            AdapterBundle::Codex(a) => a.build_argv(agent, work_dir),
            AdapterBundle::OpenCode(a) => a.build_argv(agent, work_dir),
            AdapterBundle::Custom(a) => a.build_argv(agent, work_dir),
            #[cfg(feature = "dev-harness")]
            AdapterBundle::Fake(a) => a.build_argv(agent, work_dir),
        }
    }

    pub fn new_parser(
        &self,
        max_result_bytes: usize,
        max_event_line_bytes: usize,
    ) -> Box<dyn StreamParser> {
        match self {
            AdapterBundle::Claude(_) => Box::new(claude::ClaudeParser::new(
                max_result_bytes,
                max_event_line_bytes,
            )),
            AdapterBundle::Grok(_) => Box::new(grok::GrokParser::new(
                max_result_bytes,
                max_event_line_bytes,
            )),
            AdapterBundle::Codex(_) => Box::new(codex::CodexParser::new(
                max_result_bytes,
                max_event_line_bytes,
            )),
            AdapterBundle::OpenCode(_) => Box::new(opencode::OpenCodeParser::new(
                max_result_bytes,
                max_event_line_bytes,
            )),
            AdapterBundle::Custom(c) => c.new_parser(max_result_bytes, max_event_line_bytes),
            #[cfg(feature = "dev-harness")]
            AdapterBundle::Fake(f) => f.new_parser(max_result_bytes, max_event_line_bytes),
        }
    }

    pub fn probe_version(&self) -> Option<String> {
        match self {
            AdapterBundle::Custom(_) => None,
            #[cfg(feature = "dev-harness")]
            AdapterBundle::Fake(_) => None,
            AdapterBundle::Claude(_) => probe_once("claude", &["--version"]),
            AdapterBundle::Grok(_) => probe_once("grok", &["--version"]),
            AdapterBundle::Codex(_) => probe_once("codex", &["--version"]),
            AdapterBundle::OpenCode(_) => probe_once("opencode", &["--version"]),
        }
    }

    pub fn resolve_executable_identity(&self) -> ExecutableIdentity {
        let argv0 = self.executable_name().to_string();
        let path = which(&argv0);
        let realpath = path.as_ref().and_then(|p| std::fs::canonicalize(p).ok());
        let sha256 = realpath.as_ref().and_then(|p| file_sha256(p).ok());
        let version = self.probe_version();
        let version_verified = match self.trust() {
            ExecutableTrust::StockAdapter => version.is_some(),
            ExecutableTrust::Custom => true,
        };
        ExecutableIdentity {
            argv0,
            path: path.map(|p| p.display().to_string()),
            realpath: realpath.map(|p| p.display().to_string()),
            sha256,
            version,
            version_verified,
            trust: self.trust(),
        }
    }
}

pub trait StreamParser: Send {
    fn push(&mut self, data: &[u8]) -> Result<Vec<HarnessEvent>, crate::error::StreamError>;
    fn finish(&mut self) -> Result<Vec<HarnessEvent>, crate::error::StreamError>;

    fn diagnostics(&self) -> ParserDiagnostics {
        ParserDiagnostics::default()
    }
}

#[derive(Debug, Clone, Copy, Default)]
pub struct ParserDiagnostics {
    pub unknown_event_count: u64,
    pub invalid_json_count: u64,
    pub oversized_event_count: u64,
}

fn probe_once(exe: &str, args: &[&str]) -> Option<String> {
    let output = std::process::Command::new(exe)
        .args(args)
        .stdin(Stdio::null())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .output()
        .ok()?;
    let mut text = String::from_utf8_lossy(&output.stdout).to_string();
    if text.trim().is_empty() {
        text = String::from_utf8_lossy(&output.stderr).to_string();
    }
    let line = text.lines().next().unwrap_or("").trim();
    if line.is_empty() {
        None
    } else {
        Some(line.chars().take(256).collect())
    }
}

fn which(name: &str) -> Option<PathBuf> {
    if name.contains('/') {
        let p = PathBuf::from(name);
        return if p.exists() { Some(p) } else { None };
    }
    let path = std::env::var_os("PATH")?;
    for dir in std::env::split_paths(&path) {
        let candidate = dir.join(name);
        if candidate.is_file() {
            return Some(candidate);
        }
    }
    None
}

fn file_sha256(path: &Path) -> Result<String, std::io::Error> {
    use sha2::{Digest, Sha256};
    use std::io::Read;
    let mut f = std::fs::File::open(path)?;
    let mut hasher = Sha256::new();
    let mut buf = [0u8; 8192];
    loop {
        let n = f.read(&mut buf)?;
        if n == 0 {
            break;
        }
        hasher.update(&buf[..n]);
    }
    Ok(hex::encode(hasher.finalize()))
}

/// Fake harness for vertical-slice tests — no real agent spawn when stream is synthetic.
#[cfg(feature = "dev-harness")]
#[derive(Debug, Clone)]
pub struct FakeAdapter {
    pub response_summary: String,
    pub inject_denial: bool,
    pub inject_provider: Option<String>,
    pub inject_model: Option<String>,
    pub exit_code: i32,
    pub sleep_ms: u64,
    pub stream_fixture: Option<String>,
}

#[cfg(feature = "dev-harness")]
impl FakeAdapter {
    pub fn from_spec(spec: &HarnessSpec) -> Self {
        match spec {
            HarnessSpec::Fake {
                response_summary,
                inject_denial,
                inject_provider,
                inject_model,
                exit_code,
                sleep_ms,
                stream_fixture,
                ..
            } => Self {
                response_summary: response_summary
                    .clone()
                    .unwrap_or_else(|| "fake completed".into()),
                inject_denial: *inject_denial,
                inject_provider: inject_provider.clone(),
                inject_model: inject_model.clone(),
                exit_code: exit_code.unwrap_or(0),
                sleep_ms: sleep_ms.unwrap_or(0),
                stream_fixture: stream_fixture.clone(),
            },
            _ => Self {
                response_summary: "fake completed".into(),
                inject_denial: false,
                inject_provider: None,
                inject_model: None,
                exit_code: 0,
                sleep_ms: 0,
                stream_fixture: None,
            },
        }
    }

    pub fn build_argv(&self, _agent: &AgentSpec, _work_dir: &Path) -> Vec<String> {
        // Not used for in-process fake; supervisor uses run_fake instead.
        vec!["fake-harness".into()]
    }

    pub fn new_parser(
        &self,
        max_result_bytes: usize,
        max_event_line_bytes: usize,
    ) -> Box<dyn StreamParser> {
        // Fake may replay Claude fixtures.
        Box::new(claude::ClaudeParser::new(
            max_result_bytes,
            max_event_line_bytes,
        ))
    }

    /// Produce normalized events without spawning.
    pub fn synthesize_events(&self, max_result_bytes: usize) -> Vec<HarnessEvent> {
        use crate::event::{BoundedChunk, SafeToolName, ToolId};
        use crate::identity::{IdentityEvidence, ObservedIdentity};
        use crate::task::BoundedText;

        let mut events = Vec::new();
        if let (Some(p), Some(m)) = (&self.inject_provider, &self.inject_model) {
            events.push(HarnessEvent::IdentityObserved(ObservedIdentity {
                provider: Some(p.clone()),
                model: Some(m.clone()),
                api_key_source: None,
                evidence: Some(IdentityEvidence::StreamClaim),
            }));
        } else if let Some(p) = &self.inject_provider {
            events.push(HarnessEvent::IdentityObserved(ObservedIdentity {
                provider: Some(p.clone()),
                model: self.inject_model.clone(),
                api_key_source: None,
                evidence: Some(IdentityEvidence::StreamClaim),
            }));
        }
        if self.inject_denial {
            events.push(HarnessEvent::PermissionDenied {
                id: Some(ToolId::new("fake-deny")),
                name: Some(SafeToolName::new("Bash")),
            });
        }
        events.push(HarnessEvent::FinalResult(BoundedChunk {
            text: BoundedText::with_limit_from_str(&self.response_summary, max_result_bytes),
        }));
        events.push(HarnessEvent::HarnessResult(
            crate::event::HarnessTerminalClaim::Success,
        ));
        events
    }
}

/// Resolve which binary path would be used; error if stock missing (except fake).
pub fn require_executable(bundle: &AdapterBundle) -> BrokerResult<PathBuf> {
    match bundle {
        #[cfg(feature = "dev-harness")]
        AdapterBundle::Fake(_) => Ok(PathBuf::from("fake-harness")),
        AdapterBundle::Custom(c) => {
            #[cfg(unix)]
            let executable = {
                use std::os::unix::fs::PermissionsExt;
                c.executable
                    .metadata()
                    .map(|meta| meta.is_file() && meta.permissions().mode() & 0o111 != 0)
                    .unwrap_or(false)
            };
            #[cfg(not(unix))]
            let executable = c.executable.is_file();
            if executable {
                Ok(c.executable.clone())
            } else {
                Err(SpawnError::NotFound(c.executable.display().to_string()).into())
            }
        }
        _ => {
            let name = bundle.executable_name();
            which(name).ok_or_else(|| SpawnError::NotFound(name.to_string()).into())
        }
    }
}
