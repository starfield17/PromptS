//! CLI entrypoint for subagent-broker V3.1.

#![forbid(unsafe_code)]
#![deny(unused_must_use)]
#![deny(rust_2018_idioms)]

use std::process::ExitCode;

use subagent_broker::cli;

fn main() -> ExitCode {
    let code = cli::run(std::env::args_os());
    ExitCode::from(code)
}
