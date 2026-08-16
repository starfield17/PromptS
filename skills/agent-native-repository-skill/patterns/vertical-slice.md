# Vertical Slice

## Intent

Organize code around capabilities or use cases so a change remains local.

## Prefer

```text
orders/
  create/
  cancel/
  refund/
```

or

```text
training/
  prepare_dataset/
  run_training/
  evaluate/
```

when these slices have meaningful independent behavior.

## Avoid blind slicing

Do not create one directory per trivial function or endpoint.

A slice is useful when it groups behavior, rules, tests, and dependencies that change together.

## Local layers are allowed

Within a substantial slice or module, layering may improve clarity:

```text
training/
  domain/
  application/
  adapters/
```

The rule is not "never layer". The rule is "do not force every feature through repository-wide horizontal layers."

## Success criterion

An agent implementing a feature should usually be able to read:

- local `AGENTS.md`;
- the slice implementation;
- its contract;
- its tests;

without loading most of the repository.
