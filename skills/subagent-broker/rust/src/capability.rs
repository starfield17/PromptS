//! Closed capability set — vendor permission/UX, not OS sandbox.

use serde::{Deserialize, Serialize};

use crate::error::TaskError;
use crate::task::Mode;

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Capability {
    RepoRead,
    PythonInspect,
    PythonTest,
    Patch,
}

impl Capability {
    pub fn as_str(self) -> &'static str {
        match self {
            Capability::RepoRead => "repo_read",
            Capability::PythonInspect => "python_inspect",
            Capability::PythonTest => "python_test",
            Capability::Patch => "patch",
        }
    }
}

/// Validate capability set against mode.
pub fn validate_capabilities(mode: Mode, caps: &[Capability]) -> Result<(), TaskError> {
    let has_patch = caps.contains(&Capability::Patch);
    match mode {
        Mode::ReadOnly if has_patch => Err(TaskError::Capability(
            "read_only mode cannot include Patch capability".into(),
        )),
        Mode::PatchOnly if !has_patch => Err(TaskError::Capability(
            "patch_only mode requires Patch capability (not auto-added)".into(),
        )),
        _ => Ok(()),
    }
}

/// Provider support matrix. Vendor permission flags are not interchangeable;
/// unsupported requests must fail before a process is spawned.
pub fn validate_provider_permissions(
    harness_kind: &str,
    caps: &[Capability],
) -> Result<(), TaskError> {
    for cap in caps {
        let supported = match harness_kind {
            "claude_code" | "custom" | "fake" => true,
            "grok_build" | "codex_cli" => {
                matches!(cap, Capability::RepoRead | Capability::Patch)
            }
            "opencode" => matches!(cap, Capability::RepoRead),
            _ => false,
        };
        if !supported {
            return Err(TaskError::Capability(format!(
                "harness {harness_kind} does not support requested permission {}",
                cap.as_str()
            )));
        }
    }
    Ok(())
}

/// Claude Code tool rules aligned with V2 `CLAUDE_CAPABILITY_MAP`.
pub fn claude_tool_rules(caps: &[Capability]) -> Vec<String> {
    let mut out = Vec::new();
    for cap in caps {
        let rules: &[&str] = match cap {
            Capability::RepoRead => &[
                "Read",
                "Glob",
                "Grep",
                "Bash(rg *)",
                "Bash(sed *)",
                "Bash(file *)",
                "Bash(xxd *)",
                "Bash(wc *)",
                "Bash(ls *)",
                "Bash(find *)",
                "Bash(cat *)",
                "Bash(head *)",
                "Bash(tail *)",
            ],
            Capability::PythonInspect => &["Bash(python *)", "Bash(python3 *)"],
            Capability::PythonTest => &[
                "Bash(python -m pytest *)",
                "Bash(python -m unittest *)",
                "Bash(python3 -m pytest *)",
                "Bash(python3 -m unittest *)",
            ],
            Capability::Patch => &["Edit", "Write"],
        };
        for r in rules {
            if !out.iter().any(|x| x == r) {
                out.push((*r).to_string());
            }
        }
    }
    if out.is_empty() {
        // Safe default for empty caps: read-only helpers only.
        out.extend(["Read", "Glob", "Grep"].into_iter().map(str::to_string));
    }
    out
}

/// Tool base names (before `(`) for Claude `--tools`.
pub fn claude_tool_names(caps: &[Capability]) -> Vec<String> {
    let mut names = Vec::new();
    for rule in claude_tool_rules(caps) {
        let base = rule.split('(').next().unwrap_or(rule.as_str()).to_string();
        if !names.contains(&base) {
            names.push(base);
        }
    }
    names
}

/// Grok Build `--allow` style rules (subset; vendor UX only).
pub fn grok_allow_rules(caps: &[Capability]) -> Vec<String> {
    // Grok uses permission allow rules; map to coarse tool families.
    let mut out = Vec::new();
    for cap in caps {
        match cap {
            Capability::RepoRead => {
                for r in ["Read", "Glob", "Grep", "Bash"] {
                    if !out.iter().any(|x| x == r) {
                        out.push(r.to_string());
                    }
                }
            }
            Capability::PythonInspect | Capability::PythonTest => {
                if !out.iter().any(|x| x == "Bash") {
                    out.push("Bash".into());
                }
            }
            Capability::Patch => {
                for r in ["Edit", "Write"] {
                    if !out.iter().any(|x| x == r) {
                        out.push(r.to_string());
                    }
                }
            }
        }
    }
    if out.is_empty() {
        out.extend(["Read", "Glob", "Grep"].into_iter().map(str::to_string));
    }
    out
}

#[cfg(test)]
#[allow(clippy::unwrap_used, clippy::expect_used)]
mod tests {
    use super::*;

    #[test]
    fn read_only_rejects_patch() {
        let err = validate_capabilities(Mode::ReadOnly, &[Capability::RepoRead, Capability::Patch]);
        assert!(err.is_err());
    }

    #[test]
    fn patch_only_requires_patch() {
        let err = validate_capabilities(Mode::PatchOnly, &[Capability::RepoRead]);
        assert!(err.is_err());
    }

    #[test]
    fn valid_combinations() {
        assert!(validate_capabilities(Mode::ReadOnly, &[Capability::RepoRead]).is_ok());
        assert!(
            validate_capabilities(Mode::PatchOnly, &[Capability::RepoRead, Capability::Patch])
                .is_ok()
        );
    }

    #[test]
    fn claude_rules_repo_read_no_edit() {
        let rules = claude_tool_rules(&[Capability::RepoRead]);
        assert!(rules.iter().any(|r| r == "Read"));
        assert!(!rules.iter().any(|r| r == "Edit" || r == "Write"));
        let names = claude_tool_names(&[Capability::RepoRead]);
        assert!(names.contains(&"Read".to_string()));
        assert!(!names.contains(&"Edit".to_string()));
    }

    #[test]
    fn claude_rules_patch_includes_edit_write() {
        let rules = claude_tool_rules(&[Capability::RepoRead, Capability::Patch]);
        assert!(rules.iter().any(|r| r == "Edit"));
        assert!(rules.iter().any(|r| r == "Write"));
    }

    #[test]
    fn claude_rules_dedupe() {
        let rules = claude_tool_rules(&[Capability::RepoRead, Capability::RepoRead]);
        let reads = rules.iter().filter(|r| *r == "Read").count();
        assert_eq!(reads, 1);
    }

    #[test]
    fn grok_allow_includes_bash_for_python() {
        let r = grok_allow_rules(&[Capability::PythonTest]);
        assert!(r.iter().any(|x| x == "Bash"));
    }

    #[test]
    fn unsupported_provider_permission_is_rejected() {
        assert!(validate_provider_permissions("codex_cli", &[Capability::PythonTest]).is_err());
        assert!(validate_provider_permissions("opencode", &[Capability::Patch]).is_err());
        assert!(validate_provider_permissions("claude_code", &[Capability::PythonTest]).is_ok());
    }
}
