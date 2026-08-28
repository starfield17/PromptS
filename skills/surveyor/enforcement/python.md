# Python

Python has no language-level module privacy, so enforcement is level 2: a lint
step. Use [Import Linter](https://import-linter.readthedocs.io).

```bash
pip install import-linter
```

Config lives in `.importlinter`, `setup.cfg`, or `pyproject.toml` (under
`[tool.importlinter]`). The command is `lint-imports`.

## A complete `.importlinter`

```ini
[importlinter]
root_package = myapp

# Modules cannot import each other at all. The strongest and cheapest contract.
# Use this first; fall back to `forbidden` only where a dependency is real.
[importlinter:contract:independent-modules]
name = Capability modules are independent
type = independence
modules =
    myapp.modules.training
    myapp.modules.inference
    myapp.modules.datasets

# Where a dependency is legitimate, allow the module but forbid its internals.
[importlinter:contract:no-internals]
name = Nothing reaches into another module's internals
type = forbidden
source_modules =
    myapp.modules
forbidden_modules =
    myapp.modules.training.internal
    myapp.modules.inference.internal
allow_indirect_imports = False

# Direction, inside a module that has grown layers.
[importlinter:contract:training-layers]
name = training: api -> domain, never the reverse
type = layers
layers =
    myapp.modules.training.api
    myapp.modules.training.domain

# Keep infrastructure out of the domain. Third-party names are allowed here.
[importlinter:contract:pure-domain]
name = Domain does not touch infrastructure
type = forbidden
source_modules =
    myapp.modules.training.domain
forbidden_modules =
    myapp.adapters
    requests
    sqlalchemy
    boto3
```

Contract types: `independence`, `forbidden`, `layers`, `modules`.

`allow_indirect_imports = False` is the setting people miss. Without it, a
module can launder a forbidden dependency through a third module and the
contract still passes.

## Wire it up

```makefile
check: test types boundaries

test:
	python -m pytest

types:
	pyright

boundaries:
	lint-imports
```

## Proving it works

```bash
echo "from myapp.modules.inference.internal import cache" >> src/myapp/modules/training/api/train.py
lint-imports        # must exit non-zero and name the contract
git checkout src/myapp/modules/training/api/train.py
```

If it passed, `root_package` is wrong, the module paths don't match the real
package layout, or the import is unreachable from the root package.

## Naming internals

Import Linter needs a path to forbid, so give it one. Either an `internal/`
subpackage per module, or a leading-underscore package (`_impl`). Pick one
convention repository-wide and state it in root `AGENTS.md` — a mix means half
the internals are unprotected and nobody notices.

## Also worth having

- **pyright or mypy in strict mode on the public surface.** Types are the spec
  for the boundary; a `dict[str, Any]` crossing a module edge is an unenforced
  contract.
- **`__all__` in each module's public file.** Cheap, and makes the surface
  greppable.
