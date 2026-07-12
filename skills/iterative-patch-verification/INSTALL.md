# Installation

## Generic Agent Installation

1. Extract the archive.
2. Copy the `iterative-patch-verification` directory into your agent's skill directory.
3. Ensure the agent can read `SKILL.md`.
4. Ensure the agent has permission to inspect repositories and run the project's validation commands.
5. Run the package validator:

```bash
cd iterative-patch-verification
python3 scripts/validate_skill.py
```

## Repository Requirements

The workflow is most effective when the project has:

- version control,
- a repeatable test command,
- static or type checks,
- and access to the actual source after each patch.

## Recommended Tool Access

The Lead Agent should be able to:

- extract archives,
- read the full repository,
- run shell commands,
- create temporary regression tests,
- inspect Git state,
- and package the reviewed repository.

The Local Coding Agent should be able to:

- edit files,
- run tests,
- create commits,
- and report exact limitations.

## Uninstallation

Remove the `iterative-patch-verification` directory from the agent's skill directory.
