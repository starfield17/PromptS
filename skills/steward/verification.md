# Verification integrity

An agent that can edit both the implementation and the test has two ways to turn the suite green, and one of them is much shorter. This file exists to make the short one expensive and the honest one obviously available.

Nothing here assumes bad intent. The mechanism is simpler than that: a failing assertion and a wrong implementation present identically — as a red line in the output — and the local edit that clears the red line is the edit to the assertion. An agent optimizing for the observable signal will find it, and will produce a fluent, confident explanation of why the test was wrong.

## What it actually looks like

Ordered roughly by how often it happens and how well it hides.

**Disabling.** `@pytest.mark.skip`, `@pytest.mark.xfail`, `it.skip` / `xit` / `describe.skip`, `t.Skip()`, `#[ignore]`, `@Disabled`, `@Ignore`. Also renaming `test_foo` to `check_foo` so the runner stops collecting it, and moving a file out of the tests directory.

**Removing.** Deleting an assertion but keeping the test, so the test still counts as passing. Deleting an entire test case in a commit whose message is about something else.

**Weakening.** `assert result == expected` → `assert result is not None`. `assertEqual` → `assertTrue`. A tolerance widened from `1e-9` to `1e-2`. A regex matcher relaxed to `.*`. An exact list compared as a set, or by length. `assert x in (a, b)` where it used to be `assert x == a`.

**Mocking the thing under test.** Patching the function whose behavior the test exists to check, so it returns the expected value. This is the hardest one to spot in review, because the diff looks like ordinary test setup and the test still contains real assertions — that now assert the mock's configuration back to itself.

**Swallowing.** Wrapping the body in `try/except: pass`, or an assertion inside a conditional that is never true. A test that cannot fail is worse than a deleted one, because it reports success.

**Re-recording.** Snapshot and golden-file tests regenerated with `--update-snapshots` without anyone reading the new snapshot. This is legitimate roughly half the time, which is why it needs the diff of the snapshot to be read out loud, not just the fact of regeneration.

**Moving the gate.** `continue-on-error: true` in CI, `--maxfail`, a `deselect` or `testpaths` narrowed in config, `|| true` appended to a make target, a timeout raised until a hanging test passes, retries added to a flaky test instead of a diagnosis.

The last category deserves its own rule: **any diff to CI config, test-runner config, or a check's make target during an implementation task is out of tier.** Those files are the measurement.

## Two cases the four rules don't cover on their own

**A test that is genuinely wrong** gets *deleted*, in its own commit, with the reason — not disabled. A disabled test is one nobody will read again and everyone will keep carrying: it survives refactors, it appears in counts, it makes the suite look larger than it is, and its skip reason ("flaky", "TODO") is unfalsifiable forever. Deletion is honest and reversible; disabling is neither.

**A flaky test** is a bug report about the code or the test, not an exemption. Retries hide the report. If flakiness genuinely must be tolerated for now, the skip carries an issue reference and a date, and it counts against the ratchet like any other debt.

## The check

`tools/check_tests_intact.py`. It compares test files against a base ref and fails when assertions went down or disables went up.

```python
#!/usr/bin/env python3
"""Fail when a change weakened the tests instead of fixing the code.

Usage: check_tests_intact.py [base-ref]   (default: HEAD)
"""
import fnmatch, pathlib, re, subprocess, sys

BASE = sys.argv[1] if len(sys.argv) > 1 else "HEAD"

TEST_GLOBS = [
    "tests/*", "test/*", "*/tests/*", "*/test/*",
    "*test_*.py", "*_test.py", "*_test.go", "*_test.rs",
    "*.test.ts", "*.test.tsx", "*.test.js", "*.spec.ts", "*.spec.js",
]

ASSERT = re.compile(
    r"(\bassert\b|\bassert[A-Z]\w*\(|\bexpect\(|\bshould\b"
    r"|\bt\.(Error|Fatal)\w*\(|\brequire\.\w+\(|\bassert_\w+!)"
)
DISABLE = re.compile(
    r"(@pytest\.mark\.(skip|skipif|xfail)|pytest\.skip\(|@unittest\.skip"
    r"|\b(it|test|describe)\.(skip|todo)\(|\bx(it|describe)\("
    r"|\bt\.Skip(Now)?\(|#\[ignore\]|@Disabled|@Ignore)"
)


def is_test(path: str) -> bool:
    return any(fnmatch.fnmatch(path, g) or fnmatch.fnmatch(path, f"*/{g}")
               for g in TEST_GLOBS)


def at_base(path: str) -> str | None:
    r = subprocess.run(["git", "show", f"{BASE}:{path}"],
                       capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else None


def counts(text: str) -> tuple[int, int]:
    return (len(ASSERT.findall(text)), len(DISABLE.findall(text)))


changed = subprocess.run(["git", "diff", "--name-status", BASE],
                         capture_output=True, text=True, check=True).stdout

problems = []
for line in changed.splitlines():
    parts = line.split("\t")
    status, path = parts[0], parts[-1]
    if not is_test(path):
        continue
    if status.startswith("D") or (status.startswith("R") and not is_test(parts[1])):
        problems.append(f"{path}: test file deleted or moved out of the suite")
        continue
    before = at_base(parts[1] if status.startswith("R") else path) or ""
    after = pathlib.Path(path).read_text(errors="ignore")
    a_before, d_before = counts(before)
    a_after, d_after = counts(after)
    if a_after < a_before:
        problems.append(f"{path}: assertions {a_before} -> {a_after}")
    if d_after > d_before:
        problems.append(f"{path}: disabled markers {d_before} -> {d_after}")

for p in problems:
    print(p, file=sys.stderr)

if problems:
    print(
        "\nThe tests got weaker. If that is deliberate, it is a tier-2 change:\n"
        "  - land the test change in its own commit, stating what behavior changed\n"
        "  - to remove a wrong test, delete it and say why; do not disable it\n"
        "If it is not deliberate, the code is what needs fixing.",
        file=sys.stderr)
    sys.exit(1)

print("tests intact")
```

It is deliberately crude. Counting assertions cannot see `assertEqual` becoming `assertTrue`, and no static check can see a mock that returns the expected value. It catches the common, mechanical half; the rest is what the tier-2 ordering rule and the review of the test commit are for. A crude check that fails the build still beats a precise rule in a README.

**Prove it works** the same way as any other gate — break it on purpose:

```bash
echo "@pytest.mark.skip" >> tests/test_thing.py
python3 tools/check_tests_intact.py    # must exit 1, naming the file
git checkout tests/test_thing.py
```

## The skip ratchet

The check above catches disables inside one change. It says nothing about the pile that already exists. For that, count them across the repository and ratchet the count down over time — mechanism in `ratchets.md`.

```bash
# a count, for the ratchet
grep -rEc "$DISABLE_PATTERN" tests/ | awk -F: '{s+=$2} END {print s+0}'
```

Skips that are legitimately permanent — platform-specific, requires-hardware — should be marked with a distinguishable helper (`skip_no_gpu`) and excluded from the pattern, so the number that remains is the number that represents debt.

## Done, and the stuck report

**Done** is the scenario from `SPEC.md`, or, when there is no spec, one sentence of observable behavior written before the work started. Report it by describing what you ran and what you saw, not by describing the diff. "All tests pass" is not a report of a result; it is a report of the measurement.

**Stuck** is what you produce when the change cannot be made without breaking one of the rules above. Four parts:

1. What the change needs to do, in one line.
2. The smallest reproducible case of what fails.
3. Which rule blocks the obvious workaround — the tier boundary, the read-only test, the boundary check.
4. Two options with their costs, and a recommendation.

Producing this is a completed task. The failure mode this is written against is an agent that, faced with a genuine blocker, produces a change that passes the checks and does not work, because "passes the checks" was the only terminal state it had available.
