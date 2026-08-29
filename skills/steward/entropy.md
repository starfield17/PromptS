# Entropy

The dominant long-run failure of an agent-maintained repository is not bad architecture. It is accumulation: three overlapping helpers, an interface with one implementation, a compatibility shim whose old path lost its last caller a year ago, a feature flag that has been on everywhere since it was added.

The asymmetry that causes it is structural, not a defect of any particular model. **Adding is local and provably safe: the new function has no callers, so it cannot break anything. Removing requires proving a global negative.** Under any pressure at all, an agent chooses the local move — and so does a human, which is why this is the oldest problem in the field and not a new one.

The consequence: deletion never happens as a side effect of ordinary work. It needs its own task type, its own success criterion, and its own counter.

## The four things to look for

Ordinary tools find dead symbols. These four are the ones tools miss, because everything involved is technically reachable.

**Interfaces with one implementation and no test double.** The abstraction is paying for optionality nobody exercised. Delete the interface, keep the implementation. If a second implementation later appears, extracting the interface at that point is a mechanical refactor — and it will be the *right* interface, which the speculative one usually is not.

**Overlapping implementations.** Two functions that do nearly the same thing, in different places, with different edge-case handling — one of which is a bug nobody has hit yet. Find them by behavior, not by name: they almost never share a name, since the second one exists precisely because the author did not find the first.

**Compatibility shims with no old callers.** The re-export left behind during a migration, the `v1` handler that forwards to `v2`, the parameter kept "for backward compatibility." Check for callers, including outside the repository if it is a published interface. If there are none, this is free removal.

**Configuration that has never varied.** A flag that has been the same value in every environment since it shipped, a strategy setting with one strategy, an environment variable nobody sets. Each of these multiplies the states the code can be in, and every one of those states is a thing an agent must reason about while reading.

## Where the caller graph lies

Before deleting, know that static analysis under-reports usage in these cases. Each has produced real outages.

- **Dependency injection and service registries** — the class is constructed by name from a container or a config string.
- **Reflection and dynamic dispatch** — `getattr`, `importlib`, `eval`, Java/C# reflection, Ruby `send`.
- **Entry points declared in manifests** — `pyproject.toml` scripts, `package.json` bin, plugin entry-point groups, systemd units, cron, CI workflow files.
- **Templates and query strings** — a name that only appears inside an HTML template, a SQL string, or a serialized ORM query.
- **Serialized data and migrations** — a class removed today breaks the unpickling of a queue message written yesterday, and old migrations that import application code break on replay.
- **Public API of a published library** — the callers are not in this repository and grep cannot see them.
- **Tests as the only caller** — a function used only by tests is dead code with a witness. Delete both, unless the test is a characterization test of behavior something else relies on.

Practical rule: grep for the **bare string name** in every file type, not just source — templates, configs, YAML, migrations, docs. Then check what the deployment starts. Then delete.

## The sweep

A recurring task, not a habit. Triggered by the ratchet's number rising, by a release, or by a fixed cadence.

1. Run the detectors below. Read the list; do not act on it yet — these tools have false positives and the false positives are exactly the reflection cases above.
2. Pick **one** category. Not one item, not everything.
3. For each candidate: grep by string name, check the manifest entry points, run the full suite.
4. Delete in **its own commit**, deletion only, no other changes. A pure deletion commit is trivially revertable, which is what makes the whole thing cheap enough to be worth doing. A deletion mixed into a feature commit is a landmine.
5. Lower the baseline in the same commit.

**Do not deprecate.** Deprecation is a protocol for interfaces with callers you cannot reach. Inside a repository where every caller is visible, `@deprecated` is a delayed deletion that never arrives, and it costs a permanent second code path plus a warning everyone learns to ignore. Delete it, and let the compiler or the test suite find the callers.

## Detectors

Each prints things that look unused. Each has false positives. Use them to generate candidates, never to authorize a deletion.

**Python**
```bash
vulture src/ --min-confidence 80      # dead functions, classes, variables
ruff check --select F401,F841 src/    # unused imports and locals
deptry .                              # declared dependencies nobody imports
```

**TypeScript**
```bash
npx knip                              # unused files, exports, deps — the best of these
npx ts-prune                          # unused exports only
npx depcruise --config .dependency-cruiser.js --output-type err src   # no-orphans rule
```

**Go**
```bash
go vet ./...
deadcode ./...                        # golang.org/x/tools/cmd/deadcode, call-graph based
staticcheck ./...                     # U1000 for unused unexported code
```
Go's `deadcode` is call-graph based rather than name based, which makes it the most trustworthy tool in this list — and it still cannot see reflection.

**Rust**
```bash
cargo build --workspace               # dead_code warnings, on by default
cargo machete                         # unused dependencies, fast
cargo +nightly udeps                  # slower, more accurate
```

**Any language**
```bash
git log --diff-filter=A --format=%cs -1 -- <path>   # when did this file arrive
git log --oneline -1 -- <path>                      # last time anyone touched it
```
A file untouched for two years is not automatically dead — it may be stable, which is a virtue. But an untouched file that also appears in no detector's *live* set is a strong candidate.

## The ratchet

Pick one number that represents accumulation and ratchet it: the count of `knip` findings, `vulture` hits, or `deadcode` results. Mechanism in `ratchets.md`.

Ratchet one number, not three. Three numbers going in three directions produce a dashboard, and a dashboard produces nothing.

## What not to delete

- Anything whose removal you cannot test locally.
- Error handling for a case you cannot trigger. Untriggerable is not the same as unreachable, and this is where "cleanup" turns into an outage.
- A test that looks redundant. Redundant tests cost a few seconds; the one you delete is the one that would have caught the next regression.
- Code you do not understand. "It seems unused" plus "I cannot tell what it does" is the combination that should stop a deletion, not the one that motivates it.
