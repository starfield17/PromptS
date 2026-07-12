#!/usr/bin/env python3
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = {
    "SKILL.md",
    "README.md",
    "INSTALL.md",
    "VERSION",
    "manifest.txt",
    "templates/patch-command.md",
    "templates/completion-report.md",
    "templates/source-review.md",
    "templates/final-acceptance.md",
    "checklists/baseline.md",
    "checklists/persistence.md",
    "checklists/worker-lifecycle.md",
    "checklists/messaging.md",
    "checklists/barrier.md",
    "checklists/delivery-cleanliness.md",
    "references/adversarial-test-patterns.md",
    "references/p0-p1-classification.md",
    "references/stop-conditions.md",
    "examples/phase-closure-workflow.md",
    "scripts/validate_skill.py",
}

CJK = re.compile(
    "["
    "\u3400-\u4dbf"
    "\u4e00-\u9fff"
    "\uf900-\ufaff"
    "]"
)


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def relative_files() -> set[str]:
    return {
        p.relative_to(ROOT).as_posix()
        for p in ROOT.rglob("*")
        if p.is_file()
    }


def validate_frontmatter() -> None:
    text = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        fail("SKILL.md is missing YAML frontmatter")
    end = text.find("\n---\n", 4)
    if end < 0:
        fail("SKILL.md frontmatter is not closed")
    frontmatter = text[4:end]
    for field in ("name:", "description:", "version:"):
        if field not in frontmatter:
            fail(f"SKILL.md frontmatter is missing {field}")


def validate_manifest(actual: set[str]) -> None:
    manifest_path = ROOT / "manifest.txt"
    listed = {
        line.strip()
        for line in manifest_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    }
    if listed != actual:
        missing = sorted(actual - listed)
        extra = sorted(listed - actual)
        fail(f"manifest mismatch; missing={missing}, extra={extra}")


def validate_english_only(actual: set[str]) -> None:
    for rel in sorted(actual):
        path = ROOT / rel
        if path.suffix not in {".md", ".txt", ".py", ""}:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        match = CJK.search(text)
        if match:
            fail(f"CJK character found in {rel} at index {match.start()}")


def validate_nonempty(actual: set[str]) -> None:
    for rel in sorted(actual):
        path = ROOT / rel
        if path.stat().st_size == 0:
            fail(f"empty file: {rel}")


def main() -> None:
    actual = relative_files()
    missing_required = sorted(REQUIRED - actual)
    if missing_required:
        fail(f"missing required files: {missing_required}")
    validate_frontmatter()
    validate_manifest(actual)
    validate_english_only(actual)
    validate_nonempty(actual)
    print(f"OK: validated {len(actual)} files in {ROOT.name}")


if __name__ == "__main__":
    main()
