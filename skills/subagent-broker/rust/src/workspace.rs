//! Isolated workspace construction and change detection.

use std::io::Read;
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};
use std::time::{Duration, Instant};

use sha2::{Digest, Sha256};

use crate::environment::PreparedEnvironment;
use crate::error::{BrokerResult, WorkspaceError};
use crate::git;
use crate::task::Mode;

#[derive(Debug, Clone)]
pub struct VerificationRun {
    pub command: String,
    pub exit_code: Option<i32>,
    pub timed_out: bool,
    pub stdout_bytes: u64,
    pub stderr_bytes: u64,
    pub output_truncated: bool,
}

pub fn run_verification(
    root: &Path,
    commands: &[Vec<String>],
    timeout_ms: u64,
    max_output_bytes: u64,
    environment: Option<&PreparedEnvironment>,
) -> BrokerResult<(Vec<VerificationRun>, bool)> {
    let mut results = Vec::with_capacity(commands.len());
    let mut all_passed = true;
    for argv in commands {
        let command = argv.first().cloned().unwrap_or_else(|| "<empty>".into());
        let mut command_builder = Command::new(&command);
        command_builder
            .args(&argv[1..])
            .current_dir(root)
            .stdin(Stdio::null())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped());
        if let Some(environment) = environment {
            command_builder.env_clear().envs(&environment.vars);
        }
        let mut child = match command_builder.spawn() {
            Ok(child) => child,
            Err(_) => {
                all_passed = false;
                results.push(VerificationRun {
                    command,
                    exit_code: None,
                    timed_out: false,
                    stdout_bytes: 0,
                    stderr_bytes: 0,
                    output_truncated: false,
                });
                continue;
            }
        };
        let stdout = child.stdout.take();
        let stderr = child.stderr.take();
        let stdout_thread = std::thread::spawn(move || {
            stdout
                .map(|pipe| read_bounded_pipe(pipe, max_output_bytes))
                .unwrap_or((0, false))
        });
        let stderr_thread = std::thread::spawn(move || {
            stderr
                .map(|pipe| read_bounded_pipe(pipe, max_output_bytes))
                .unwrap_or((0, false))
        });
        let deadline = Instant::now() + Duration::from_millis(timeout_ms.max(1));
        let mut timed_out = false;
        let status = loop {
            match child.try_wait() {
                Ok(Some(status)) => break Some(status),
                Ok(None) if Instant::now() >= deadline => {
                    timed_out = true;
                    let _ = child.kill();
                    break child.wait().ok();
                }
                Ok(None) => std::thread::sleep(Duration::from_millis(10)),
                Err(_) => break None,
            }
        };
        let (stdout_bytes, stdout_truncated) = stdout_thread.join().unwrap_or((0, true));
        let (stderr_bytes, stderr_truncated) = stderr_thread.join().unwrap_or((0, true));
        let exit_code = status.and_then(|status| status.code());
        let passed = !timed_out && status.is_some_and(|status| status.success());
        all_passed &= passed;
        results.push(VerificationRun {
            command,
            exit_code,
            timed_out,
            stdout_bytes,
            stderr_bytes,
            output_truncated: stdout_truncated || stderr_truncated,
        });
    }
    Ok((results, all_passed))
}

fn read_bounded_pipe<R: Read>(mut pipe: R, max_bytes: u64) -> (u64, bool) {
    let mut buffer = [0u8; 16 * 1024];
    let mut total = 0u64;
    let mut truncated = false;
    loop {
        match pipe.read(&mut buffer) {
            Ok(0) => break,
            Ok(n) => {
                total = total.saturating_add(n as u64);
                if total > max_bytes {
                    truncated = true;
                }
            }
            Err(_) => {
                truncated = true;
                break;
            }
        }
    }
    (total, truncated)
}

#[derive(Debug, Clone)]
pub struct Workspace {
    pub root: PathBuf,
    pub baseline_sha: String,
    pub baseline_manifest_sha: String,
    pub baseline_bundle_sha256: Option<String>,
    pub baseline_bundle_path: Option<PathBuf>,
    pub mode: Mode,
    pub source_head: Option<String>,
    pub source_visible_sha256: String,
    pub max_workspace_files: u64,
    pub max_file_bytes: u64,
    pub max_workspace_bytes_after_run: u64,
}

pub fn prepare_workspace(
    source_root: &Path,
    dest: &Path,
    mode: Mode,
    max_files: u64,
    max_bytes: u64,
) -> BrokerResult<Workspace> {
    prepare_workspace_with_budget(
        source_root,
        dest,
        mode,
        max_files,
        max_bytes,
        max_bytes,
        max_bytes,
    )
}

pub fn prepare_workspace_with_budget(
    source_root: &Path,
    dest: &Path,
    mode: Mode,
    max_files: u64,
    max_bytes: u64,
    max_file_bytes: u64,
    max_workspace_bytes_after_run: u64,
) -> BrokerResult<Workspace> {
    if !source_root.exists() {
        return Err(WorkspaceError::Message(format!(
            "source_root missing: {}",
            source_root.display()
        ))
        .into());
    }
    if git::has_submodules(source_root) {
        return Err(WorkspaceError::Message(
            "submodules are not supported until explicit semantics exist".into(),
        )
        .into());
    }
    let source_head = if git::is_git_repo(source_root) {
        Some(git::head_sha(source_root)?)
    } else {
        None
    };
    let source_visible_sha256 =
        visible_state_sha256_with_limits(source_root, max_files, max_bytes, max_file_bytes)?;

    if dest.exists() {
        std::fs::remove_dir_all(dest).map_err(|e| WorkspaceError::Message(e.to_string()))?;
    }
    std::fs::create_dir_all(dest).map_err(|e| WorkspaceError::Message(e.to_string()))?;

    // Copy Git-visible state only: tracked plus non-ignored untracked paths.
    if git::is_git_repo(source_root) {
        copy_git_visible_tree(source_root, dest, max_files, max_bytes, max_file_bytes)?;
    } else {
        // Kept only for the in-process fake/test vertical slice.
        copy_tree_with_file_limit(source_root, dest, max_files, max_bytes, max_file_bytes)?;
    }

    // Standalone git repo for isolation
    // Remove any copied .git
    let git_dir = dest.join(".git");
    if git_dir.exists() {
        std::fs::remove_dir_all(&git_dir).map_err(|e| WorkspaceError::Message(e.to_string()))?;
    }
    git::init_standalone(dest)?;
    let baseline_sha = git::commit_all(dest, "baseline")?;
    let manifest = build_manifest_with_limits(dest, max_files, max_bytes, max_file_bytes)?;
    let manifest_sha = sha256_hex(manifest.as_bytes());

    let bundle_path = dest
        .parent()
        .unwrap_or_else(|| Path::new("."))
        .join("baseline.bundle");
    let baseline_bundle_sha256 = Some(git::create_baseline_bundle(dest, &bundle_path)?);

    Ok(Workspace {
        root: dest.to_path_buf(),
        baseline_sha,
        baseline_manifest_sha: manifest_sha,
        baseline_bundle_sha256,
        baseline_bundle_path: Some(bundle_path),
        mode,
        source_head,
        source_visible_sha256,
        max_workspace_files: max_files,
        max_file_bytes,
        max_workspace_bytes_after_run,
    })
}

/// Create trusted baseline.bundle beside agent_dir for patch_only workspaces.
pub fn create_agent_baseline_bundle(ws: &mut Workspace, agent_dir: &Path) -> BrokerResult<()> {
    let bundle_path = agent_dir.join("baseline.bundle");
    if ws.baseline_bundle_path.as_deref() == Some(bundle_path.as_path())
        && ws.baseline_bundle_sha256.is_some()
    {
        return Ok(());
    }
    let sha = git::create_baseline_bundle(&ws.root, &bundle_path)?;
    ws.baseline_bundle_sha256 = Some(sha);
    ws.baseline_bundle_path = Some(bundle_path);
    Ok(())
}

fn copy_tree_with_file_limit(
    src: &Path,
    dst: &Path,
    max_files: u64,
    max_bytes: u64,
    max_file_bytes: u64,
) -> BrokerResult<()> {
    let mut file_count = 0u64;
    let mut byte_count = 0u64;
    copy_tree_inner(
        src,
        dst,
        src,
        &mut file_count,
        &mut byte_count,
        max_files,
        max_bytes,
        max_file_bytes,
    )
}

#[cfg(unix)]
fn copy_git_visible_tree(
    src: &Path,
    dst: &Path,
    max_files: u64,
    max_bytes: u64,
    max_file_bytes: u64,
) -> BrokerResult<()> {
    use std::os::unix::fs::symlink;
    let paths = git::list_file_paths_nul_with_limits(src, max_files, max_bytes)?;
    let mut count = 0u64;
    let mut bytes = 0u64;
    for rel in paths {
        let source = src.join(&rel);
        let meta = match std::fs::symlink_metadata(&source) {
            Ok(meta) => meta,
            Err(e) if e.kind() == std::io::ErrorKind::NotFound => continue,
            Err(e) => return Err(WorkspaceError::Message(e.to_string()).into()),
        };
        count = count.saturating_add(1);
        bytes = bytes.saturating_add(meta.len());
        if meta.is_file() && meta.len() > max_file_bytes {
            return Err(WorkspaceError::Message(format!(
                "file exceeds max_file_bytes ({}): {}",
                max_file_bytes,
                source.display()
            ))
            .into());
        }
        if count > max_files || bytes > max_bytes {
            return Err(WorkspaceError::Message("workspace size limit exceeded".into()).into());
        }
        let target = dst.join(&rel);
        if let Some(parent) = target.parent() {
            std::fs::create_dir_all(parent).map_err(|e| WorkspaceError::Message(e.to_string()))?;
        }
        if meta.file_type().is_symlink() {
            let link =
                std::fs::read_link(&source).map_err(|e| WorkspaceError::Message(e.to_string()))?;
            validate_symlink_target(src, &source, &link)?;
            symlink(link, target).map_err(|e| WorkspaceError::Message(e.to_string()))?;
        } else if meta.is_file() {
            std::fs::copy(source, target).map_err(|e| WorkspaceError::Message(e.to_string()))?;
        }
    }
    Ok(())
}

#[cfg(not(unix))]
fn copy_git_visible_tree(
    _src: &Path,
    _dst: &Path,
    _max_files: u64,
    _max_bytes: u64,
    _max_file_bytes: u64,
) -> BrokerResult<()> {
    Err(WorkspaceError::Message("Git-visible copy requires Unix in V3".into()).into())
}

#[allow(clippy::too_many_arguments)]
fn copy_tree_inner(
    src_root: &Path,
    dst_root: &Path,
    current: &Path,
    file_count: &mut u64,
    byte_count: &mut u64,
    max_files: u64,
    max_bytes: u64,
    max_file_bytes: u64,
) -> BrokerResult<()> {
    let entries = std::fs::read_dir(current).map_err(|e| WorkspaceError::Message(e.to_string()))?;
    for entry in entries {
        let entry = entry.map_err(|e| WorkspaceError::Message(e.to_string()))?;
        let name = entry.file_name();
        let name_str = name.to_string_lossy();
        if name_str == ".git" || name_str == ".subagents" || name_str == "target" {
            continue;
        }
        let path = entry.path();
        let rel = path
            .strip_prefix(src_root)
            .map_err(|e| WorkspaceError::Message(e.to_string()))?;
        let dest = dst_root.join(rel);
        let ft = entry
            .file_type()
            .map_err(|e| WorkspaceError::Message(e.to_string()))?;
        if ft.is_dir() {
            std::fs::create_dir_all(&dest).map_err(|e| WorkspaceError::Message(e.to_string()))?;
            copy_tree_inner(
                src_root,
                dst_root,
                &path,
                file_count,
                byte_count,
                max_files,
                max_bytes,
                max_file_bytes,
            )?;
        } else if ft.is_file() {
            *file_count += 1;
            if *file_count > max_files {
                return Err(WorkspaceError::Message(format!(
                    "workspace exceeds max_workspace_files ({max_files})"
                ))
                .into());
            }
            let meta = entry
                .metadata()
                .map_err(|e| WorkspaceError::Message(e.to_string()))?;
            if meta.len() > max_file_bytes {
                return Err(WorkspaceError::Message(format!(
                    "file exceeds max_file_bytes ({}): {}",
                    max_file_bytes,
                    path.display()
                ))
                .into());
            }
            *byte_count += meta.len();
            if *byte_count > max_bytes {
                return Err(WorkspaceError::Message(format!(
                    "workspace exceeds max_workspace_bytes ({max_bytes})"
                ))
                .into());
            }
            if let Some(parent) = dest.parent() {
                std::fs::create_dir_all(parent)
                    .map_err(|e| WorkspaceError::Message(e.to_string()))?;
            }
            std::fs::copy(&path, &dest).map_err(|e| WorkspaceError::Message(e.to_string()))?;
        } else if ft.is_symlink() {
            #[cfg(unix)]
            {
                use std::os::unix::fs::symlink;
                *file_count = file_count.saturating_add(1);
                if *file_count > max_files {
                    return Err(WorkspaceError::Message(format!(
                        "workspace exceeds max_workspace_files ({max_files})"
                    ))
                    .into());
                }
                let link = std::fs::read_link(&path)
                    .map_err(|e| WorkspaceError::Message(e.to_string()))?;
                validate_symlink_target(src_root, &path, &link)?;
                if let Some(parent) = dest.parent() {
                    std::fs::create_dir_all(parent)
                        .map_err(|e| WorkspaceError::Message(e.to_string()))?;
                }
                symlink(link, dest).map_err(|e| WorkspaceError::Message(e.to_string()))?;
            }
        }
    }
    Ok(())
}

pub fn build_manifest(root: &Path) -> BrokerResult<String> {
    build_manifest_with_limits(root, u64::MAX, u64::MAX, u64::MAX)
}

pub fn build_manifest_with_limits(
    root: &Path,
    max_files: u64,
    max_bytes: u64,
    max_file_bytes: u64,
) -> BrokerResult<String> {
    #[cfg(unix)]
    {
        use std::os::unix::ffi::OsStrExt;
        use std::os::unix::fs::MetadataExt;
        let mut paths = if git::is_git_repo(root) {
            git::list_file_paths_nul_with_limits(root, max_files, max_bytes)?
        } else {
            collect_tree_paths(root)?
        };
        paths.sort_by(|a, b| a.as_os_str().as_bytes().cmp(b.as_os_str().as_bytes()));
        let mut lines = Vec::new();
        let mut total_bytes = 0u64;
        if paths.len() as u64 > max_files {
            return Err(WorkspaceError::Message(format!(
                "workspace exceeds max_workspace_files ({max_files})"
            ))
            .into());
        }
        for rel in paths {
            let full = root.join(&rel);
            let meta = match std::fs::symlink_metadata(&full) {
                Ok(meta) => meta,
                Err(e) if e.kind() == std::io::ErrorKind::NotFound => continue,
                Err(e) => return Err(WorkspaceError::Message(e.to_string()).into()),
            };
            let (kind, content_hash, content_len) = if meta.file_type().is_symlink() {
                let link = std::fs::read_link(&full)
                    .map_err(|e| WorkspaceError::Message(e.to_string()))?;
                validate_symlink_target(root, &full, &link)?;
                let content = link.as_os_str().as_bytes();
                ("symlink", sha256_hex(content), content.len() as u64)
            } else if meta.is_file() {
                if meta.len() > max_file_bytes {
                    return Err(WorkspaceError::Message(format!(
                        "file exceeds max_file_bytes ({}): {}",
                        max_file_bytes,
                        full.display()
                    ))
                    .into());
                }
                let (hash, len) = hash_file(&full)?;
                ("file", hash, len)
            } else {
                return Err(WorkspaceError::Message(format!(
                    "unsupported workspace entry: {}",
                    full.display()
                ))
                .into());
            };
            total_bytes = total_bytes.saturating_add(content_len);
            if total_bytes > max_bytes {
                return Err(WorkspaceError::Message(format!(
                    "workspace exceeds max_workspace_bytes ({max_bytes})"
                ))
                .into());
            }
            lines.push(format!(
                "{}\t{}\t{:o}\t{}",
                hex::encode(rel.as_os_str().as_bytes()),
                kind,
                meta.mode() & 0o7777,
                content_hash
            ));
        }
        Ok(lines.join("\n"))
    }
    #[cfg(not(unix))]
    {
        let _ = root;
        Err(WorkspaceError::Message("manifest requires Unix in V3".into()).into())
    }
}

pub fn visible_state_sha256(root: &Path) -> BrokerResult<String> {
    visible_state_sha256_with_limits(root, u64::MAX, u64::MAX, u64::MAX)
}

pub fn visible_state_sha256_with_limits(
    root: &Path,
    max_files: u64,
    max_bytes: u64,
    max_file_bytes: u64,
) -> BrokerResult<String> {
    Ok(sha256_hex(
        build_manifest_with_limits(root, max_files, max_bytes, max_file_bytes)?.as_bytes(),
    ))
}

fn hash_file(path: &Path) -> BrokerResult<(String, u64)> {
    let mut file = std::fs::File::open(path)
        .map_err(|e| WorkspaceError::Message(format!("open {}: {e}", path.display())))?;
    let mut hasher = Sha256::new();
    let mut buffer = [0u8; 64 * 1024];
    let mut total = 0u64;
    loop {
        let n = file
            .read(&mut buffer)
            .map_err(|e| WorkspaceError::Message(format!("read {}: {e}", path.display())))?;
        if n == 0 {
            break;
        }
        total = total.saturating_add(n as u64);
        hasher.update(&buffer[..n]);
    }
    Ok((hex::encode(hasher.finalize()), total))
}

fn validate_symlink_target(root: &Path, link_path: &Path, target: &Path) -> BrokerResult<()> {
    use std::path::Component;
    if target.is_absolute() {
        return Err(WorkspaceError::Message(format!(
            "absolute symlink is not allowed: {} -> {}",
            link_path.display(),
            target.display()
        ))
        .into());
    }
    let rel = link_path
        .strip_prefix(root)
        .map_err(|e| WorkspaceError::Message(e.to_string()))?;
    let parent = rel.parent().unwrap_or_else(|| Path::new(""));
    let mut normalized = PathBuf::new();
    for component in parent.components().chain(target.components()) {
        match component {
            Component::CurDir => {}
            Component::Normal(part) => normalized.push(part),
            Component::ParentDir => {
                if !normalized.pop() {
                    return Err(WorkspaceError::Message(format!(
                        "symlink escapes workspace: {} -> {}",
                        link_path.display(),
                        target.display()
                    ))
                    .into());
                }
            }
            Component::RootDir | Component::Prefix(_) => {
                return Err(WorkspaceError::Message(format!(
                    "absolute symlink is not allowed: {} -> {}",
                    link_path.display(),
                    target.display()
                ))
                .into())
            }
        }
    }
    Ok(())
}

fn collect_tree_paths(root: &Path) -> BrokerResult<Vec<PathBuf>> {
    fn visit(root: &Path, current: &Path, out: &mut Vec<PathBuf>) -> BrokerResult<()> {
        for entry in
            std::fs::read_dir(current).map_err(|e| WorkspaceError::Message(e.to_string()))?
        {
            let entry = entry.map_err(|e| WorkspaceError::Message(e.to_string()))?;
            if matches!(
                entry.file_name().to_str(),
                Some(".git" | ".subagents" | "target")
            ) {
                continue;
            }
            let path = entry.path();
            let kind = entry
                .file_type()
                .map_err(|e| WorkspaceError::Message(e.to_string()))?;
            if kind.is_dir() {
                visit(root, &path, out)?;
            } else {
                out.push(
                    path.strip_prefix(root)
                        .map_err(|e| WorkspaceError::Message(e.to_string()))?
                        .to_path_buf(),
                );
            }
        }
        Ok(())
    }
    let mut paths = Vec::new();
    visit(root, root, &mut paths)?;
    Ok(paths)
}

pub fn sha256_hex(data: &[u8]) -> String {
    let mut h = Sha256::new();
    h.update(data);
    hex::encode(h.finalize())
}

pub fn detect_changes(ws: &Workspace) -> BrokerResult<(Vec<String>, Vec<u8>)> {
    detect_changes_with_limits(ws, u64::MAX)
}

pub fn detect_changes_with_limits(
    ws: &Workspace,
    max_patch_bytes: u64,
) -> BrokerResult<(Vec<String>, Vec<u8>)> {
    // Never trust harness-controlled `.git`. Rebuild an audit repository from the
    // bundle stored outside the workspace, then overlay only filesystem content.
    let bundle = ws
        .baseline_bundle_path
        .as_ref()
        .ok_or_else(|| WorkspaceError::Message("trusted baseline bundle is missing".into()))?;
    let expected = ws
        .baseline_bundle_sha256
        .as_ref()
        .ok_or_else(|| WorkspaceError::Message("trusted baseline bundle hash is missing".into()))?;
    let actual = sha256_file_hex(bundle)?;
    if &actual != expected {
        return Err(WorkspaceError::Message("trusted baseline bundle hash mismatch".into()).into());
    }
    let temp = tempfile::tempdir().map_err(|e| WorkspaceError::Message(e.to_string()))?;
    let audit = temp.path().join("audit");
    git::clone_bundle(bundle, &audit)?;
    clear_worktree(&audit)?;
    let _ = build_manifest_with_limits(
        &ws.root,
        ws.max_workspace_files,
        ws.max_workspace_bytes_after_run,
        ws.max_file_bytes,
    )?;
    copy_tree_with_file_limit(
        &ws.root,
        &audit,
        ws.max_workspace_files,
        ws.max_workspace_bytes_after_run,
        ws.max_file_bytes,
    )?;
    git::run_git(&audit, &["add", "-A"])?;
    let diff = git::run_git_bytes_bounded(
        &audit,
        &["diff", "--cached", "--binary", "HEAD", "--"],
        max_patch_bytes,
    )?;
    let names = git::run_git_bytes_bounded(
        &audit,
        &["diff", "--cached", "--name-only", "-z", "HEAD", "--"],
        max_patch_bytes,
    )?;
    let mut paths = Vec::new();
    for part in names.split(|b| *b == 0).filter(|p| !p.is_empty()) {
        paths.push(display_repo_path(part));
    }
    paths.sort();
    paths.dedup();
    Ok((paths, diff))
}

pub fn sha256_file_hex(path: &Path) -> BrokerResult<String> {
    Ok(hash_file(path)?.0)
}

fn display_repo_path(bytes: &[u8]) -> String {
    match std::str::from_utf8(bytes) {
        Ok(path) => path.to_string(),
        Err(_) => {
            let mut out = String::new();
            for byte in bytes {
                if byte.is_ascii_alphanumeric() || matches!(*byte, b'/' | b'.' | b'_' | b'-') {
                    out.push(*byte as char);
                } else {
                    out.push_str(&format!("%{byte:02X}"));
                }
            }
            out
        }
    }
}

fn clear_worktree(root: &Path) -> BrokerResult<()> {
    for entry in std::fs::read_dir(root).map_err(|e| WorkspaceError::Message(e.to_string()))? {
        let entry = entry.map_err(|e| WorkspaceError::Message(e.to_string()))?;
        if entry.file_name() == ".git" {
            continue;
        }
        let path = entry.path();
        let ty = entry
            .file_type()
            .map_err(|e| WorkspaceError::Message(e.to_string()))?;
        if ty.is_dir() {
            std::fs::remove_dir_all(path).map_err(|e| WorkspaceError::Message(e.to_string()))?;
        } else {
            std::fs::remove_file(path).map_err(|e| WorkspaceError::Message(e.to_string()))?;
        }
    }
    Ok(())
}

pub fn assert_read_only_clean(ws: &Workspace) -> BrokerResult<()> {
    assert_read_only_clean_with_limits(ws, u64::MAX)
}

pub fn assert_read_only_clean_with_limits(
    ws: &Workspace,
    max_patch_bytes: u64,
) -> BrokerResult<()> {
    let (paths, _) = detect_changes_with_limits(ws, max_patch_bytes)?;
    if !paths.is_empty() {
        return Err(WorkspaceError::Message(format!(
            "read_only workspace was modified: {paths:?}"
        ))
        .into());
    }
    Ok(())
}

pub fn write_baseline_manifest(agent_dir: &Path, ws: &Workspace) -> BrokerResult<()> {
    let mut manifest = serde_json::json!({
        "baseline_sha": ws.baseline_sha,
        "manifest_sha256": ws.baseline_manifest_sha,
        "source_head": ws.source_head,
        "source_visible_sha256": ws.source_visible_sha256,
    });
    if let Some(ref b) = ws.baseline_bundle_sha256 {
        manifest["baseline_bundle_sha256"] = serde_json::json!(b);
        manifest["baseline_bundle"] = serde_json::json!("baseline.bundle");
    }
    manifest["max_workspace_files"] = serde_json::json!(ws.max_workspace_files);
    manifest["max_file_bytes"] = serde_json::json!(ws.max_file_bytes);
    manifest["max_workspace_bytes_after_run"] = serde_json::json!(ws.max_workspace_bytes_after_run);
    crate::persistence::atomic_write_json(&agent_dir.join("baseline_manifest.json"), &manifest)
}
