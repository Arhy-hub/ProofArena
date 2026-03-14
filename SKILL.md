---
name: proof-committee
description: >
  Multi-agent mathematical proof checker. Use this skill whenever a user submits a
  conjecture + proof and wants it checked, verified, challenged, or evaluated for gaps.
  Triggers on: "check my proof", "is this proof valid", "verify this argument",
  "find a counterexample", "does this proof work", or any submission of mathematical
  reasoning that needs validation. Handles algebra, number theory, divisibility,
  parity, and basic combinatorics. Orchestrates three agents — Prover, Skeptic, Judge
  — and returns a structured verdict with a timeline of agent interactions.
compatibility:
  tools: [bash, python]
  packages: [anthropic, sympy, numpy]
---

# Proof Committee Skill

## What this skill does

Runs a three-agent pipeline to evaluate a mathematical proof:

1. **Prover** — parses the proof into structured, numbered steps
2. **Skeptic** — tests each step for counterexamples (numeric + symbolic)
3. **Judge** — synthesises a final verdict and confidence score

Read `CLAUDE.md` for full project layout and design decisions before proceeding.

---

## Triggering this skill

When the user submits a conjecture + proof (in any format — plain English, LaTeX,
pseudocode, or a mix), activate this skill. You do not need explicit "check my proof"
language — any mathematical argument presented for evaluation qualifies.

**Extract from the user's message:**
- `conjecture`: the statement being proved (may be implicit in the proof)
- `proof`: the argument or derivation

If either is missing, ask once: "Could you share the conjecture you're proving, or is it stated within the proof?"

---

## Orchestration Steps

### Step 1 — Run the Prover
Run `workers/prover.py`. Send the conjecture + proof as JSON on stdin.
Expected output: `ProverOutput` JSON (see `references/verdict_schema.md`).

If the Prover cannot parse the proof at all, return immediately:
```
Verdict: uncertain
Explanation: "The proof could not be parsed into discrete steps. Please rewrite with explicit step-by-step reasoning."
```

### Step 2 — Run the Skeptic
Run `workers/skeptic.py`. Send the `ProverOutput` as JSON on stdin.
The Skeptic has access to `workers/skeptic_tools.py` — invoke it for numeric/symbolic checks.
Expected output: `SkepticReport` JSON.

### Step 3 — Run the Judge
Run `workers/judge.py`. Send both `ProverOutput` + `SkepticReport` as JSON on stdin.
Expected output: `JudgeVerdict` JSON (final result).

### Step 4 — Format and return
Assemble the `CommitteeResult` (see `CLAUDE.md` §Output Format).
Present to the user as:
- A clear verdict line (bold)
- The Judge's explanation (prose)
- The agent timeline (labelled, colour-coded if in UI context)
- Any counterexample found (formatted clearly)

---

## Output presentation (text mode)

```
╔══════════════════════════════════════════╗
║  PROOF COMMITTEE VERDICT                 ║
╠══════════════════════════════════════════╣
║  Result:     Proof likely valid          ║
║  Confidence: 0.91                        ║
╚══════════════════════════════════════════╝

TIMELINE
────────
[PROVER]   Parsed 3 steps. Step 1: ASSUMPTION. Step 2: DEDUCTION. Step 3: QED.
[SKEPTIC]  Tested n ∈ {-5…5}. All steps passed. No counterexample found.
[JUDGE]    Both agents agree. Argument is structurally sound. No gaps detected.
```

---

## Confidence thresholds

| Score | Label | Meaning |
|---|---|---|
| 0.85 – 1.0 | Proof likely valid | No issues found; high confidence |
| 0.60 – 0.84 | Proof plausible | Minor gaps or unverifiable steps |
| 0.30 – 0.59 | Proof incomplete | Missing steps or weak deductions |
| 0.00 – 0.29 | Proof invalid | Counterexample found or critical flaw |

---

## Reference files

Load these as needed (do not preload all — load on demand):

| File | When to load |
|---|---|
| `references/proof_formats.md` | If the proof uses LaTeX, structured notation, or an unusual format |
| `references/counterexample_strategies.md` | Before running the Skeptic on a new domain |
| `references/verdict_schema.md` | To check JSON field names / required fields |
| `assets/example_proofs.md` | If you need a reference correct/incorrect proof to calibrate |

---

## UI context

If this skill is called from a web UI (Streamlit / React / HTML artifact):

- Emit `AgentMessage` objects with `role`, `content`, `delay_ms` fields
- Add 600ms simulated delay between Prover → Skeptic, 800ms between Skeptic → Judge
- Colour coding: Prover = blue (#185FA5), Skeptic = red (#A32D2D), Judge = green (#3B6D11)
- The `timeline` list in `CommitteeResult` is the canonical source for UI replay
