#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REQUIRED = {
    "SKILL.md",
    "README.md",
    "LICENSE",
    "SOURCE.md",
    "manifest.txt",
    "scripts/validate.py",
    "upstream/grill-me/SKILL.md",
    "upstream/grilling/SKILL.md",
}


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def main() -> None:
    actual = {
        p.relative_to(ROOT).as_posix()
        for p in ROOT.rglob("*")
        if p.is_file()
    }

    missing = sorted(REQUIRED - actual)
    if missing:
        fail(f"missing required files: {missing}")

    manifest = {
        line.strip()
        for line in (ROOT / "manifest.txt").read_text(encoding="utf-8").splitlines()
        if line.strip()
    }
    if manifest != actual:
        fail(
            "manifest mismatch: "
            f"missing={sorted(actual - manifest)}, "
            f"extra={sorted(manifest - actual)}"
        )

    skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    if not skill.startswith("---\n"):
        fail("SKILL.md is missing YAML frontmatter")
    for field in ("name: grill-me", "description:"):
        if field not in skill:
            fail(f"SKILL.md is missing {field}")

    for rel in sorted(actual):
        path = ROOT / rel
        if path.stat().st_size == 0:
            fail(f"empty file: {rel}")

    print(f"OK: validated {len(actual)} files")
    for rel in sorted(actual):
        digest = hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()
        print(f"{digest}  {rel}")


if __name__ == "__main__":
    main()
