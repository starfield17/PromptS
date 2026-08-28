# Go

Go needs the least tooling of any language here, because two of the rules you'd
otherwise write tests for are enforced by the compiler.

## Level 1: `internal/`, which is free

Any package under a directory named `internal/` is importable only by code
rooted at that directory's parent. So this:

```text
modules/
  training/
    training.go          # public surface
    internal/
      cache/
      solver/
  inference/
    inference.go
    internal/
```

means `modules/inference` **cannot compile** if it imports
`modules/training/internal/cache`. No config, no lint step, no CI job, nothing
to misconfigure, and no way for an agent to work around it without moving files.

Put an `internal/` in every module and you have already bought most of what
architecture tests are usually for. Cycles are likewise a compile error, so the
"no circular dependencies" rule needs no enforcement at all.

Keep the public surface small and in one file at the module root. If a type has
to cross the boundary, define it there.

## Level 2: depguard, for what `internal/` can't say

`internal/` blocks reaching *past* a module. It does not block module A
depending on module B's public API when it shouldn't. For that, depguard via
golangci-lint:

```yaml
linters:
  enable:
    - depguard
linters-settings:
  depguard:
    rules:
      training:
        files:
          - "**/modules/training/**"
        deny:
          - pkg: "myapp/modules/inference"
            desc: "training must not depend on inference; extract to core instead"
      domain:
        files:
          - "**/modules/*/domain/**"
        deny:
          - pkg: "database/sql"
            desc: "domain stays free of infrastructure"
          - pkg: "net/http"
            desc: "domain stays free of infrastructure"
```

Config layout moved between golangci-lint v1 and v2 (v2 nests settings under
`linters:`). Run `golangci-lint config verify` after writing this, or the whole
block can be silently ignored.

## Wire it up

```makefile
check:
	go build ./...
	go vet ./...
	go test ./...
	golangci-lint run
```

`go build ./...` is doing real boundary work here, not just compiling.

## Proving it works

```bash
# the internal/ rule
echo 'import _ "myapp/modules/training/internal/cache"' >> modules/inference/inference.go
go build ./...        # must fail: use of internal package not allowed
git checkout modules/inference/inference.go

# the depguard rule
echo 'import _ "myapp/modules/inference"' >> modules/training/training.go
golangci-lint run     # must fail with your desc string
git checkout modules/training/training.go
```

Test both. The first will work; the second is the one that gets silently
misconfigured.
