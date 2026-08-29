# Change tiers

The tier is a property of the diff. It is not a judgment about how big or risky the change feels, because that judgment is made by the party who wants the change to be small, and it is always rounded down.

## The config

`tools/tiers.txt` — one rule per line, `kind` then a glob. Fill it in once, from the repository's actual layout.

```text
# Tier 4 — structure. Back to surveyor.
structure  .importlinter
structure  .dependency-cruiser.js
structure  tools/boundaries.yaml
structure  **/Cargo.toml
structure  **/go.mod

# Tier 3 — contract. Someone outside this module depends on it.
contract   src/modules/*/index.ts
contract   src/modules/*/public.py
contract   **/openapi.yaml
contract   **/*.proto
contract   migrations/**
contract   **/schema.sql
contract   src/api/**

# Tier 2 — the measurement itself.
test       tests/**
test       **/test_*.py
test       **/*_test.go
test       **/*.test.ts
test       **/*.spec.ts

# Everything else is tier 1.
```

Getting the `contract` list right is most of the value here, and it is the part only this repository knows. If `surveyor` has already run, the public surface files named in each module's `AGENTS.md` are exactly this list — copy them over.

## The classifier

`tools/classify_change.py`:

```python
#!/usr/bin/env python3
"""Print the tier of the current change. Usage: classify_change.py [base-ref]"""
import fnmatch, pathlib, subprocess, sys

BASE = sys.argv[1] if len(sys.argv) > 1 else "HEAD"
CFG = pathlib.Path("tools/tiers.txt")

rules = []
for line in CFG.read_text().splitlines():
    line = line.split("#", 1)[0].strip()
    if line:
        kind, _, glob = line.partition(" ")
        rules.append((kind, glob.strip()))

changed = subprocess.run(
    ["git", "diff", "--name-only", BASE],
    capture_output=True, text=True, check=True).stdout.split()
changed += subprocess.run(
    ["git", "ls-files", "--others", "--exclude-standard"],
    capture_output=True, text=True, check=True).stdout.split()

def kinds(path: str) -> set[str]:
    out = set()
    for kind, glob in rules:
        if fnmatch.fnmatch(path, glob) or fnmatch.fnmatch(path, f"*/{glob}"):
            out.add(kind)
    return out

hits = {"structure": [], "contract": [], "test": [], "internal": []}
for path in sorted(set(changed)):
    for kind in kinds(path) or {"internal"}:
        hits[kind].append(path)

if not any(hits.values()):
    print("tier 0 — nothing changed")
    sys.exit(0)

for kind, tier, verdict in [
    ("structure", 4, "STOP. Dependency policy or module set changed — this is surveyor's job."),
    ("contract",  3, "STOP. A public surface changed. Name the callers, get a human yes."),
    ("test",      2, "Tests changed. They land in their own commit, before the implementation."),
]:
    if hits[kind]:
        print(f"tier {tier} — {verdict}")
        for p in hits[kind]:
            print(f"  {p}")
        sys.exit(tier)

print(f"tier 1 — internal only ({len(hits['internal'])} file(s)). Existing tests are the gate.")
sys.exit(0)
```

The exit code is the tier for 2, 3 and 4, and `0` for tier 1 — so a non-zero exit means exactly "this needs more than just doing it": `python3 tools/classify_change.py || echo "not a tier-1 change"`.

Run it **twice** — once against the plan, once against the finished diff. The second run is the one that catches the change that grew.

## What each tier actually requires

**Tier 1 · internal.** No process. Make the change, run the existing gates. The absence of ceremony is the point: a tier system whose cheapest lane still costs a document will be bypassed for small changes, and small changes are most changes.

**Tier 2 · behavior.** The rule is ordering, not approval. Change the tests first, in their own commit, and watch them fail for the reason you expect. Then implement. This is the whole of TDD that matters here, and it exists for a mechanical reason rather than a philosophical one: when the test and the implementation move in one commit, nothing distinguishes "I changed the expected behavior" from "I made the assertion match whatever the code now does," including for the agent writing it.

**Tier 3 · contract.** Stop and produce three things before touching anything: the list of call sites (`grep`, not memory), what breaks for each, and whether the change is additive or breaking. Additive changes to a surface with a handful of internal callers are usually fine to proceed on after saying so. Breaking changes need a human. Adding one function to a public surface **is** a tier-3 change; the size of the addition is not the issue, the permanence of the promise is.

**Tier 4 · structure.** Not this skill. New module, deleted module, or an edit to the dependency policy — that is a boundary decision and belongs to `surveyor`.

## Cases that look ambiguous and are not

| Situation | Tier | Why |
|---|---|---|
| Fixing a bug that a test asserted the wrong behavior for | 2 | The test changes. It changes first, and the commit says what was wrong about it |
| Adding a test for existing untested code | 2, trivially | Only tests move. Nothing to serialize against |
| Renaming a private function used in 30 places | 1 | Nothing crosses a boundary; the compiler or test suite is the gate |
| Renaming an exported function with one internal caller | 3 | It is on the surface. Cheap to do, still tier 3 |
| Bumping a dependency version | 3 | Behavior arrives from outside with nobody reading the diff |
| Adding a feature flag defaulting to off | 1 | Until something reads it across a boundary |
| Deleting a module nobody imports | 4 | The module set is the structure |
| Changing a config default in production | 3 | Config is a contract with the deployment, and it has no test |

## When the tier rises mid-task

The correct move is to stop, not to finish and disclose. Concretely: keep the tier-1 part if it stands alone and is worth landing, revert the rest, and report — "this needs a change to `modules/export`'s public surface because X; here are the callers; do you want it?"

The reason to be strict about this is that "I was already almost done" is the argument that eventually consumes every boundary in the repository. It is also always true, which is what makes it useless as a criterion.
