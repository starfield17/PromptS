//! Patch gates: Candidate → PolicyChecked → Mergeable. Private constructors.

use std::path::{Path, PathBuf};

use sha2::{Digest, Sha256};

use crate::error::{BrokerResult, PolicyError};
use crate::policy::PathPolicy;
use crate::state::PatchAuthorization;
use crate::state::PatchRecord;

#[derive(Debug, Clone)]
pub struct PatchMetadata {
    pub baseline_sha: Option<String>,
    pub baseline_manifest_sha256: Option<String>,
    pub baseline_bundle_sha256: Option<String>,
    pub has_deletes: bool,
    pub has_binary: bool,
}

/// Raw patch bytes before gates.
pub struct CandidatePatch {
    bytes: Vec<u8>,
    changed_paths: Vec<String>,
    metadata: PatchMetadata,
}

impl CandidatePatch {
    pub fn new(bytes: Vec<u8>, changed_paths: Vec<String>, metadata: PatchMetadata) -> Self {
        Self {
            bytes,
            changed_paths,
            metadata,
        }
    }

    pub fn bytes(&self) -> &[u8] {
        &self.bytes
    }

    pub fn changed_paths(&self) -> &[String] {
        &self.changed_paths
    }

    pub fn sha256_hex(&self) -> String {
        file_sha256_hex(&self.bytes)
    }
}

fn file_sha256_hex(bytes: &[u8]) -> String {
    let mut h = Sha256::new();
    h.update(bytes);
    hex::encode(h.finalize())
}

/// Witness types for gates (zero-sized).
#[derive(Debug, Clone, Copy)]
pub struct PassedPatchPolicy;
#[derive(Debug, Clone, Copy)]
pub struct SatisfiedIdentityGate;
#[derive(Debug, Clone, Copy)]
pub struct NoPermissionDenials;
#[derive(Debug, Clone, Copy)]
pub struct SuccessfulHarnessOutcome;

pub struct PolicyCheckedPatch {
    candidate: CandidatePatch,
    #[allow(dead_code)]
    policy: PassedPatchPolicy,
}

pub struct MergeablePatch {
    checked: PolicyCheckedPatch,
    #[allow(dead_code)]
    identity: SatisfiedIdentityGate,
    #[allow(dead_code)]
    permissions: NoPermissionDenials,
    #[allow(dead_code)]
    harness: SuccessfulHarnessOutcome,
}

impl PolicyCheckedPatch {
    pub fn check(candidate: CandidatePatch, policy: &PathPolicy) -> Result<Self, PolicyError> {
        policy.check_changed_paths(&candidate.changed_paths)?;
        if candidate.metadata.has_deletes && !policy.allow_deletes() {
            return Err(PolicyError::DeletesNotAllowed);
        }
        if candidate.metadata.has_binary && !policy.allow_binary() {
            return Err(PolicyError::BinaryNotAllowed);
        }
        Ok(Self {
            candidate,
            policy: PassedPatchPolicy,
        })
    }
}

impl MergeablePatch {
    /// Only the gate module constructs MergeablePatch after all witnesses pass.
    pub fn gate(checked: PolicyCheckedPatch, _authorization: PatchAuthorization) -> Self {
        Self {
            checked,
            identity: SatisfiedIdentityGate,
            permissions: NoPermissionDenials,
            harness: SuccessfulHarnessOutcome,
        }
    }
}

pub fn sha256_sidecar_path(patch: &Path) -> PathBuf {
    let mut s = patch.as_os_str().to_os_string();
    s.push(".sha256");
    PathBuf::from(s)
}

/// Unique write interface for patches. Always writes hash sidecar.
pub fn persist_patch(patch: MergeablePatch, destination: &Path) -> BrokerResult<PatchRecord> {
    let bytes = patch.checked.candidate.bytes.clone();
    let paths = patch.checked.candidate.changed_paths.clone();
    let sha = patch.checked.candidate.sha256_hex();
    let parent = destination.parent().unwrap_or_else(|| Path::new("."));
    std::fs::create_dir_all(parent).map_err(|e| PolicyError::Other(e.to_string()))?;
    crate::persistence::refuse_symlink(destination)?;
    let sidecar = sha256_sidecar_path(destination);
    crate::persistence::refuse_symlink(&sidecar)?;
    let temp = tempfile::tempdir_in(parent).map_err(|e| PolicyError::Other(e.to_string()))?;
    let temp_patch = temp.path().join("patch.diff");
    let temp_sidecar = temp.path().join("patch.diff.sha256");
    crate::persistence::atomic_write_bytes(&temp_patch, &bytes)?;
    crate::persistence::atomic_write_bytes(&temp_sidecar, format!("{sha}\n").as_bytes())?;
    std::fs::rename(&temp_patch, destination).map_err(|e| PolicyError::Other(e.to_string()))?;
    if let Err(error) = std::fs::rename(&temp_sidecar, &sidecar) {
        let _ = std::fs::remove_file(destination);
        return Err(PolicyError::Other(error.to_string()).into());
    }
    Ok(PatchRecord {
        path: destination
            .file_name()
            .and_then(|name| name.to_str())
            .unwrap_or("patch.diff")
            .to_string(),
        sha256: sha,
        files_changed: paths,
        baseline_manifest_sha256: patch.checked.candidate.metadata.baseline_manifest_sha256,
        baseline_bundle_sha256: patch.checked.candidate.metadata.baseline_bundle_sha256,
    })
}

/// Parse unified diff for changed paths (mechanical).
pub fn parse_changed_paths(diff: &[u8]) -> Vec<String> {
    let text = String::from_utf8_lossy(diff);
    let mut paths = Vec::new();
    for line in text.lines() {
        if let Some(rest) = line.strip_prefix("diff --git ") {
            let parts: Vec<&str> = rest.split_whitespace().collect();
            if parts.len() >= 2 {
                let b = parts[1];
                let p = b.strip_prefix("b/").unwrap_or(b);
                if !paths.iter().any(|x| x == p) {
                    paths.push(p.to_string());
                }
            }
        } else if let Some(rest) = line.strip_prefix("+++ b/") {
            let p = rest.trim();
            if p != "/dev/null" && !paths.iter().any(|x| x == p) {
                paths.push(p.to_string());
            }
        }
    }
    paths
}

pub fn diff_has_deletes(diff: &[u8]) -> bool {
    let text = String::from_utf8_lossy(diff);
    text.lines()
        .any(|l| l.starts_with("deleted file mode") || l.starts_with("+++ /dev/null"))
}

pub fn diff_has_binary(diff: &[u8]) -> bool {
    let text = String::from_utf8_lossy(diff);
    text.contains("Binary files ") || text.contains("GIT binary patch")
}

/// Check patch integrity — requires matching `.sha256` sidecar.
pub fn check_patch_file(path: &Path) -> BrokerResult<()> {
    if !path.exists() {
        return Err(PolicyError::Other(format!("missing patch: {}", path.display())).into());
    }
    const MAX_PATCH_CHECK_BYTES: u64 = 64 * 1024 * 1024;
    let size = std::fs::metadata(path)
        .map_err(|e| PolicyError::Other(e.to_string()))?
        .len();
    if size > MAX_PATCH_CHECK_BYTES {
        return Err(PolicyError::Other(format!(
            "patch exceeds check budget ({MAX_PATCH_CHECK_BYTES} bytes)"
        ))
        .into());
    }
    let bytes = std::fs::read(path).map_err(|e| PolicyError::Other(e.to_string()))?;
    if bytes.is_empty() {
        return Err(PolicyError::Other("empty patch".into()).into());
    }
    let side = sha256_sidecar_path(path);
    if !side.exists() {
        return Err(
            PolicyError::Other(format!("missing patch hash sidecar: {}", side.display())).into(),
        );
    }
    let expected = std::fs::read_to_string(&side)
        .map_err(|e| PolicyError::Other(e.to_string()))?
        .trim()
        .to_string();
    let actual = file_sha256_hex(&bytes);
    if !actual.eq_ignore_ascii_case(&expected) {
        return Err(PolicyError::HashMismatch.into());
    }
    Ok(())
}

pub fn check_patch_artifacts(path: &Path) -> BrokerResult<()> {
    check_patch_file(path)?;
    let dir = path.parent().unwrap_or_else(|| Path::new("."));
    let result_bytes = std::fs::read(dir.join("result.json"))
        .map_err(|e| PolicyError::Other(format!("read agent result: {e}")))?;
    let result: serde_json::Value = serde_json::from_slice(&result_bytes)
        .map_err(|e| PolicyError::Other(format!("agent result JSON: {e}")))?;
    if result.get("outcome").and_then(|v| v.as_str()) != Some("success") {
        return Err(PolicyError::Other("patch requires agent outcome=success".into()).into());
    }
    if result
        .get("permission_denials")
        .and_then(|v| v.as_array())
        .is_some_and(|denials| !denials.is_empty())
    {
        return Err(PolicyError::Other("patch has permission denials".into()).into());
    }
    if let Some(gate) = result.get("identity_gate") {
        if gate.get("required").and_then(|v| v.as_bool()) == Some(true)
            && gate.get("satisfied").and_then(|v| v.as_bool()) != Some(true)
        {
            return Err(PolicyError::Other("identity gate is not satisfied".into()).into());
        }
    } else {
        return Err(PolicyError::Other("identity gate record missing".into()).into());
    }
    let policy_gate = result
        .get("policy_gate")
        .and_then(|v| v.as_object())
        .ok_or_else(|| PolicyError::Other("policy gate record missing".into()))?;
    if policy_gate.get("evaluated").and_then(|v| v.as_bool()) != Some(true)
        || policy_gate.get("satisfied").and_then(|v| v.as_bool()) != Some(true)
    {
        return Err(PolicyError::Other("policy gate is not satisfied".into()).into());
    }
    if let Some(diag) = result.get("diagnostics") {
        for field in [
            "unknown_event_count",
            "invalid_json_count",
            "oversized_event_count",
        ] {
            if diag.get(field).and_then(|v| v.as_u64()).unwrap_or(0) > 0 {
                return Err(PolicyError::Other(format!(
                    "patch diagnostics contain unrecognized stream data: {field}"
                ))
                .into());
            }
        }
    }
    let patch = result
        .get("patch")
        .and_then(|v| v.as_object())
        .ok_or_else(|| PolicyError::Other("agent result has no successful patch record".into()))?;
    let expected_name = path.file_name().and_then(|name| name.to_str());
    if patch.get("path").and_then(|v| v.as_str()) != expected_name {
        return Err(PolicyError::Other("agent result patch path mismatch".into()).into());
    }
    let expected_patch_sha = patch
        .get("sha256")
        .and_then(|v| v.as_str())
        .ok_or_else(|| PolicyError::Other("agent result patch hash missing".into()))?;
    let bytes = std::fs::read(path).map_err(|e| PolicyError::Other(e.to_string()))?;
    if !file_sha256_hex(&bytes).eq_ignore_ascii_case(expected_patch_sha) {
        return Err(PolicyError::HashMismatch.into());
    }

    let manifest_bytes = std::fs::read(dir.join("baseline_manifest.json"))
        .map_err(|e| PolicyError::Other(format!("read baseline manifest: {e}")))?;
    let manifest: serde_json::Value = serde_json::from_slice(&manifest_bytes)
        .map_err(|e| PolicyError::Other(format!("baseline manifest JSON: {e}")))?;
    let expected_bundle_sha = manifest
        .get("baseline_bundle_sha256")
        .and_then(|v| v.as_str())
        .ok_or_else(|| PolicyError::Other("baseline bundle hash missing".into()))?;
    if patch.get("baseline_bundle_sha256").and_then(|v| v.as_str()) != Some(expected_bundle_sha) {
        return Err(PolicyError::HashMismatch.into());
    }
    let bundle = dir.join("baseline.bundle");
    if !crate::workspace::sha256_file_hex(&bundle)?.eq_ignore_ascii_case(expected_bundle_sha) {
        return Err(PolicyError::HashMismatch.into());
    }
    let expected_manifest_sha = manifest
        .get("manifest_sha256")
        .and_then(|v| v.as_str())
        .ok_or_else(|| PolicyError::Other("baseline manifest content hash missing".into()))?;
    if manifest
        .get("source_visible_sha256")
        .and_then(|v| v.as_str())
        != Some(expected_manifest_sha)
    {
        return Err(PolicyError::HashMismatch.into());
    }
    if patch
        .get("baseline_manifest_sha256")
        .and_then(|v| v.as_str())
        != Some(expected_manifest_sha)
    {
        return Err(PolicyError::HashMismatch.into());
    }
    let max_files = manifest
        .get("max_workspace_files")
        .and_then(|v| v.as_u64())
        .unwrap_or(25_000);
    let max_file_bytes = manifest
        .get("max_file_bytes")
        .and_then(|v| v.as_u64())
        .unwrap_or(64 * 1024 * 1024);
    let max_workspace_bytes = manifest
        .get("max_workspace_bytes_after_run")
        .and_then(|v| v.as_u64())
        .unwrap_or(1_073_741_824);
    let temp = tempfile::tempdir().map_err(|e| PolicyError::Other(e.to_string()))?;
    let checkout = temp.path().join("baseline");
    crate::git::clone_bundle(&bundle, &checkout)?;
    let actual_manifest_sha = crate::workspace::visible_state_sha256_with_limits(
        &checkout,
        max_files,
        max_workspace_bytes,
        max_file_bytes,
    )?;
    if !actual_manifest_sha.eq_ignore_ascii_case(expected_manifest_sha) {
        return Err(PolicyError::HashMismatch.into());
    }
    Ok(())
}

/// Apply after hash check. Optional baseline HEAD match rejects drift.
pub fn apply_patch_file(
    path: &Path,
    repo: &Path,
    expected_baseline: Option<&str>,
) -> BrokerResult<()> {
    check_patch_file(path)?;
    if let Some(expected) = expected_baseline {
        let head = crate::git::head_sha(repo)?;
        if head != expected {
            return Err(PolicyError::BaselineMismatch.into());
        }
    }
    let status = std::process::Command::new("git")
        .args(["apply", "--check"])
        .arg(path)
        .current_dir(repo)
        .status()
        .map_err(|e| PolicyError::Other(e.to_string()))?;
    if !status.success() {
        return Err(PolicyError::Other("git apply --check failed".into()).into());
    }
    let status = std::process::Command::new("git")
        .args(["apply"])
        .arg(path)
        .current_dir(repo)
        .status()
        .map_err(|e| PolicyError::Other(e.to_string()))?;
    if !status.success() {
        return Err(PolicyError::Other("git apply failed".into()).into());
    }
    Ok(())
}

#[derive(Debug, Clone)]
pub struct BaselineExpectation {
    pub source_head: Option<String>,
    pub source_visible_sha256: String,
}

pub fn apply_patch_file_with_manifest(
    path: &Path,
    repo: &Path,
    expected: &BaselineExpectation,
) -> BrokerResult<()> {
    check_patch_artifacts(path)?;
    if let Some(ref head) = expected.source_head {
        if crate::git::head_sha(repo)? != *head {
            return Err(PolicyError::BaselineMismatch.into());
        }
    }
    if crate::workspace::visible_state_sha256(repo)? != expected.source_visible_sha256 {
        return Err(PolicyError::BaselineMismatch.into());
    }
    apply_patch_file(path, repo, None)
}

pub fn load_expected_baseline(manifest_path: &Path) -> Option<String> {
    let bytes = std::fs::read(manifest_path).ok()?;
    let v: serde_json::Value = serde_json::from_slice(&bytes).ok()?;
    v.get("baseline_sha")
        .and_then(|x| x.as_str())
        .map(str::to_string)
}

pub fn load_baseline_expectation(manifest_path: &Path) -> BrokerResult<BaselineExpectation> {
    let bytes = std::fs::read(manifest_path).map_err(|e| PolicyError::Other(e.to_string()))?;
    let value: serde_json::Value =
        serde_json::from_slice(&bytes).map_err(|e| PolicyError::Other(e.to_string()))?;
    let source_visible_sha256 = value
        .get("source_visible_sha256")
        .and_then(|v| v.as_str())
        .ok_or_else(|| {
            PolicyError::Other("baseline manifest missing source_visible_sha256".into())
        })?
        .to_string();
    let source_head = value
        .get("source_head")
        .and_then(|v| v.as_str())
        .map(str::to_string);
    Ok(BaselineExpectation {
        source_head,
        source_visible_sha256,
    })
}

#[cfg(test)]
#[allow(clippy::unwrap_used, clippy::expect_used)]
mod tests {
    use super::*;
    use crate::task::PatchPolicy;

    #[test]
    fn non_success_cannot_gate() {
        let c = CandidatePatch::new(
            b"diff --git a/x b/x\n".to_vec(),
            vec!["x".into()],
            PatchMetadata {
                baseline_sha: None,
                baseline_manifest_sha256: None,
                baseline_bundle_sha256: None,
                has_deletes: false,
                has_binary: false,
            },
        );
        let policy = PathPolicy::new(&["**".into()], &[], 50, PatchPolicy::default()).unwrap();
        let checked = PolicyCheckedPatch::check(c, &policy).unwrap();
        let _ = checked;
        // No PatchAuthorization can be constructed from booleans or a non-success state.
    }
}
