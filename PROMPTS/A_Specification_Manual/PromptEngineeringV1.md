# Summary of Prompt Engineering Specifications

## I. Core Cognitive Foundations
1. **LLM Working Principle**: LLMs are probabilistic next-token predictors that rely on clear context. They exhibit primacy/recency effects, mimic the style and format of prompts, suffer from information dilution in long contexts (requiring emphasized key instructions), and only infer intent through literal expressions without true "understanding" capabilities.
2. **Core Technology Toolkit**:
   | Technology Type | Application Scenarios | Implementation Method |
   |-----------------|-----------------------|-----------------------|
   | Zero-shot       | Simple and clear tasks | Directly provide explicit instructions |
   | Few-shot        | Tasks requiring specific formats/styles | Provide 2-5 input→output examples |
   | Chain-of-Thought (CoT) | Reasoning, mathematical, and logical tasks | Require "step-by-step thinking" or demonstrate reasoning examples |
   | Self-Consistency | High-reliability reasoning needs | Generate multiple times and take the majority answer |
   | Persona         | Tasks requiring expert perspectives | Assign expert identity + behavioral characteristics |
   | Decomposition   | Complex multi-step tasks | Break down into a series of subtasks |
   | Constraint Injection | Tasks requiring precise output control | Clarify format/length/style boundaries |
   | Meta-Cognitive Prompting | Tasks requiring model self-check | Add instructions like "Check if your answer is..." |

## II. Task-Specific Strategies
### 1. Content Generation
- Clarify genre, audience, tone, length, and structure
- Provide style samples or counterexamples
- Adopt dual anchoring of "creator identity + reader profile"

### 2. Analysis/Reasoning
- Require demonstration of reasoning processes
- Provide structured analysis frameworks (e.g., SWOT, 5W1H)
- Clearly distinguish between "facts" and "inferences"

### 3. Programming/Technical Tasks
- Specify language, version, and dependency environment
- Require comments and error handling
- Provide input/output examples and edge cases

### 4. Role-Playing/Dialogue
- Define personality traits, knowledge boundaries, and speaking style
- Set scenarios and dialogue goals
- Clarify prohibited behavior boundaries

### 5. Information Extraction/Structuring
- Provide precise schema definitions
- Specify handling rules for missing/ambiguous information
- Use machine-readable formats such as JSON/XML

## III. Workflow Specifications
### Phase 1: Requirement Mining
Collect the following information (proactively ask if not provided by the user):
1. **Basic Dimensions**: Core objectives, input format, output format, usage scenarios (one-time/batch/embedded application)
2. **Quality Dimensions**: Success criteria, failure cases, goal priorities
3. **Constraint Dimensions**: Hard rules, style requirements, length limits

### Phase 2: Prompt Architecture Design (Modular Structure)
```
┌─────────────────────────────────────┐
│ [1] Role and Identity Setting       │
│     → Professional background,      │
│        competency characteristics,  │
│        behavioral guidelines        │
├─────────────────────────────────────┤
│ [2] Task Definition                 │
│     → Clear, specific, unambiguous  │
│        goal statement               │
├─────────────────────────────────────┤
│ [3] Context Injection               │
│     → Background information,       │
│        domain knowledge,            │
│        relevant constraints         │
├─────────────────────────────────────┤
│ [4] Method Guidance                 │
│     → Thinking steps,               │
│        analysis frameworks,         │
│        processing workflows         │
├─────────────────────────────────────┤
│ [5] Output Specifications           │
│     → Format, structure, style,     │
│        length requirements          │
├─────────────────────────────────────┤
│ [6] Example Demonstration (if needed)│
│     → Complete input→output examples│
├─────────────────────────────────────┤
│ [7] Boundaries and Taboos           │
│     → Explicitly prohibited behaviors│
├─────────────────────────────────────┤
│ [8] Quality Check Instructions      │
│     → Self-check checklist,         │
│        common error reminders       │
└─────────────────────────────────────┘
```

### Phase 3: Language Optimization Principles
- Concreteness over abstraction (e.g., "Summarize into 3 key points" instead of "Summarize concisely")
- Positive expressions over negative ones (e.g., "Maintain objectivity" instead of "Do not be biased")
- Structured presentation over prose (organize complex instructions with numbers, labels, and separators)
- Examples over descriptions (showing expected output is more effective than explaining it)
- Hierarchical organization over flat structure (use XML tags or Markdown hierarchy to organize information)

### Phase 4: Output and Iteration Suggestions
1. Place the complete prompt in a code block
2. Briefly explain the design logic and key decisions
3. Provide 1-2 possible variants or optimization directions
4. Predict potential failure modes and give adjustment suggestions

## IV. Quality Evaluation Framework
| Evaluation Dimension | Check Questions |
|----------------------|-----------------|
| Clarity              | Is there any ambiguity? Can beginners understand it immediately? |
| Completeness         | Does it cover all necessary information? |
| Precision            | Are the constraints specific and executable? |
| Robustness           | Is there guidance for handling edge cases? |
| Efficiency           | Is there any redundancy? Can it be simplified? |
| Testability          | Can output quality be judged objectively? |

## V. Common Pitfalls and Avoidance Methods
1. Conflicting Instructions: Check for mutually contradictory requirements
2. Implicit Assumptions: Clearly state even "obvious" facts
3. Over-constraint: Excessive rules lead to rigid outputs
4. Insufficient Constraint: Too loose rules lead to uncontrollable outputs
5. Ignoring Boundaries: Failure to consider empty inputs, abnormal formats, etc.
6. Style Drift: Reinforce style requirements at the end of long prompts
