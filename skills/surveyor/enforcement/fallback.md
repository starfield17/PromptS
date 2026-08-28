# Fallback: a boundary check you write yourself

Use this when no tool fits the language, when the repository is polyglot, or
when adding a dependency for this is more friction than it's worth. Text
scanning is crude — it will miss dynamic imports and it doesn't understand
transitive dependencies — but a crude check that fails the build beats a precise
rule that lives in a README.

Put the policy in data, not in the script. The policy is the thing people edit.

`tools/boundaries.yaml`:

```yaml
root: src
modules:
  training:
    may_depend_on: [core]
  inference:
    may_depend_on: [core]
  core:
    may_depend_on: []
internal_dir: internal      # nothing outside a module may import past this
```

`tools/check_boundaries.py`:

```python
#!/usr/bin/env python3
"""Fail if a module imports something its policy does not allow."""
import re, sys, pathlib, yaml

CFG = yaml.safe_load(open("tools/boundaries.yaml"))
ROOT = pathlib.Path(CFG["root"])
MODULES = CFG["modules"]
INTERNAL = CFG.get("internal_dir", "internal")

# Widen this for other languages; the shape of an import line is all we need.
IMPORT = re.compile(
    r"""^\s*(?:from|import|use|require\(|#include\s*["<])\s*["'<]?([\w./:-]+)""",
    re.MULTILINE,
)
SUFFIXES = {".py", ".ts", ".tsx", ".js", ".go", ".rs", ".java", ".kt"}

def module_of(path: pathlib.Path) -> str | None:
    parts = path.relative_to(ROOT).parts
    return parts[1] if len(parts) > 1 and parts[0] == "modules" else None

violations = []
for f in ROOT.rglob("*"):
    if f.suffix not in SUFFIXES or not f.is_file():
        continue
    owner = module_of(f)
    if owner is None:
        continue
    allowed = set(MODULES.get(owner, {}).get("may_depend_on", [])) | {owner}
    for target in IMPORT.findall(f.read_text(errors="ignore")):
        for other in MODULES:
            if other == owner or f"modules/{other}" not in target.replace(".", "/"):
                continue
            if other not in allowed:
                violations.append(f"{f}: {owner} -> {other} (not allowed)")
            elif f"/{INTERNAL}/" in target.replace(".", "/"):
                violations.append(f"{f}: {owner} -> {other} internals")

for v in sorted(set(violations)):
    print(v, file=sys.stderr)
print(f"{len(set(violations))} boundary violation(s)", file=sys.stderr)
sys.exit(1 if violations else 0)
```

Wire it into the same `check` target as everything else.

## Making the failure message useful

The agent that hits this reads only the last few lines of output. Say what was
violated and what to do instead, not just that something failed:

```text
src/modules/training/train.py: training -> inference (not allowed)
  training may depend on: core
  If this dependency is real, it is a boundary change: update
  tools/boundaries.yaml in its own commit and say why.
```

That last sentence is doing the important work. Without it the agent's next move
is to add `inference` to `may_depend_on` inside the same commit as the feature,
and the policy quietly becomes whatever the code already does.

## Proving it works

Add a forbidden import, run it, confirm the exit code is non-zero and the
message names the right pair, then remove it. Also add an *allowed* import and
confirm it passes — a regex that matches nothing exits 0 on everything, which
looks identical to success.
