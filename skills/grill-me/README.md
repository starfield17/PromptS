# Grill Me — Standalone Codex Skill

This package combines Matt Pocock's upstream `grill-me` launcher and the delegated `grilling` implementation into one self-contained skill.

The installed skill has no dependency on a separate `/grilling` skill.

## Manual Installation

### Recommended Codex location

Codex currently recommends the shared Agent Skills directory:

```text
~/.agents/skills/grill-me/
```

Copy the entire `grill-me` directory, not only `SKILL.md`.

Linux or macOS:

```bash
mkdir -p ~/.agents/skills
cp -R grill-me ~/.agents/skills/grill-me
```

Windows PowerShell:

```powershell
$skills = Join-Path $HOME ".agents\skills"
New-Item -ItemType Directory -Force -Path $skills | Out-Null
Copy-Item -Recurse -Force ".\grill-me" (Join-Path $skills "grill-me")
```

### Legacy Codex location

Some Codex versions also discover:

```text
~/.codex/skills/grill-me/
```

The current shared convention is `~/.agents/skills`.

## Usage

Ask Codex to:

```text
Grill me about this plan.
```

The skill will:

- ask one decision question at a time,
- provide a recommended answer for each question,
- inspect available facts instead of asking you for them,
- walk the decision tree until shared understanding is reached,
- and avoid implementing the plan until you confirm alignment.

## Package Contents

```text
grill-me/
├── SKILL.md
├── README.md
├── LICENSE
├── SOURCE.md
├── manifest.txt
├── scripts/
│   └── validate.py
└── upstream/
    ├── grill-me/
    │   └── SKILL.md
    └── grilling/
        └── SKILL.md
```

The files under `upstream/` are preserved copies of the two source skill files. `SKILL.md` is the standalone combined version intended for installation.
