#!/usr/bin/env bash
# One-shot build of subagent-broker and install the host binary into bin/.
# The scripts/subagent-broker launcher selects the packaged architecture.
set -euo pipefail

if [ -z "${BASH_VERSION:-}" ]; then
  echo "error: this script requires bash (run: bash $0 ...)" >&2
  exit 1
fi

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
RUST_DIR="$ROOT/rust"
case "$(uname -m)" in
  x86_64|amd64) TARGET_DIR="$ROOT/bin/linux-x86_64" ;;
  aarch64|arm64) TARGET_DIR="$ROOT/bin/linux-aarch64" ;;
  *)
    echo "error: unsupported host architecture: $(uname -m)" >&2
    exit 1
    ;;
esac
OUT_BIN="$TARGET_DIR/subagent-broker"
LAUNCHER="$ROOT/scripts/subagent-broker"

PROFILE="${PROFILE:-release}"
NO_INSTALL="${NO_INSTALL:-0}"
JOBS=""

usage() {
  cat <<'EOF'
Usage: build.sh [options]

One-shot Cargo build of subagent-broker; installs to the host bin/ directory.

Options:
  --release          Release profile (default)
  --debug            Debug profile
  --no-install       Build only; do not copy into bin/
  -j, --jobs N       Pass -j N to cargo
  -h, --help         Show this help

Environment:
  PROFILE=release|debug   Same as --release / --debug
  NO_INSTALL=1            Same as --no-install
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --release)
      PROFILE=release
      shift
      ;;
    --debug)
      PROFILE=debug
      shift
      ;;
    --no-install)
      NO_INSTALL=1
      shift
      ;;
    -j|--jobs)
      if [[ $# -lt 2 ]]; then
        echo "error: $1 requires a value" >&2
        exit 1
      fi
      JOBS="$2"
      shift 2
      ;;
    -j*)
      JOBS="${1#-j}"
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

case "$PROFILE" in
  release|debug) ;;
  *)
    echo "error: PROFILE must be release or debug (got: $PROFILE)" >&2
    exit 1
    ;;
esac

if [[ ! -f "$RUST_DIR/Cargo.toml" ]]; then
  echo "error: missing $RUST_DIR/Cargo.toml" >&2
  exit 1
fi

if ! command -v cargo >/dev/null 2>&1; then
  echo "error: cargo not found on PATH" >&2
  exit 1
fi

CARGO_ARGS=(build --locked)
if [[ "$PROFILE" == "release" ]]; then
  CARGO_ARGS+=(--release)
fi
if [[ -n "$JOBS" ]]; then
  CARGO_ARGS+=(-j "$JOBS")
fi

echo "==> cargo ${CARGO_ARGS[*]} (cwd=$RUST_DIR)"
(
  cd "$RUST_DIR"
  cargo "${CARGO_ARGS[@]}"
)

if [[ "$PROFILE" == "release" ]]; then
  SRC_BIN="$RUST_DIR/target/release/subagent-broker"
else
  SRC_BIN="$RUST_DIR/target/debug/subagent-broker"
fi

if [[ ! -f "$SRC_BIN" ]]; then
  echo "error: expected binary not found: $SRC_BIN" >&2
  exit 1
fi
if [[ ! -x "$SRC_BIN" ]]; then
  chmod +x "$SRC_BIN" || {
    echo "error: binary is not executable: $SRC_BIN" >&2
    exit 1
  }
fi

if [[ "$NO_INSTALL" == "1" ]]; then
  echo "==> built (no install) $SRC_BIN"
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$SRC_BIN"
  elif command -v shasum >/dev/null 2>&1; then
    shasum -a 256 "$SRC_BIN"
  fi
  echo "==> build ok"
  exit 0
fi

# Atomic install: avoid ETXTBSY when replacing a running binary (cp onto open inode).
mkdir -p "$TARGET_DIR"
cleanup_tmp() {
  rm -f "$TMP"
}
trap cleanup_tmp EXIT

TMP="$TARGET_DIR/.subagent-broker.tmp.$$"
cp -f "$SRC_BIN" "$TMP"
chmod +x "$TMP"
mv -f "$TMP" "$OUT_BIN"
trap - EXIT

if [[ ! -x "$OUT_BIN" ]]; then
  echo "error: installed binary missing or not executable: $OUT_BIN" >&2
  exit 1
fi
if [[ ! -x "$LAUNCHER" ]]; then
  echo "error: launcher missing or not executable: $LAUNCHER" >&2
  exit 1
fi

# Quick start check (catches broken dynamic link / wrong arch early).
if ! "$LAUNCHER" --help >/dev/null 2>&1; then
  echo "error: packaged launcher failed to run: $LAUNCHER --help" >&2
  exit 1
fi

echo "==> installed $OUT_BIN"
if size=$(stat -c%s "$OUT_BIN" 2>/dev/null); then
  echo "    size=${size} bytes"
elif size=$(wc -c <"$OUT_BIN" 2>/dev/null); then
  echo "    size=${size} bytes"
fi
if command -v sha256sum >/dev/null 2>&1; then
  sha256sum "$OUT_BIN"
elif command -v shasum >/dev/null 2>&1; then
  shasum -a 256 "$OUT_BIN"
fi
echo "==> build ok"
