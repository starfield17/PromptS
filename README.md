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

## Directory Structure

```
PromptS/
├── PROMPTS/
│   ├── A_Specification_Manual/     # Prompt engineering philosophy & guides
│   │   ├── Prompt_Design_Philosophy_V1.0.md
│   │   ├── Prompt_Design_Philosophy_V2.0.md
│   │   ├── Prompt_Design_Philosophy_V3.0.md
│   │   └── PromptEngineeringV1-V3.md
│   │
│   ├── Chem/                       # Chemistry domain prompts
│   │   └── Chemistry_Expert_Assistant.md
│   │
│   ├── Code/                       # Programming & architecture prompts
│   │   ├── The_Pragmatic_Kernel_Architect.md
│   │   └── The_Pragmatic_Kernel_Architect_aggressive.md
│   │
│   ├── CN_-_EN_translator/         # Chinese to English translation
│   │   ├── CN_-_EN_translator_A.md
│   │   ├── CN_-_EN_translator_A_0.md
│   │   └── CN_-_EN_translator_A_Lite.md
│   │
│   ├── Legal/                      # Legal domain prompts
│   │   ├── Legal.md
│   │   ├── Legal_CN.md
│   │   ├── Legal_professional.md
│   │   └── Legal_professional_CN.md
│   │
│   ├── Lilika/                     # Specialized role prompts
│   │   ├── Lilika.md
│   │   └── Lilika_V2.md
│   │
│   ├── MPhi/                       # Philosophy prompts
│   │   ├── MPhiV1.md
│   │   ├── MPhiV2.md
│   │   └── MPhiV3.md
│   │
│   ├── Multiple_translator/        # Multi-language translation
│   │   ├── multiple_translatorV1_ForceKnowledgeBase.md
│   │   └── multiple_translatorV1_ForceKnowledgeBase_0.md
│   │
│   ├── Phi/                        # Philosophy prompts (alternative versions)
│   │   ├── PhiV1.md
│   │   ├── PhiV2.md
│   │   ├── PhiV3.md
│   │   └── PhiV4.md
│   │
│   ├── Pure_Bilingual_Translator/  # Bilingual translation
│   │   └── Pure_Bilingual_Translator.md
│   │
│   ├── System_Prompt_generator/    # Tools for generating prompts
│   │   ├── System_Prompt_generator.md
│   │   ├── System_Prompt_generator_v2.md
│   │   └── System_Prompt_generator_v3.md
│   │
│   ├── Tutor/                      # Tutoring & education prompts
│   │   ├── TutorV1.md
│   │   ├── TutorV1_CN.md
│   │   ├── TutorV2.md
│   │   └── TutorV2_CN.md
│   │
│   ├── prompt_v1.md                # Legacy/general prompts
│   ├── prompt_v2.md
│   ├── prompt_v3.md
│   └── prompt_v3Q.md
│
└── README.md                       # This file
```

## Prompts by Category

### Code & Development

| Prompt | Description |
|--------|-------------|
| `The_Pragmatic_Kernel_Architect` | A performance-obsessed architect focused on hardware reality, data structure primacy, and eliminating unnecessary complexity |
| `The_Pragmatic_Kernel_Architect_aggressive` | Aggressive variant with stronger emphasis on truth-telling and zero tolerance for over-engineering |

### Translation

| Prompt | Description |
|--------|-------------|
| `CN_-_EN_translator_A` | Chinese to English translator with cultural nuance awareness |
| `CN_-_EN_translator_A_Lite` | Lightweight version for faster translation tasks |
| `CN_-_EN_translator_A_0` | Zero-shot variant for flexible translation |
| `multiple_translatorV1_ForceKnowledgeBase` | Multi-language translator with knowledge base enforcement |
| `Pure_Bilingual_Translator` | Clean bilingual translation without additional commentary |

### Education

| Prompt | Description |
|--------|-------------|
| `TutorV1` | General-purpose tutor with adaptive teaching strategies |
| `TutorV2` | Enhanced tutor with improved Socratic questioning |
| `TutorV1_CN` | Chinese version of V1 tutor |
| `TutorV2_CN` | Chinese version of V2 tutor |

### Legal

| Prompt | Description |
|--------|-------------|
| `Legal` | General legal assistant prompt |
| `Legal_professional` | Professional-grade legal analysis with higher rigor |
| `Legal_CN` | Chinese legal assistant |
| `Legal_professional_CN` | Professional Chinese legal assistant |

### Philosophy & Reasoning

| Prompt | Description |
|--------|-------------|
| `PhiV1-V4` | Philosophical reasoning prompts with varying depth and methodology |
| `MPhiV1-V3` | Alternative philosophy prompts emphasizing different aspects of thought |

### Specialized Domains

| Prompt | Description |
|--------|-------------|
| `Chemistry_Expert_Assistant` | Chemistry domain expert with scientific rigor |
| `Lilika` / `Lilika_V2` | Specialized role prompts for specific use cases |

### Prompt Engineering Tools

| Prompt | Description |
|--------|-------------|
| `System_Prompt_generator` | Generate new system prompts with structured approach |
| `System_Prompt_generator_v2` | Enhanced generator with more flexibility |
| `System_Prompt_generator_v3` | Latest version with comprehensive feature set |

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
