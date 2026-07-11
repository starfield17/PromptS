//! Canonical broker prompt shared by every provider adapter.

use crate::task::{AgentSpec, Mode};

pub fn render(agent: &AgentSpec, work_dir: &std::path::Path) -> String {
    let allowed = if agent.allowed_paths.is_empty() {
        "<none>".to_string()
    } else {
        agent.allowed_paths.join(", ")
    };
    let denied = if agent.deny_paths.is_empty() {
        "<none>".to_string()
    } else {
        agent.deny_paths.join(", ")
    };
    let permissions = if agent.capabilities.is_empty() {
        "<none>".to_string()
    } else {
        agent
            .capabilities
            .iter()
            .map(|permission| permission.as_str())
            .collect::<Vec<_>>()
            .join(", ")
    };
    let mode = match agent.mode {
        Mode::ReadOnly => "read_only",
        Mode::PatchOnly => "patch_only",
    };
    let patch_instruction = match agent.mode {
        Mode::ReadOnly => "Do not modify any file. If diagnosis is impossible without a write, report needs_analysis.",
        Mode::PatchOnly => "Only modify files matching Allowed paths. If a safe patch cannot be produced, return needs_analysis without editing.",
    };
    format!(
        "Working directory: {}\n\nMode: {mode}\nAllowed paths: {allowed}\nDenied paths: {denied}\nRequested permissions: {permissions}\nAvailable command examples: repo_read=rg, sed, cat, find; python_inspect=python3 -c; python_test=python3 -m pytest; patch=edit files under Allowed paths.\n{patch_instruction}\nDo not add diagnostic-only failing tests. Return a concise final response and state verification results separately.\n\nGoal:\n{}",
        work_dir.display(),
        agent.goal
    )
}

#[cfg(test)]
#[allow(clippy::unwrap_used)]
mod tests {
    use super::*;
    use crate::capability::Capability;
    use crate::identity::IdentityRequirement;
    use crate::task::{AgentId, EnvironmentSpec, HarnessSpec, IsolationMode, Limits, PatchPolicy};

    #[test]
    fn renders_policy_and_permissions() {
        let agent = AgentSpec {
            id: AgentId::new("a").unwrap(),
            goal: "inspect".into(),
            harness: HarnessSpec::Custom {
                executable: "/bin/true".into(),
                args: Vec::new(),
                stream_family: Some("plain".into()),
            },
            mode: Mode::PatchOnly,
            isolation: IsolationMode::CopyIsolation,
            source_root: ".".into(),
            allowed_paths: vec!["src/**".into()],
            deny_paths: vec!["secrets/**".into()],
            capabilities: vec![Capability::RepoRead, Capability::Patch],
            identity: IdentityRequirement::default(),
            environment: EnvironmentSpec::default(),
            limits: Limits::default(),
            patch_policy: PatchPolicy::default(),
            require_patch: false,
            required_paths: Vec::new(),
            verification: Vec::new(),
        };
        let prompt = render(&agent, std::path::Path::new("/tmp/work"));
        assert!(prompt.contains("Allowed paths: src/**"));
        assert!(prompt.contains("Requested permissions: repo_read, patch"));
        assert!(prompt.contains("Mode: patch_only"));
    }
}
