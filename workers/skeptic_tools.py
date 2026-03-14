"""
skeptic_tools.py — SymPy + NumPy utilities for the Skeptic agent.

Provides:
    numeric_test(predicate, domain, ...)  → (passed: bool, counterexample)
    symbolic_verify(lhs, rhs, vars, ...)  → (verified: bool, detail: str)
    find_counterexample(predicate, values) → counterexample value or None
    test_divisibility(expr_str, divisor, var, test_range) → SkepticResult
    test_parity(expr_str, var, test_range)  → SkepticResult
    test_identity(lhs_str, rhs_str, vars, test_range) → SkepticResult
"""

from __future__ import annotations
import numpy as np
from dataclasses import dataclass
from typing import Callable, Any, Optional
import textwrap


# ── Standard test sets ─────────────────────────────────────────────────────────

STANDARD_INTEGERS = [-100, -10, -5, -3, -2, -1, 0, 1, 2, 3, 5, 10, 100]
EDGE_CASES        = [-2, -1, 0, 1, 2]
PRIMES            = [2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 97, 101]
COMPOSITES        = [4, 6, 8, 9, 12, 15, 100, 1001]


# ── Result type ────────────────────────────────────────────────────────────────

@dataclass
class SkepticResult:
    status: str             # "PASS" | "FAIL" | "UNCERTAIN"
    test_type: str          # "numeric" | "symbolic" | "both"
    evidence: str
    counterexample: Optional[str] = None


# ── Core utilities ─────────────────────────────────────────────────────────────

def numeric_test(
    predicate: Callable[[Any], bool],
    domain: str = "integers",
    custom_values: Optional[list] = None,
) -> tuple[bool, Optional[Any]]:
    """
    Test a boolean predicate over a standard test set.

    Args:
        predicate: A function that takes a value and returns True if the claim holds.
        domain: "integers" (default), "primes", "composites", "naturals"
        custom_values: If provided, use these values instead.

    Returns:
        (passed, counterexample) — counterexample is None if all pass.

    Example:
        ok, ce = numeric_test(lambda n: (n**2 + n) % 2 == 0)
        # ok=True, ce=None
    """
    if custom_values is not None:
        values = custom_values
    elif domain == "integers":
        values = STANDARD_INTEGERS
    elif domain == "primes":
        values = PRIMES
    elif domain == "composites":
        values = COMPOSITES
    elif domain == "naturals":
        values = [0, 1, 2, 3, 4, 5, 10, 100]
    else:
        values = STANDARD_INTEGERS

    for v in values:
        try:
            if not predicate(v):
                return False, v
        except Exception as e:
            return False, f"Exception at {v}: {e}"

    return True, None


def find_counterexample(
    predicate: Callable[[Any], bool],
    search_range: range,
) -> Optional[Any]:
    """
    Exhaustive search for a counterexample in the given range.

    Args:
        predicate: Returns True if the claim holds for this value.
        search_range: e.g. range(-1000, 1001)

    Returns:
        The first counterexample found, or None.

    Example:
        ce = find_counterexample(lambda n: (n**2 + n) % 2 == 0, range(-1000, 1001))
        # None — no counterexample
    """
    for v in search_range:
        try:
            if not predicate(v):
                return v
        except Exception:
            return v
    return None


def symbolic_verify(
    lhs: str,
    rhs: str,
    vars: list[str],
    domain: str = "integer",
) -> tuple[bool, str]:
    """
    Check whether two SymPy expressions are symbolically equal.

    Args:
        lhs, rhs: Expression strings parseable by SymPy.
        vars: Variable name strings, e.g. ["n", "k"].
        domain: SymPy domain for symbols: "integer", "real", "complex".

    Returns:
        (verified, detail) — detail describes what SymPy found.

    Example:
        ok, detail = symbolic_verify("n*(n+1)", "n**2 + n", ["n"])
        # ok=True, detail="SymPy confirms n*(n+1) - (n**2 + n) simplifies to 0."
    """
    try:
        from sympy import symbols, simplify, sympify

        sym_kwargs = {"integer": True} if domain == "integer" else {"real": True}
        sym_vars = {v: symbols(v, **sym_kwargs) for v in vars}

        lhs_expr = sympify(lhs, locals=sym_vars)
        rhs_expr = sympify(rhs, locals=sym_vars)
        diff = simplify(lhs_expr - rhs_expr)

        if diff == 0:
            return True, f"SymPy confirms {lhs} - ({rhs}) simplifies to 0."
        else:
            return False, f"SymPy found non-zero difference: {diff}. Expressions are NOT equal."

    except ImportError:
        return False, "SymPy not installed. Cannot perform symbolic verification."
    except Exception as e:
        return False, f"SymPy error: {e}"


# ── Higher-level test helpers ──────────────────────────────────────────────────

def test_divisibility(
    expr_str: str,
    divisor: int,
    var: str = "n",
    test_range: range = range(-50, 51),
) -> SkepticResult:
    """
    Test whether expr_str is always divisible by divisor for integer var.

    Example:
        result = test_divisibility("n**2 + n", 2, "n")
        # SkepticResult(status='PASS', ...)
    """
    def predicate(val):
        local = {var: val}
        result = eval(expr_str, {"__builtins__": {}}, local)  # noqa: S307
        return int(result) % divisor == 0

    ce = find_counterexample(predicate, test_range)
    val = eval(expr_str, {"__builtins__": {}}, {var: ce}) if ce is not None else None

    if ce is None:
        return SkepticResult(
            status="PASS",
            test_type="numeric",
            evidence=f"Tested {var} ∈ [{test_range.start}, {test_range.stop-1}]. "
                     f"{expr_str} is divisible by {divisor} for all tested values.",
        )
    else:
        return SkepticResult(
            status="FAIL",
            test_type="numeric",
            evidence=f"Counterexample found at {var} = {ce}: {expr_str} = {val}, not divisible by {divisor}.",
            counterexample=f"{var} = {ce} gives {expr_str} = {val}",
        )


def test_parity(
    expr_str: str,
    var: str = "n",
    expected_parity: str = "even",
    test_range: range = range(-50, 51),
) -> SkepticResult:
    """
    Test whether expr_str is always even or always odd.

    Args:
        expected_parity: "even" or "odd"
    """
    parity_val = 0 if expected_parity == "even" else 1

    def predicate(val):
        local = {var: val}
        result = eval(expr_str, {"__builtins__": {}}, local)  # noqa: S307
        return int(result) % 2 == parity_val

    ce = find_counterexample(predicate, test_range)

    if ce is None:
        return SkepticResult(
            status="PASS",
            test_type="numeric",
            evidence=f"Tested {var} ∈ [{test_range.start}, {test_range.stop-1}]. "
                     f"{expr_str} is always {expected_parity}.",
        )
    else:
        val = eval(expr_str, {"__builtins__": {}}, {var: ce})
        return SkepticResult(
            status="FAIL",
            test_type="numeric",
            evidence=f"Counterexample: {var} = {ce} gives {expr_str} = {val} (not {expected_parity}).",
            counterexample=f"{var} = {ce} gives {expr_str} = {val}",
        )


def test_identity(
    lhs_str: str,
    rhs_str: str,
    vars: list[str],
    test_range: range = range(-20, 21),
) -> SkepticResult:
    """
    Test an algebraic identity numerically and then symbolically.

    Example:
        result = test_identity("n*(n+1)", "n**2 + n", ["n"])
    """
    # Numeric pass first
    def predicate(val):
        local = {vars[0]: val}
        lhs_val = eval(lhs_str, {"__builtins__": {}}, local)  # noqa: S307
        rhs_val = eval(rhs_str, {"__builtins__": {}}, local)  # noqa: S307
        return lhs_val == rhs_val

    ce = find_counterexample(predicate, test_range)

    if ce is not None:
        val_lhs = eval(lhs_str, {"__builtins__": {}}, {vars[0]: ce})
        val_rhs = eval(rhs_str, {"__builtins__": {}}, {vars[0]: ce})
        return SkepticResult(
            status="FAIL",
            test_type="numeric",
            evidence=f"Counterexample: {vars[0]} = {ce} gives LHS={val_lhs} ≠ RHS={val_rhs}.",
            counterexample=f"{vars[0]} = {ce}: {lhs_str} = {val_lhs}, {rhs_str} = {val_rhs}",
        )

    # Symbolic pass
    sym_ok, sym_detail = symbolic_verify(lhs_str, rhs_str, vars)
    if sym_ok:
        return SkepticResult(
            status="PASS",
            test_type="both",
            evidence=f"Numeric: tested {vars[0]} ∈ [{test_range.start}, {test_range.stop-1}], all pass. "
                     f"Symbolic: {sym_detail}",
        )
    else:
        return SkepticResult(
            status="UNCERTAIN",
            test_type="both",
            evidence=f"Numeric tests pass, but symbolic check inconclusive: {sym_detail}",
        )


def test_inequality(
    lhs_str: str,
    rhs_str: str,
    var: str = "n",
    strict: bool = False,
    test_range: range = range(-50, 51),
) -> SkepticResult:
    """
    Test whether lhs ≥ rhs (or lhs > rhs if strict) for integer var.
    """
    op = ">" if strict else ">="
    op_fn = (lambda a, b: a > b) if strict else (lambda a, b: a >= b)

    def predicate(val):
        local = {var: val}
        lhs_val = eval(lhs_str, {"__builtins__": {}}, local)  # noqa: S307
        rhs_val = eval(rhs_str, {"__builtins__": {}}, local)  # noqa: S307
        return op_fn(lhs_val, rhs_val)

    ce = find_counterexample(predicate, test_range)

    if ce is None:
        return SkepticResult(
            status="PASS",
            test_type="numeric",
            evidence=f"Tested {var} ∈ [{test_range.start}, {test_range.stop-1}]. "
                     f"{lhs_str} {op} {rhs_str} holds for all tested values.",
        )
    else:
        lhs_val = eval(lhs_str, {"__builtins__": {}}, {var: ce})
        rhs_val = eval(rhs_str, {"__builtins__": {}}, {var: ce})
        return SkepticResult(
            status="FAIL",
            test_type="numeric",
            evidence=f"Counterexample: {var} = {ce} gives {lhs_str} = {lhs_val} {op} {rhs_str} = {rhs_val} is FALSE.",
            counterexample=f"{var} = {ce}: {lhs_val} not {op} {rhs_val}",
        )


# ── Demo ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=== skeptic_tools.py demo ===\n")

    print("1. test_divisibility(n**2 + n, 2):")
    r = test_divisibility("n**2 + n", 2)
    print(f"   status={r.status}, evidence={r.evidence}\n")

    print("2. test_identity(n*(n+1), n**2 + n):")
    r = test_identity("n*(n+1)", "n**2 + n", ["n"])
    print(f"   status={r.status}, test_type={r.test_type}\n")

    print("3. test_parity(n**2 + n, expected_parity='even'):")
    r = test_parity("n**2 + n", expected_parity="even")
    print(f"   status={r.status}\n")

    print("4. find_counterexample for (a+b)**2 == a**2 + b**2 [FALSE claim]:")
    # Simplified to single var for demo
    ce = find_counterexample(lambda n: (n + 1)**2 == n**2 + 1, range(-10, 11))
    print(f"   counterexample={ce}\n")

    print("5. test_divisibility(n**3 - n, 6) [should PASS]:")
    r = test_divisibility("n**3 - n", 6)
    print(f"   status={r.status}\n")
