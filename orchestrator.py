"""
orchestrator.py — Proof Committee orchestrator

Spawns or calls the three worker agents (Prover → Skeptic → Judge) and
assembles a CommitteeResult. Can be used as a library (imported by app.py)
or run directly from the CLI.

Usage (CLI):
    python orchestrator.py \
        --conjecture "For all integers n, n² + n is even." \
        --proof "n² + n = n(n+1). One of n or n+1 is always even."

    # Multiple skeptics (majority vote):
    python orchestrator.py --conjecture "..." --proof "..." --skeptics 3

    # JSON output:
    python orchestrator.py --conjecture "..." --proof "..." --json
"""

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.parse
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

import anthropic
from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).parent
WORKERS = ROOT / "workers"


def lean4web_link(sketch: str) -> str:
    return f"https://live.lean-lang.org/#code={urllib.parse.quote(sketch)}"


# ── Data classes ───────────────────────────────────────────────────────────────

@dataclass
class AgentMessage:
    role: str          # "PROVER" | "SKEPTIC" | "JUDGE" | "SYSTEM"
    content: str
    delay_ms: int = 0
    step_refs: list[int] = field(default_factory=list)


@dataclass
class CommitteeResult:
    verdict: str
    verdict_label: str
    confidence: float
    issue_step: Optional[int]
    counterexample: Optional[str]
    explanation: str
    suggestions: list[str]
    lean_statement: Optional[str]
    prover_output: dict
    skeptic_report: dict
    judge_verdict: dict
    lean_search: dict
    timeline: list[AgentMessage]
    model: str
    duration_ms: int
    timestamp: str


# ── Worker caller ───────────────────────────────────────────────────────────────

def _call_worker(script: Path, payload: dict) -> dict:
    """Spawn a worker subprocess, pass JSON on stdin, return parsed JSON from stdout."""
    result = subprocess.run(
        [sys.executable, str(script)],
        input=json.dumps(payload, ensure_ascii=False),
        capture_output=True,
        text=True,
        env=os.environ,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Worker {script.name} exited with code {result.returncode}.\n"
            f"stderr: {result.stderr}"
        )
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"Worker {script.name} returned invalid JSON: {e}\n"
            f"stdout: {result.stdout[:500]}"
        )


# ── Agent runners ──────────────────────────────────────────────────────────────

def run_prover(conjecture: str, proof: str, timeline: list) -> dict:
    timeline.append(AgentMessage(
        role="PROVER",
        content="Receiving proof... parsing into structured steps.",
        delay_ms=0,
    ))

    result = _call_worker(WORKERS / "prover.py", {"conjecture": conjecture, "proof": proof})

    if "error" in result:
        raise RuntimeError(f"Prover error: {result['error']}")

    n_steps = len(result.get("steps", []))
    types = " → ".join(s["type"] for s in result.get("steps", []))
    timeline.append(AgentMessage(
        role="PROVER",
        content=f"Parsed {n_steps} steps. Structure: {types}.",
        delay_ms=400,
        step_refs=list(range(1, n_steps + 1)),
    ))

    for w in result.get("parse_warnings", []):
        timeline.append(AgentMessage(role="PROVER", content=f"Warning: {w}", delay_ms=200))

    return result


def run_skeptic(prover_output: dict, timeline: list) -> dict:
    timeline.append(AgentMessage(
        role="SKEPTIC",
        content="Received proof structure. Beginning adversarial testing...",
        delay_ms=600,
    ))

    testable = [s for s in prover_output.get("steps", []) if s.get("can_be_tested")]
    timeline.append(AgentMessage(
        role="SKEPTIC",
        content=f"Testing {len(testable)} step(s) with numeric and symbolic checks.",
        delay_ms=300,
    ))

    result = _call_worker(WORKERS / "skeptic.py", prover_output)

    if "error" in result:
        raise RuntimeError(f"Skeptic error: {result['error']}")

    for sr in result.get("step_results", []):
        icon = "✓" if sr["status"] == "PASS" else ("✗" if sr["status"] == "FAIL" else "?")
        timeline.append(AgentMessage(
            role="SKEPTIC",
            content=f"Step {sr['step']}: {sr['status']} {icon} — {sr['evidence']}",
            delay_ms=500,
            step_refs=[sr["step"]],
        ))
        if sr.get("counterexample"):
            timeline.append(AgentMessage(
                role="SKEPTIC",
                content=f"COUNTEREXAMPLE found: {sr['counterexample']}",
                delay_ms=100,
                step_refs=[sr["step"]],
            ))

    for gap in result.get("gap_flags", []):
        steps = gap["between_steps"]
        timeline.append(AgentMessage(
            role="SKEPTIC",
            content=f"Gap detected between steps {steps[0]} and {steps[1]}: {gap['description']}",
            delay_ms=300,
        ))

    obj = result.get("strongest_objection")
    if obj:
        timeline.append(AgentMessage(
            role="SKEPTIC", content=f"Strongest objection: {obj}", delay_ms=200
        ))

    assessment = result.get("overall_skeptic_assessment", "UNCERTAIN")
    timeline.append(AgentMessage(
        role="SKEPTIC",
        content=f"Assessment complete. Overall: {assessment}.",
        delay_ms=300,
    ))

    return result


def run_judge(prover_output: dict, skeptic_report: dict, lean_search: dict, timeline: list) -> dict:
    timeline.append(AgentMessage(
        role="JUDGE",
        content="Reviewing Prover output and Skeptic report...",
        delay_ms=800,
    ))

    mathlib_context = {
        "mathlib_found": lean_search.get("mathlib_found", False),
        "mathlib_matches": lean_search.get("mathlib_matches", []),
    }

    result = _call_worker(
        WORKERS / "judge.py",
        {"prover_output": prover_output, "skeptic_report": skeptic_report, "mathlib_context": mathlib_context},
    )

    if "error" in result:
        raise RuntimeError(f"Judge error: {result['error']}")

    verdict = result.get("verdict", "uncertain")
    label = result.get("verdict_label", verdict)
    confidence = result.get("confidence", 0.5)
    issue = result.get("issue_step")
    ce = result.get("counterexample")
    explanation = result.get("explanation", "")

    issue_str = f" — issue at step {issue}" if issue else ""
    timeline.append(AgentMessage(
        role="JUDGE",
        content=f"Verdict: {label}{issue_str}. Confidence: {confidence:.2f}.",
        delay_ms=600,
    ))
    if ce:
        timeline.append(AgentMessage(
            role="JUDGE", content=f"Counterexample: {ce}", delay_ms=200
        ))
    timeline.append(AgentMessage(role="JUDGE", content=explanation, delay_ms=300))

    for s in result.get("suggestions", []):
        timeline.append(AgentMessage(
            role="JUDGE", content=f"Suggestion: {s}", delay_ms=200
        ))

    return result


# ── Majority vote ───────────────────────────────────────────────────────────────

def _majority_skeptic(reports: list[dict]) -> dict:
    from collections import Counter
    if len(reports) == 1:
        return reports[0]

    merged = dict(reports[0])
    step_map: dict[int, list[dict]] = {}
    for r in reports:
        for sr in r.get("step_results", []):
            step_map.setdefault(sr["step"], []).append(sr)

    merged_steps = []
    for step, results in sorted(step_map.items()):
        statuses = [r["status"] for r in results]
        majority = Counter(statuses).most_common(1)[0][0]
        chosen = next((r for r in results if r["status"] == majority), results[0])
        merged_steps.append(chosen)
    merged["step_results"] = merged_steps

    assessments = [r.get("overall_skeptic_assessment", "UNCERTAIN") for r in reports]
    merged["overall_skeptic_assessment"] = Counter(assessments).most_common(1)[0][0]
    merged["counterexample_found"] = any(r.get("counterexample_found") for r in reports)
    return merged


# ── Committee class (importable by app.py) ─────────────────────────────────────

class ProofCommittee:
    def __init__(self, model: str = "claude-sonnet-4-6"):
        self.model = model

    def evaluate(
        self,
        conjecture: str = "",
        proof: str = "",
        n_skeptics: int = 1,
        file_path: Optional[str] = None,
        file_type: Optional[str] = None,
    ) -> CommitteeResult:
        import datetime
        timeline: list[AgentMessage] = []
        t0 = time.time()

        timeline.append(AgentMessage(
            role="SYSTEM",
            content=f"Proof Committee convened. Model: {self.model}. Skeptics: {n_skeptics}.",
            delay_ms=0,
        ))

        # Optional file extraction — runs before everything else
        if file_path and file_type:
            timeline.append(AgentMessage(
                role="SYSTEM",
                content=f"Extracting proof from {file_type} file...",
                delay_ms=0,
            ))
            extracted = _call_worker(
                WORKERS / "pdf_extractor.py",
                {"file_path": file_path, "file_type": file_type},
            )
            if extracted.get("error") and not extracted.get("conjecture"):
                raise RuntimeError(f"Extraction failed: {extracted['error']}")
            conjecture = extracted.get("conjecture") or conjecture
            proof = extracted.get("proof") or proof
            method = extracted.get("extraction_method", "unknown")
            timeline.append(AgentMessage(
                role="SYSTEM",
                content=f"Extraction complete via {method}.",
                delay_ms=200,
            ))

        # Step 0: Lean/Mathlib search — runs first, feeds into Judge
        try:
            lean_search_result = _call_worker(WORKERS / "lean_search.py", {"conjecture": conjecture})
        except Exception as e:
            lean_search_result = {"mathlib_matches": [], "mathlib_found": False, "error": str(e)}

        prover_output = run_prover(conjecture, proof, timeline)

        if n_skeptics == 1:
            skeptic_report = run_skeptic(prover_output, timeline)
        else:
            from concurrent.futures import ThreadPoolExecutor
            with ThreadPoolExecutor(max_workers=n_skeptics) as ex:
                futures = [ex.submit(run_skeptic, prover_output, []) for _ in range(n_skeptics)]
                reports = [f.result() for f in futures]
            skeptic_report = _majority_skeptic(reports)
            timeline.append(AgentMessage(
                role="SKEPTIC",
                content=f"Majority vote across {n_skeptics} skeptics. Assessment: {skeptic_report['overall_skeptic_assessment']}.",
                delay_ms=400,
            ))

        judge_verdict = run_judge(prover_output, skeptic_report, lean_search_result, timeline)

        # Generate lean4web link now that Judge has produced a sketch
        lean_sketch = judge_verdict.get("lean_statement") or ""
        lean_search_result["lean4web_link"] = lean4web_link(lean_sketch) if lean_sketch else ""

        duration_ms = int((time.time() - t0) * 1000)

        return CommitteeResult(
            verdict=judge_verdict.get("verdict", "uncertain"),
            verdict_label=judge_verdict.get("verdict_label", "Cannot assess"),
            confidence=judge_verdict.get("confidence", 0.5),
            issue_step=judge_verdict.get("issue_step"),
            counterexample=judge_verdict.get("counterexample"),
            explanation=judge_verdict.get("explanation", ""),
            suggestions=judge_verdict.get("suggestions", []),
            lean_statement=judge_verdict.get("lean_statement"),
            prover_output=prover_output,
            skeptic_report=skeptic_report,
            judge_verdict=judge_verdict,
            lean_search=lean_search_result,
            timeline=timeline,
            model=self.model,
            duration_ms=duration_ms,
            timestamp=datetime.datetime.utcnow().isoformat() + "Z",
        )


# ── CLI ────────────────────────────────────────────────────────────────────────

def _print_result(result: CommitteeResult, as_json: bool = False) -> None:
    if as_json:
        print(json.dumps(asdict(result), indent=2, ensure_ascii=False))
        return

    width = 46
    verdict_map = {
        "valid": "✓  Proof likely valid",
        "plausible": "~  Proof plausible",
        "incomplete": "△  Proof incomplete",
        "invalid": "✗  Proof invalid",
        "uncertain": "?  Cannot assess",
    }
    label = verdict_map.get(result.verdict, result.verdict_label)

    print()
    print("╔" + "═" * width + "╗")
    print("║  PROOF COMMITTEE VERDICT" + " " * (width - 25) + "║")
    print("╠" + "═" * width + "╣")
    print(f"║  Result:     {label:<{width - 14}}║")
    print(f"║  Confidence: {result.confidence:<{width - 14}.2f}║")
    if result.issue_step:
        issue = f"Step {result.issue_step}"
        print(f"║  Issue at:   {issue:<{width - 14}}║")
    print("╚" + "═" * width + "╝")

    print("\nTIMELINE")
    print("─" * 50)
    for msg in result.timeline:
        role_pad = f"[{msg.role}]".ljust(10)
        print(f"{role_pad} {msg.content}")

    print("\nEXPLANATION")
    print("─" * 50)
    print(result.explanation)

    if result.counterexample:
        print("\nCOUNTEREXAMPLE")
        print("─" * 50)
        print(result.counterexample)

    if result.suggestions:
        print("\nSUGGESTIONS")
        print("─" * 50)
        for i, s in enumerate(result.suggestions, 1):
            print(f"{i}. {s}")

    if result.lean_statement:
        print("\nLEAN 4 SKETCH")
        print("─" * 50)
        print(result.lean_statement)

    print(f"\n[Completed in {result.duration_ms}ms using {result.model}]")


def main():
    parser = argparse.ArgumentParser(description="Proof Committee — multi-agent proof checker")
    parser.add_argument("--conjecture", required=True, help="The statement being proved")
    parser.add_argument("--proof", required=True, help="The proof text")
    parser.add_argument("--model", default="claude-sonnet-4-6", help="Anthropic model ID")
    parser.add_argument("--skeptics", type=int, default=1, help="Number of skeptic agents")
    parser.add_argument("--json", action="store_true", help="Output raw JSON")
    args = parser.parse_args()

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("Error: ANTHROPIC_API_KEY not set.", file=sys.stderr)
        sys.exit(1)

    committee = ProofCommittee(model=args.model)
    result = committee.evaluate(
        conjecture=args.conjecture,
        proof=args.proof,
        n_skeptics=args.skeptics,
    )
    _print_result(result, as_json=args.json)


if __name__ == "__main__":
    main()
