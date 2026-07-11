//! Workspace isolation: dirty source tree must not be mutated; agent changes detectable.

#![allow(clippy::unwrap_used, clippy::expect_used)]

use std::fs;
#[cfg(unix)]
use std::os::unix::ffi::OsStringExt;
use std::process::Command;

use subagent_broker::task::Mode;
use subagent_broker::workspace::{detect_changes, prepare_workspace};
use tempfile::tempdir;

#[test]
fn dirty_tree_source_preserved_and_agent_changes_detected() {
    let dir = tempdir().unwrap();
    let src = dir.path().join("repo");
    fs::create_dir_all(src.join("sub")).unwrap();
    fs::write(src.join("tracked.txt"), "t0\n").unwrap();
    fs::write(src.join("sub/nested.txt"), "n0\n").unwrap();
    fs::write(src.join(".gitignore"), "ignored-secret\n").unwrap();
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
        .args(["commit", "-q", "-m", "base"])
        .current_dir(&src)
        .status()
        .unwrap();

    // dirty: unstaged modify + untracked
    fs::write(src.join("tracked.txt"), "t1\n").unwrap();
    fs::write(src.join("untracked.txt"), "u\n").unwrap();
    fs::write(src.join("ignored-secret"), "must not be delegated\n").unwrap();

    let ws_dest = dir.path().join("v3ws");
    let ws = prepare_workspace(&src, &ws_dest, Mode::PatchOnly, 10_000, 50_000_000).unwrap();
    assert!(!ws.root.join("ignored-secret").exists());

    // Mutate agent workspace like a harness would.
    fs::write(ws.root.join("tracked.txt"), "t2\n").unwrap();
    fs::write(ws.root.join("new_from_agent.txt"), "x\n").unwrap();
    #[cfg(unix)]
    fs::write(
        ws.root
            .join(std::ffi::OsString::from_vec(b"nonutf8-\xff.txt".to_vec())),
        "raw path\n",
    )
    .unwrap();

    let (paths, diff) = detect_changes(&ws).unwrap();
    assert!(
        paths.iter().any(|p| p.contains("tracked")),
        "paths={paths:?}"
    );
    assert!(
        paths.iter().any(|p| p.contains("new_from_agent")),
        "paths={paths:?}"
    );
    #[cfg(unix)]
    assert!(paths.iter().any(|p| p.contains("%FF")), "paths={paths:?}");
    assert!(!diff.is_empty());

    // Source must remain dirty as before prepare (isolation).
    assert_eq!(fs::read_to_string(src.join("tracked.txt")).unwrap(), "t1\n");
    assert!(src.join("untracked.txt").exists());
}
