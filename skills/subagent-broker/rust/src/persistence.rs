//! Atomic persistence of result.json and summary.md. Single authority: RunState.

use std::fs::{self, File, OpenOptions};
use std::io::Write;
use std::path::{Path, PathBuf};

use fs2::FileExt;

use crate::error::{BrokerResult, PersistenceError};
use crate::render::{render_summary, run_state_to_json};
use crate::state::RunState;
use crate::task::RunId;

pub struct RunDirectory {
    pub root: PathBuf,
    _lock: File,
}

impl RunDirectory {
    pub fn create(base: &Path, run_id: &RunId) -> BrokerResult<Self> {
        let root = base.join(run_id.as_str());
        if root.exists() || root.symlink_metadata().is_ok() {
            return Err(PersistenceError::RunExists(root.display().to_string()).into());
        }
        fs::create_dir_all(&root).map_err(|e| PersistenceError::Io(e.to_string()))?;
        refuse_symlink(&root)?;
        let lock_path = root.join(".lock");
        refuse_symlink_if_exists(&lock_path)?;
        let lock = OpenOptions::new()
            .create(true)
            .read(true)
            .write(true)
            .truncate(false)
            .open(&lock_path)
            .map_err(|e| PersistenceError::Io(e.to_string()))?;
        lock.try_lock_exclusive().map_err(|_| {
            PersistenceError::LockHeld(format!(
                "run_id {} already locked by another process",
                run_id
            ))
        })?;
        Ok(Self { root, _lock: lock })
    }

    pub fn open_readonly(base: &Path, run_id: &str) -> BrokerResult<PathBuf> {
        let root = base.join(run_id);
        if !root.join("result.json").exists() {
            return Err(PersistenceError::Missing(root.display().to_string()).into());
        }
        Ok(root)
    }

    pub fn agent_dir(&self, agent_id: &str) -> BrokerResult<PathBuf> {
        let d = self.root.join(agent_id);
        refuse_symlink_if_exists(&d)?;
        fs::create_dir_all(&d).map_err(|e| PersistenceError::Io(e.to_string()))?;
        Ok(d)
    }

    pub fn persist_live(&self, state: &RunState) -> BrokerResult<()> {
        self.write_result(state)?;
        self.write_summary(state)?;
        Ok(())
    }

    pub fn append_event(&self, value: &serde_json::Value) -> BrokerResult<()> {
        let line = serde_json::to_string(value).map_err(|e| PersistenceError::Io(e.to_string()))?;
        append_events_jsonl(&self.root.join("events.jsonl"), &line)
    }

    /// Append an event only when the resulting JSONL file stays within the
    /// caller's budget. Returns `false` when the event was dropped.
    pub fn append_event_with_limit(
        &self,
        value: &serde_json::Value,
        max_bytes: u64,
    ) -> BrokerResult<bool> {
        let line = serde_json::to_string(value).map_err(|e| PersistenceError::Io(e.to_string()))?;
        let path = self.root.join("events.jsonl");
        let current = path.metadata().map(|m| m.len()).unwrap_or(0);
        let required = (line.len() as u64).saturating_add(1);
        if current > max_bytes || required > max_bytes.saturating_sub(current) {
            return Ok(false);
        }
        append_events_jsonl(&path, &line)?;
        Ok(true)
    }

    pub fn persist_terminal(&self, state: &RunState) -> BrokerResult<()> {
        for agent in state.agents_in_order() {
            let dir = self.agent_dir(agent.agent_id.as_str())?;
            let agent_json = run_state_to_json(state);
            if let Some(arr) = agent_json.get("agents").and_then(|a| a.as_array()) {
                for item in arr {
                    if item.get("agent_id").and_then(|v| v.as_str())
                        == Some(agent.agent_id.as_str())
                    {
                        let path = dir.join("result.json");
                        atomic_write_json(&path, item)?;
                    }
                }
            }
        }
        self.write_summary(state)?;
        self.write_result(state)?;
        Ok(())
    }

    fn write_result(&self, state: &RunState) -> BrokerResult<()> {
        let path = self.root.join("result.json");
        let value = run_state_to_json(state);
        atomic_write_json(&path, &value)
    }

    fn write_summary(&self, state: &RunState) -> BrokerResult<()> {
        let path = self.root.join("summary.md");
        let text = render_summary(state);
        atomic_write_bytes(&path, text.as_bytes())
    }
}

/// Refuse to write through a symlink destination (no follow).
pub fn refuse_symlink(path: &Path) -> BrokerResult<()> {
    if path
        .symlink_metadata()
        .map(|m| m.file_type().is_symlink())
        .unwrap_or(false)
    {
        return Err(PersistenceError::Io(format!(
            "refusing to use symlink path: {}",
            path.display()
        ))
        .into());
    }
    Ok(())
}

fn refuse_symlink_if_exists(path: &Path) -> BrokerResult<()> {
    if path.exists() || path.symlink_metadata().is_ok() {
        refuse_symlink(path)?;
    }
    Ok(())
}

pub fn atomic_write_json(path: &Path, value: &serde_json::Value) -> BrokerResult<()> {
    let bytes =
        serde_json::to_vec_pretty(value).map_err(|e| PersistenceError::Io(e.to_string()))?;
    atomic_write_bytes(path, &bytes)
}

pub fn atomic_write_bytes(path: &Path, bytes: &[u8]) -> BrokerResult<()> {
    refuse_symlink_if_exists(path)?;
    let parent = path.parent().unwrap_or_else(|| Path::new("."));
    refuse_symlink_if_exists(parent)?;
    fs::create_dir_all(parent).map_err(|e| PersistenceError::Io(e.to_string()))?;
    let tmp = parent.join(format!(
        ".{}.tmp",
        path.file_name().and_then(|s| s.to_str()).unwrap_or("file")
    ));
    // Also refuse if tmp is somehow a symlink
    refuse_symlink_if_exists(&tmp)?;
    {
        let mut f = File::create(&tmp).map_err(|e| PersistenceError::Io(e.to_string()))?;
        f.write_all(bytes)
            .map_err(|e| PersistenceError::Io(e.to_string()))?;
        f.sync_all()
            .map_err(|e| PersistenceError::Io(e.to_string()))?;
    }
    // Final destination must not be a symlink (attacker may race; check again)
    refuse_symlink_if_exists(path)?;
    // On Unix, rename over symlink replaces the link itself without following — still refuse
    // if path is currently a symlink so we never write through it.
    if path
        .symlink_metadata()
        .map(|m| m.file_type().is_symlink())
        .unwrap_or(false)
    {
        let _ = fs::remove_file(&tmp);
        return Err(PersistenceError::Io(format!(
            "refusing to replace symlink destination: {}",
            path.display()
        ))
        .into());
    }
    fs::rename(&tmp, path).map_err(|e| PersistenceError::Io(e.to_string()))?;
    Ok(())
}

pub fn load_result_json(run_dir: &Path) -> BrokerResult<serde_json::Value> {
    let path = run_dir.join("result.json");
    refuse_symlink(&path)?;
    let bytes = fs::read(&path).map_err(|e| PersistenceError::Io(e.to_string()))?;
    serde_json::from_slice(&bytes).map_err(|e| PersistenceError::Corrupt(e.to_string()).into())
}

pub fn default_subagents_base(cwd: &Path) -> PathBuf {
    cwd.join(".subagents")
}

/// Append a diagnostic JSONL line without following a symlink destination.
pub fn append_events_jsonl(path: &Path, line: &str) -> BrokerResult<()> {
    refuse_symlink_if_exists(path)?;
    let parent = path.parent().unwrap_or_else(|| Path::new("."));
    fs::create_dir_all(parent).map_err(|e| PersistenceError::Io(e.to_string()))?;
    let mut f = OpenOptions::new()
        .create(true)
        .append(true)
        .open(path)
        .map_err(|e| PersistenceError::Io(e.to_string()))?;
    // Re-check after open (TOCTOU best-effort)
    refuse_symlink(path)?;
    writeln!(f, "{line}").map_err(|e| PersistenceError::Io(e.to_string()))?;
    Ok(())
}
