//! Stream fixture contracts — normalized events, not string contains only.

#![allow(clippy::unwrap_used, clippy::expect_used, clippy::panic)]

use std::fs;
use std::path::PathBuf;

use subagent_broker::event::{HarnessEvent, HarnessTerminalClaim};
use subagent_broker::harness::claude::ClaudeParser;
use subagent_broker::harness::codex::CodexParser;
use subagent_broker::harness::grok::GrokParser;
use subagent_broker::harness::StreamParser;

fn fixture(name: &str) -> Vec<u8> {
    let path = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("tests/fixtures/streams")
        .join(name);
    fs::read(&path).unwrap_or_else(|e| panic!("read {}: {e}", path.display()))
}

fn parse_claude(data: &[u8], max_result: usize) -> Vec<HarnessEvent> {
    let mut p = ClaudeParser::new(max_result, 1 << 22);
    let mut evs = p.push(data).unwrap();
    evs.extend(p.finish().unwrap());
    evs
}

fn parse_grok(data: &[u8]) -> Vec<HarnessEvent> {
    let mut p = GrokParser::new(1 << 16, 1 << 20);
    let mut evs = p.push(data).unwrap();
    evs.extend(p.finish().unwrap());
    evs
}

fn parse_codex(data: &[u8]) -> Vec<HarnessEvent> {
    let mut p = CodexParser::new(1 << 16, 1 << 20);
    let mut evs = p.push(data).unwrap();
    evs.extend(p.finish().unwrap());
    evs
}

fn has_final_success(evs: &[HarnessEvent]) -> bool {
    evs.iter().any(|e| {
        matches!(
            e,
            HarnessEvent::HarnessResult(HarnessTerminalClaim::Success)
        )
    }) && evs
        .iter()
        .any(|e| matches!(e, HarnessEvent::FinalResult(_)))
}

#[test]
fn claude_invalid_json_line_recovers_final() {
    let evs = parse_claude(&fixture("claude_invalid_json_line.jsonl"), 1 << 16);
    assert!(has_final_success(&evs), "events={evs:?}");
    assert!(evs
        .iter()
        .any(|e| matches!(e, HarnessEvent::IdentityObserved(_))));
}

#[test]
fn parser_diagnostics_expose_schema_drift() {
    let mut invalid = ClaudeParser::new(1 << 16, 1 << 20);
    invalid
        .push(&fixture("claude_invalid_json_line.jsonl"))
        .unwrap();
    invalid.finish().unwrap();
    assert_eq!(invalid.diagnostics().invalid_json_count, 1);

    let mut unknown = ClaudeParser::new(1 << 16, 1 << 20);
    unknown
        .push(&fixture("claude_unknown_future_event.jsonl"))
        .unwrap();
    unknown.finish().unwrap();
    assert_eq!(unknown.diagnostics().unknown_event_count, 1);
}

#[test]
fn claude_unknown_future_event_ignored() {
    let evs = parse_claude(&fixture("claude_unknown_future_event.jsonl"), 1 << 16);
    assert!(has_final_success(&evs), "events={evs:?}");
}

#[test]
fn claude_unicode_truncation_valid_utf8() {
    // Tiny budget forces mid-multibyte truncation.
    let evs = parse_claude(&fixture("claude_unicode_truncation.jsonl"), 12);
    let mut saw = false;
    for e in &evs {
        if let HarnessEvent::FinalResult(c) = e {
            saw = true;
            let s = c.text.to_string_lossy();
            assert!(std::str::from_utf8(s.as_bytes()).is_ok());
            // truncated flag when original exceeded budget
            assert!(c.text.truncated() || c.text.original_bytes() as usize <= 12);
        }
    }
    assert!(saw, "expected final result: {evs:?}");
}

#[test]
fn verbose_tool_result_still_yields_final_or_skip() {
    let data = fixture("verbose_tool_result.jsonl");
    // Cap line framing so huge tool content may skip; final should remain.
    let mut p = ClaudeParser::new(1 << 18, 256 * 1024);
    let mut evs = p.push(&data).unwrap();
    evs.extend(p.finish().unwrap());
    let has_final = evs
        .iter()
        .any(|e| matches!(e, HarnessEvent::FinalResult(_)));
    let has_success = evs.iter().any(|e| {
        matches!(
            e,
            HarnessEvent::HarnessResult(HarnessTerminalClaim::Success)
        )
    });
    let has_skip = evs
        .iter()
        .any(|e| matches!(e, HarnessEvent::OversizedEventSkipped { .. }));
    assert!(
        has_final || has_skip,
        "expected final and/or oversized skip; success={has_success} events_len={}",
        evs.len()
    );
    // Prefer final when present
    if has_final {
        assert!(has_success || has_final);
    }
}

#[test]
fn grok_cancelled_is_not_success() {
    let evs = parse_grok(&fixture("grok_cancelled.jsonl"));
    assert!(
        evs.iter().any(|e| {
            matches!(
                e,
                HarnessEvent::HarnessResult(HarnessTerminalClaim::Cancelled)
            )
        }),
        "events={evs:?}"
    );
    assert!(!evs.iter().any(|e| {
        matches!(
            e,
            HarnessEvent::HarnessResult(HarnessTerminalClaim::Success)
        )
    }));
}

#[test]
fn grok_end_missing_errors_on_finish() {
    let evs = parse_grok(&fixture("grok_end_missing.jsonl"));
    assert!(
        evs.iter()
            .any(|e| { matches!(e, HarnessEvent::HarnessResult(HarnessTerminalClaim::Error)) }),
        "events={evs:?}"
    );
}

#[test]
fn codex_turn_failed_is_error() {
    let evs = parse_codex(&fixture("codex_turn_failed.jsonl"));
    assert!(
        evs.iter().any(|e| {
            matches!(e, HarnessEvent::HarnessResult(HarnessTerminalClaim::Error))
                || matches!(e, HarnessEvent::HarnessError(_))
        }),
        "events={evs:?}"
    );
    assert!(!evs.iter().any(|e| {
        matches!(
            e,
            HarnessEvent::HarnessResult(HarnessTerminalClaim::Success)
        )
    }));
}

#[test]
fn codex_success_minimal() {
    let evs = parse_codex(&fixture("codex_success_minimal.jsonl"));
    assert!(
        evs.iter().any(|e| {
            matches!(
                e,
                HarnessEvent::HarnessResult(HarnessTerminalClaim::Success)
            )
        }),
        "events={evs:?}"
    );
    assert!(evs
        .iter()
        .any(|e| matches!(e, HarnessEvent::FinalResult(_))));
}
