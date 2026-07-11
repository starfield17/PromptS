//! Fuzz-style smoke: random bytes must not panic; buffers stay bounded.

#![allow(clippy::unwrap_used, clippy::expect_used)]

use proptest::prelude::*;
use subagent_broker::event::HarnessEvent;
use subagent_broker::harness::claude::ClaudeParser;
use subagent_broker::harness::StreamParser;
use subagent_broker::task::{BoundedText, RepoPath};

proptest! {
    #![proptest_config(ProptestConfig::with_cases(64))]

    #[test]
    fn claude_parser_never_panics_on_bytes(data in prop::collection::vec(any::<u8>(), 0..4096)) {
        let max_line = 512usize;
        let mut p = ClaudeParser::new(256, max_line);
        let r1 = p.push(&data);
        prop_assert!(r1.is_ok());
        let r2 = p.finish();
        prop_assert!(r2.is_ok());
        // Denial metadata must never embed raw command payloads from input blindly as long strings
        if let Ok(evs) = r2 {
            for e in evs {
                if let HarnessEvent::PermissionDenied { name, .. } = e {
                    prop_assert!(name.as_ref().map(|n| n.as_str().len()).unwrap_or(0) <= 128);
                }
            }
        }
    }

    #[test]
    fn repo_path_never_panics(s in "\\PC*") {
        let _ = RepoPath::new(&s);
    }

    #[test]
    fn bounded_text_len_cap(s in "\\PC{0,800}", lim in 1usize..64) {
        let mut t = BoundedText::new(lim);
        t.push_str(&s, lim);
        prop_assert!(t.len() <= lim);
        prop_assert!(std::str::from_utf8(t.raw_bytes()).is_ok());
    }
}

#[test]
fn denial_fixture_has_no_command_payload() {
    let data = std::fs::read(
        std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .join("tests/fixtures/streams/denial_with_success_claim.jsonl"),
    )
    .unwrap();
    let mut p = ClaudeParser::new(1 << 16, 1 << 20);
    let mut evs = p.push(&data).unwrap();
    evs.extend(p.finish().unwrap());
    for e in evs {
        if let HarnessEvent::PermissionDenied { name, id } = e {
            // Only safe tool name / id — never full command from tool_input
            if let Some(n) = name {
                assert_ne!(n.as_str(), "cat /etc/shadow");
                assert!(!n.as_str().contains("/etc/shadow"));
            }
            let _ = id;
        }
    }
}
