//! Symlink must not redirect artifact writes.

#![allow(clippy::unwrap_used, clippy::expect_used)]
#![cfg(unix)]

use std::fs;
use std::os::unix::fs::symlink;
use std::process::Command;

use subagent_broker::persistence::{atomic_write_bytes, refuse_symlink};
use subagent_broker::task::Mode;
use subagent_broker::workspace::prepare_workspace;
use tempfile::tempdir;

#[test]
fn atomic_write_refuses_symlink_destination() {
    let dir = tempdir().unwrap();
    let evil = dir.path().join("evil_target");
    fs::write(&evil, b"owned").unwrap();
    let dest = dir.path().join("result.json");
    symlink(&evil, &dest).unwrap();
    let err = atomic_write_bytes(&dest, b"hijack").unwrap_err();
    assert!(err.to_string().to_lowercase().contains("symlink"), "{err}");
    // Evil file must not be overwritten with hijack content
    assert_eq!(fs::read(&evil).unwrap(), b"owned");
}

#[test]
fn refuse_symlink_ok_for_normal_path() {
    let dir = tempdir().unwrap();
    let p = dir.path().join("normal");
    fs::write(&p, b"x").unwrap();
    refuse_symlink(&p).unwrap();
}

fn git_init(path: &std::path::Path) {
    Command::new("git")
        .args(["init", "-q"])
        .current_dir(path)
        .status()
        .unwrap();
    Command::new("git")
        .args(["config", "user.email", "test@example.invalid"])
        .current_dir(path)
        .status()
        .unwrap();
    Command::new("git")
        .args(["config", "user.name", "test"])
        .current_dir(path)
        .status()
        .unwrap();
}

#[test]
fn workspace_rejects_absolute_and_escape_symlinks() {
    let dir = tempdir().unwrap();
    let source = dir.path().join("source");
    fs::create_dir_all(&source).unwrap();
    fs::write(source.join("README.md"), "ok\n").unwrap();
    git_init(&source);
    let outside = dir.path().join("outside");
    fs::write(&outside, "secret\n").unwrap();
    symlink(&outside, source.join("absolute-link")).unwrap();
    Command::new("git")
        .args(["add", "README.md", "absolute-link"])
        .current_dir(&source)
        .status()
        .unwrap();
    Command::new("git")
        .args(["commit", "-q", "-m", "baseline"])
        .current_dir(&source)
        .status()
        .unwrap();
    let err = prepare_workspace(
        &source,
        &dir.path().join("workspace"),
        Mode::ReadOnly,
        100,
        1_000_000,
    )
    .unwrap_err();
    assert!(err.to_string().contains("symlink"), "{err}");
}

#[test]
fn workspace_allows_internal_relative_symlink() {
    let dir = tempdir().unwrap();
    let source = dir.path().join("source");
    fs::create_dir_all(&source).unwrap();
    fs::write(source.join("README.md"), "ok\n").unwrap();
    symlink("README.md", source.join("readme-link")).unwrap();
    git_init(&source);
    Command::new("git")
        .args(["add", "README.md", "readme-link"])
        .current_dir(&source)
        .status()
        .unwrap();
    Command::new("git")
        .args(["commit", "-q", "-m", "baseline"])
        .current_dir(&source)
        .status()
        .unwrap();
    prepare_workspace(
        &source,
        &dir.path().join("workspace"),
        Mode::ReadOnly,
        100,
        1_000_000,
    )
    .unwrap();
}
