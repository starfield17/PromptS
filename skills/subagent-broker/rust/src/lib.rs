//! subagent-broker V3.1 — local short-lived deterministic process broker.

#![forbid(unsafe_code)]
#![deny(unused_must_use)]
#![deny(rust_2018_idioms)]

pub mod capability;
pub mod cli;
pub mod environment;
pub mod error;
pub mod event;
pub mod git;
pub mod harness;
pub mod identity;
pub mod patch;
pub mod persistence;
pub mod platform;
pub mod policy;
pub mod prompt;
pub mod redact;
pub mod render;
pub mod state;
pub mod state_owner;
pub mod supervisor;
pub mod task;
pub mod workspace;

pub use error::{BrokerError, BrokerResult};
pub use task::TaskPacket;
