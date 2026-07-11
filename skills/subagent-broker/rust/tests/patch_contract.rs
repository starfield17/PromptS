//! Patch gate contract tests.

#![allow(clippy::unwrap_used, clippy::expect_used)]

use subagent_broker::event::{HarnessEvent, HarnessTerminalClaim, SafeToolName};
use subagent_broker::identity::{IdentityRequirement, RequestedIdentity};
use subagent_broker::patch::{CandidatePatch, PatchMetadata, PolicyCheckedPatch};
use subagent_broker::policy::PathPolicy;
use subagent_broker::state::AgentRuntime;
use subagent_broker::task::{AgentId, Mode, PatchPolicy};

fn runtime(identity: IdentityRequirement) -> AgentRuntime {
    AgentRuntime::new(
        AgentId::new("a").unwrap(),
        Mode::PatchOnly,
        RequestedIdentity {
            harness: "fake".into(),
            model: None,
        },
        identity,
        1024,
    )
}

#[test]
fn denial_cannot_produce_mergeable_patch() {
    let mut agent = runtime(IdentityRequirement::default());
    agent.apply_harness_event(HarnessEvent::PermissionDenied {
        id: None,
        name: Some(SafeToolName::new("Bash")),
    });
    agent.apply_harness_event(HarnessEvent::HarnessResult(HarnessTerminalClaim::Success));
    agent.record_process_exit(Some(0));
    assert!(agent.patch_authorization(None).is_none());
}

#[test]
fn identity_fail_cannot_produce_mergeable_patch() {
    let mut agent = runtime(IdentityRequirement {
        required: true,
        expected_provider: Some("anthropic".into()),
        ..Default::default()
    });
    agent.apply_harness_event(HarnessEvent::HarnessResult(HarnessTerminalClaim::Success));
    agent.record_process_exit(Some(0));
    assert!(agent.patch_authorization(None).is_none());
}

#[test]
fn non_success_harness_cannot_produce_mergeable_patch() {
    let mut agent = runtime(IdentityRequirement::default());
    agent.apply_harness_event(HarnessEvent::HarnessResult(HarnessTerminalClaim::Error));
    agent.record_process_exit(Some(0));
    assert!(agent.patch_authorization(None).is_none());
}

#[test]
fn path_policy_blocks_denied() {
    let c = CandidatePatch::new(
        b"diff --git a/secrets/x b/secrets/x\n".to_vec(),
        vec!["secrets/x".into()],
        PatchMetadata {
            baseline_sha: None,
            baseline_manifest_sha256: None,
            baseline_bundle_sha256: None,
            has_deletes: false,
            has_binary: false,
        },
    );
    let policy = PathPolicy::new(
        &["**".into()],
        &["secrets/**".into()],
        50,
        PatchPolicy::default(),
    )
    .unwrap();
    assert!(PolicyCheckedPatch::check(c, &policy).is_err());
}
