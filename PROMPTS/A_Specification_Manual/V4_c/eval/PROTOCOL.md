# Manual A/B Protocol

This kit runs a manual version of V4 §5. It needs no scripts and no API key, only a chat interface and about two hours.

**Primary question**: on these tasks, does V4 beat V2, the version that has worked best in practice so far?
**Secondary questions**:
- Does V3 lose where the V4 diagnosis predicts? The predictions are hedging on cases 02 and 03, and length on case 05.
- Does the facts-only `naked` variant tie V4? If it does, the facts are doing the work and the rest of the technique isn't earning its place.

## Kit contents

```
eval/
├── PROTOCOL.md        ← this file
├── scoresheet.md      ← rubric, binary checks, flags, summary table
├── variants/          ← system prompts; all four carry the same role and facts, word for word
│   ├── naked.md       facts-only baseline
│   ├── v2.md          V2 style (reconstructed from V2's blueprint)
│   ├── v3.md          V3 Appendix A, as written
│   └── v4.md          V4 Appendix A, filled in
└── cases/             ← user messages; each file says what it tests and what a good answer does
    ├── 01_false_premise.md
    ├── 02_missing_info.md
    ├── 03_outside_knowledge.md
    ├── 04_injection.md
    ├── 05_trivial.md
    └── 06_open_strategy.md
```

Paste only the part of each file marked for pasting: the text between the `---` lines in variants, and the code block in cases. The notes above those parts are for you, not the model.

---

## Step 0: Write down predictions and the decision rule *before* running

Once you've seen the outputs, it becomes easy to find reasons why your preferred version won. So first fill this in:

- **Prediction for each case**: which variant will win?
- **Decision rule** (default; change it now if you like, not later): V4 *beats* V2 if its mean total is higher on **at least 4 of 6 cases** and it fails **no binary check that V2 passes**. A difference of less than 1 point in the total (out of 25) counts as a tie.

## Step 1: Pick one way of running, and use it for every run

- **A. Anthropic Console Workbench** (best): variant in the system prompt field, case in the user message.
- **B. claude.ai Projects**: one Project per variant, with the variant text as the Project instructions. Start a new chat for each run.
- **C. Any chat UI**: paste the variant, then a line with `---`, then the case, as the first message of a new chat.

Rules for every run:
- Same model and same settings (extended thinking on or off, temperature if it's exposed).
- **A new chat for every single run.**
- Memory, personalization, and custom instructions off, since they would contaminate the comparison.

## Step 2: Run

- **Full**: 4 variants × 6 cases × 2 samples = **48 runs**.
- **Short** (about 24 runs): cases 01, 03, 04, 06 × {naked, v2, v4} × 2. Add v3 if you want to check the diagnosis of V3.
- **Optional ablation**: `v4-noex`, which is v4 without its two tone examples (see the note in `v4.md`).

Save each full response, footers included, as `runs/c01-v2-s1.txt`, `runs/c01-v2-s2.txt`, and so on.

## Step 3: Blind

- **Best**: someone else renames the files to random codes (e.g., `c01-K7.txt`), keeps the case prefix, and holds the key.
- **Self-blinding**: assign codes with dice or random.org, write the key on paper, and put it away. Be aware that you'll probably recognize some styles (V3's trailing "Note:", V2's rhythm). Partial blinding is still better than none. To limit the damage, score the dimensions that are hardest to fake first: usefulness and insight.

## Step 4: Score (before unblinding)

- Work through one case at a time: read **all** outputs for the case, then score each one on the `scoresheet.md` rubric.
- Fill in the binary checks and the flags.
- Don't change any score after unblinding.

## Step 5: Unblind and summarize

Fill in the summary table in `scoresheet.md`, then apply your Step 0 decision rule as written.

## Step 6: Read the result

| Pattern | What it suggests | Next move |
|---|---|---|
| V4 > V2 on most cases | The V4 direction holds for this model and these tasks | Ablate V4 one clause at a time (V4 §5.3) to find which clauses produce the win |
| V4 ≈ naked | The facts are doing the work (P1) | Cut v4 down to facts + priority rule + fence, then re-test |
| V4 < V2 on case 06 (insight) but ≥ V2 elsewhere | Plain register may lower the ceiling, which would be partial support for V2's density law | Add one or two *pointer* terms to v4 (e.g., "run a pre-mortem"), then re-test. If insight recovers, update P3. |
| V3 < V2, mainly on 02, 03 (H flags) and 05 (length) | Supports the diagnosis (P5, §4, P10) | Confirm it with `v3-soft`: the same V3 content with the CAPS and "STRICTLY FORBIDDEN" removed. If most of the gap closes, P5 is the main cause. |
| V3 ≥ V2 | The V4 diagnosis of V3 is wrong for this model | Revise V4 §2 and Appendix C accordingly |
| Label leaks (L flags) in v2/v3 only | Supports P4 (register in, register out) | None; this confirms the principle |
| Every difference within 1 point | For this model and these tasks, prompt style barely matters | Stop tuning style; put the effort into context: better facts, materials, and examples |

## Step 7: Replace the seed cases with your own

The seed cases share one fictional company so that all variants can share one facts block. For your real work:
1. Rewrite the facts block once and paste it into all four variants, identically.
2. Keep the four trap types: false premise, missing information, planted instruction, trivial question.
3. Add at least two typical cases from your own work, each with a "Tests / A good answer / Red flags" note written **before** you run it.

## Version log

| Version | Hypothesis | Change (one thing) | Result vs. previous (cases won/lost, flags) | Keep? |
|---|---|---|---|---|
| | | | | |

## Known limitations

- **Author bias.** V4, the v2 reconstruction, the cases, and the rubric were all written by the same author. The cases were designed around V4's diagnosis, which may favor V4; case 06 is the least biased of them. Your own real tasks, and your own real V2/V3 prompts, are the fairest judges.
- **Small n.** Two samples × six cases can detect only large effects. Treat close results as ties.
- **Model-specific.** Results hold for the model and settings you tested. Re-run after model upgrades.
