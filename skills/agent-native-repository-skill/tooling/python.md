# Python Architecture Enforcement

## Recommended tools

Choose the lightest option that fits the repository.

### Import Linter

Useful for explicit package contracts and forbidden imports.

Example conceptual contract:

```ini
[contract: training does not depend on deploy internals]
type = forbidden
source_modules = app.modules.training
forbidden_modules = app.modules.deploy.internal
```

### pytest architecture tests

For small repositories, a custom test that walks Python imports may be enough.

Keep the rule explicit and failure messages clear.

### pyright / mypy

Use type checking to reinforce public contracts and plugin protocols.

### Protocols / ABCs

Use `typing.Protocol` or ABCs only at genuine ports.

Do not wrap ordinary functions in protocols without a concrete reason.

## Suggested commands

```text
python -m pytest
python -m importlinter
pyright
```

Expose a canonical wrapper such as:

```text
make architecture-test
```

or a project-native task command.
