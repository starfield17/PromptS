//! Git orchestration via system git (argv arrays, NUL-delimited where possible).

use std::io::Read;
use std::path::Path;
use std::process::{Command, Stdio};

use crate::error::{BrokerResult, GitError};

pub fn run_git(cwd: &Path, args: &[&str]) -> BrokerResult<String> {
    let output = Command::new("git")
        .args(args)
        .current_dir(cwd)
        .output()
        .map_err(|e| GitError::Message(format!("spawn git: {e}")))?;
    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        return Err(GitError::Message(format!(
            "git {} failed: {}",
            args.join(" "),
            stderr.chars().take(512).collect::<String>()
        ))
        .into());
    }
    Ok(String::from_utf8_lossy(&output.stdout).into_owned())
}

pub fn run_git_bytes(cwd: &Path, args: &[&str]) -> BrokerResult<Vec<u8>> {
    let output = Command::new("git")
        .args(args)
        .current_dir(cwd)
        .output()
        .map_err(|e| GitError::Message(format!("spawn git: {e}")))?;
    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        return Err(GitError::Message(format!(
            "git {} failed: {}",
            args.join(" "),
            stderr.chars().take(512).collect::<String>()
        ))
        .into());
    }
    Ok(output.stdout)
}

/// Run git while retaining at most `max_bytes` of stdout. This prevents a
/// malicious or unexpectedly large diff from becoming an unbounded Vec.
pub fn run_git_bytes_bounded(cwd: &Path, args: &[&str], max_bytes: u64) -> BrokerResult<Vec<u8>> {
    let mut child = Command::new("git")
        .args(args)
        .current_dir(cwd)
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .map_err(|e| GitError::Message(format!("spawn git: {e}")))?;
    let mut stdout = child
        .stdout
        .take()
        .ok_or_else(|| GitError::Message("git stdout unavailable".into()))?;
    let mut bytes = Vec::new();
    let mut buffer = [0u8; 64 * 1024];
    loop {
        let n = stdout
            .read(&mut buffer)
            .map_err(|e| GitError::Message(format!("read git stdout: {e}")))?;
        if n == 0 {
            break;
        }
        if bytes.len() as u64 > max_bytes.saturating_sub(n as u64) {
            let _ = child.kill();
            let _ = child.wait();
            return Err(GitError::Message(format!(
                "git output exceeds budget ({max_bytes} bytes)"
            ))
            .into());
        }
        bytes.extend_from_slice(&buffer[..n]);
    }
    let output = child
        .wait_with_output()
        .map_err(|e| GitError::Message(format!("wait git: {e}")))?;
    if !output.status.success() {
        return Err(GitError::Message(format!(
            "git {} failed: {}",
            args.join(" "),
            String::from_utf8_lossy(&output.stderr)
                .chars()
                .take(512)
                .collect::<String>()
        ))
        .into());
    }
    Ok(bytes)
}

pub fn git_version() -> BrokerResult<String> {
    let output = Command::new("git")
        .arg("--version")
        .output()
        .map_err(|e| GitError::Message(e.to_string()))?;
    Ok(String::from_utf8_lossy(&output.stdout).trim().to_string())
}

pub fn is_git_repo(path: &Path) -> bool {
    path.join(".git").exists()
        || Command::new("git")
            .args(["rev-parse", "--is-inside-work-tree"])
            .current_dir(path)
            .output()
            .map(|o| o.status.success())
            .unwrap_or(false)
}

pub fn has_submodules(path: &Path) -> bool {
    path.join(".gitmodules").exists()
}

pub fn head_sha(cwd: &Path) -> BrokerResult<String> {
    let s = run_git(cwd, &["rev-parse", "HEAD"])?;
    Ok(s.trim().to_string())
}

/// List tracked + untracked non-ignored files (NUL-delimited plumbing).
pub fn list_files_nul(cwd: &Path) -> BrokerResult<Vec<String>> {
    let mut files = Vec::new();
    // tracked
    let tracked = run_git_bytes(cwd, &["ls-files", "-z"])?;
    for part in tracked.split(|b| *b == 0) {
        if part.is_empty() {
            continue;
        }
        files.push(String::from_utf8_lossy(part).into_owned());
    }
    // untracked non-ignored
    let untracked = run_git_bytes(cwd, &["ls-files", "-z", "--others", "--exclude-standard"])?;
    for part in untracked.split(|b| *b == 0) {
        if part.is_empty() {
            continue;
        }
        let s = String::from_utf8_lossy(part).into_owned();
        if !files.contains(&s) {
            files.push(s);
        }
    }
    Ok(files)
}

/// Lossless tracked + non-ignored untracked paths on Unix.
#[cfg(unix)]
pub fn list_file_paths_nul(cwd: &Path) -> BrokerResult<Vec<std::path::PathBuf>> {
    list_file_paths_nul_with_limits(cwd, u64::MAX, u64::MAX)
}

#[cfg(unix)]
pub fn list_file_paths_nul_with_limits(
    cwd: &Path,
    max_paths: u64,
    max_output_bytes: u64,
) -> BrokerResult<Vec<std::path::PathBuf>> {
    use std::os::unix::ffi::OsStringExt;
    let mut files = Vec::new();
    for args in [
        &["ls-files", "-z"][..],
        &["ls-files", "-z", "--others", "--exclude-standard"][..],
    ] {
        let output = run_git_bytes_bounded(cwd, args, max_output_bytes)?;
        for part in output.split(|b| *b == 0).filter(|p| !p.is_empty()) {
            let first = part.split(|b| *b == b'/').next().unwrap_or(part);
            if first == b".git"
                || first == b".subagents"
                || first.starts_with(b".env")
                || first == b"secrets"
            {
                continue;
            }
            let path = std::path::PathBuf::from(std::ffi::OsString::from_vec(part.to_vec()));
            if !files.contains(&path) {
                files.push(path);
                if files.len() as u64 > max_paths {
                    return Err(GitError::Message(format!(
                        "git file list exceeds max_paths ({max_paths})"
                    ))
                    .into());
                }
            }
        }
    }
    Ok(files)
}

pub fn export_diff(cwd: &Path, baseline: &str) -> BrokerResult<Vec<u8>> {
    // Include untracked by first adding in a copy — for standalone agent repo, plain diff works.
    run_git_bytes(cwd, &["diff", "--binary", baseline, "--"])
}

pub fn init_standalone(repo: &Path) -> BrokerResult<()> {
    std::fs::create_dir_all(repo).map_err(|e| GitError::Message(e.to_string()))?;
    run_git(repo, &["init", "-q"])?;
    run_git(repo, &["config", "user.email", "broker@local"])?;
    run_git(repo, &["config", "user.name", "subagent-broker"])?;
    Ok(())
}

pub fn commit_all(repo: &Path, message: &str) -> BrokerResult<String> {
    run_git(repo, &["add", "-A"])?;
    // Allow empty for baseline
    let _ = Command::new("git")
        .args(["commit", "-q", "--allow-empty", "-m", message])
        .current_dir(repo)
        .status();
    head_sha(repo)
}

/// Create a git bundle of HEAD without following a symlink destination.
pub fn create_baseline_bundle(repo: &Path, bundle_path: &Path) -> BrokerResult<String> {
    use crate::persistence::refuse_symlink;
    use std::fs;

    if bundle_path
        .symlink_metadata()
        .map(|m| m.file_type().is_symlink())
        .unwrap_or(false)
    {
        return Err(GitError::Message(format!(
            "refusing to write baseline bundle through symlink: {}",
            bundle_path.display()
        ))
        .into());
    }
    if let Some(parent) = bundle_path.parent() {
        fs::create_dir_all(parent).map_err(|e| GitError::Message(e.to_string()))?;
        refuse_symlink(parent).map_err(|e| GitError::Message(e.to_string()))?;
    }
    if bundle_path.exists() {
        fs::remove_file(bundle_path).map_err(|e| GitError::Message(e.to_string()))?;
    }
    run_git(
        repo,
        &[
            "bundle",
            "create",
            &bundle_path.display().to_string(),
            "HEAD",
        ],
    )?;
    refuse_symlink(bundle_path).map_err(|e| GitError::Message(e.to_string()))?;
    crate::workspace::sha256_file_hex(bundle_path)
}

pub fn clone_bundle(bundle_path: &Path, destination: &Path) -> BrokerResult<()> {
    let output = Command::new("git")
        .arg("clone")
        .arg("-q")
        .arg(bundle_path)
        .arg(destination)
        .output()
        .map_err(|e| GitError::Message(format!("spawn git clone: {e}")))?;
    if !output.status.success() {
        return Err(GitError::Message(format!(
            "git clone trusted bundle failed: {}",
            String::from_utf8_lossy(&output.stderr)
                .chars()
                .take(512)
                .collect::<String>()
        ))
        .into());
    }
    Ok(())
}
