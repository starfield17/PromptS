#!/usr/bin/env bash
# Emit release metadata for subagent-broker V3.1 (stdout). Does not install/replace skill.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
RUST_DIR="$ROOT/rust"
BIN="${SUBAGENT_BROKER_BIN:-$ROOT/scripts/subagent-broker}"
ALT_BIN="$RUST_DIR/target/release/subagent-broker"
case "$(uname -m)" in
  x86_64|amd64) HOST_TARGET="linux-x86_64" ;;
  aarch64|arm64) HOST_TARGET="linux-aarch64" ;;
  *) HOST_TARGET="unknown" ;;
esac
PACKAGED_BIN="$ROOT/bin/$HOST_TARGET/subagent-broker"

echo "=== subagent-broker V3.1 release metadata ==="
echo "skill_root=$ROOT"
echo "date_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
if git -C "$ROOT" rev-parse --verify HEAD >/dev/null 2>&1; then
  echo "git_commit=$(git -C "$ROOT" rev-parse HEAD)"
else
  echo "git_commit=unavailable"
fi

if command -v rustc >/dev/null 2>&1; then
  echo "rustc=$(rustc -vV | awk '/^release:/{print $2}')"
  echo "host=$(rustc -vV | awk '/^host:/{print $2}')"
else
  echo "rustc=unavailable"
fi

if [[ -f "$RUST_DIR/Cargo.lock" ]]; then
  echo "cargo_lock_sha256=$(sha256sum "$RUST_DIR/Cargo.lock" | awk '{print $1}')"
fi

if [[ -x "$BIN" ]]; then
  echo "launcher_path=$BIN"
  echo "launcher_sha256=$(sha256sum "$BIN" | awk '{print $1}')"
  file "$BIN" || true
fi
if [[ -x "$PACKAGED_BIN" ]]; then
  echo "binary_path=$PACKAGED_BIN"
  echo "binary_sha256=$(sha256sum "$PACKAGED_BIN" | awk '{print $1}')"
  file "$PACKAGED_BIN" || true
elif [[ -x "$ALT_BIN" ]]; then
  echo "binary_path=$ALT_BIN"
  echo "binary_sha256=$(sha256sum "$ALT_BIN" | awk '{print $1}')"
  file "$ALT_BIN" || true
else
  echo "binary_path=missing"
fi

if [[ -d "$RUST_DIR" ]] && command -v cargo >/dev/null 2>&1; then
  echo "--- cargo metadata packages (name@version) ---"
  (cd "$RUST_DIR" && cargo metadata --format-version 1 --no-deps 2>/dev/null | \
    python3 -c 'import json,sys; d=json.load(sys.stdin); print(d["packages"][0]["name"], d["packages"][0]["version"])' 2>/dev/null) || true
  echo "--- dependency count ---"
  (cd "$RUST_DIR" && cargo metadata --format-version 1 2>/dev/null | \
    python3 -c 'import json,sys; d=json.load(sys.stdin); print(len(d.get("packages",[])))' 2>/dev/null) || true
fi

if command -v cargo-cyclonedx >/dev/null 2>&1 && [[ -d "$RUST_DIR" ]]; then
  echo "cyclonedx=available (run: cd rust && cargo cyclonedx)"
else
  echo "cyclonedx=not installed (optional)"
fi

echo "=== end ==="
