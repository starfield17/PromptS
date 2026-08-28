# Retrofitting an existing repository

A repository that has run for a while contains information a new one doesn't:
which files actually change together, and which boundaries people already
respect without being told. Read that information before proposing anything.

The failure mode here is the six-month migration that gets abandoned at month
two, leaving the codebase in two incompatible styles at once — worse than
either. Everything below is built to avoid it.

## 1. Find the seams from history

Files that change in the same commits belong on the same side of a boundary.
This turns the three-changes test from a guess into a measurement.

`tools/cochange.py`:

```python
#!/usr/bin/env python3
"""Which files keep changing together? Run inside a git repository."""
import subprocess, itertools, collections, re, sys

WINDOW = sys.argv[1] if len(sys.argv) > 1 else "12 months ago"
MAX_FILES = 30            # skip sweeping refactors and reformat commits

log = subprocess.run(
    ["git", "log", "--format=%H", "--name-only", f"--since={WINDOW}"],
    capture_output=True, text=True, check=True).stdout

commits, cur = [], []
for line in log.splitlines():
    if not line.strip():
        continue
    if re.fullmatch(r"[0-9a-f]{40}", line):
        if cur:
            commits.append(cur)
        cur = []
    else:
        cur.append(line)
if cur:
    commits.append(cur)

pairs = collections.Counter()
for files in commits:
    files = sorted(set(files))
    if len(files) > MAX_FILES:
        continue
    for a, b in itertools.combinations(files, 2):
        pairs[(a, b)] += 1

print(f"{len(commits)} commits since {WINDOW}\n")
for (a, b), n in pairs.most_common(40):
    print(f"{n:4}  {a}\n      {b}\n")
```

Read the output for two things:

- **Pairs that cross your intended boundary, often.** The boundary is in the
  wrong place, or those two files should be one.
- **Pairs in the same directory that never co-change.** That directory is two
  things wearing one name — a candidate to split.

Aggregating by directory instead of by file makes the picture clearer on large
repositories; change the `combinations` input to the parent directories.

## 2. Declare the boundary before moving anything

Write the policy — the import-linter contract, the dependency-cruiser rule, the
YAML — against the layout you *have*. Do not move files yet.

Running it now will report a pile of violations. That number is the point.

## 3. Ratchet

Record today's violation count as a baseline. Fail the build only when the count
goes **up**.

```makefile
boundaries:
	@lint-imports --verbose > /tmp/b.txt 2>&1 || true
	@current=$$(grep -c BROKEN /tmp/b.txt); \
	baseline=$$(cat tools/boundaries.baseline); \
	if [ $$current -gt $$baseline ]; then \
	  echo "boundary violations rose: $$baseline -> $$current"; \
	  cat /tmp/b.txt; exit 1; \
	elif [ $$current -lt $$baseline ]; then \
	  echo "violations fell to $$current; lower the baseline in the same commit"; \
	  exit 1; \
	fi
```

Failing on a *decrease* is deliberate. It forces the baseline down as cleanup
happens, so the ratchet can never slip backwards. Without it the number drifts
upward again over a few months and nobody notices.

Three properties make this the right move:

- It starts protecting the repository the same afternoon.
- No flag day, no long-lived branch, no half-migrated state.
- An agent can be handed "lower the baseline by one" as a self-contained task
  with an unambiguous success condition.

Prefer a per-contract baseline over a single global count. One number lets a new
violation in module A hide behind a fix in module B.

## 4. Move one boundary at a time

Pick the boundary with the most crossings and fix only that one. Each step is a
complete, shippable change:

1. Create the module's public surface — one file that re-exports what outsiders
   already use. Nothing moves yet.
2. Point external callers at the surface. Mechanical, reviewable, no behavior
   change.
3. Move the rest behind `internal/`. Now the check enforces it.
4. Lower the baseline.

Steps 1 and 2 deliver most of the value; step 3 is what makes it stick.

## What not to do

- **Do not restructure and change behavior in the same commit.** When something
  breaks you need to know which one did it, and so does the agent bisecting it.
- **Do not create the empty target layout first.** A tree of empty directories
  named after the architecture you intend is an invitation to put things in the
  wrong one.
- **Do not delete the old path as a courtesy in step 2.** Leave the re-export
  until callers are actually gone; it costs one line and removes the pressure to
  do everything at once.
- **Do not add a boundary you cannot check.** If there's no mechanism, the
  retrofit has no ratchet, and it will be undone by the third busy week.
