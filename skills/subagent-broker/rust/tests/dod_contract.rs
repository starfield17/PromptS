//! Additional DoD coverage: bounds, properties, git/workspace.

#![allow(clippy::unwrap_used, clippy::expect_used)]

use proptest::prelude::*;
use subagent_broker::event::{BoundedChunk, HarnessEvent, HarnessTerminalClaim, SafeToolName};
use subagent_broker::harness::claude::ClaudeParser;
use subagent_broker::harness::StreamParser;
use subagent_broker::identity::{
    IdentityEvidence, IdentityRequirement, ObservedIdentity, RequestedIdentity,
};
use subagent_broker::patch::{
    diff_has_binary, diff_has_deletes, CandidatePatch, PatchMetadata, PolicyCheckedPatch,
};
use subagent_broker::policy::PathPolicy;
use subagent_broker::state::{AgentRuntime, BlockReason, FailureReason, Outcome};
use subagent_broker::task::{AgentId, BoundedText, Mode, PatchPolicy, RepoPath};
use subagent_broker::workspace::prepare_workspace;
use tempfile::tempdir;

#[test]
fn oversized_final_result_forces_response_truncated() {
    let big = "X".repeat(10_000);
    let line =
        format!(r#"{{"type":"result","subtype":"success","is_error":false,"result":"{big}"}}"#);
    let mut p = ClaudeParser::new(100, 1 << 22);
    let mut evs = p.push(line.as_bytes()).unwrap();
    evs.extend(p.finish().unwrap());

    let mut agent = AgentRuntime::new(
        AgentId::new("a").unwrap(),
        Mode::ReadOnly,
        RequestedIdentity {
            harness: "claude_code".into(),
            model: None,
        },
        IdentityRequirement::default(),
        100,
    );
    for e in evs {
        agent.apply_harness_event(e);
    }
    let o = agent.finish_without_patch(None);
    assert!(
        matches!(
            o,
            Outcome::Failed {
                reason: FailureReason::ResponseTruncated,
                ..
            }
        ),
        "got {o:?}"
    );
    assert!(o.patch().is_none());
}

#[test]
fn twenty_mib_tool_result_line_is_skipped_not_buffered() {
    let mut huge = String::with_capacity(21 * 1024 * 1024);
    huge.push_str(
        r#"{"type":"user","message":{"content":[{"type":"tool_result","tool_use_id":"t1","content":""#,
    );
    huge.extend(std::iter::repeat('a').take(20 * 1024 * 1024));
    huge.push_str(r#""}]}}"#);
    huge.push('\n');
    huge.push_str(
        r#"{"type":"result","subtype":"success","is_error":false,"result":"FINAL_AFTER_HUGE"}"#,
    );
    huge.push('\n');

    let max_line = 1024 * 1024;
    let mut p = ClaudeParser::new(64 * 1024, max_line);
    let mut evs = p.push(huge.as_bytes()).unwrap();
    evs.extend(p.finish().unwrap());

    assert!(
        evs.iter()
            .any(|e| matches!(e, HarnessEvent::OversizedEventSkipped { .. })),
        "expected oversized skip"
    );
    let mut saw_final = false;
    for e in &evs {
        if let HarnessEvent::FinalResult(BoundedChunk { text }) = e {
            assert!(text.to_string_lossy().contains("FINAL_AFTER_HUGE"));
            saw_final = true;
        }
    }
    assert!(
        saw_final,
        "final result must still parse after oversized skip"
    );
}

proptest! {
    #[test]
    fn repo_path_never_escapes(s in ".*") {
        if let Ok(p) = RepoPath::new(&s) {
            prop_assert!(!p.as_str().starts_with('/'));
            prop_assert!(!p.as_str().is_empty());
            prop_assert!(!p.as_str().split('/').any(|seg| seg.is_empty() || seg == "." || seg == ".."));
        }
    }

    #[test]
    fn bounded_text_never_exceeds_limit(s in "\\PC{0,500}", lim in 1usize..64) {
        let mut t = BoundedText::new(lim);
        t.push_str(&s, lim);
        prop_assert!(t.len() <= lim);
    }

    #[test]
    fn denial_never_success(tool in "[A-Za-z]{1,16}") {
        let mut agent = AgentRuntime::new(
            AgentId::new("a").unwrap(),
            Mode::ReadOnly,
            RequestedIdentity {
                harness: "fake".into(),
                model: None,
            },
            IdentityRequirement::default(),
            1024,
        );
        agent.apply_harness_event(HarnessEvent::PermissionDenied {
            id: None,
            name: Some(SafeToolName::new(tool)),
        });
        agent.apply_harness_event(HarnessEvent::HarnessResult(HarnessTerminalClaim::Success));
        let o = agent.finish_without_patch(None);
        let is_blocked = matches!(o, Outcome::Blocked { .. });
        prop_assert!(is_blocked);
        prop_assert_eq!(o.reason_str(), Some("permission_denied"));
        prop_assert!(o.patch().is_none());
    }
}

#[test]
fn identity_mismatch_never_success_no_patch() {
    let req = IdentityRequirement {
        required: true,
        expected_provider: Some("anthropic".into()),
        ..Default::default()
    };
    let mut agent = AgentRuntime::new(
        AgentId::new("a").unwrap(),
        Mode::ReadOnly,
        RequestedIdentity {
            harness: "claude_code".into(),
            model: Some("claude-x".into()),
        },
        req,
        1024,
    );
    agent.apply_harness_event(HarnessEvent::IdentityObserved(ObservedIdentity {
        provider: Some("xai".into()),
        model: Some("grok".into()),
        api_key_source: None,
        evidence: Some(IdentityEvidence::StreamClaim),
    }));
    agent.apply_harness_event(HarnessEvent::HarnessResult(HarnessTerminalClaim::Success));
    let o = agent.finish_without_patch(None);
    assert!(matches!(
        o,
        Outcome::Blocked {
            reason: BlockReason::ProviderMismatch
        }
    ));
    assert!(o.patch().is_none());
}

#[test]
fn workspace_preserves_dirty_source_and_detects_change() {
    let dir = tempdir().unwrap();
    let src = dir.path().join("src_repo");
    std::fs::create_dir_all(&src).unwrap();
    std::fs::write(src.join("a.txt"), "hello").unwrap();
    std::fs::write(src.join("dirty.bin"), b"\0\x01\x02binary").unwrap();
    std::fs::write(src.join("café.txt"), "cafe").unwrap();

    let dest = dir.path().join("agent_ws");
    let ws = prepare_workspace(&src, &dest, Mode::PatchOnly, 1000, 10_000_000).unwrap();
    assert_eq!(std::fs::read_to_string(src.join("a.txt")).unwrap(), "hello");
    assert!(src.join("dirty.bin").exists());

    std::fs::write(ws.root.join("a.txt"), "changed").unwrap();
    let (paths, diff) = subagent_broker::workspace::detect_changes(&ws).unwrap();
    assert!(paths.iter().any(|p| p.contains("a.txt")), "{paths:?}");
    assert!(!diff.is_empty());

    assert!(diff_has_binary(b"Binary files a/x and b/x differ\n"));
    assert!(diff_has_deletes(b"deleted file mode 100644\n"));
}

#[test]
fn binary_policy_blocks_mergeable() {
    let c = CandidatePatch::new(
        b"Binary files a/x.bin and b/x.bin differ\n".to_vec(),
        vec!["x.bin".into()],
        PatchMetadata {
            baseline_sha: None,
            baseline_manifest_sha256: None,
            baseline_bundle_sha256: None,
            has_deletes: false,
            has_binary: true,
        },
    );
    let policy = PathPolicy::new(
        &["**".into()],
        &[],
        50,
        PatchPolicy {
            allow_deletes: false,
            allow_binary_changes: false,
        },
    )
    .unwrap();
    assert!(PolicyCheckedPatch::check(c, &policy).is_err());
}

#[test]
fn delete_policy_blocks_mergeable() {
    let c = CandidatePatch::new(
        b"deleted file mode 100644\n".to_vec(),
        vec!["gone.txt".into()],
        PatchMetadata {
            baseline_sha: None,
            baseline_manifest_sha256: None,
            baseline_bundle_sha256: None,
            has_deletes: true,
            has_binary: false,
        },
    );
    let policy = PathPolicy::new(&["**".into()], &[], 50, PatchPolicy::default()).unwrap();
    assert!(PolicyCheckedPatch::check(c, &policy).is_err());
}
