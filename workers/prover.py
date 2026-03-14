#!/usr/bin/env python3
"""
workers/prover.py — Prover worker

Reads {"conjecture": "...", "proof": "..."} JSON from stdin.
Calls Claude API to decompose proof into structured steps.
Writes ProverOutput JSON to stdout.

Usage:
    echo '{"conjecture": "...", "proof": "..."}' | python workers/prover.py
"""

import json
import os
import sys

import anthropic
from dotenv import load_dotenv

load_dotenv()

SYSTEM_PROMPT = """You are a mathematical proof parser. Your sole task is to decompose a proof into
structured, numbered steps. For each step, identify:

1. The step number
2. The step type (one of: ASSUMPTION, DEFINITION, CLAIM, DEDUCTION, LEMMA_USE, QED)
3. The mathematical content of the step, rewritten clearly and precisely
4. Any variables introduced in this step
5. Any prior steps this step depends on (list step numbers)
6. A flag: can_be_tested (true if the step makes a numeric or symbolic claim testable
   over concrete values; false if it is purely structural)



Output ONLY valid JSON matching this schema exactly. No prose before or after:
{
  "conjecture": "...",
  "steps": [
    {
      "step": 1,
      "type": "ASSUMPTION|DEFINITION|CLAIM|DEDUCTION|LEMMA_USE|QED",
      "content": "...",
      "variables": ["n", "k"],
      "depends_on": [],
      "can_be_tested": true
    }
  ],
  "parse_warnings": [],
  "unparseable_fragments": []
}

If a step claims something is true without any mathematical 
justification, mark it as CLAIM and add to parse_warnings: 
"Step N: assertion without justification"

"""


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

    response = client.messages.create(
        model=model,
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": json.dumps(data, ensure_ascii=False)}],
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
