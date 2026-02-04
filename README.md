# PromptS

A comprehensive collection of high-quality system prompts for AI assistants (LLMs), featuring specialized prompts for coding, translation, tutoring, legal work, chemistry, philosophy, and more.

## Overview

PromptS is a curated repository of carefully designed system prompts organized by domain. Each prompt is crafted using a constitutional framework that defines the AI's "existence" - what it can reason about, how it should think, what constraints it must follow, and what goals it must pursue.

### Design Philosophy

All prompts in this repository follow the **F-O-P-T Framework** (Field-Ontic-Phenomenon-Teleology):

- **Field**: The jurisdiction/context in which the AI operates - rules of interpretation and priority
- **Ontic**: What exists in this world - entities, terminology, evidence boundaries
- **Phenomenon**: How the AI perceives, reasons, and self-examines - cognitive processes
- **Teleology**: The ultimate purpose and ethical boundaries - success criteria and hard prohibitions

This framework, detailed in `PROMPTS/A_Specification_Manual/Prompt_Design_Philosophy_V3.0.md`, enables prompts that produce consistent, high-quality outputs while avoiding hallucinations and maintaining clear reasoning chains.

## Usage

### Basic Usage

Copy any `.md` file content and use it as the system prompt for your LLM. Each prompt is self-contained and includes all necessary instructions.

### Recommended Workflow

1. **Browse** the `PROMPTS/` directory to find a prompt matching your needs
2. **Copy** the full content of the selected `.md` file
3. **Configure** any placeholder variables if present
4. **Use** as your system prompt

### Creating Custom Prompts

For creating new prompts, start with the specification manual:

```bash
# Read the design philosophy
cat PROMPTS/A_Specification_Manual/Prompt_Design_Philosophy_V3.0.md

# Use the generator
cat PROMPTS/System_Prompt_generator/System_Prompt_generator_v3.md
```

## Key Features

- **Constitutional Design**: Every prompt defines clear boundaries, truth regimes, and adjudication logic
- **Hallucination Prevention**: Built-in epistemic boundaries and ontological gap detection
- **Self-Correction**: Prompts include internal critique mechanisms before output
- **Conflict Resolution**: Clear hierarchy when multiple goals or constraints conflict
- **Multi-Language Support**: Many prompts available in both English and Chinese

## Version History

| Version | Description |
|---------|-------------|
| V3.0 | Complete constitutional framework with F-O-P-T matrix |
| V2.0 | Enhanced methodology with phase transitions |
| V1.0 | Foundational prompt engineering principles |

## Contributing

This repository is a personal collection of curated prompts. If you have suggestions or improvements, feel free to open an issue or submit a pull request.

## License

This repository is for personal and educational use. Each prompt is provided as-is for use with AI assistants.

## Acknowledgments

The prompts in this repository draw from:
- Constitutional AI principles
- Linguistic philosophy (Wittgenstein, Austin, Searle)
- Systems thinking and cognitive architecture
- Best practices from the AI alignment and prompt engineering communities
