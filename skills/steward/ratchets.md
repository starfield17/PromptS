# Ratchets

A ratchet turns a rule nobody can obey today into a gate that works today. Instead of "there must be no skipped tests" — false, and therefore ignored — it says "there are 34 skipped tests, and 35 fails the build."

Use one when the honest current count is not zero and getting it to zero is a project. If the count is already zero, do not add a ratchet: a rule that says "never" is cheaper and clearer.

## The script

`tools/ratchet.sh`:

```bash
#!/usr/bin/env bash
# ratchet.sh NAME BASELINE_FILE COMMAND...
# COMMAND must print a single integer on stdout.
set -uo pipefail

name="$1"; baseline_file="$2"; shift 2

current=$("$@" 2>/dev/null | tail -1 | tr -dc '0-9')
[ -z "$current" ] && { echo "ratchet:$name: command produced no count" >&2; exit 2; }
[ -f "$baseline_file" ] || { echo "$current" > "$baseline_file"; echo "ratchet:$name: baseline set to $current"; exit 0; }
baseline=$(tr -dc '0-9' < "$baseline_file")

if [ "$current" -gt "$baseline" ]; then
  echo "ratchet:$name: $baseline -> $current. This change added $((current - baseline))." >&2
  echo "Fix it here, or make the exception explicit and raise the baseline in its own commit." >&2
  exit 1
elif [ "$current" -lt "$baseline" ]; then
  echo "ratchet:$name: down to $current from $baseline. Update $baseline_file in this commit." >&2
  exit 1
fi
echo "ratchet:$name: $current (unchanged)"
```

Wire it in with everything else:

```makefile
check: test types boundaries tests-intact entropy

boundaries:
	./tools/ratchet.sh boundaries tools/baselines/boundaries \
	  bash -c 'lint-imports 2>&1 | grep -c BROKEN'

tests-intact:
	python3 tools/check_tests_intact.py origin/main
	./tools/ratchet.sh skips tools/baselines/skips \
	  bash -c 'grep -rEc "@pytest\.mark\.(skip|xfail)" tests/ | awk -F: "{s+=\$$2} END {print s+0}"'

entropy:
	./tools/ratchet.sh deadcode tools/baselines/deadcode \
	  bash -c 'vulture src/ --min-confidence 80 | wc -l'
```

## Why it also fails when the count goes down

This looks wrong the first time and is the load-bearing part.

If a decrease passes silently, the baseline file stays at the old number, and that slack is spent — silently — by the next change that adds a violation. Cleanup work produces no lasting protection, and the count drifts back up over a few months with every individual build green. Forcing the baseline down in the same commit as the cleanup is what makes the ratchet monotonic, which is the entire point of calling it a ratchet.

The cost is one number edited per cleanup commit. That is also a benefit: the diff shows the number moving, so progress is visible in review instead of being invisible work.

## Rules that make ratchets survive

**One counter per thing, and prefer per-module counters to one global number.** A single number lets a new violation in module A hide behind a fix in module B. `lint-imports` reports per contract; keep them separate.

**The baseline file is versioned and its changes are reviewed.** A baseline raised in the same commit as a feature is the failure mode this whole mechanism exists to prevent — it is the boundary-check equivalent of editing the test. Raising a baseline is a tier-2 event: separate commit, stated reason.

**Never auto-update the baseline.** A make target that writes the current count is a ratchet with the pawl removed.

**Cap the number of ratchets at three.** Every ratchet is a build failure someone must interpret at an inconvenient moment. Boundaries, disabled tests, dead code — those three cover the accumulation that actually compounds. A fourth mostly teaches people to run `make check -k`.

## Adding one to an existing repository

1. Run the counting command. Get the real number. Do not flinch at it — the number is the reason the ratchet exists rather than a rule.
2. Commit it as the baseline, alone, with a message saying what it counts.
3. Add a violation on purpose and confirm the build fails with a message that names what to do. A ratchet that has never failed has not been shown to work, and the usual cause of a silent pass is a counting command that matches nothing and prints `0` forever.
4. Only then hand out cleanup tasks. "Lower `tools/baselines/skips` by one" is an unusually good agent task: self-contained, unambiguous success condition, and impossible to fake without editing a file that shows up in review.
