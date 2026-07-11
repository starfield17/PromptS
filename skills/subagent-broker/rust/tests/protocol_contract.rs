//! Protocol contract tests for Task/Result V3.

#![allow(clippy::unwrap_used, clippy::expect_used)]

use subagent_broker::task::TaskPacket;

#[test]
fn schema_version_must_be_3() {
    let v2 = r#"{"schema_version":2,"run_id":"r1","agents":[{"id":"a","goal":"g","harness":{"kind":"fake"},"mode":"read_only","capabilities":["repo_read"]}]}"#;
    let err = TaskPacket::parse_str(v2).unwrap_err();
    let msg = err.to_string();
    assert!(msg.contains("schema_version") || msg.contains("2"), "{msg}");
}

#[test]
fn rejects_unknown_fields() {
    let j = r#"{
        "schema_version": 3,
        "run_id": "r1",
        "unexpected_top": true,
        "agents": [{
            "id": "a",
            "goal": "g",
            "harness": {"kind": "fake"},
            "mode": "read_only",
            "capabilities": ["repo_read"]
        }]
    }"#;
    assert!(TaskPacket::parse_str(j).is_err());
}

#[test]
fn accepts_v3_example_shape() {
    let path = concat!(
        env!("CARGO_MANIFEST_DIR"),
        "/../templates/task.v3.example.json"
    );
    let result = TaskPacket::load_path(std::path::Path::new(path));
    assert!(result.is_ok(), "{result:?}");
}

#[test]
fn result_template_is_schema_3() {
    let path = concat!(
        env!("CARGO_MANIFEST_DIR"),
        "/../templates/result.v3.example.json"
    );
    let bytes = std::fs::read(path).expect("result template");
    let v: serde_json::Value = serde_json::from_slice(&bytes).expect("json");
    assert_eq!(v["schema_version"], 3);
    assert!(v.get("revision").is_some());
    assert!(v.get("agents").is_some());
}
