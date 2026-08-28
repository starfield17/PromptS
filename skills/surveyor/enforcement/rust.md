# Rust

Rust needs essentially no architecture tooling, because the crate graph *is* the
dependency policy and `cargo` refuses to violate it. Use that instead of adding
a lint layer.

## Level 1: one crate per module

```text
Cargo.toml              # [workspace] members
crates/
  core/
  training/
  inference/
  app/                  # the only crate that knows about all of them
```

`crates/training/Cargo.toml`:

```toml
[package]
name = "training"

[dependencies]
core = { path = "../core" }
# inference is absent, so training cannot import it. That is the whole policy.
```

Three properties fall out for free:

- **The policy is declarative and reviewable.** A forbidden dependency appears as
  a line added to `Cargo.toml` — visible in any diff, unlike an import buried in
  a file.
- **Cycles are impossible.** Cargo rejects a cyclic workspace.
- **It cannot be bypassed.** There is no import that works around a missing
  dependency.

An agent that needs a new cross-crate dependency has to state it in a manifest,
which is exactly the interruption you want at a boundary change.

## The public surface

`pub` at the crate root is the surface. Everything else is `pub(crate)`.

```rust
// crates/training/src/lib.rs
mod solver;              // private
mod cache;               // private
pub mod api;             // the surface

pub use api::{Trainer, TrainConfig};
```

`pub(crate)` and module privacy are compiler-enforced, so "don't touch our
internals" is not a rule anyone has to remember.

## When to stay in one crate

Splitting has a real cost: compile times, version churn in manifests, and a
`[workspace]` to maintain. Stay in one crate with private modules until the
three-changes test says a boundary is real. `pub(crate)` alone gets you most of
the way at L0/L1.

## Level 2: only if you need it

```bash
cargo install cargo-deny
```

`deny.toml` `[bans]` blocks specific crates repository-wide — useful for "no
crate may depend on the deprecated client" or for licence and advisory policy.
It is not needed for internal architecture; the workspace already did that.

## Wire it up

```makefile
check:
	cargo build --workspace
	cargo clippy --workspace -- -D warnings
	cargo test --workspace
```

## Proving it works

```bash
echo 'use inference::Engine;' >> crates/training/src/lib.rs
cargo build --workspace     # must fail: unresolved import
git checkout crates/training/src/lib.rs
```

If this *succeeds*, `inference` is reachable — usually because it was added to
`[dependencies]` at some point and nobody removed it, or because a shared crate
re-exports it. The second case is worth hunting down: a crate that re-exports
its own dependencies erases every boundary downstream of it.
