# TypeScript

Two mechanisms, and you want both. `exports` is level 1 — the resolver refuses
the import, no config to misconfigure. dependency-cruiser is level 2 and covers
what `exports` can't (cycles, direction, same-package rules).

## Level 1: package `exports`

In a monorepo, make each module a package and let Node's resolver enforce the
surface:

```json
{
  "name": "@app/training",
  "exports": {
    ".": "./src/index.ts"
  }
}
```

With no subpath entries, `@app/training/internal/cache` does not resolve. This
is the strongest boundary TypeScript offers and it costs one JSON key.

## Level 2: dependency-cruiser

```bash
npm i -D dependency-cruiser
```

`.dependency-cruiser.js`:

```js
module.exports = {
  forbidden: [
    {
      name: 'no-circular',
      severity: 'error',
      comment: 'Cycles make every change global.',
      from: {},
      to: { circular: true },
    },
    {
      name: 'no-cross-module-internals',
      severity: 'error',
      comment: 'Import a module through its index, never past it.',
      from: { path: '^src/modules/([^/]+)/' },
      to: { path: '^src/modules/(?!$1)[^/]+/(?!index\\.ts)' },
    },
    {
      name: 'domain-is-pure',
      severity: 'error',
      comment: 'Domain code must stay testable without infrastructure.',
      from: { path: '^src/modules/[^/]+/domain/' },
      to: { path: '^src/adapters/|^node_modules/(axios|pg|aws-sdk)' },
    },
    {
      name: 'no-orphans',
      severity: 'warn',
      comment: 'Dead file, or a missing import.',
      from: { orphan: true, pathNot: '\\.d\\.ts$|^src/index\\.ts$' },
      to: {},
    },
  ],
  options: {
    doNotFollow: { path: 'node_modules' },
    tsConfig: { fileName: 'tsconfig.json' },
    tsPreCompilationDeps: true,
  },
};
```

The `$1` in `no-cross-module-internals` back-references the capture group from
`from.path`, so one rule covers every module and keeps covering new ones. Rules
written per-module have to be edited each time someone adds a module, and they
won't be.

`tsPreCompilationDeps: true` matters — without it, type-only imports are
invisible, and a type-only import across a boundary is still a boundary
violation.

## Wire it up

```json
{
  "scripts": {
    "check": "npm run test && npm run types && npm run boundaries",
    "types": "tsc --noEmit",
    "boundaries": "depcruise --config .dependency-cruiser.js src"
  }
}
```

## Proving it works

```bash
echo "import { cache } from '../inference/internal/cache';" >> src/modules/training/train.ts
npm run boundaries    # must fail, naming no-cross-module-internals
git checkout src/modules/training/train.ts
```

A silent pass almost always means `src` wasn't the right root, or the paths in
the rules don't match the real layout. `depcruise --output-type dot src` and
looking at the graph finds it fast.

## Not worth it

`eslint-plugin-boundaries` does a subset of this and needs its own layer
taxonomy declared. If dependency-cruiser is already running, adding it buys
little.
