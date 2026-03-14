# ProofArena

A multi-agent proof verification system. Submit a mathematical conjecture and proof — three AI agents (Prover, Skeptic, Judge) collaborate to verify it.

## How It Works

1. **Prover** — parses the proof into typed steps
2. **Skeptic** — runs numeric (NumPy) and symbolic (SymPy) tests to find counterexamples
3. **Judge** — synthesises a final verdict with confidence score and explanation

Each agent is a standalone subprocess that reads JSON from stdin and writes JSON to stdout. The orchestrator wires them together and streams results to the UI.

## Setup

```bash
pip install anthropic sympy numpy streamlit

export ANTHROPIC_API_KEY=your_key_here

streamlit run app.py
```

## Headless Usage

```bash
python orchestrator.py \
  --conjecture "For all n, n² + n is even." \
  --proof "n² + n = n(n+1). Consecutive integers have opposite parity. □"

# JSON output
python orchestrator.py --conjecture "..." --proof "..." --json

# Multiple skeptics (majority vote)
python orchestrator.py --conjecture "..." --proof "..." --skeptics 3
```

## Project Structure

```
app.py              # Streamlit UI
orchestrator.py     # Spawns workers, assembles results
workers/
  prover.py         # Worker 1: proof parsing
  skeptic.py        # Worker 2: numeric + symbolic testing
  judge.py          # Worker 3: final verdict
references/         # Schemas, strategies, proof format guides
assets/             # Example proofs for UI buttons
```

## Requirements

- Python ≥ 3.11
- Anthropic API key
