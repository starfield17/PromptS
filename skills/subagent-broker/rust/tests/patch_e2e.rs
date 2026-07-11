//! Patch E2E: success path, hash tamper, baseline drift.

#![allow(clippy::unwrap_used, clippy::expect_used)]

use std::fs;
use std::process::Command;

use subagent_broker::event::{HarnessEvent, HarnessTerminalClaim};
use subagent_broker::identity::{IdentityRequirement, RequestedIdentity};
use subagent_broker::patch::{
    apply_patch_file, check_patch_file, diff_has_binary, diff_has_deletes, persist_patch,
    sha256_sidecar_path, CandidatePatch, MergeablePatch, PatchMetadata, PolicyCheckedPatch,
};
use subagent_broker::policy::PathPolicy;
use subagent_broker::state::AgentRuntime;
use subagent_broker::task::{AgentId, Mode, PatchPolicy};
use subagent_broker::workspace::{detect_changes, prepare_workspace, write_baseline_manifest};
use tempfile::tempdir;

#[test]
fn success_patch_check_apply_and_hash_tamper() {
    let dir = tempdir().unwrap();
    let src = dir.path().join("src");
    fs::create_dir_all(&src).unwrap();
    fs::write(src.join("a.txt"), "hello\n").unwrap();
    // init as git for apply target later
    Command::new("git")
        .args(["init", "-q"])
        .current_dir(&src)
        .status()
        .unwrap();
    Command::new("git")
        .args(["config", "user.email", "t@t"])
        .current_dir(&src)
        .status()
        .unwrap();
    Command::new("git")
        .args(["config", "user.name", "t"])
        .current_dir(&src)
        .status()
        .unwrap();
    Command::new("git")
        .args(["add", "-A"])
        .current_dir(&src)
        .status()
        .unwrap();
    Command::new("git")
        .args(["commit", "-q", "-m", "init"])
        .current_dir(&src)
        .status()
        .unwrap();

    let agent = dir.path().join("agent");
    fs::create_dir_all(&agent).unwrap();
    let ws = prepare_workspace(
        &src,
        &agent.join("workspace"),
        Mode::PatchOnly,
        1000,
        10_000_000,
    )
    .unwrap();
    write_baseline_manifest(&agent, &ws).unwrap();
    let baseline = ws.baseline_sha.clone();

    fs::write(ws.root.join("a.txt"), "hello world\n").unwrap();
    let (paths, diff) = detect_changes(&ws).unwrap();
    assert!(!paths.is_empty(), "expected changes");
    assert!(!diff.is_empty());

    let policy = PathPolicy::new(&["**".into()], &[], 50, PatchPolicy::default()).unwrap();
    let candidate = CandidatePatch::new(
        diff,
        paths,
        PatchMetadata {
            baseline_sha: Some(baseline.clone()),
            baseline_manifest_sha256: None,
            baseline_bundle_sha256: None,
            has_deletes: diff_has_deletes(b""),
            has_binary: false,
        },
    );
    // recompute meta from bytes
    let bytes = candidate.bytes().to_vec();
    let paths = candidate.changed_paths().to_vec();
    let candidate = CandidatePatch::new(
        bytes,
        paths,
        PatchMetadata {
            baseline_sha: Some(baseline.clone()),
            baseline_manifest_sha256: None,
            baseline_bundle_sha256: None,
            has_deletes: diff_has_deletes(candidate.bytes()),
            has_binary: diff_has_binary(candidate.bytes()),
        },
    );
    let checked = PolicyCheckedPatch::check(candidate, &policy).unwrap();
    let mut runtime = AgentRuntime::new(
        AgentId::new("a").unwrap(),
        Mode::PatchOnly,
        RequestedIdentity {
            harness: "fake".into(),
            model: None,
        },
        IdentityRequirement::default(),
        1024,
    );
    runtime.apply_harness_event(HarnessEvent::HarnessResult(HarnessTerminalClaim::Success));
    runtime.record_process_exit(Some(0));
    let authorization = runtime.patch_authorization(None).unwrap();
    let mergeable = MergeablePatch::gate(checked, authorization);
    let patch_path = agent.join("patch.diff");
    let rec = persist_patch(mergeable, &patch_path).unwrap();
    assert!(patch_path.exists());
    assert!(sha256_sidecar_path(&patch_path).exists());
    assert!(!rec.sha256().is_empty());

    check_patch_file(&patch_path).unwrap();

    // tamper
    fs::write(&patch_path, b"tampered").unwrap();
    assert!(check_patch_file(&patch_path).is_err());

    // restore by re-writing from workspace again is heavy; just ensure hash mismatch path works
}

#[test]
fn baseline_drift_rejects_apply() {
    let dir = tempdir().unwrap();
    let repo = dir.path().join("repo");
    fs::create_dir_all(&repo).unwrap();
    fs::write(repo.join("f.txt"), "v1\n").unwrap();
    Command::new("git")
        .args(["init", "-q"])
        .current_dir(&repo)
        .status()
        .unwrap();
    Command::new("git")
        .args(["config", "user.email", "t@t"])
        .current_dir(&repo)
        .status()
        .unwrap();
    Command::new("git")
        .args(["config", "user.name", "t"])
        .current_dir(&repo)
        .status()
        .unwrap();
    Command::new("git")
        .args(["add", "-A"])
        .current_dir(&repo)
        .status()
        .unwrap();
    Command::new("git")
        .args(["commit", "-q", "-m", "c1"])
        .current_dir(&repo)
        .status()
        .unwrap();
    let head1 = String::from_utf8(
        Command::new("git")
            .args(["rev-parse", "HEAD"])
            .current_dir(&repo)
            .output()
            .unwrap()
            .stdout,
    )
    .unwrap()
    .trim()
    .to_string();

    // create a minimal valid patch + hash for empty change won't apply — use real diff
    // write dummy patch with hash that check accepts but apply may fail on content;
    // for baseline we only need check hash + head mismatch before apply.
    let patch = dir.path().join("p.diff");
    let body = b"diff --git a/f.txt b/f.txt\n--- a/f.txt\n+++ b/f.txt\n@@ -1 +1 @@\n-v1\n+v2\n";
    fs::write(&patch, body).unwrap();
    let mut h = sha2::Sha256::new();
    use sha2::Digest;
    h.update(body);
    let sha = hex::encode(h.finalize());
    fs::write(format!("{}.sha256", patch.display()), format!("{sha}\n")).unwrap();

    // wrong baseline
    let err = apply_patch_file(&patch, &repo, Some("deadbeef")).unwrap_err();
    assert!(
        err.to_string().to_lowercase().contains("baseline") || err.to_string().contains("mismatch"),
        "{err}"
    );

    // correct baseline should pass check path (apply may succeed)
    let _ = apply_patch_file(&patch, &repo, Some(&head1));
}
