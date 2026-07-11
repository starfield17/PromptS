#!/usr/bin/env bash
# Remove built binary and Cargo intermediate artifacts (target/, fuzz target/, leftovers).
set -euo pipefail

if [ -z "${BASH_VERSION:-}" ]; then
  echo "error: this script requires bash (run: bash $0 ...)" >&2
  exit 1
fi

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
RUST_DIR="$ROOT/rust"
OUT_BIN_DIR="$ROOT/bin"

DRY_RUN=0
KEEP_BINARY=0

usage() {
  cat <<'EOF'
Usage: clean.sh [options]

Remove the skill binary and Cargo build products under this skill tree.

Options:
  --dry-run        Print paths that would be removed; do not delete
  --keep-binary    Leave packaged bin/ binaries; still clean target dirs
  -h, --help       Show this help

Removes (when present):
  bin/linux-x86_64/subagent-broker and bin/linux-aarch64/subagent-broker
  bin/.subagent-broker.tmp.*
  rust/target/
  rust/fuzz/target/
  release-artifacts/   (skill root, if left from CI/local packaging)
  rust/Cargo.lock.bak

Does not remove:
  rust/Cargo.lock, sources, templates, references, or runtime .subagents/
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    --keep-binary)
      KEEP_BINARY=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "error: unknown option: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

rm_path() {
  local path="$1"
  if [[ ! -e "$path" && ! -L "$path" ]]; then
    return 0
  fi
  if [[ "$DRY_RUN" == "1" ]]; then
    echo "    would remove $path"
    return 0
  fi
  rm -rf "$path"
  echo "    removed $path"
}

echo "==> clean binary and build products under $ROOT"
if [[ "$DRY_RUN" == "1" ]]; then
  echo "    (dry-run: no deletions)"
fi

if [[ "$KEEP_BINARY" == "1" ]]; then
  echo "    keeping $OUT_BIN_DIR (--keep-binary)"
else
  if [[ -d "$OUT_BIN_DIR" ]]; then
    rm_path "$OUT_BIN_DIR"
  else
    echo "    no bin/"
  fi
fi

# Leftovers from interrupted atomic installs in build.sh
shopt -s nullglob
tmp_files=("$OUT_BIN_DIR"/.subagent-broker.tmp.*)
shopt -u nullglob
if ((${#tmp_files[@]})); then
  for f in "${tmp_files[@]}"; do
    rm_path "$f"
  done
else
  echo "    no bin/.subagent-broker.tmp.*"
fi

if [[ -d "$RUST_DIR/target" ]]; then
  rm_path "$RUST_DIR/target"
else
  echo "    no rust/target"
fi

if [[ -d "$RUST_DIR/fuzz/target" ]]; then
  rm_path "$RUST_DIR/fuzz/target"
else
  echo "    no rust/fuzz/target"
fi

if [[ -d "$ROOT/release-artifacts" ]]; then
  rm_path "$ROOT/release-artifacts"
else
  echo "    no release-artifacts/"
fi

if [[ -e "$RUST_DIR/Cargo.lock.bak" ]]; then
  rm_path "$RUST_DIR/Cargo.lock.bak"
fi

echo "==> clean ok"
