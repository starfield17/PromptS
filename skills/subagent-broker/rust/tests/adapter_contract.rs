//! Adapter argv and permission support contracts; no vendor credentials needed.

#![allow(clippy::unwrap_used, clippy::expect_used)]

use serde_json::json;
use subagent_broker::harness::AdapterBundle;
use subagent_broker::task::TaskPacket;

fn packet(kind: &str, permissions: &[&str], mode: &str) -> TaskPacket {
    let harness = if kind == "custom" {
        json!({
            "kind": "custom",
            "executable": "/bin/true",
            "stream_family": "plain"
        })
    } else {
        json!({"kind": kind})
    };
    TaskPacket::parse_slice(
        serde_json::to_vec(&json!({
            "schema_version": 3,
            "run_id": format!("adapter-{kind}"),
            "agents": [{
                "id": "worker",
                "goal": "inspect",
                "harness": harness,
                "mode": mode,
                "requested_permissions": permissions,
                "allowed_paths": ["src/**"],
                "deny_paths": ["secrets/**"]
            }]
        }))
        .unwrap()
        .as_slice(),
    )
    .unwrap()
}

#[test]
fn adapters_receive_the_canonical_prompt() {
    for kind in ["claude_code", "grok_build", "codex_cli", "custom"] {
        let parsed = packet(kind, &["repo_read"], "read_only");
        let spec = &parsed.agents[0];
        let bundle = AdapterBundle::from_spec(&spec.harness).unwrap();
        let argv = bundle.build_argv(spec, std::path::Path::new("/tmp/work"));
        let prompt = argv.last().unwrap();
        assert!(prompt.contains("Allowed paths: src/**"), "{kind}: {prompt}");
        assert!(
            prompt.contains("Denied paths: secrets/**"),
            "{kind}: {prompt}"
        );
        assert!(
            prompt.contains("Requested permissions: repo_read"),
            "{kind}: {prompt}"
        );
    }
}

#[test]
fn unsupported_permission_is_rejected_before_spawn() {
    let value = json!({
        "schema_version": 3,
        "run_id": "unsupported-permission",
        "agents": [{
            "id": "worker",
            "goal": "inspect",
            "harness": {"kind": "codex_cli"},
            "mode": "read_only",
            "requested_permissions": ["repo_read", "python_test"]
        }]
    });
    assert!(TaskPacket::parse_slice(&serde_json::to_vec(&value).unwrap()).is_err());
}
