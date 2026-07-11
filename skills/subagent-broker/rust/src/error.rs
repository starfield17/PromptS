//! Closed error model for the broker.

use thiserror::Error;

pub type BrokerResult<T> = Result<T, BrokerError>;

#[derive(Debug, Error)]
pub enum BrokerError {
    #[error("task error: {0}")]
    Task(#[from] TaskError),
    #[error("workspace error: {0}")]
    Workspace(#[from] WorkspaceError),
    #[error("git error: {0}")]
    Git(#[from] GitError),
    #[error("spawn error: {0}")]
    Spawn(#[from] SpawnError),
    #[error("stream error: {0}")]
    Stream(#[from] StreamError),
    #[error("persistence error: {0}")]
    Persistence(#[from] PersistenceError),
    #[error("policy error: {0}")]
    Policy(#[from] PolicyError),
    #[error("unsupported platform")]
    UnsupportedPlatform,
    #[error("cli error: {0}")]
    Cli(String),
    #[error("internal error: {0}")]
    Internal(String),
}

#[derive(Debug, Error)]
pub enum TaskError {
    #[error("schema_version must be 3 (got {0}); migrate V1/V2 packets offline")]
    SchemaVersion(u32),
    #[error("missing schema_version; V3 requires schema_version=3")]
    MissingSchemaVersion,
    #[error("invalid JSON: {0}")]
    InvalidJson(String),
    #[error("unknown field or invalid shape: {0}")]
    UnknownField(String),
    #[error("invalid run_id: {0}")]
    InvalidRunId(String),
    #[error("invalid agent_id: {0}")]
    InvalidAgentId(String),
    #[error("invalid path: {0}")]
    InvalidPath(String),
    #[error("invalid capability combination: {0}")]
    Capability(String),
    #[error("invalid environment name: {0}")]
    EnvName(String),
    #[error("no agents in task packet")]
    EmptyAgents,
    #[error("duplicate agent id: {0}")]
    DuplicateAgent(String),
    #[error("{0}")]
    Other(String),
}

#[derive(Debug, Error)]
pub enum WorkspaceError {
    #[error("{0}")]
    Message(String),
}

#[derive(Debug, Error)]
pub enum GitError {
    #[error("{0}")]
    Message(String),
}

#[derive(Debug, Error)]
pub enum SpawnError {
    #[error("command not found: {0}")]
    NotFound(String),
    #[error("spawn failed: {0}")]
    Failed(String),
    #[error("platform does not support process groups")]
    ProcessGroup,
}

#[derive(Debug, Error)]
pub enum StreamError {
    #[error("invalid stream: {0}")]
    Invalid(String),
    #[error("response truncated")]
    Truncated,
    #[error("oversized event line ({0} bytes)")]
    OversizedLine(u64),
}

#[derive(Debug, Error)]
pub enum PersistenceError {
    #[error("io: {0}")]
    Io(String),
    #[error("run lock held by another process: {0}")]
    LockHeld(String),
    #[error("run directory already exists: {0}; choose a new run_id")]
    RunExists(String),
    #[error("run directory missing: {0}")]
    Missing(String),
    #[error("corrupt result.json: {0}")]
    Corrupt(String),
}

#[derive(Debug, Error)]
pub enum PolicyError {
    #[error("path not allowed: {0}")]
    PathNotAllowed(String),
    #[error("path denied: {0}")]
    PathDenied(String),
    #[error("too many files changed: {0}")]
    TooManyFiles(usize),
    #[error("deletes not allowed")]
    DeletesNotAllowed,
    #[error("binary changes not allowed")]
    BinaryNotAllowed,
    #[error("baseline mismatch")]
    BaselineMismatch,
    #[error("hash mismatch")]
    HashMismatch,
    #[error("{0}")]
    Other(String),
}

impl BrokerError {
    /// Exit code for CLI: 2 = precondition/schema, 1 = finished non-success, 0 = success.
    pub fn exit_code(&self) -> u8 {
        match self {
            BrokerError::Task(_)
            | BrokerError::Cli(_)
            | BrokerError::UnsupportedPlatform
            | BrokerError::Spawn(SpawnError::NotFound(_))
            | BrokerError::Persistence(PersistenceError::LockHeld(_))
            | BrokerError::Persistence(PersistenceError::RunExists(_))
            | BrokerError::Persistence(PersistenceError::Missing(_)) => 2,
            _ => 1,
        }
    }

    /// Bounded user-facing message (no env values, credentials, or full argv).
    pub fn user_message(&self) -> String {
        let s = self.to_string();
        if s.chars().count() > 512 {
            format!("{}…", s.chars().take(509).collect::<String>())
        } else {
            s
        }
    }
}
