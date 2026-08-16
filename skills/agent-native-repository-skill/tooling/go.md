# Go Architecture Enforcement

Go already provides strong repository boundaries when package layout is used deliberately.

## Prefer language-native boundaries

Use:

- `internal/` to prevent external imports;
- small packages with clear ownership;
- interfaces at consumer-owned variation points;
- `go list -deps` or custom tests for dependency policies;
- `go vet` and staticcheck for correctness.

## Example

```text
internal/
  training/
  inference/
pkg/
  modelapi/   # only if truly public/stable
```

Do not put everything under `pkg/` just to make it reusable.

## Dependency checks

For repositories with strict module rules, add a small Go test or script that inspects package dependencies and fails on forbidden edges.

Keep the dependency policy as data when practical:

```text
training -> core, modelapi
inference -> core, modelapi
training -X-> inference/internal
```

## Interfaces

In Go, prefer small interfaces defined near the consumer.

Avoid large framework-style base interfaces.
