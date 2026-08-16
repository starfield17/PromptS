# Ports and Adapters

## Use ports for real boundaries

Good port candidates:

- inference engine;
- model backend;
- object storage;
- external API;
- database;
- queue/transport;
- hardware device;
- cloud provider.

## Do not use ports for symmetry

Do not automatically wrap every standard library call or pure function in an interface.

Before creating a port, identify the variation or isolation requirement in one sentence.

If that sentence is vague, keep the code concrete.

## Plugin shape

A plugin system should normally contain:

```text
contract
registry/discovery mechanism
implementation packages
contract tests
```

Avoid central `if backend == ...` switches spread throughout the codebase.

Prefer registration/discovery localized to the extension boundary.

## Contract stability

Keep plugin contracts narrow and semantic.

Bad:

```text
BasePlugin with 35 optional methods
```

Better:

```text
TrainingBackend.train(request) -> result
ModelConverter.convert(request) -> artifact
InferenceBackend.predict(batch) -> predictions
```

Split contracts when implementations do not support the same lifecycle.
