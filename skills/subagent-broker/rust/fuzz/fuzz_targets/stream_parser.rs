#![no_main]

use libfuzzer_sys::fuzz_target;
use subagent_broker::harness::claude::ClaudeParser;
use subagent_broker::harness::StreamParser;

fuzz_target!(|data: &[u8]| {
    let mut p = ClaudeParser::new(64 * 1024, 256 * 1024);
    let _ = p.push(data);
    let _ = p.finish();
});
