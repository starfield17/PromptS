//! Identity: requested / executable / observed — claims, not crypto proof.

use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, Default)]
#[serde(deny_unknown_fields)]
pub struct IdentityRequirement {
    #[serde(default)]
    pub required: bool,
    #[serde(default)]
    pub expected_provider: Option<String>,
    #[serde(default)]
    pub expected_model_prefix: Option<String>,
    #[serde(default)]
    pub expected_executable_realpath: Option<String>,
    #[serde(default)]
    pub expected_executable_sha256: Option<String>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct RequestedIdentity {
    pub harness: String,
    pub model: Option<String>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ExecutableTrust {
    StockAdapter,
    Custom,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ExecutableIdentity {
    pub argv0: String,
    pub path: Option<String>,
    pub realpath: Option<String>,
    pub sha256: Option<String>,
    pub version: Option<String>,
    #[serde(default)]
    pub version_verified: bool,
    pub trust: ExecutableTrust,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum IdentityEvidence {
    StreamClaim,
    Missing,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, Default)]
pub struct ObservedIdentity {
    pub provider: Option<String>,
    pub model: Option<String>,
    pub api_key_source: Option<String>,
    pub evidence: Option<IdentityEvidence>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct IdentityGateResult {
    pub required: bool,
    pub satisfied: bool,
    pub reason: Option<String>,
}

pub fn bounded_identity_label(value: &str) -> String {
    value.chars().take(256).collect()
}

/// Evaluate identity gate. Stream identity is claimed/observed, not verified provider.
pub fn evaluate_identity_gate(
    req: &IdentityRequirement,
    observed: &ObservedIdentity,
    executable: Option<&ExecutableIdentity>,
) -> IdentityGateResult {
    if !req.required {
        return IdentityGateResult {
            required: false,
            satisfied: true,
            reason: None,
        };
    }

    // Custom/strong path: expected executable realpath/hash.
    if let Some(expected_rp) = &req.expected_executable_realpath {
        match executable.and_then(|e| e.realpath.as_ref()) {
            Some(rp) if rp == expected_rp => {}
            Some(_) => {
                return IdentityGateResult {
                    required: true,
                    satisfied: false,
                    reason: Some("executable_realpath_mismatch".into()),
                };
            }
            None => {
                return IdentityGateResult {
                    required: true,
                    satisfied: false,
                    reason: Some("executable_realpath_missing".into()),
                };
            }
        }
    }
    if let Some(expected_hash) = &req.expected_executable_sha256 {
        match executable.and_then(|e| e.sha256.as_ref()) {
            Some(h) if h.eq_ignore_ascii_case(expected_hash) => {}
            Some(_) => {
                return IdentityGateResult {
                    required: true,
                    satisfied: false,
                    reason: Some("executable_sha256_mismatch".into()),
                };
            }
            None => {
                return IdentityGateResult {
                    required: true,
                    satisfied: false,
                    reason: Some("executable_sha256_missing".into()),
                };
            }
        }
    }

    let needs_stream = req.expected_provider.is_some() || req.expected_model_prefix.is_some();
    let has_exec_constraint =
        req.expected_executable_realpath.is_some() || req.expected_executable_sha256.is_some();

    if needs_stream {
        if observed.provider.is_none() && observed.model.is_none() {
            return IdentityGateResult {
                required: true,
                satisfied: false,
                reason: Some("identity_missing".into()),
            };
        }
        if let Some(ep) = &req.expected_provider {
            match &observed.provider {
                Some(p) if p.eq_ignore_ascii_case(ep) => {}
                Some(_) => {
                    return IdentityGateResult {
                        required: true,
                        satisfied: false,
                        reason: Some("provider_mismatch".into()),
                    };
                }
                None => {
                    return IdentityGateResult {
                        required: true,
                        satisfied: false,
                        reason: Some("provider_mismatch".into()),
                    };
                }
            }
        }
        if let Some(prefix) = &req.expected_model_prefix {
            match &observed.model {
                Some(m) if m.starts_with(prefix.as_str()) => {}
                Some(_) => {
                    return IdentityGateResult {
                        required: true,
                        satisfied: false,
                        reason: Some("provider_mismatch".into()),
                    };
                }
                None => {
                    return IdentityGateResult {
                        required: true,
                        satisfied: false,
                        reason: Some("provider_mismatch".into()),
                    };
                }
            }
        }
    } else if !has_exec_constraint {
        // required=true but no concrete expectation: still need some observed claim
        // or executable constraints. For custom harness, realpath/hash is required.
        if observed.provider.is_none() && observed.model.is_none() {
            return IdentityGateResult {
                required: true,
                satisfied: false,
                reason: Some("identity_missing".into()),
            };
        }
    }

    IdentityGateResult {
        required: true,
        satisfied: true,
        reason: None,
    }
}

#[cfg(test)]
#[allow(clippy::unwrap_used, clippy::expect_used)]
mod tests {
    use super::*;

    #[test]
    fn mismatch_provider_blocks() {
        let req = IdentityRequirement {
            required: true,
            expected_provider: Some("anthropic".into()),
            expected_model_prefix: Some("claude-".into()),
            ..Default::default()
        };
        let obs = ObservedIdentity {
            provider: Some("xai".into()),
            model: Some("grok-code-fast".into()),
            api_key_source: None,
            evidence: Some(IdentityEvidence::StreamClaim),
        };
        let g = evaluate_identity_gate(&req, &obs, None);
        assert!(!g.satisfied);
        assert_eq!(g.reason.as_deref(), Some("provider_mismatch"));
    }

    #[test]
    fn any_denial_not_here_but_missing_blocks() {
        let req = IdentityRequirement {
            required: true,
            expected_provider: Some("anthropic".into()),
            ..Default::default()
        };
        let obs = ObservedIdentity::default();
        let g = evaluate_identity_gate(&req, &obs, None);
        assert!(!g.satisfied);
    }
}
