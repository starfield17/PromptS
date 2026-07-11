//! Diagnostic redaction — harness still receives full goal; logs/argv dumps do not.

/// Redact goal text for diagnostic logs (never store secrets in event argv dumps).
pub fn redact_goal_for_diag(goal: &str) -> String {
    format!("[redacted goal len={}]", goal.chars().count())
}

/// Replace exact goal occurrences in argv with a redacted token for diagnostics.
pub fn redact_argv_for_diag(argv: &[String], goal: &str) -> Vec<String> {
    if goal.is_empty() {
        return argv.to_vec();
    }
    let token = redact_goal_for_diag(goal);
    argv.iter()
        .map(|arg| {
            if arg == goal {
                token.clone()
            } else if arg.contains(goal) {
                // Prompt wrappers that embed the goal.
                arg.replace(goal, &token)
            } else {
                arg.clone()
            }
        })
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn redacts_exact_goal_arg() {
        let goal = "secret mission xyz";
        let argv = vec!["claude".into(), goal.to_string()];
        let out = redact_argv_for_diag(&argv, goal);
        assert_eq!(out[0], "claude");
        assert!(out[1].starts_with("[redacted goal len="));
        assert!(!out[1].contains("secret"));
    }

    #[test]
    fn redacts_embedded_goal() {
        let goal = "do the thing";
        let argv = vec![format!("Working directory: /tmp\n\nTask: {goal}\n")];
        let out = redact_argv_for_diag(&argv, goal);
        assert!(!out[0].contains("do the thing"));
        assert!(out[0].contains("[redacted goal len="));
    }
}
