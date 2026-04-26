# Runtime directory

Runtime outputs should normally be written outside the packaged skill, typically to `.CC_subagent/` in the active repository or working directory.

Recommended layout:

```text
.CC_subagent/
  index.json
  summary.md
  summary.json
  runs/
  workspaces/
```

The wrapper keeps workspaces and run artifacts so Codex can inspect behavior after the subprocess exits.
