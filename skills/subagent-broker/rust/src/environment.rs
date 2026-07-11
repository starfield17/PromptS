//! Minimal isolated environment construction. Values are never logged.

use std::collections::HashMap;
use std::ffi::{OsStr, OsString};
use std::path::{Path, PathBuf};

use crate::task::{EnvironmentSpec, HomeMode};

const PASSTHROUGH: &[&str] = &[
    "PATH",
    "LANG",
    "LC_ALL",
    "LC_CTYPE",
    "SSL_CERT_FILE",
    "SSL_CERT_DIR",
    "CURL_CA_BUNDLE",
    "REQUESTS_CA_BUNDLE",
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "NO_PROXY",
    "http_proxy",
    "https_proxy",
    "no_proxy",
    "ALL_PROXY",
    "all_proxy",
];

/// Host-auth / config keys preserved only when `home=host` (values never logged).
const HOST_CONFIG_KEYS: &[&str] = &[
    "USER",
    "LOGNAME",
    "SHELL",
    "TERM",
    "COLORTERM",
    "XDG_CONFIG_HOME",
    "XDG_CACHE_HOME",
    "XDG_DATA_HOME",
    "XDG_STATE_HOME",
    "TMPDIR",
    "TMP",
    "TEMP",
    "GROK_HOME",
    "CODEX_HOME",
    "CLAUDE_CONFIG_DIR",
    "CLAUDE_HOME",
];

#[derive(Debug, Clone)]
pub struct PreparedEnvironment {
    pub vars: HashMap<OsString, OsString>,
    pub home_mode: HomeMode,
    pub allowed_env_names: Vec<String>,
    pub host_configuration_exposed: bool,
    pub reproducibility: &'static str,
}

pub fn build_environment(
    spec: &EnvironmentSpec,
    work_dir: &Path,
    isolated_home: &Path,
) -> PreparedEnvironment {
    let mut vars: HashMap<OsString, OsString> = HashMap::new();

    for key in PASSTHROUGH {
        if let Some(v) = std::env::var_os(key) {
            vars.insert(OsString::from(*key), v);
        }
    }

    let mut allowed_names = Vec::new();
    for name in &spec.allowed_env {
        if allowed_names.contains(name) {
            continue;
        }
        if let Some(v) = std::env::var_os(name) {
            vars.insert(OsString::from(name), v);
        }
        allowed_names.push(name.clone());
    }

    match spec.home {
        HomeMode::Isolated => {
            set(&mut vars, "HOME", isolated_home);
            set(&mut vars, "TMPDIR", &isolated_home.join("tmp"));
            set(&mut vars, "XDG_CONFIG_HOME", &isolated_home.join("config"));
            set(&mut vars, "XDG_CACHE_HOME", &isolated_home.join("cache"));
            set(&mut vars, "XDG_DATA_HOME", &isolated_home.join("data"));
            set(&mut vars, "GROK_HOME", &isolated_home.join("grok"));
            set(&mut vars, "CODEX_HOME", &isolated_home.join("codex"));
            set(
                &mut vars,
                "CLAUDE_CONFIG_DIR",
                &isolated_home.join("claude"),
            );
            set(&mut vars, "PWD", work_dir);
            PreparedEnvironment {
                vars,
                home_mode: HomeMode::Isolated,
                allowed_env_names: allowed_names,
                host_configuration_exposed: false,
                reproducibility: "full",
            }
        }
        HomeMode::Host => {
            // Explicit opt-in: keep host HOME and harness config dirs so OAuth/login works.
            // Sandbox/isolated HOME forces re-login and often yields no stream response.
            let host_home = std::env::var_os("HOME")
                .map(PathBuf::from)
                .unwrap_or_else(|| isolated_home.to_path_buf());
            set(&mut vars, "HOME", &host_home);
            for key in HOST_CONFIG_KEYS {
                if let Some(v) = std::env::var_os(key) {
                    vars.insert(OsString::from(*key), v);
                }
            }
            // Prefer host TMPDIR when present; otherwise a private tmp under isolated_home.
            if !vars.contains_key(OsStr::new("TMPDIR")) {
                set(&mut vars, "TMPDIR", &isolated_home.join("tmp"));
            }
            set(&mut vars, "PWD", work_dir);
            PreparedEnvironment {
                vars,
                home_mode: HomeMode::Host,
                allowed_env_names: allowed_names,
                host_configuration_exposed: true,
                reproducibility: "reduced",
            }
        }
    }
}

fn set(map: &mut HashMap<OsString, OsString>, key: &str, path: &Path) {
    map.insert(OsString::from(key), path.as_os_str().to_os_string());
}

pub fn apply_to_command(cmd: &mut tokio::process::Command, env: &PreparedEnvironment) {
    cmd.env_clear();
    for (k, v) in &env.vars {
        cmd.env(k, v);
    }
}

/// Names only for diagnostics — never values.
pub fn env_names_for_summary(env: &PreparedEnvironment) -> Vec<String> {
    let mut names: Vec<String> = env
        .vars
        .keys()
        .filter_map(|k| k.to_str().map(str::to_string))
        .collect();
    names.sort();
    names
}

pub fn ensure_isolated_dirs(isolated_home: &Path) -> std::io::Result<()> {
    for sub in ["tmp", "config", "cache", "data", "grok", "codex", "claude"] {
        std::fs::create_dir_all(isolated_home.join(sub))?;
    }
    Ok(())
}

#[allow(dead_code)]
pub fn os_str(s: &str) -> &OsStr {
    OsStr::new(s)
}

#[cfg(test)]
#[allow(clippy::unwrap_used)]
mod tests {
    use super::*;
    use crate::task::EnvironmentSpec;
    use std::sync::Mutex;
    use tempfile::tempdir;

    static ENV_LOCK: Mutex<()> = Mutex::new(());

    #[test]
    fn isolated_overrides_harness_homes() {
        let dir = tempdir().unwrap();
        let iso = dir.path().join("iso");
        std::fs::create_dir_all(&iso).unwrap();
        let env = build_environment(&EnvironmentSpec::default(), dir.path(), &iso);
        assert!(!env.host_configuration_exposed);
        let grok = env.vars.get(OsStr::new("GROK_HOME")).unwrap();
        assert!(grok.to_string_lossy().contains("grok"));
        assert!(grok.to_string_lossy().contains("iso"));
    }

    #[test]
    fn host_preserves_home_and_does_not_force_isolated_grok() {
        let dir = tempdir().unwrap();
        let iso = dir.path().join("iso");
        std::fs::create_dir_all(&iso).unwrap();
        let spec = EnvironmentSpec {
            home: HomeMode::Host,
            allowed_env: vec![],
        };
        let env = build_environment(&spec, dir.path(), &iso);
        assert!(env.host_configuration_exposed);
        assert_eq!(env.reproducibility, "reduced");
        let home = env.vars.get(OsStr::new("HOME")).unwrap();
        // Must not point at isolated home when host HOME is set.
        if std::env::var_os("HOME").is_some() {
            assert!(!home.to_string_lossy().ends_with("iso"));
        }
    }

    #[test]
    fn host_does_not_pass_credentials_without_allowlist() {
        let _guard = ENV_LOCK.lock().unwrap();
        let previous = std::env::var_os("OPENAI_API_KEY");
        std::env::set_var("OPENAI_API_KEY", "broker-test-secret");
        let dir = tempdir().unwrap();
        let spec = EnvironmentSpec {
            home: HomeMode::Host,
            allowed_env: vec![],
        };
        let env = build_environment(&spec, dir.path(), &dir.path().join("iso"));
        assert!(!env.vars.contains_key(OsStr::new("OPENAI_API_KEY")));
        if let Some(value) = previous {
            std::env::set_var("OPENAI_API_KEY", value);
        } else {
            std::env::remove_var("OPENAI_API_KEY");
        }
    }
}
