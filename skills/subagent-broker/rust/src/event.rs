//! Normalized harness events — no tool input/output/thinking/credentials.

use crate::identity::ObservedIdentity;
use crate::task::BoundedText;

/// Safe tool name only (no command text).
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct SafeToolName(String);

impl SafeToolName {
    pub fn new(raw: impl Into<String>) -> Self {
        let s = raw.into();
        let trimmed: String = s.chars().take(128).collect();
        Self(trimmed)
    }

    pub fn as_str(&self) -> &str {
        &self.0
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ToolId(String);

impl ToolId {
    pub fn new(raw: impl Into<String>) -> Self {
        let s = raw.into();
        let trimmed: String = s.chars().take(128).collect();
        Self(trimmed)
    }

    pub fn as_str(&self) -> &str {
        &self.0
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct BoundedChunk {
    pub text: BoundedText,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum HarnessTerminalClaim {
    Success,
    Error,
    Cancelled,
    MaxTurns,
    MaxTokens,
    Refusal,
    Other(String),
}

#[derive(Debug, Clone)]
pub enum HarnessEvent {
    AssistantText(BoundedChunk),
    FinalResult(BoundedChunk),
    ToolStarted {
        id: ToolId,
        name: SafeToolName,
    },
    ToolFinished {
        id: ToolId,
        is_error: bool,
    },
    PermissionDenied {
        id: Option<ToolId>,
        name: Option<SafeToolName>,
    },
    IdentityObserved(ObservedIdentity),
    HarnessResult(HarnessTerminalClaim),
    HarnessError(BoundedText),
    OversizedEventSkipped {
        bytes: u64,
    },
}

/// Events sent to the single StateOwner writer.
#[derive(Debug)]
pub enum StateEvent {
    AgentStarted {
        agent_id: String,
    },
    Harness(HarnessEvent),
    ProcessExited {
        code: Option<i32>,
        signal: Option<i32>,
    },
    DescendantsTerminated,
    IdleTimeout,
    TotalTimeout,
    Cancelled,
    InternalError(String),
    Activity,
}
