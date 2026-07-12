# Iterative Patch Verification Skill

A reusable agent skill for improving AI-written software through bounded patch rounds, independent source review, and adversarial correctness testing.

## What It Does

This skill helps a strong Lead Agent supervise a less reliable Local Coding Agent.

The Lead Agent:

- extracts architecture invariants,
- groups defects into bounded patches,
- reviews completion reports,
- inspects the actual repository,
- adds adversarial tests,
- and decides when P0 correctness is closed.

The Local Coding Agent:

- implements each patch,
- adds regression coverage,
- runs validation,
- commits the result,
- and reports limitations.

## Installation

Copy the entire `iterative-patch-verification` directory into the skill directory used by your agent environment.

Generic layout:

```text
<agent-skill-directory>/
└── iterative-patch-verification/
    ├── SKILL.md
    ├── README.md
    ├── templates/
    ├── checklists/
    ├── references/
    ├── examples/
    └── scripts/
```

The required entry point is `SKILL.md`.

## Validation

Run:

```bash
python3 scripts/validate_skill.py
```

The validator checks:

- required package files,
- frontmatter metadata,
- manifest completeness,
- missing or unexpected files,
- and CJK characters in user-facing text.

## Typical Use

1. Give the Lead Agent the project archive, architecture manual, and defect list.
2. Ask it to establish a baseline and produce the first patch command.
3. Forward that command to the Local Coding Agent.
4. Return the completion report to the Lead Agent.
5. Upload the latest repository package.
6. Repeat source review and correctness patches until stop conditions are met.

## Version

`1.0.0`
