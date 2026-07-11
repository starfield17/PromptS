//! CLI: run, status, patch check/apply, doctor.

use std::ffi::OsString;
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;

use clap::{Parser, Subcommand};

use crate::environment::{build_environment, ensure_isolated_dirs};
use crate::error::{BrokerError, BrokerResult, TaskError};
use crate::harness::AdapterBundle;
#[cfg(feature = "dev-harness")]
use crate::harness::FakeAdapter;
use crate::identity::RequestedIdentity;
#[cfg(feature = "dev-harness")]
use crate::identity::{ExecutableIdentity, ExecutableTrust};
use crate::patch::{
    apply_patch_file_with_manifest, check_patch_artifacts, diff_has_binary, diff_has_deletes,
    load_baseline_expectation, CandidatePatch, MergeablePatch, PatchMetadata, PolicyCheckedPatch,
};
use crate::persistence::{default_subagents_base, load_result_json, RunDirectory};
use crate::policy::PathPolicy;
use crate::render::render_status;
use crate::state::{AgentRuntime, Outcome, OutcomeKind, Phase, RunState};
#[cfg(feature = "dev-harness")]
use crate::supervisor::run_fake_harness;
use crate::supervisor::{
    apply_supervised_to_agent, enforce_normalized_event_budget, forced_outcome_from_run,
    run_external_harness_with_sink_budget,
};
#[cfg(feature = "dev-harness")]
use crate::task::HarnessSpec;
use crate::task::{IsolationMode, Mode, ResourceBudget, TaskPacket};
use crate::workspace::{self, prepare_workspace_with_budget};

#[derive(Debug, Parser)]
#[command(
    name = "subagent-broker",
    version = "3.1.0",
    about = "V3.1 subagent process broker"
)]
pub struct Cli {
    #[command(subcommand)]
    pub command: Commands,
}

#[derive(Debug, Subcommand)]
pub enum Commands {
    /// Run a task packet (always synchronous).
    Run {
        tasks: PathBuf,
        /// Base directory for .subagents (default: cwd/.subagents parent = cwd)
        #[arg(long)]
        cwd: Option<PathBuf>,
    },
    /// Show status from result.json
    Status {
        run_dir: PathBuf,
        /// Emit the complete result JSON instead of the concise human view.
        #[arg(long)]
        json: bool,
    },
    /// Patch operations
    Patch {
        #[command(subcommand)]
        action: PatchCmd,
    },
    /// Read-only diagnostics
    Doctor,
    /// Validate skill layout and V3 templates
    ValidateSkill {
        /// Skill root directory (default: parent of binary or cwd)
        #[arg(default_value = ".")]
        path: PathBuf,
    },
}

#[derive(Debug, Subcommand)]
pub enum PatchCmd {
    Check {
        patch: PathBuf,
    },
    Apply {
        patch: PathBuf,
        #[arg(long, default_value = ".")]
        repo: PathBuf,
    },
}

/// Entry from main: returns process exit code.
pub fn run<I, T>(args: I) -> u8
where
    I: IntoIterator<Item = T>,
    T: Into<OsString> + Clone,
{
    let cli = match Cli::try_parse_from(args) {
        Ok(c) => c,
        Err(e) => {
            let _ = e.print();
            return if e.use_stderr() { 2 } else { 0 };
        }
    };

    let rt = match tokio::runtime::Builder::new_multi_thread()
        .enable_all()
        .build()
    {
        Ok(rt) => rt,
        Err(e) => {
            eprintln!("failed to start runtime: {e}");
            return 2;
        }
    };

    match cli.command {
        Commands::Run { tasks, cwd } => {
            let cwd = cwd
                .unwrap_or_else(|| std::env::current_dir().unwrap_or_else(|_| PathBuf::from(".")));
            match rt.block_on(cmd_run(&tasks, &cwd)) {
                Ok(code) => code,
                Err(e) => {
                    eprintln!("{}", e.user_message());
                    e.exit_code()
                }
            }
        }
        Commands::Status { run_dir, json } => match cmd_status(&run_dir, json) {
            Ok(()) => 0,
            Err(e) => {
                eprintln!("{}", e.user_message());
                e.exit_code()
            }
        },
        Commands::Patch { action } => match action {
            PatchCmd::Check { patch } => match check_patch_artifacts(&patch) {
                Ok(()) => {
                    println!("patch ok: {}", patch.display());
                    0
                }
                Err(e) => {
                    eprintln!("{}", e.user_message());
                    1
                }
            },
            PatchCmd::Apply { patch, repo } => {
                let baseline = load_baseline_expectation(
                    &patch
                        .parent()
                        .unwrap_or_else(|| Path::new("."))
                        .join("baseline_manifest.json"),
                );
                match baseline.and_then(|b| apply_patch_file_with_manifest(&patch, &repo, &b)) {
                    Ok(()) => {
                        println!("applied: {}", patch.display());
                        0
                    }
                    Err(e) => {
                        eprintln!("{}", e.user_message());
                        1
                    }
                }
            }
        },
        Commands::Doctor => match cmd_doctor() {
            Ok(()) => 0,
            Err(e) => {
                eprintln!("{}", e.user_message());
                2
            }
        },
        Commands::ValidateSkill { path } => match cmd_validate_skill(&path) {
            Ok(()) => {
                println!("validate-skill: ok ({})", path.display());
                0
            }
            Err(e) => {
                eprintln!("validate-skill: {}", e.user_message());
                2
            }
        },
    }
}

fn cmd_status(run_dir: &Path, json: bool) -> BrokerResult<()> {
    let value = load_result_json(run_dir)?;
    if json {
        println!(
            "{}",
            serde_json::to_string_pretty(&value).unwrap_or_default()
        );
        return Ok(());
    }
    if let Some(run_id) = value.get("run_id").and_then(|v| v.as_str()) {
        println!(
            "run_id={run_id} phase={} outcome={} revision={}",
            value.get("phase").and_then(|v| v.as_str()).unwrap_or("?"),
            value
                .get("outcome")
                .and_then(|v| v.as_str())
                .unwrap_or("in_progress"),
            value.get("revision").and_then(|v| v.as_u64()).unwrap_or(0)
        );
    }
    Ok(())
}

fn cmd_doctor() -> BrokerResult<()> {
    println!("subagent-broker V3.1 doctor (read-only)");
    println!(
        "platform: {} {}",
        std::env::consts::OS,
        std::env::consts::ARCH
    );
    if !crate::platform::platform_supported() {
        println!("supported: NO (Linux required for V3 MVP)");
    } else {
        println!("supported: yes (Linux)");
    }
    match crate::git::git_version() {
        Ok(v) => println!("git: {v}"),
        Err(e) => println!("git: unavailable ({e})"),
    }
    for name in ["claude", "grok", "codex", "opencode"] {
        match which_path(name) {
            Some(p) => {
                let rp = std::fs::canonicalize(&p)
                    .map(|x| x.display().to_string())
                    .unwrap_or_else(|_| p.display().to_string());
                let ver = probe_version(name);
                println!(
                    "harness {name}: path={} realpath={} version={}",
                    p.display(),
                    rp,
                    ver.as_deref().unwrap_or("-")
                );
            }
            None => println!("harness {name}: not found on PATH"),
        }
    }
    println!("note: doctor does not start agent sessions");
    Ok(())
}

fn which_path(name: &str) -> Option<PathBuf> {
    let path = std::env::var_os("PATH")?;
    for dir in std::env::split_paths(&path) {
        let c = dir.join(name);
        if c.is_file() {
            return Some(c);
        }
    }
    None
}

fn probe_version(name: &str) -> Option<String> {
    let out = std::process::Command::new(name)
        .arg("--version")
        .output()
        .ok()?;
    let mut t = String::from_utf8_lossy(&out.stdout).to_string();
    if t.trim().is_empty() {
        t = String::from_utf8_lossy(&out.stderr).to_string();
    }
    let line = t.lines().next().unwrap_or("").trim();
    if line.is_empty() {
        None
    } else {
        Some(line.chars().take(256).collect())
    }
}

fn cmd_validate_skill(root: &Path) -> BrokerResult<()> {
    let required = [
        "SKILL.md",
        "templates/task.v3.example.json",
        "templates/result.v3.example.json",
        "references/protocol.md",
        "references/isolation.md",
        "references/examples.md",
        "rust/Cargo.toml",
    ];
    for rel in required {
        let p = root.join(rel);
        if !p.is_file() {
            return Err(BrokerError::Cli(format!("missing required file: {rel}")));
        }
    }
    let task_path = root.join("templates/task.v3.example.json");
    let _packet = TaskPacket::load_path(&task_path)?;
    let result_bytes = std::fs::read(root.join("templates/result.v3.example.json"))
        .map_err(|e| BrokerError::Cli(e.to_string()))?;
    let v: serde_json::Value = serde_json::from_slice(&result_bytes)
        .map_err(|e| BrokerError::Cli(format!("result template JSON: {e}")))?;
    if v.get("schema_version").and_then(|x| x.as_u64()) != Some(3) {
        return Err(BrokerError::Cli(
            "result.v3.example.json must have schema_version 3".into(),
        ));
    }
    let bin = root.join("scripts/subagent-broker");
    if !bin.is_file() {
        return Err(BrokerError::Cli(
            "missing required executable: scripts/subagent-broker".into(),
        ));
    }
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        let mode = std::fs::metadata(&bin)
            .map_err(|e| BrokerError::Cli(e.to_string()))?
            .permissions()
            .mode();
        if mode & 0o111 == 0 {
            return Err(BrokerError::Cli(
                "scripts/subagent-broker exists but is not executable".into(),
            ));
        }
    }
    let st = std::process::Command::new(&bin)
        .arg("doctor")
        .status()
        .map_err(|e| BrokerError::Cli(format!("cannot start scripts/subagent-broker: {e}")))?;
    if !st.success() {
        return Err(BrokerError::Cli(
            "scripts/subagent-broker doctor failed".into(),
        ));
    }
    Ok(())
}

async fn cmd_run(tasks_path: &Path, cwd: &Path) -> BrokerResult<u8> {
    if !crate::platform::platform_supported() {
        return Err(BrokerError::UnsupportedPlatform);
    }

    let packet = TaskPacket::load_path(tasks_path)?;
    for spec in &packet.agents {
        if spec.isolation == IsolationMode::Strict {
            return Err(TaskError::Other(
                "strict isolation is unavailable in this release; use copy_isolation explicitly"
                    .into(),
            )
            .into());
        }
        let bundle = AdapterBundle::from_spec(&spec.harness)?;
        let _ = crate::harness::require_executable(&bundle)?;
        #[cfg(feature = "dev-harness")]
        if matches!(spec.harness, HarnessSpec::Fake { .. }) {
            continue;
        }
        let source = if spec.source_root == "." {
            cwd.to_path_buf()
        } else {
            cwd.join(&spec.source_root)
        };
        if !crate::git::is_git_repo(&source) {
            return Err(TaskError::Other(format!(
                "source_root must be a Git workspace: {}",
                source.display()
            ))
            .into());
        }
        if crate::git::has_submodules(&source) {
            return Err(TaskError::Other("submodules are not supported in V3".into()).into());
        }
    }
    let base = default_subagents_base(cwd);
    std::fs::create_dir_all(&base)
        .map_err(|e| BrokerError::Persistence(crate::error::PersistenceError::Io(e.to_string())))?;

    let run_dir = RunDirectory::create(&base, &packet.run_id)?;
    crate::persistence::atomic_write_bytes(&run_dir.root.join("events.jsonl"), b"")?;
    let mut state = RunState::new(packet.run_id.clone());
    for spec in &packet.agents {
        state.insert_agent(AgentRuntime::new_with_isolation(
            spec.id.clone(),
            spec.mode,
            RequestedIdentity {
                harness: spec.harness.kind_name().into(),
                model: spec.harness.model().map(str::to_string),
            },
            spec.identity.clone(),
            spec.limits.max_result_bytes as usize,
            spec.isolation,
        ));
    }
    run_dir.persist_live(&state)?;
    let run_root = run_dir.root.clone();

    let cancel_flag = Arc::new(AtomicBool::new(false));
    let (cancel_tx, cancel_rx) = tokio::sync::watch::channel(false);
    {
        let flag = cancel_flag.clone();
        let tx = cancel_tx.clone();
        tokio::spawn(async move {
            if tokio::signal::ctrl_c().await.is_ok() {
                flag.store(true, Ordering::SeqCst);
                let _ = tx.send(true);
            }
        });
    }

    let resources = packet.resources.clone();
    let (owner_tx, owner_rx) = crate::state_owner::StateOwner::channel();
    let owner = crate::state_owner::StateOwner::new(state, run_dir, resources.max_events_log_bytes);
    let owner_handle = tokio::spawn(async move { owner.run(owner_rx).await });

    let concurrency = packet.max_concurrency.max(1);
    let sem = Arc::new(tokio::sync::Semaphore::new(concurrency));
    let mut joins = Vec::new();

    for agent_spec in packet.agents {
        if cancel_flag.load(Ordering::SeqCst) {
            break;
        }
        let permit = match sem.clone().acquire_owned().await {
            Ok(p) => p,
            Err(_) => break,
        };
        if cancel_flag.load(Ordering::SeqCst) {
            drop(permit);
            break;
        }
        let cwd = cwd.to_path_buf();
        let cancel_rx = cancel_rx.clone();
        let cancel_flag = cancel_flag.clone();
        let owner_tx = owner_tx.clone();
        let run_root = run_root.clone();
        let resources = resources.clone();
        joins.push(tokio::spawn(async move {
            let _permit = permit;
            let result = run_one_agent_worker(
                &run_root,
                &agent_spec,
                &cwd,
                cancel_rx,
                &cancel_flag,
                &owner_tx,
                &resources,
            )
            .await;
            match result {
                Ok(runtime) => {
                    crate::state_owner::StateOwner::send_critical(
                        &owner_tx,
                        crate::state_owner::OwnerMsg::UpsertAgent(runtime),
                    )
                    .await;
                }
                Err(e) => {
                    let mut runtime = AgentRuntime::new_with_isolation(
                        agent_spec.id.clone(),
                        agent_spec.mode,
                        RequestedIdentity {
                            harness: agent_spec.harness.kind_name().into(),
                            model: agent_spec.harness.model().map(str::to_string),
                        },
                        agent_spec.identity.clone(),
                        agent_spec.limits.max_result_bytes as usize,
                        agent_spec.isolation,
                    );
                    let _ = runtime.finish(
                        Some(Outcome::Failed {
                            reason: crate::state::FailureReason::Internal,
                            detail: Some(e.user_message()),
                        }),
                        None,
                    );
                    crate::state_owner::StateOwner::send_critical(
                        &owner_tx,
                        crate::state_owner::OwnerMsg::UpsertAgent(runtime),
                    )
                    .await;
                }
            }
        }));
    }

    for j in joins {
        let _ = j.await;
    }

    crate::state_owner::StateOwner::send_critical(
        &owner_tx,
        crate::state_owner::OwnerMsg::Shutdown,
    )
    .await;
    drop(owner_tx);

    let (mut state, run_dir) = owner_handle
        .await
        .map_err(|e| BrokerError::Internal(format!("state owner join: {e}")))??;

    let interrupted = cancel_flag.load(Ordering::SeqCst);
    if interrupted {
        for agent in state
            .agents_in_order()
            .map(|a| a.agent_id.as_str().to_string())
            .collect::<Vec<_>>()
        {
            if let Some(a) = state.agent_mut(&agent) {
                if a.phase != Phase::Finished {
                    let _ = a.finish(
                        Some(Outcome::Cancelled {
                            detail: Some("SIGINT".into()),
                        }),
                        None,
                    );
                }
            }
        }
        state.recompute_run_outcome();
    }

    state.recompute_run_outcome();
    run_dir.persist_terminal(&state)?;

    println!("{}", render_status(&state));
    println!("result: {}", run_root.join("result.json").display());
    println!("summary: {}", run_root.join("summary.md").display());

    if interrupted || state.outcome == Some(OutcomeKind::Cancelled) {
        return Ok(130);
    }
    if state.is_success() {
        Ok(0)
    } else {
        Ok(1)
    }
}

/// Worker: no shared RunState; returns finished AgentRuntime.
async fn run_one_agent_worker(
    run_root: &Path,
    spec: &crate::task::AgentSpec,
    cwd: &Path,
    cancel_rx: tokio::sync::watch::Receiver<bool>,
    cancel_flag: &AtomicBool,
    owner_tx: &tokio::sync::mpsc::Sender<crate::state_owner::OwnerMsg>,
    resources: &ResourceBudget,
) -> BrokerResult<AgentRuntime> {
    let agent_dir = run_root.join(spec.id.as_str());
    std::fs::create_dir_all(&agent_dir)
        .map_err(|e| BrokerError::Persistence(crate::error::PersistenceError::Io(e.to_string())))?;
    let task_json = serde_json::to_value(spec).unwrap_or_default();
    crate::persistence::atomic_write_json(&agent_dir.join("task.json"), &task_json)?;
    crate::persistence::atomic_write_bytes(&agent_dir.join("prompt.txt"), spec.goal.as_bytes())?;

    let mut runtime = AgentRuntime::new_with_isolation(
        spec.id.clone(),
        spec.mode,
        RequestedIdentity {
            harness: spec.harness.kind_name().into(),
            model: spec.harness.model().map(str::to_string),
        },
        spec.identity.clone(),
        spec.limits.max_result_bytes as usize,
        spec.isolation,
    );
    runtime.prepare();
    crate::state_owner::StateOwner::send_critical(
        owner_tx,
        crate::state_owner::OwnerMsg::UpsertAgent(runtime.clone()),
    )
    .await;

    let source = if spec.source_root == "." {
        cwd.to_path_buf()
    } else {
        cwd.join(&spec.source_root)
    };

    let work_root = agent_dir.join("workspace");
    let mut ws = prepare_workspace_with_budget(
        &source,
        &work_root,
        spec.mode,
        spec.limits.max_workspace_files,
        spec.limits.max_workspace_bytes,
        resources.max_file_bytes,
        resources.max_workspace_bytes_after_run,
    )?;
    workspace::create_agent_baseline_bundle(&mut ws, &agent_dir)?;
    workspace::write_baseline_manifest(&agent_dir, &ws)?;

    let isolated_home = agent_dir.join("home");
    ensure_isolated_dirs(&isolated_home)
        .map_err(|e| BrokerError::Persistence(crate::error::PersistenceError::Io(e.to_string())))?;
    let env = build_environment(&spec.environment, &ws.root, &isolated_home);
    runtime.environment = Some(crate::state::EnvironmentRecord {
        home: match env.home_mode {
            crate::task::HomeMode::Isolated => "isolated".into(),
            crate::task::HomeMode::Host => "host".into(),
        },
        allowed_env_names: env.allowed_env_names.clone(),
        host_configuration_exposed: env.host_configuration_exposed,
        reproducibility: env.reproducibility.into(),
    });

    let bundle = AdapterBundle::from_spec(&spec.harness)?;
    let executable = match &bundle {
        #[cfg(feature = "dev-harness")]
        AdapterBundle::Fake(_) => ExecutableIdentity {
            argv0: "fake-harness".into(),
            path: Some("fake-harness".into()),
            realpath: Some("fake-harness".into()),
            sha256: None,
            version: Some("fake-3".into()),
            version_verified: true,
            trust: ExecutableTrust::Custom,
        },
        _ => bundle.resolve_executable_identity(),
    };
    runtime.start(executable);
    crate::state_owner::StateOwner::send_critical(
        owner_tx,
        crate::state_owner::OwnerMsg::UpsertAgent(runtime.clone()),
    )
    .await;

    let stdout_log = agent_dir.join("stdout.log");
    let stderr_log = agent_dir.join("stderr.log");

    let mut supervised = match &spec.harness {
        #[cfg(feature = "dev-harness")]
        HarnessSpec::Fake { .. } => {
            let mut fake = FakeAdapter::from_spec(&spec.harness);
            if let Some(ref p) = fake.stream_fixture {
                let candidate = PathBuf::from(p);
                if !candidate.is_absolute() {
                    let alt = cwd.join(p);
                    if alt.exists() {
                        fake.stream_fixture = Some(alt.display().to_string());
                    }
                }
            }
            run_fake_harness(&fake, &spec.limits, Some(&stdout_log), Some(cancel_rx)).await?
        }
        _ => {
            let argv = bundle.build_argv(spec, &ws.root);
            // Diagnostic dump: redacted goal only
            let redacted = crate::redact::redact_argv_for_diag(&argv, &spec.goal);
            let argv_json = serde_json::json!({ "argv": redacted });
            let _ = crate::persistence::atomic_write_json(
                &agent_dir.join("argv.diag.json"),
                &argv_json,
            );
            let parser = bundle.new_parser(
                spec.limits.max_result_bytes as usize,
                spec.limits.max_event_line_bytes as usize,
            );
            run_external_harness_with_sink_budget(
                &argv,
                &ws.root,
                &env,
                &spec.limits,
                parser,
                Some(&stdout_log),
                Some(&stderr_log),
                Some(cancel_rx),
                Some((owner_tx.clone(), spec.id.as_str().to_string())),
                resources.max_normalized_events,
            )
            .await?
        }
    };

    enforce_normalized_event_budget(
        &mut supervised,
        resources.max_normalized_events,
        spec.limits.max_result_bytes as usize,
    );
    apply_supervised_to_agent(&mut runtime, &supervised);
    let mut forced = forced_outcome_from_run(&supervised);
    if cancel_flag.load(Ordering::SeqCst) && forced.is_none() {
        forced = Some(Outcome::Cancelled {
            detail: Some("SIGINT".into()),
        });
    }
    if forced.is_none() && !spec.verification.is_empty() {
        match workspace::run_verification(
            &ws.root,
            &spec.verification,
            spec.limits.timeout_ms,
            spec.limits.max_result_bytes,
            Some(&env),
        ) {
            Ok((runs, passed)) => {
                runtime.record_verification(
                    runs.iter()
                        .map(|run| crate::state::VerificationResult {
                            command: run.command.clone(),
                            exit_code: run.exit_code,
                            timed_out: run.timed_out,
                            stdout_bytes: run.stdout_bytes,
                            stderr_bytes: run.stderr_bytes,
                            output_truncated: run.output_truncated,
                        })
                        .collect(),
                    passed,
                );
                if !passed {
                    forced = Some(Outcome::Failed {
                        reason: crate::state::FailureReason::VerificationFailed,
                        detail: Some("broker verification command failed".into()),
                    });
                }
            }
            Err(error) => {
                runtime.record_verification(Vec::new(), false);
                forced = Some(Outcome::Failed {
                    reason: crate::state::FailureReason::VerificationFailed,
                    detail: Some(error.user_message()),
                });
            }
        }
    }

    let mut patch_record = None;

    match spec.mode {
        Mode::ReadOnly => {
            if let Err(e) =
                workspace::assert_read_only_clean_with_limits(&ws, resources.max_patch_bytes)
            {
                let _ = runtime.finish(
                    Some(Outcome::Failed {
                        reason: crate::state::FailureReason::ReadOnlyWrite,
                        detail: Some(e.user_message()),
                    }),
                    None,
                );
                return Ok(runtime);
            }
        }
        Mode::PatchOnly => {
            let (paths, diff) =
                workspace::detect_changes_with_limits(&ws, resources.max_patch_bytes)?;
            runtime.files_changed = paths.clone();
            if spec.require_patch && paths.is_empty() && forced.is_none() {
                forced = Some(Outcome::Failed {
                    reason: crate::state::FailureReason::VerificationFailed,
                    detail: Some("required patch was not produced".into()),
                });
            }
            if !spec.required_paths.is_empty()
                && spec
                    .required_paths
                    .iter()
                    .any(|required| !paths.iter().any(|actual| actual == required))
                && forced.is_none()
            {
                forced = Some(Outcome::Failed {
                    reason: crate::state::FailureReason::VerificationFailed,
                    detail: Some("required patch path was not changed".into()),
                });
            }
            if !diff.is_empty() || !paths.is_empty() {
                let policy = PathPolicy::new(
                    &spec.allowed_paths,
                    &spec.deny_paths,
                    spec.limits.max_files_changed as usize,
                    spec.patch_policy.clone(),
                )?;
                let meta = PatchMetadata {
                    baseline_sha: Some(ws.baseline_sha.clone()),
                    baseline_manifest_sha256: Some(ws.baseline_manifest_sha.clone()),
                    baseline_bundle_sha256: ws.baseline_bundle_sha256.clone(),
                    has_deletes: diff_has_deletes(&diff),
                    has_binary: diff_has_binary(&diff),
                };
                let candidate = CandidatePatch::new(diff, paths, meta);
                if let Some(authorization) = runtime.patch_authorization(forced.as_ref()) {
                    match PolicyCheckedPatch::check(candidate, &policy) {
                        Ok(checked) => {
                            runtime.policy_gate = Some(crate::state::PolicyGateRecord {
                                evaluated: true,
                                satisfied: true,
                                reason: None,
                            });
                            let mergeable = MergeablePatch::gate(checked, authorization);
                            let dest = agent_dir.join("patch.diff");
                            match crate::patch::persist_patch(mergeable, &dest) {
                                Ok(rec) => patch_record = Some(rec),
                                Err(e) => {
                                    runtime.policy_gate = Some(crate::state::PolicyGateRecord {
                                        evaluated: true,
                                        satisfied: false,
                                        reason: Some(e.user_message()),
                                    });
                                    let _ = runtime.finish(
                                        Some(Outcome::Blocked {
                                            reason: crate::state::BlockReason::PatchPolicy,
                                        }),
                                        None,
                                    );
                                    runtime.response.summary = e.user_message();
                                    return Ok(runtime);
                                }
                            }
                        }
                        Err(error) => {
                            runtime.policy_gate = Some(crate::state::PolicyGateRecord {
                                evaluated: true,
                                satisfied: false,
                                reason: Some(error.to_string()),
                            });
                            let _ = runtime.finish(
                                Some(Outcome::Blocked {
                                    reason: crate::state::BlockReason::PatchPolicy,
                                }),
                                None,
                            );
                            return Ok(runtime);
                        }
                    }
                }
            } else {
                runtime.policy_gate = Some(crate::state::PolicyGateRecord {
                    evaluated: false,
                    satisfied: false,
                    reason: Some("no changes".into()),
                });
            }
        }
    }

    let _ = runtime.finish(forced, patch_record);
    Ok(runtime)
}
