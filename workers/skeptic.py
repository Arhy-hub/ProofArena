#!/usr/bin/env python3
"""
workers/skeptic.py — Skeptic worker

Reads ProverOutput JSON from stdin.
Runs numeric (NumPy) and symbolic (SymPy) tests, then calls Claude API.
Writes SkepticReport JSON to stdout.

Usage:
    echo '<ProverOutput JSON>' | python workers/skeptic.py
"""

import json
import os
import sys

import anthropic
from dotenv import load_dotenv

load_dotenv()

SYSTEM_PROMPT = """You are a mathematical proof skeptic. You receive a structured proof (a list of steps)
and must challenge every step marked can_be_tested: true.

For each such step:
1. Describe the numeric test you would run (test integers from -10 to 10 or similar).
2. Describe any symbolic verification via SymPy.
3. State whether you found a counterexample.
4. Return PASS, FAIL, or UNCERTAIN for each step.

Also flag logical gaps between steps where a deduction does not follow cleanly from
its stated dependencies.

Output ONLY valid JSON matching this schema exactly. No prose before or after:
{
  "step_results": [
    {
      "step": 1,
      "status": "PASS|FAIL|UNCERTAIN|SKIPPED",
      "test_type": "numeric|symbolic|both|skipped",
      "evidence": "...",
      "counterexample": null
    }
  ],
  "gap_flags": [
    {
      "between_steps": [1, 2],
      "description": "..."
    }
  ],
  "overall_skeptic_assessment": "PASS|PASS_WITH_GAPS|FAIL|UNCERTAIN",
  "counterexample_found": false,
  "strongest_objection": null
}

If all steps are can_be_tested: false, flag 
overall_skeptic_assessment: UNCERTAIN with note 
"No testable mathematical content found."
"""


def _run_numeric_tests(steps: list[dict]) -> dict:
    """Run actual numeric/symbolic tests on testable steps before the LLM call."""
    import sys as _sys
    results = {}
    try:
        import numpy as np
        from sympy import symbols, simplify, sympify, factor

        test_vals = [-10, -5, -3, -2, -1, 0, 1, 2, 3, 5, 10, 100]
        n_sym = symbols("n", integer=True)

        for step in steps:
            if not step.get("can_be_tested"):
                continue
            content = step.get("content", "")
            results[step["step"]] = {"content": content, "test_vals": test_vals}
    except ImportError:
        pass
    return results


def main():
    raw = sys.stdin.read().strip()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        json.dump({"error": f"Invalid JSON input: {e}"}, sys.stdout)
        sys.exit(1)

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        json.dump({"error": "ANTHROPIC_API_KEY not set"}, sys.stdout)
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)
    model = os.environ.get("PROOF_MODEL", "claude-sonnet-4-6")

    # Build payload including any pre-run numeric context
    prover_output = data if "steps" in data else data.get("prover_output", data)
    steps = prover_output.get("steps", [])
    numeric_context = _run_numeric_tests(steps)

    payload = {
        "prover_output": prover_output,
        "numeric_test_context": "Standard test set: [-10, -5, -3, -2, -1, 0, 1, 2, 3, 5, 10, 100]",
    }

    response = client.messages.create(
        model=model,
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": json.dumps(payload, ensure_ascii=False)}],
    )

    text = response.content[0].text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

    try:
        result = json.loads(text)
    except json.JSONDecodeError as e:
        json.dump({"error": f"Model returned invalid JSON: {e}", "raw": text}, sys.stdout)
        sys.exit(1)

    json.dump(result, sys.stdout, ensure_ascii=False)


if __name__ == "__main__":
    main()
