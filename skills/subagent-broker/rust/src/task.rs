//! Task packet V3 — strict JSON, deny unknown fields.

use std::collections::HashSet;
use std::path::{Path, PathBuf};

use serde::{Deserialize, Serialize};

use crate::capability::{validate_capabilities, Capability};
use crate::error::{BrokerResult, TaskError};
use crate::identity::IdentityRequirement;

/// Validated run_id: no `.`, `..`, path separators, or empty.
#[derive(Debug, Clone, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(try_from = "String", into = "String")]
pub struct RunId(String);

impl RunId {
    pub fn new(raw: impl Into<String>) -> Result<Self, TaskError> {
        let s = raw.into();
        validate_id(&s, "run_id").map_err(TaskError::InvalidRunId)?;
        Ok(Self(s))
    }

    pub fn as_str(&self) -> &str {
        &self.0
    }
}

impl TryFrom<String> for RunId {
    type Error = TaskError;
    fn try_from(value: String) -> Result<Self, Self::Error> {
        Self::new(value)
    }
}

impl From<RunId> for String {
    fn from(v: RunId) -> Self {
        v.0
    }
}

impl std::fmt::Display for RunId {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.write_str(&self.0)
    }
}

/// Validated agent_id.
#[derive(Debug, Clone, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(try_from = "String", into = "String")]
pub struct AgentId(String);

impl AgentId {
    pub fn new(raw: impl Into<String>) -> Result<Self, TaskError> {
        let s = raw.into();
        validate_id(&s, "agent_id").map_err(TaskError::InvalidAgentId)?;
        Ok(Self(s))
    }

    pub fn as_str(&self) -> &str {
        &self.0
    }
}

impl TryFrom<String> for AgentId {
    type Error = TaskError;
    fn try_from(value: String) -> Result<Self, Self::Error> {
        Self::new(value)
    }
}

impl From<AgentId> for String {
    fn from(v: AgentId) -> Self {
        v.0
    }
}

impl std::fmt::Display for AgentId {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.write_str(&self.0)
    }
}

fn validate_id(s: &str, kind: &str) -> Result<(), String> {
    if s.is_empty() {
        return Err(format!("{kind} must not be empty"));
    }
    if s == "." || s == ".." {
        return Err(format!("{kind} must not be '.' or '..'"));
    }
    if s.contains('/') || s.contains('\\') || s.contains('\0') {
        return Err(format!("{kind} must not contain path separators or NUL"));
    }
    if s.contains("..") {
        return Err(format!("{kind} must not contain '..'"));
    }
    Ok(())
}

/// Repo-relative path: normalized `/`, no `..`, no absolute, no empty segments.
#[derive(Debug, Clone, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(try_from = "String", into = "String")]
pub struct RepoPath(String);

impl RepoPath {
    pub fn new(raw: impl AsRef<str>) -> Result<Self, TaskError> {
        let raw = raw.as_ref().replace('\\', "/");
        if raw.is_empty() {
            return Err(TaskError::InvalidPath("path must not be empty".into()));
        }
        if raw.starts_with('/') {
            return Err(TaskError::InvalidPath(format!(
                "path must be repo-relative, not absolute: {raw}"
            )));
        }
        if raw.as_bytes().get(1) == Some(&b':')
            && raw.as_bytes().first().is_some_and(u8::is_ascii_alphabetic)
        {
            return Err(TaskError::InvalidPath(format!(
                "path must not use a drive prefix: {raw}"
            )));
        }
        if raw.contains('\0') {
            return Err(TaskError::InvalidPath("path must not contain NUL".into()));
        }
        let mut parts = Vec::new();
        for seg in raw.split('/') {
            if seg.is_empty() || seg == "." {
                return Err(TaskError::InvalidPath(format!(
                    "path must not contain empty or '.' segments: {raw}"
                )));
            }
            if seg == ".." {
                return Err(TaskError::InvalidPath(format!(
                    "path must not contain '..': {raw}"
                )));
            }
            parts.push(seg);
        }
        if parts.is_empty() {
            return Err(TaskError::InvalidPath(format!(
                "path resolves empty: {raw}"
            )));
        }
        let normalized = parts.join("/");
        let first = parts[0];
        if first == ".git" || first == ".subagents" || first == "secrets" {
            return Err(TaskError::InvalidPath(format!(
                "path points at denied root: {normalized}"
            )));
        }
        if first.starts_with(".env") {
            return Err(TaskError::InvalidPath(format!(
                "path points at secret-like root: {normalized}"
            )));
        }
        Ok(Self(normalized))
    }

    pub fn as_str(&self) -> &str {
        &self.0
    }

    pub fn as_path(&self) -> &Path {
        Path::new(&self.0)
    }
}

impl TryFrom<String> for RepoPath {
    type Error = TaskError;
    fn try_from(value: String) -> Result<Self, Self::Error> {
        Self::new(value)
    }
}

impl From<RepoPath> for String {
    fn from(v: RepoPath) -> Self {
        v.0
    }
}

impl std::fmt::Display for RepoPath {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.write_str(&self.0)
    }
}

/// Bounded UTF-8 text with entrance-time memory limit.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct BoundedText {
    text: String,
    original_bytes: u64,
    truncated: bool,
}

impl BoundedText {
    pub fn new(_limit: usize) -> Self {
        Self {
            text: String::new(),
            original_bytes: 0,
            truncated: false,
        }
    }

    pub fn with_limit_from_str(s: &str, limit: usize) -> Self {
        let mut t = Self::new(limit);
        t.push_str(s, limit);
        t
    }

    pub fn push_str(&mut self, s: &str, limit: usize) {
        self.original_bytes = self.original_bytes.saturating_add(s.len() as u64);
        self.push_str_bounded(s, limit);
    }

    pub fn push_bytes(&mut self, data: &[u8], limit: usize) {
        self.original_bytes = self.original_bytes.saturating_add(data.len() as u64);
        let text = String::from_utf8_lossy(data);
        self.push_str_bounded(&text, limit);
    }

    pub fn push_bounded(&mut self, other: &BoundedText, limit: usize) {
        let before = self.original_bytes;
        self.push_str_bounded(&other.text, limit);
        self.original_bytes = before.saturating_add(other.original_bytes);
        self.truncated |= other.truncated;
    }

    fn push_str_bounded(&mut self, value: &str, limit: usize) {
        if self.text.len() >= limit {
            self.truncated = true;
            return;
        }
        let remaining = limit - self.text.len();
        if value.len() <= remaining {
            self.text.push_str(value);
            return;
        }
        let mut end = remaining;
        while end > 0 && !value.is_char_boundary(end) {
            end -= 1;
        }
        self.text.push_str(&value[..end]);
        self.truncated = true;
    }

    pub fn as_str(&self) -> &str {
        &self.text
    }

    pub fn to_string_lossy(&self) -> String {
        self.text.clone()
    }

    pub fn raw_bytes(&self) -> &[u8] {
        self.text.as_bytes()
    }

    pub fn truncated(&self) -> bool {
        self.truncated
    }

    pub fn original_bytes(&self) -> u64 {
        self.original_bytes
    }

    pub fn len(&self) -> usize {
        self.text.len()
    }

    pub fn is_empty(&self) -> bool {
        self.text.is_empty()
    }

    pub fn into_string(self) -> String {
        self.text
    }

    pub fn from_captured_bytes(captured: &[u8], original_bytes: u64, limit: usize) -> Self {
        let text = String::from_utf8_lossy(captured);
        let mut value = Self::with_limit_from_str(&text, limit);
        value.original_bytes = original_bytes;
        value.truncated |= original_bytes > value.text.len() as u64;
        value
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Mode {
    ReadOnly,
    PatchOnly,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize, Default)]
#[serde(rename_all = "snake_case")]
pub enum IsolationMode {
    #[default]
    CopyIsolation,
    Strict,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(tag = "kind", rename_all = "snake_case", deny_unknown_fields)]
pub enum HarnessSpec {
    ClaudeCode {
        #[serde(default)]
        model: Option<String>,
    },
    GrokBuild {
        #[serde(default)]
        model: Option<String>,
    },
    CodexCli {
        #[serde(default)]
        model: Option<String>,
    },
    #[serde(rename = "opencode")]
    OpenCode {
        #[serde(default)]
        model: Option<String>,
    },
    Custom {
        executable: PathBuf,
        #[serde(default)]
        args: Vec<String>,
        #[serde(default)]
        stream_family: Option<String>,
    },
    /// Test-only / vertical-slice harness that never spawns a real agent.
    #[cfg(feature = "dev-harness")]
    Fake {
        #[serde(default)]
        model: Option<String>,
        #[serde(default)]
        response_summary: Option<String>,
        #[serde(default)]
        inject_denial: bool,
        #[serde(default)]
        inject_provider: Option<String>,
        #[serde(default)]
        inject_model: Option<String>,
        #[serde(default)]
        exit_code: Option<i32>,
        #[serde(default)]
        sleep_ms: Option<u64>,
        #[serde(default)]
        stream_fixture: Option<String>,
    },
}

impl HarnessSpec {
    pub fn kind_name(&self) -> &'static str {
        match self {
            HarnessSpec::ClaudeCode { .. } => "claude_code",
            HarnessSpec::GrokBuild { .. } => "grok_build",
            HarnessSpec::CodexCli { .. } => "codex_cli",
            HarnessSpec::OpenCode { .. } => "opencode",
            HarnessSpec::Custom { .. } => "custom",
            #[cfg(feature = "dev-harness")]
            HarnessSpec::Fake { .. } => "fake",
        }
    }

    pub fn model(&self) -> Option<&str> {
        match self {
            HarnessSpec::ClaudeCode { model }
            | HarnessSpec::GrokBuild { model }
            | HarnessSpec::CodexCli { model }
            | HarnessSpec::OpenCode { model } => model.as_deref(),
            #[cfg(feature = "dev-harness")]
            HarnessSpec::Fake { model, .. } => model.as_deref(),
            HarnessSpec::Custom { .. } => None,
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case", deny_unknown_fields)]
pub enum HomeMode {
    Isolated,
    Host,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct EnvironmentSpec {
    #[serde(default = "default_home")]
    pub home: HomeMode,
    #[serde(default)]
    pub allowed_env: Vec<String>,
}

fn default_home() -> HomeMode {
    HomeMode::Isolated
}

impl Default for EnvironmentSpec {
    fn default() -> Self {
        Self {
            home: HomeMode::Isolated,
            allowed_env: Vec::new(),
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Limits {
    #[serde(default = "default_timeout_ms")]
    pub timeout_ms: u64,
    #[serde(default = "default_idle_timeout_ms")]
    pub idle_timeout_ms: u64,
    #[serde(default = "default_term_grace_ms")]
    pub term_grace_ms: u64,
    #[serde(default = "default_pipe_grace_ms")]
    pub pipe_grace_ms: u64,
    #[serde(default = "default_max_result_bytes")]
    pub max_result_bytes: u64,
    #[serde(default = "default_max_raw_log_bytes")]
    pub max_raw_log_bytes: u64,
    #[serde(default = "default_max_event_line_bytes")]
    pub max_event_line_bytes: u64,
    #[serde(default = "default_max_workspace_files")]
    pub max_workspace_files: u64,
    #[serde(default = "default_max_workspace_bytes")]
    pub max_workspace_bytes: u64,
    #[serde(default = "default_max_files_changed")]
    pub max_files_changed: u64,
}

fn default_timeout_ms() -> u64 {
    1_800_000
}
fn default_idle_timeout_ms() -> u64 {
    180_000
}
fn default_term_grace_ms() -> u64 {
    1_500
}
fn default_pipe_grace_ms() -> u64 {
    1_000
}
fn default_max_result_bytes() -> u64 {
    262_144
}
fn default_max_raw_log_bytes() -> u64 {
    1_048_576
}
fn default_max_event_line_bytes() -> u64 {
    8_388_608
}
fn default_max_workspace_files() -> u64 {
    25_000
}
fn default_max_workspace_bytes() -> u64 {
    1_073_741_824
}
fn default_max_files_changed() -> u64 {
    50
}

impl Default for Limits {
    fn default() -> Self {
        Self {
            timeout_ms: default_timeout_ms(),
            idle_timeout_ms: default_idle_timeout_ms(),
            term_grace_ms: default_term_grace_ms(),
            pipe_grace_ms: default_pipe_grace_ms(),
            max_result_bytes: default_max_result_bytes(),
            max_raw_log_bytes: default_max_raw_log_bytes(),
            max_event_line_bytes: default_max_event_line_bytes(),
            max_workspace_files: default_max_workspace_files(),
            max_workspace_bytes: default_max_workspace_bytes(),
            max_files_changed: default_max_files_changed(),
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, Default)]
#[serde(deny_unknown_fields)]
pub struct PatchPolicy {
    #[serde(default)]
    pub allow_deletes: bool,
    #[serde(default)]
    pub allow_binary_changes: bool,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct AgentSpec {
    pub id: AgentId,
    pub goal: String,
    pub harness: HarnessSpec,
    pub mode: Mode,
    #[serde(default)]
    pub isolation: IsolationMode,
    #[serde(default = "default_source_root")]
    pub source_root: String,
    #[serde(default)]
    pub allowed_paths: Vec<String>,
    #[serde(default)]
    pub deny_paths: Vec<String>,
    #[serde(default, rename = "requested_permissions", alias = "capabilities")]
    pub capabilities: Vec<Capability>,
    #[serde(default)]
    pub identity: IdentityRequirement,
    #[serde(default)]
    pub environment: EnvironmentSpec,
    #[serde(default)]
    pub limits: Limits,
    #[serde(default)]
    pub patch_policy: PatchPolicy,
    #[serde(default)]
    pub require_patch: bool,
    #[serde(default)]
    pub required_paths: Vec<String>,
    #[serde(default)]
    pub verification: Vec<Vec<String>>,
}

fn default_source_root() -> String {
    ".".into()
}
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ResourceBudget {
    #[serde(default = "default_max_task_bytes")]
    pub max_task_bytes: u64,
    #[serde(default = "default_max_agents")]
    pub max_agents: usize,
    #[serde(default = "default_max_total_goal_bytes")]
    pub max_total_goal_bytes: u64,
    #[serde(default = "default_max_file_bytes")]
    pub max_file_bytes: u64,
    #[serde(default = "default_max_workspace_bytes_after_run")]
    pub max_workspace_bytes_after_run: u64,
    #[serde(default = "default_max_patch_bytes")]
    pub max_patch_bytes: u64,
    #[serde(default = "default_max_normalized_events")]
    pub max_normalized_events: usize,
    #[serde(default = "default_max_events_log_bytes")]
    pub max_events_log_bytes: u64,
}

fn default_max_task_bytes() -> u64 {
    4 * 1024 * 1024
}
fn default_max_agents() -> usize {
    64
}
fn default_max_total_goal_bytes() -> u64 {
    4 * 1024 * 1024
}
fn default_max_file_bytes() -> u64 {
    64 * 1024 * 1024
}
fn default_max_workspace_bytes_after_run() -> u64 {
    1_073_741_824
}
fn default_max_patch_bytes() -> u64 {
    16 * 1024 * 1024
}
fn default_max_normalized_events() -> usize {
    4096
}
fn default_max_events_log_bytes() -> u64 {
    4 * 1024 * 1024
}

impl Default for ResourceBudget {
    fn default() -> Self {
        Self {
            max_task_bytes: default_max_task_bytes(),
            max_agents: default_max_agents(),
            max_total_goal_bytes: default_max_total_goal_bytes(),
            max_file_bytes: default_max_file_bytes(),
            max_workspace_bytes_after_run: default_max_workspace_bytes_after_run(),
            max_patch_bytes: default_max_patch_bytes(),
            max_normalized_events: default_max_normalized_events(),
            max_events_log_bytes: default_max_events_log_bytes(),
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct TaskPacket {
    pub schema_version: u32,
    pub run_id: RunId,
    #[serde(default = "default_max_concurrency")]
    pub max_concurrency: usize,
    #[serde(default)]
    pub resources: ResourceBudget,
    pub agents: Vec<AgentSpec>,
}

fn default_max_concurrency() -> usize {
    2
}

impl TaskPacket {
    const HARD_MAX_TASK_BYTES: u64 = 16 * 1024 * 1024;

    pub fn parse_slice(bytes: &[u8]) -> BrokerResult<Self> {
        let v: serde_json::Value =
            serde_json::from_slice(bytes).map_err(|e| TaskError::InvalidJson(e.to_string()))?;
        match v.get("schema_version") {
            None => return Err(TaskError::MissingSchemaVersion.into()),
            Some(sv) => {
                let n = sv.as_u64().unwrap_or(0) as u32;
                if n != 3 {
                    return Err(TaskError::SchemaVersion(n).into());
                }
            }
        }
        let packet: TaskPacket =
            serde_json::from_value(v).map_err(|e| TaskError::UnknownField(e.to_string()))?;
        packet.validate()?;
        if bytes.len() as u64 > packet.resources.max_task_bytes {
            return Err(TaskError::Other(format!(
                "task packet exceeds configured limit ({} bytes)",
                packet.resources.max_task_bytes
            ))
            .into());
        }
        Ok(packet)
    }

    pub fn parse_str(s: &str) -> BrokerResult<Self> {
        Self::parse_slice(s.as_bytes())
    }

    pub fn load_path(path: &Path) -> BrokerResult<Self> {
        let size = std::fs::metadata(path)
            .map_err(|e| TaskError::Other(format!("stat {}: {e}", path.display())))?
            .len();
        if size > Self::HARD_MAX_TASK_BYTES {
            return Err(TaskError::Other(format!(
                "task packet exceeds hard limit ({} bytes)",
                Self::HARD_MAX_TASK_BYTES
            ))
            .into());
        }
        let bytes = std::fs::read(path)
            .map_err(|e| TaskError::Other(format!("read {}: {e}", path.display())))?;
        let packet = Self::parse_slice(&bytes)?;
        if size > packet.resources.max_task_bytes {
            return Err(TaskError::Other(format!(
                "task packet exceeds configured limit ({} bytes)",
                packet.resources.max_task_bytes
            ))
            .into());
        }
        Ok(packet)
    }

    fn validate(&self) -> Result<(), TaskError> {
        if self.schema_version != 3 {
            return Err(TaskError::SchemaVersion(self.schema_version));
        }
        if self.agents.is_empty() {
            return Err(TaskError::EmptyAgents);
        }
        if self.max_concurrency == 0 {
            return Err(TaskError::Other("max_concurrency must be >= 1".into()));
        }
        let resources = &self.resources;
        if resources.max_task_bytes == 0
            || resources.max_agents == 0
            || resources.max_total_goal_bytes == 0
            || resources.max_file_bytes == 0
            || resources.max_workspace_bytes_after_run == 0
            || resources.max_patch_bytes == 0
            || resources.max_normalized_events == 0
            || resources.max_events_log_bytes == 0
        {
            return Err(TaskError::Other(
                "all resource budget values must be greater than zero".into(),
            ));
        }
        if self.agents.len() > resources.max_agents {
            return Err(TaskError::Other(format!(
                "agent count exceeds configured limit ({})",
                resources.max_agents
            )));
        }
        let total_goal_bytes = self
            .agents
            .iter()
            .map(|agent| agent.goal.len() as u64)
            .sum::<u64>();
        if total_goal_bytes > resources.max_total_goal_bytes {
            return Err(TaskError::Other(format!(
                "total goal bytes exceed configured limit ({})",
                resources.max_total_goal_bytes
            )));
        }
        let mut seen = HashSet::new();
        for agent in &self.agents {
            if !seen.insert(agent.id.as_str().to_string()) {
                return Err(TaskError::DuplicateAgent(agent.id.to_string()));
            }
            validate_capabilities(agent.mode, &agent.capabilities)?;
            crate::capability::validate_provider_permissions(
                agent.harness.kind_name(),
                &agent.capabilities,
            )?;
            if agent.mode == Mode::PatchOnly && agent.allowed_paths.is_empty() {
                return Err(TaskError::Other(
                    "patch_only requires a non-empty allowed_paths set".into(),
                ));
            }
            if agent.goal.len() > 65_536 {
                return Err(TaskError::Other(
                    "goal exceeds 64 KiB prompt/argv safety limit".into(),
                ));
            }
            if agent.harness.model().is_some_and(|model| model.len() > 256) {
                return Err(TaskError::Other("harness model exceeds 256 bytes".into()));
            }
            validate_env_names(&agent.environment.allowed_env)?;
            if let Some(ref hash) = agent.identity.expected_executable_sha256 {
                if hash.len() != 64 || !hash.bytes().all(|b| b.is_ascii_hexdigit()) {
                    return Err(TaskError::Other(
                        "expected_executable_sha256 must be 64 hexadecimal characters".into(),
                    ));
                }
            }
            if let Some(ref path) = agent.identity.expected_executable_realpath {
                if !Path::new(path).is_absolute() {
                    return Err(TaskError::Other(
                        "expected_executable_realpath must be absolute".into(),
                    ));
                }
            }
            if agent
                .identity
                .expected_provider
                .as_ref()
                .is_some_and(|value| value.len() > 256)
                || agent
                    .identity
                    .expected_model_prefix
                    .as_ref()
                    .is_some_and(|value| value.len() > 256)
            {
                return Err(TaskError::Other(
                    "identity provider/model constraints exceed 256 bytes".into(),
                ));
            }
            if [
                agent.limits.timeout_ms,
                agent.limits.idle_timeout_ms,
                agent.limits.term_grace_ms,
                agent.limits.pipe_grace_ms,
                agent.limits.max_result_bytes,
                agent.limits.max_raw_log_bytes,
                agent.limits.max_event_line_bytes,
                agent.limits.max_workspace_files,
                agent.limits.max_workspace_bytes,
                agent.limits.max_files_changed,
            ]
            .contains(&0)
            {
                return Err(TaskError::Other(
                    "all limits must be greater than zero".into(),
                ));
            }
            if agent.source_root != "." {
                let _ = RepoPath::new(&agent.source_root)?;
            }
            for p in &agent.allowed_paths {
                if p != "**" {
                    if p.starts_with('/') || p.contains('\\') {
                        return Err(TaskError::InvalidPath(format!(
                            "allowed_paths must be relative: {p}"
                        )));
                    }
                    if p.split('/').any(|s| s.is_empty() || s == "." || s == "..") {
                        return Err(TaskError::InvalidPath(format!(
                            "allowed_paths must contain canonical segments: {p}"
                        )));
                    }
                }
            }
            for p in &agent.deny_paths {
                if p.starts_with('/')
                    || p.contains('\\')
                    || p.split('/').any(|s| s.is_empty() || s == "." || s == "..")
                {
                    return Err(TaskError::InvalidPath(format!(
                        "deny_paths must use canonical repo-relative segments: {p}"
                    )));
                }
            }
            if agent.require_patch && agent.mode != Mode::PatchOnly {
                return Err(TaskError::Other(
                    "require_patch is only valid in patch_only mode".into(),
                ));
            }
            for path in &agent.required_paths {
                RepoPath::new(path)?;
            }
            if agent.verification.len() > 32 {
                return Err(TaskError::Other(
                    "verification command count exceeds 32".into(),
                ));
            }
            for command in &agent.verification {
                if command.is_empty() {
                    return Err(TaskError::Other(
                        "verification commands must not be empty".into(),
                    ));
                }
                if command.len() > 64 || command.iter().any(|arg| arg.len() > 4096) {
                    return Err(TaskError::Other(
                        "verification command argv exceeds safety limit".into(),
                    ));
                }
            }
            if let HarnessSpec::Custom { executable, .. } = &agent.harness {
                if !executable.is_absolute() {
                    return Err(TaskError::Other(
                        "custom harness executable must be an absolute path".into(),
                    ));
                }
                if agent.identity.required
                    && agent.identity.expected_executable_realpath.is_none()
                    && agent.identity.expected_executable_sha256.is_none()
                {
                    return Err(TaskError::Other(
                        "custom harness with identity.required=true requires expected_executable_realpath or expected_executable_sha256".into(),
                    ));
                }
            }
            if matches!(agent.harness, HarnessSpec::OpenCode { .. })
                && agent.mode == Mode::PatchOnly
            {
                return Err(TaskError::Capability(
                    "opencode is a limited read_only adapter in V3".into(),
                ));
            }
        }
        Ok(())
    }
}

fn validate_env_names(names: &[String]) -> Result<(), TaskError> {
    let mut seen = HashSet::new();
    for name in names {
        if name.is_empty()
            || !name.chars().all(|c| c.is_ascii_alphanumeric() || c == '_')
            || name.chars().next().is_some_and(|c| c.is_ascii_digit())
        {
            return Err(TaskError::EnvName(name.clone()));
        }
        if !seen.insert(name.clone()) {
            continue;
        }
    }
    Ok(())
}

#[cfg(test)]
#[allow(clippy::unwrap_used)]
mod tests {
    use super::*;

    #[test]
    fn rejects_v2_schema() {
        let j = r#"{"schema_version":2,"run_id":"r","agents":[]}"#;
        let err = TaskPacket::parse_str(j).unwrap_err();
        assert!(matches!(
            err,
            crate::error::BrokerError::Task(TaskError::SchemaVersion(2))
        ));
    }

    #[test]
    fn rejects_path_escape_in_id() {
        assert!(RunId::new("../x").is_err());
        assert!(AgentId::new("a/b").is_err());
        assert!(RepoPath::new("../etc/passwd").is_err());
        assert!(RepoPath::new("/abs").is_err());
    }

    #[test]
    fn repo_path_rejects_non_canonical_segments() {
        assert!(RepoPath::new("a//b").is_err());
        assert!(RepoPath::new("a/./b").is_err());
    }

    #[test]
    fn custom_required_identity_needs_executable_constraint() {
        let json = r#"{
          "schema_version":3,"run_id":"r","agents":[{
            "id":"a","goal":"x",
            "harness":{"kind":"custom","executable":"/bin/true"},
            "mode":"read_only","capabilities":["repo_read"],
            "identity":{"required":true}
          }]}
        "#;
        assert!(TaskPacket::parse_str(json).is_err());
    }

    #[test]
    fn opencode_patch_only_is_rejected() {
        let json = r#"{
          "schema_version":3,"run_id":"r","agents":[{
            "id":"a","goal":"x","harness":{"kind":"opencode"},
            "mode":"patch_only","capabilities":["repo_read","patch"]
          }]}
        "#;
        assert!(TaskPacket::parse_str(json).is_err());
    }

    #[test]
    fn patch_only_empty_allowed_paths_is_rejected() {
        let json = r#"{
          "schema_version":3,"run_id":"r","agents":[{
            "id":"a","goal":"x","harness":{"kind":"custom","executable":"/bin/true"},
            "mode":"patch_only","requested_permissions":["repo_read","patch"]
          }]}
        "#;
        assert!(TaskPacket::parse_str(json).is_err());
    }

    #[test]
    fn bounded_text_respects_limit() {
        let mut t = BoundedText::new(5);
        t.push_str("hello world", 5);
        assert_eq!(t.as_str(), "hello");
        assert!(t.truncated());
        assert_eq!(t.original_bytes(), 11);
        assert!(t.len() <= 5);
    }

    #[test]
    fn bounded_text_unicode_no_half_char() {
        // "你" is 3 bytes; limit 4 should not split mid-character into invalid UTF-8.
        let mut t = BoundedText::new(4);
        t.push_str("你好世界", 4);
        let s = t.to_string_lossy();
        assert!(std::str::from_utf8(t.raw_bytes()).is_ok());
        assert_eq!(s, "你");
        assert!(t.len() <= 4);
        assert!(t.truncated());
    }

    #[test]
    fn bounded_text_boundary_cases_keep_complete_utf8() {
        for (input, expected, limit) in [("€X", "€", 3), ("😀X", "", 3), ("😀X", "😀", 4)]
        {
            let mut t = BoundedText::new(limit);
            t.push_str(input, limit);
            assert_eq!(t.as_str(), expected);
            assert!(std::str::from_utf8(t.raw_bytes()).is_ok());
        }
    }

    #[test]
    #[cfg(feature = "dev-harness")]
    fn parses_v3_minimal() {
        let j = r#"{
            "schema_version": 3,
            "run_id": "review-001",
            "agents": [{
                "id": "reviewer",
                "goal": "look",
                "harness": {"kind": "fake", "model": "fake-1", "response_summary": "ok"},
                "mode": "read_only",
                "capabilities": ["repo_read"]
            }]
        }"#;
        let p = TaskPacket::parse_str(j).unwrap();
        assert_eq!(p.run_id.as_str(), "review-001");
        assert_eq!(p.agents.len(), 1);
    }
}
