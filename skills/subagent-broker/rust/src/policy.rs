//! Mechanical path policy — no business-semantic checks.

use globset::{Glob, GlobSet, GlobSetBuilder};

use crate::error::{BrokerResult, PolicyError};
use crate::task::{PatchPolicy, RepoPath};

pub struct PathPolicy {
    allowed: GlobSet,
    denied: GlobSet,
    max_files_changed: usize,
    patch_policy: PatchPolicy,
}

impl PathPolicy {
    pub fn new(
        allowed_paths: &[String],
        deny_paths: &[String],
        max_files_changed: usize,
        patch_policy: PatchPolicy,
    ) -> BrokerResult<Self> {
        Ok(Self {
            allowed: build_globs(allowed_paths)?,
            denied: build_globs(deny_paths)?,
            max_files_changed,
            patch_policy,
        })
    }

    pub fn path_allowed(&self, path: &str) -> bool {
        if self.denied.is_match(path) {
            return false;
        }
        !self.allowed.is_empty() && self.allowed.is_match(path)
    }

    pub fn check_changed_paths(&self, paths: &[String]) -> Result<(), PolicyError> {
        if paths.len() > self.max_files_changed {
            return Err(PolicyError::TooManyFiles(paths.len()));
        }
        for p in paths {
            if !self.path_allowed(p) {
                if self.denied.is_match(p) {
                    return Err(PolicyError::PathDenied(p.clone()));
                }
                return Err(PolicyError::PathNotAllowed(p.clone()));
            }
            // RepoPath validation for non-glob concrete paths
            if let Err(e) = RepoPath::new(p) {
                return Err(PolicyError::Other(e.to_string()));
            }
        }
        Ok(())
    }

    pub fn allow_deletes(&self) -> bool {
        self.patch_policy.allow_deletes
    }

    pub fn allow_binary(&self) -> bool {
        self.patch_policy.allow_binary_changes
    }
}

fn build_globs(patterns: &[String]) -> BrokerResult<GlobSet> {
    let mut b = GlobSetBuilder::new();
    for p in patterns {
        let glob = Glob::new(p)
            .map_err(|e| crate::error::TaskError::Other(format!("invalid glob {p}: {e}")))?;
        b.add(glob);
    }
    b.build()
        .map_err(|e| crate::error::TaskError::Other(e.to_string()).into())
}

#[cfg(test)]
#[allow(clippy::unwrap_used, clippy::expect_used)]
mod tests {
    use super::*;
    use crate::task::PatchPolicy;

    #[test]
    fn deny_wins() {
        let p = PathPolicy::new(
            &["**".into()],
            &["secrets/**".into()],
            50,
            PatchPolicy::default(),
        )
        .expect("policy");
        assert!(!p.path_allowed("secrets/key"));
        assert!(p.path_allowed("src/main.rs"));
    }

    #[test]
    fn empty_allow_set_is_fail_closed() {
        let p = PathPolicy::new(&[], &[], 50, PatchPolicy::default()).expect("policy");
        assert!(!p.path_allowed("src/main.rs"));
        assert!(p.check_changed_paths(&["src/main.rs".into()]).is_err());
    }
}
