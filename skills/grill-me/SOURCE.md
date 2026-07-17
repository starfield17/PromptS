# Source and Attribution

## Upstream Repository

- Repository: https://github.com/mattpocock/skills
- Original author: Matt Pocock
- License: MIT

## Files Combined

### Launcher

```text
skills/productivity/grill-me/SKILL.md
```

GitHub blob SHA at packaging time:

```text
9470cfcfe231a35e46494cddbacdd395991afb1e
```

### Implementation

```text
skills/productivity/grilling/SKILL.md
```

GitHub blob SHA at packaging time:

```text
52d8eb3cadd2dca62634d5dccfa73ea6b725b117
```

## Packaging Change

The upstream `grill-me` skill delegates to `/grilling`. This package inlines the behavior from `grilling` into a single standalone `grill-me/SKILL.md` so it can be copied manually into a Codex skills directory without installing a second skill.

The original upstream files are included unchanged under `upstream/`.
