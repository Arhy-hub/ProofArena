#!/usr/bin/env python3
"""
workers/judge.py — Judge worker

Reads {"prover_output": {...}, "skeptic_report": {...}} JSON from stdin.
Calls Claude API to synthesise a final verdict.
Writes JudgeVerdict JSON to stdout.

Usage:
    echo '{"prover_output": {...}, "skeptic_report": {...}}' | python workers/judge.py
"""

import json
import os
import sys

import anthropic
from dotenv import load_dotenv

load_dotenv()

SYSTEM_PROMPT = """You are a mathematical proof judge. You receive both a ProverOutput (structured proof
steps) and a SkepticReport (test results, gap flags). Synthesise a definitive verdict.

Output ONLY valid JSON matching this schema exactly. No prose before or after:
{
  "verdict": "valid|plausible|incomplete|invalid|uncertain",
  "verdict_label": "Proof likely valid",
  "confidence": 0.91,
  "issue_step": null,
  "counterexample": null,
  "explanation": "...",
  "step_assessments": [
    { "step": 1, "assessment": "SOUND|WEAK|GAP|WRONG|UNTESTED", "note": null }
  ],
  "suggestions": [],
  "lean_statement": null
}

If the majority of steps are CLAIM type with no supporting 
DEDUCTION steps, or if parse_warnings contain 
"assertion without justification", return verdict: incomplete 
regardless of Skeptic results.

base_confidence = 0.60  # start skeptical, not optimistic

Deductions:
- Each UNCERTAIN step:              -0.15  (was -0.10)
- Each parse_warning:               -0.10  (was -0.05)
- Each gap_flag:                    -0.20  (was -0.15)
- CLAIM step with no DEDUCTION      
  anywhere in proof:                -0.20  (new)
- Majority of steps are CLAIM type: -0.25  (new)
- No testable steps at all:         -0.20  (new)
- Unnamed lemma invoked:            -0.12  (was -0.08)

If parse_warnings contain "assertion without justification" 
for more than one step → verdict cannot be "valid", 
minimum verdict is "incomplete" regardless of confidence score.

Verdict mapping:
- valid (0.85-1.0): all steps pass, no gaps
- plausible (0.60-0.84): minor gaps, conclusion probably correct
- incomplete (0.30-0.59): missing steps or weak justification
- invalid (0.00-0.29): counterexample found or critical flaw
- uncertain: too many untestable claims

Keep explanation under 120 words, addressed directly to the proof author."""


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
