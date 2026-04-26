# Delegation Patterns

## Single explorer

Use one `explorer` subagent to map an unfamiliar repository, identify relevant files, and recommend next steps. Codex then decides whether to delegate implementation.

## Implementer plus reviewer

Use an `implementer` to create a patch and a `reviewer` to critique the patch. Codex inspects both outputs before applying changes.

## Parallel alternatives

Launch multiple implementers with different constraints, such as minimal patch, broader refactor, or backwards-compatible design. Codex compares results and chooses the safest path.

## Split by surface area

Run separate subagents for backend, frontend, tests, docs, migrations, or release notes when those areas are independent.

## Adversarial review

After implementation, launch an `adversary` subagent to look for regressions, security issues, edge cases, and overbroad changes.

## Collision follow-up

If parallel tasks touch the same file, stop short of auto-applying either patch. Use a focused `reviewer` or `adversary` task to compare intent, then let Codex choose the final change set.
