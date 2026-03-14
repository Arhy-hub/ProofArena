# Proof Committee — Project Guide

A multi-agent proof verification system. Three external worker processes
(Prover, Skeptic, Judge) are spawned by a central orchestrator and wired
to a Streamlit UI. Each worker is a fully independent Python script: reads
JSON from stdin, does its job, writes JSON to stdout.

---

## Project Layout

```
proof-committee/
├── CLAUDE.md                  ← you are here
├── SKILL.md                   ← skill descriptor (triggering + orchestration steps)
├── app.py                     ← Streamlit UI (entry point for users)
├── orchestrator.py            ← spawns workers, pipes JSON, assembles CommitteeResult
├── requirements.txt           ← anthropic, sympy, numpy, streamlit
├── workers/
│   ├── prover.py              ← Worker 1: parses proof into typed steps via Claude API
│   ├── skeptic.py             ← Worker 2: numeric + symbolic testing via Claude + SymPy/NumPy
│   └── judge.py               ← Worker 3: synthesises verdict via Claude API
├── references/
│   ├── verdict_schema.md      ← JSON schemas for ProverOutput, SkepticReport, JudgeVerdict
│   ├── counterexample_strategies.md  ← Skeptic testing playbooks by domain
│   └── proof_formats.md       ← Handling LaTeX, induction, Lean, informal proofs
└── assets/
    └── example_proofs.md      ← Labelled correct/incorrect proofs for UI example buttons
```

---

## Architecture

```
                    ┌─────────────────────────────────┐
      app.py        │        orchestrator.py           │
   (Streamlit UI)──▶│  spawns workers via subprocess   │
        ▲           └────────┬──────────┬──────────────┘
        │                    │          │
        │        ┌───────────▼──┐  ┌────▼─────────────┐
        │        │ prover.py    │  │ skeptic.py        │
        │        │ (Worker 1)   │  │ (Worker 2)        │
        │        │              │  │                   │
        │        │ stdin: JSON  │  │ stdin: JSON       │
        │        │ calls Claude │  │ calls Claude      │
        │        │ stdout: JSON │  │ + SymPy / NumPy   │
        │        └──────────────┘  │ stdout: JSON      │
        │                          └───────────────────┘
        │
        │        ┌──────────────────────────────────────┐
        │        │ judge.py  (Worker 3)                 │
        │        │ stdin: ProverOutput + SkepticReport  │
        │        │ calls Claude                         │
        │        │ stdout: JudgeVerdict JSON            │
        │        └──────────────────────────────────────┘
        │
        └── CommitteeResult (verdict + timeline) rendered in Streamlit
```

---

## Worker Contract

Every worker is a standalone executable. The orchestrator calls each one via
`subprocess.run`, passing JSON on stdin and reading JSON from stdout.

```bash
# Worker 1
echo '{"conjecture": "...", "proof": "..."}' | python workers/prover.py

# Worker 2
echo '<ProverOutput JSON>' | python workers/skeptic.py

# Worker 3
echo '{"prover_output": {...}, "skeptic_report": {...}}' | python workers/judge.py
```

Workers are completely stateless. No shared memory, no sockets, no database.
The orchestrator owns all state.

---

## Data Flow

```
{ conjecture, proof }
        ↓  prover.py
ProverOutput  { steps: [ {step, type, content, can_be_tested, depends_on} ] }
        ↓  skeptic.py
SkepticReport { step_results: [{step, status, counterexample}], gap_flags, overall }
        ↓  judge.py
JudgeVerdict  { verdict, confidence, issue_step, counterexample, explanation }
        ↓  orchestrator
CommitteeResult + timeline: [AgentMessage]
        ↓  app.py
Streamlit UI  (timeline replay + verdict card)
```

---

## Streamlit UI — `app.py`

Clean, minimal academic aesthetic. Runs with `streamlit run app.py`.

Layout:
- **Top**: Conjecture + proof text inputs, "Load example" buttons, Submit
- **Middle**: Three agent status badges (Prover / Skeptic / Judge) updating live
- **Timeline panel**: Agent messages stream in sequentially with role labels and colour coding
  - Prover = blue, Skeptic = red, Judge = green
- **Verdict card**: Colour-coded result (green/amber/red) with confidence score,
  explanation, counterexample if found, and suggestions
- **Sidebar**: Raw JSON inspector (ProverOutput → SkepticReport → JudgeVerdict)

Key Streamlit patterns used:
- `st.status()` for live agent progress
- `st.session_state` to preserve results across reruns
- `st.empty()` + incremental appends for streaming timeline
- `st.expander` for raw JSON sidebar

---

## Running the System

```bash
# Install dependencies
pip install anthropic sympy numpy streamlit

# Set API key
export ANTHROPIC_API_KEY=sk-...

# Launch UI
streamlit run app.py

# Or run headless via orchestrator directly
python orchestrator.py \
  --conjecture "For all n, n² + n is even." \
  --proof "n² + n = n(n+1). Consecutive integers have opposite parity. □"

# Multiple skeptics (majority vote)
python orchestrator.py --conjecture "..." --proof "..." --skeptics 3

# JSON output
python orchestrator.py --conjecture "..." --proof "..." --json
```

---

## Key Design Decisions

1. **Workers are external processes** — each agent is a subprocess, not a function call.
   This means each can be swapped, versioned, or scaled independently.
2. **Orchestrator owns state** — workers are pure functions over JSON; the orchestrator
   assembles the timeline and result.
3. **Skeptic is tool-augmented** — numeric (NumPy) and symbolic (SymPy) checks run
   inside `skeptic.py` before the LLM call, so Claude sees real test results.
4. **UI is decoupled** — `app.py` calls `orchestrator.py` as a library import
   (not subprocess), so Streamlit can stream the timeline incrementally.
5. **Timeline is first-class** — every agent emits `AgentMessage` objects consumed
   directly by the UI for live replay.

---

## Environment

```
Python ≥ 3.11
anthropic >= 0.25.0
sympy >= 1.12
numpy >= 1.26
streamlit >= 1.35.0
```

---

## Extension Hooks

- **Multiple Skeptics**: `orchestrator.py` accepts `n_skeptics`; spawns workers in
  parallel via `ThreadPoolExecutor` and majority-votes their reports.
- **Lean integration**: Judge emits optional `lean_statement` field; orchestrator
  can pipe to `lean4 --check` if available.
- **Streaming UI**: Workers can flush newline-delimited JSON lines; orchestrator
  yields `AgentMessage` objects; `app.py` appends to timeline in real time.
- **Expanded domains**: Add domain-specific test strategies to
  `references/counterexample_strategies.md` and the Skeptic picks them up automatically.
