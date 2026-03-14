# Verdict Schema Reference

All JSON schemas used by the Proof Committee pipeline. Load this file when you need
to check field names, required fields, or produce structured output.

---

## ProverOutput

Produced by: `workers/prover.md`
Consumed by: `workers/skeptic.md`, `workers/judge.md`

```typescript
interface ProverOutput {
  conjecture: string;            // The statement being proved
  steps: ProverStep[];
  parse_warnings: string[];      // e.g. "Step 2: implicit claim — ..."
  unparseable_fragments: string[];
}

interface ProverStep {
  step: number;                  // 1-indexed
  type: StepType;
  content: string;               // Clear English restatement of the step
  variables: string[];           // Variables in scope at this step
  depends_on: number[];          // Indices of prior steps this deduces from
  can_be_tested: boolean;        // Whether the step has testable numeric/symbolic content
}

type StepType =
  | "ASSUMPTION"   // Hypothesis taken as given
  | "DEFINITION"   // Notation or variable introduced
  | "CLAIM"        // Stated fact not justified in this proof
  | "DEDUCTION"    // Conclusion from prior steps
  | "LEMMA_USE"    // Named theorem or lemma invoked
  | "QED";         // Final conclusion
```

---

## SkepticReport

Produced by: `workers/skeptic.md`
Consumed by: `workers/judge.md`

```typescript
interface SkepticReport {
  step_results: StepResult[];
  gap_flags: GapFlag[];
  overall_skeptic_assessment: SkepticAssessment;
  counterexample_found: boolean;
  strongest_objection: string | null;    // null if no objections
}

interface StepResult {
  step: number;
  status: StepStatus;
  test_type: "numeric" | "symbolic" | "both" | "skipped";
  evidence: string;                      // Plain English description of what was tested
  counterexample: string | null;         // null if none found
}

interface GapFlag {
  between_steps: [number, number];       // e.g. [2, 3]
  description: string;
}

type StepStatus = "PASS" | "FAIL" | "UNCERTAIN" | "SKIPPED";

type SkepticAssessment =
  | "PASS"             // All testable steps pass; no gaps
  | "PASS_WITH_GAPS"   // Steps pass but logical gaps or weak justifications
  | "FAIL"             // Counterexample found or step fails
  | "UNCERTAIN";       // Too many untestable steps
```

---

## JudgeVerdict

Produced by: `workers/judge.md`
Consumed by: `scripts/run_committee.py` (assembled into CommitteeResult)

```typescript
interface JudgeVerdict {
  verdict: VerdictValue;
  verdict_label: string;           // Human-readable label string
  confidence: number;              // 0.0 – 1.0
  issue_step: number | null;       // First problematic step, or null
  counterexample: string | null;
  explanation: string;             // ≤120 words, addressed to the proof author
  step_assessments: StepAssessment[];
  suggestions: string[];           // Actionable notes; empty [] for valid proofs
  lean_statement: string | null;   // Lean 4 tactic sketch, or null
}

interface StepAssessment {
  step: number;
  assessment: StepAssessmentValue;
  note: string | null;
}

type VerdictValue = "valid" | "plausible" | "incomplete" | "invalid" | "uncertain";

type StepAssessmentValue = "SOUND" | "WEAK" | "GAP" | "WRONG" | "UNTESTED";
```

---

## CommitteeResult

Final assembled output from `scripts/run_committee.py`.
This is what the UI and CLI consume.

```typescript
interface CommitteeResult {
  // Core verdict fields (mirrored from JudgeVerdict)
  verdict: VerdictValue;
  verdict_label: string;
  confidence: number;
  issue_step: number | null;
  counterexample: string | null;
  explanation: string;
  suggestions: string[];
  lean_statement: string | null;

  // Full sub-outputs (available for inspection)
  prover_output: ProverOutput;
  skeptic_report: SkepticReport;
  judge_verdict: JudgeVerdict;

  // Timeline for UI replay
  timeline: AgentMessage[];

  // Metadata
  model: string;
  duration_ms: number;
  timestamp: string;            // ISO 8601
}

interface AgentMessage {
  role: "PROVER" | "SKEPTIC" | "JUDGE" | "SYSTEM";
  content: string;              // Human-readable message for display
  delay_ms: number;             // Simulated delay before showing this message
  step_refs: number[];          // Which proof steps this message refers to (may be empty)
}
```

---

## Timeline message format

Timeline messages are plain English, not JSON. They are assembled by `run_committee.py`
from the structured sub-outputs. Examples:

```
[PROVER]   Parsing proof... 4 steps identified. Types: ASSUMPTION → DEDUCTION → DEDUCTION → QED.
[PROVER]   Warning: Step 2 contains an implicit claim about parity. Flagged for Skeptic.
[SKEPTIC]  Testing Step 1 (algebraic identity)... SymPy confirms n*(n+1) = n²+n. ✓
[SKEPTIC]  Testing Step 2 (parity claim)... Numeric test over {-10…10}. All pass. ✓
[SKEPTIC]  Testing Step 3 (product is even)... Numeric test over {-100…100}. All pass. ✓
[SKEPTIC]  No gaps detected between steps. Overall: PASS.
[JUDGE]    Reviewing Prover + Skeptic reports...
[JUDGE]    Verdict: Proof likely valid. Confidence: 0.91.
```

---

## Null / missing field conventions

| Situation | Field value |
|---|---|
| No issue found | `issue_step: null` |
| No counterexample | `counterexample: null` |
| No suggestions | `suggestions: []` |
| Lean not applicable | `lean_statement: null` |
| Step not testable | `test_type: "skipped"`, `status: "SKIPPED"` |
| No gaps | `gap_flags: []` |
| No parse warnings | `parse_warnings: []`, `unparseable_fragments: []` |
