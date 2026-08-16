# Agent Native Repository Skill

A thin repository-architecture skill for coding agents.

It intentionally avoids orchestration. Its job is to provide repository-specific architecture policy, local context conventions, scaffolding guidance, and executable guardrails.

## Intended use

Use this skill when:

- starting a new agent-maintained repository;
- refactoring a repository that has become difficult for coding agents to navigate;
- introducing module boundaries or plugin contracts;
- adding architecture tests;
- designing `AGENTS.md` hierarchy;
- reviewing whether an abstraction improves or harms context locality.

## Not intended for

This skill does not prescribe:

- mandatory planning workflows;
- subagent orchestration;
- brainstorming rituals;
- fixed review pipelines;
- generic chain-of-thought procedures.

## Core formula

```text
Model decides how to work.
Repository defines what is allowed.
Tests enforce the boundary.
Skill supplies missing knowledge.
```

## Default architectural bias

```text
Capability-oriented modules
+ Vertical slices
+ Ports & Adapters at real variation points
+ DDD only where domain complexity justifies it
+ KISS
+ Architecture tests
+ Hierarchical AGENTS.md
```

Architecture is proportional to actual complexity. A small CLI should stay a small CLI.
