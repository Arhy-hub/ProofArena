"""
parse_steps.py — Proof step extraction and manipulation utilities.

Used by run_committee.py and optionally by the Prover agent when called programmatically.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
import re


STEP_TYPES = {"ASSUMPTION", "DEFINITION", "CLAIM", "DEDUCTION", "LEMMA_USE", "QED"}


@dataclass
class ProverStep:
    step: int
    type: str
    content: str
    variables: list[str] = field(default_factory=list)
    depends_on: list[int] = field(default_factory=list)
    can_be_tested: bool = True

    def __post_init__(self):
        if self.type not in STEP_TYPES:
            raise ValueError(f"Invalid step type: {self.type}. Must be one of {STEP_TYPES}")


@dataclass
class ProverOutput:
    conjecture: str
    steps: list[ProverStep]
    parse_warnings: list[str] = field(default_factory=list)
    unparseable_fragments: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "conjecture": self.conjecture,
            "steps": [
                {
                    "step": s.step,
                    "type": s.type,
                    "content": s.content,
                    "variables": s.variables,
                    "depends_on": s.depends_on,
                    "can_be_tested": s.can_be_tested,
                }
                for s in self.steps
            ],
            "parse_warnings": self.parse_warnings,
            "unparseable_fragments": self.unparseable_fragments,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ProverOutput":
        steps = [ProverStep(**s) for s in data.get("steps", [])]
        return cls(
            conjecture=data["conjecture"],
            steps=steps,
            parse_warnings=data.get("parse_warnings", []),
            unparseable_fragments=data.get("unparseable_fragments", []),
        )

    def testable_steps(self) -> list[ProverStep]:
        return [s for s in self.steps if s.can_be_tested]

    def step_by_number(self, n: int) -> Optional[ProverStep]:
        return next((s for s in self.steps if s.step == n), None)

    def dependency_chain(self, step_num: int) -> list[int]:
        """Return all transitive dependencies of a step (breadth-first)."""
        visited = set()
        queue = [step_num]
        result = []
        while queue:
            current = queue.pop(0)
            if current in visited:
                continue
            visited.add(current)
            step = self.step_by_number(current)
            if step:
                result.append(current)
                queue.extend(step.depends_on)
        return sorted(result)

    def summary(self) -> str:
        types = " → ".join(s.type for s in self.steps)
        return (
            f"{len(self.steps)} steps: {types}\n"
            f"Testable: {len(self.testable_steps())}\n"
            f"Warnings: {len(self.parse_warnings)}"
        )


# ── Heuristic pre-parser ───────────────────────────────────────────────────────

# These patterns help infer step types from raw text before sending to the LLM.
# The LLM Prover makes the final call; this is just a lightweight hint layer.

_ASSUMPTION_PATTERNS = [
    r"^(let|assume|suppose|given that|fix)\b",
    r"^(for all|for any|for some)\b",
    r"^(hypothesis|claim without proof)\b",
]

_DEFINITION_PATTERNS = [
    r"^(define|set|let .* =|write .* =|denote)\b",
    r"^(we (have|write|set|define))\b",
    r"=.*factoring|factor(ing|ed)? (as|out)",
]

_DEDUCTION_PATTERNS = [
    r"^(therefore|hence|thus|so|it follows|consequently)\b",
    r"\b(implies|gives us|we get|we conclude|we obtain)\b",
    r"^(combining|substituting|applying)\b",
]

_LEMMA_PATTERNS = [
    r"^by (theorem|lemma|corollary|proposition|the fact that)\b",
    r"\b(by .*(theorem|lemma|result|identity))\b",
    r"\b(a standard result|a well-known fact)\b",
]

_QED_PATTERNS = [
    r"(□|∎|q\.e\.d\.?|qed)",
    r"^(this completes the proof|the proof is complete)\b",
    r"^(therefore .* is (proved|proven|established))\b",
]

_VAGUE_PHRASES = [
    "it is obvious", "clearly", "trivially", "it is easy to see",
    "obviously", "it follows immediately", "one can easily",
]


def _matches_any(text: str, patterns: list[str]) -> bool:
    t = text.strip().lower()
    return any(re.search(p, t) for p in patterns)


def infer_step_type(sentence: str) -> str:
    """Heuristically infer a step type from a sentence. Returns a suggestion string."""
    s = sentence.strip()
    if _matches_any(s, _QED_PATTERNS):
        return "QED"
    if _matches_any(s, _ASSUMPTION_PATTERNS):
        return "ASSUMPTION"
    if _matches_any(s, _DEFINITION_PATTERNS):
        return "DEFINITION"
    if _matches_any(s, _LEMMA_PATTERNS):
        return "LEMMA_USE"
    if _matches_any(s, _DEDUCTION_PATTERNS):
        return "DEDUCTION"
    return "CLAIM"  # default


def detect_vague_phrases(text: str) -> list[str]:
    """Return any vague hedging phrases found in the text."""
    t = text.lower()
    return [phrase for phrase in _VAGUE_PHRASES if phrase in t]


def extract_variables(text: str) -> list[str]:
    """
    Heuristically extract likely variable names from a proof sentence.
    Looks for single lowercase letters that appear in math context.
    """
    # Common single-letter variable patterns (preceded by "let", "=", or math operators)
    candidates = re.findall(r'\b([a-z])\b', text)
    # Filter out common English short words
    stopwords = {"a", "i", "s", "t", "e", "o", "x", "y"}
    math_vars = {"n", "k", "m", "p", "q", "r", "d", "c", "b"}
    found = []
    for c in candidates:
        if c in math_vars or (c not in stopwords and c.isalpha()):
            if c not in found:
                found.append(c)
    return found[:8]  # cap at 8 to avoid noise


def split_into_sentences(proof_text: str) -> list[str]:
    """
    Split a proof into candidate sentences for step extraction.
    Handles common proof punctuation (periods, "Therefore...", "Hence...").
    """
    # Preserve sentence breaks, split on ". " but not on e.g., "i.e." or decimal
    text = proof_text.strip()
    # Protect common abbreviations
    for abbr in ["i.e.", "e.g.", "w.l.o.g.", "resp.", "cf.", "vs."]:
        text = text.replace(abbr, abbr.replace(".", "·"))

    # Split on period-space or period-newline
    parts = re.split(r'\.\s+|\n+', text)
    # Restore abbreviations
    parts = [p.replace("·", ".") for p in parts]
    return [p.strip() for p in parts if p.strip()]


def validate_prover_output(data: dict) -> list[str]:
    """
    Validate a ProverOutput dict and return a list of issues found.
    Empty list means no issues.
    """
    issues = []

    if "conjecture" not in data or not data["conjecture"]:
        issues.append("Missing 'conjecture' field.")

    steps = data.get("steps", [])
    if not steps:
        issues.append("No steps found in prover output.")
        return issues

    step_nums = [s.get("step") for s in steps]
    if step_nums != list(range(1, len(steps) + 1)):
        issues.append(f"Step numbers are not sequential: {step_nums}")

    if steps[-1].get("type") != "QED":
        issues.append("Last step is not of type QED.")

    for s in steps:
        if s.get("type") not in STEP_TYPES:
            issues.append(f"Step {s.get('step')}: invalid type '{s.get('type')}'.")
        for dep in s.get("depends_on", []):
            if dep >= s.get("step", 0):
                issues.append(
                    f"Step {s.get('step')} depends on step {dep}, which comes later or is itself."
                )

    return issues


# ── Demo ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    sample_proof = """
    Let n be any integer. Then n² + n = n(n+1).
    Since n and n+1 are consecutive integers, one of them is even.
    Therefore n(n+1) is even. Hence n² + n is even. □
    """

    sentences = split_into_sentences(sample_proof)
    print("Sentences detected:")
    for i, s in enumerate(sentences, 1):
        t = infer_step_type(s)
        vague = detect_vague_phrases(s)
        vars_ = extract_variables(s)
        print(f"  {i}. [{t}] {s[:60]}{'...' if len(s)>60 else ''}")
        if vague:
            print(f"       ⚠ Vague: {vague}")
        if vars_:
            print(f"       vars: {vars_}")
