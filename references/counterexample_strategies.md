# Counterexample Strategies

Domain-specific guidance for the Skeptic agent. Load the relevant section before
testing a proof. Default: Number Theory / Algebra.

---

## 1. Number Theory & Divisibility

### Standard test set
```python
integers = [-100, -10, -5, -3, -2, -1, 0, 1, 2, 3, 5, 10, 100, 997, 1000]
primes   = [2, 3, 5, 7, 11, 13, 17, 19, 23, 101, 9973]
composites = [4, 6, 8, 9, 12, 15, 100, 1000]
```

### Key edge cases to always test
- `n = 0` — many divisibility claims break at zero
- `n = 1` and `n = -1` — units in the integers
- `n = 2` — smallest prime; often a parity edge case
- `n` negative — proofs often implicitly assume positive integers

### Common claim patterns

| Claim pattern | Skeptic test |
|---|---|
| "n² + f(n) is always [even/odd/divisible by k]" | Test `f(n) % k` for n in standard set |
| "If p is prime then g(p) has property X" | Test g(p) for first 20 primes |
| "For all n, n(n+1)(n+2) is divisible by 6" | Test product % 6 for standard set |
| "n³ - n is divisible by 6" | Factor as (n-1)n(n+1) and test |

### SymPy patterns
```python
from sympy import isprime, divisors, factorint, Mod, symbols, simplify

n = symbols('n', integer=True)

# Check algebraic identity
simplify(expr_lhs - expr_rhs)  # should be 0

# Check divisibility modulo k symbolically
# Often easier to just test numerically for small k

# Factor to expose structure
from sympy import factor
factor(n**2 + n)  # → n*(n + 1)
```

---

## 2. Parity Arguments

### Test strategy
- Always test both even and odd n
- Test `n` and `n+1` together (consecutive parity)
- Watch for implicit positivity assumptions

```python
even_ns = [-4, -2, 0, 2, 4, 100]
odd_ns  = [-3, -1, 1, 3, 5, 99]

# Standard parity check
for n in even_ns + odd_ns:
    claim_holds = (your_expression(n) % 2 == 0)
    if not claim_holds:
        print(f"COUNTEREXAMPLE: n = {n}")
```

### Common gap: sign of even numbers
- "n is even, so n = 2k" is fine — but k can be negative!
- Watch for steps that then treat k as positive without saying so.

---

## 3. Algebraic Identities

### Test strategy
```python
import numpy as np
from sympy import symbols, expand, simplify, factor

# 1. Symbolic: are the two sides identical?
lhs = ...
rhs = ...
assert simplify(lhs - rhs) == 0

# 2. Numeric: random float/integer test
rng = np.random.default_rng(42)
test_vals = rng.integers(-100, 100, size=1000)
for n_val in test_vals:
    lhs_val = lhs.subs(n, n_val)
    rhs_val = rhs.subs(n, n_val)
    assert lhs_val == rhs_val, f"COUNTEREXAMPLE: n = {n_val}"
```

### Common algebraic traps
| Trap | Example | Note |
|---|---|---|
| Division in integers | "Divide both sides by n" | Fails at n = 0; also loses parity |
| Square root | "Take √ of both sides" | Only valid for non-negative |
| Factoring sign errors | (a-b)(a+b) = a²-b², not a²+b² | Always expand to verify |
| Hidden assumption | "Since n > 0..." not stated | Test negative values |

---

## 4. Modular Arithmetic

### Test strategy
```python
from sympy import Mod, symbols

n, k = symbols('n k', integer=True)

# Test claim: n³ ≡ n (mod 3) for all n
for n_val in range(-20, 21):
    assert (n_val**3 - n_val) % 3 == 0, f"n = {n_val}"

# Systematic modular testing
modulus = 6
for n_val in range(modulus):  # Only need to test one complete residue class
    result = (n_val**2 + n_val) % modulus
    print(f"n ≡ {n_val} (mod {modulus}): n²+n ≡ {result}")
```

### Key insight: periodicity
For claims of the form "f(n) ≡ 0 (mod k) for all n", you only need to test
`n ∈ {0, 1, ..., k-1}`. If it holds for all residues, it holds for all integers.

---

## 5. Inequalities

### Test strategy
- Test at boundary values (where the inequality is tightest)
- Test at equality cases if the claim is strict (>)
- Test both extremes of any stated domain

```python
# Example: prove a²+b² ≥ 2ab for all reals
import numpy as np
rng = np.random.default_rng(0)
a_vals = rng.uniform(-100, 100, 10000)
b_vals = rng.uniform(-100, 100, 10000)
violations = np.where(a_vals**2 + b_vals**2 < 2*a_vals*b_vals)
if len(violations[0]) > 0:
    i = violations[0][0]
    print(f"COUNTEREXAMPLE: a={a_vals[i]:.4f}, b={b_vals[i]:.4f}")
```

### Equality cases
Always check: does the proof claim strict or non-strict inequality?
If strict (>), find at least one case where equality holds and flag it.

---

## 6. Induction Proofs

### What the Skeptic checks for induction
1. **Base case:** Is the base case actually verified? Test it numerically.
2. **Inductive step:** Does the step correctly assume P(k) and derive P(k+1)?
   - Common flaw: using P(k+1) in the proof of P(k+1) (circular)
   - Common flaw: off-by-one error (using P(k-1) instead of P(k))
3. **Domain:** Does the base case match the stated domain?
   - "For all n ≥ 1": base case must be n = 1, not n = 0

### Testing inductive claims
```python
# Verify the formula holds for many values (doesn't verify induction structure,
# but catches wrong formulas)
def formula(n):
    return n * (n + 1) // 2  # e.g., sum of first n integers

for n in range(1, 101):
    actual = sum(range(1, n+1))
    assert formula(n) == actual, f"Formula wrong at n = {n}"
```

---

## 7. Combinatorics

### Test strategy
- Small cases: test n ∈ {0, 1, 2, 3, 4, 5}
- Use `math.comb(n, k)` for binomial coefficients
- Use `math.factorial` for factorials
- Verify identities via enumeration for small n

```python
import math

# Verify: C(n, k) + C(n, k+1) = C(n+1, k+1) (Pascal's identity)
for n in range(0, 15):
    for k in range(0, n):
        lhs = math.comb(n, k) + math.comb(n, k+1)
        rhs = math.comb(n+1, k+1)
        assert lhs == rhs, f"FAIL: n={n}, k={k}"
```

---

## When to give up and return UNCERTAIN

Return `UNCERTAIN` for a step if:
- The claim involves limits, derivatives, or continuity (beyond SymPy's integer domain)
- The claim invokes a named theorem you cannot independently verify
- The variables are over an uncountable domain with no computable test
- SymPy's simplification returns a non-zero expression but you cannot determine if
  it's truly nonzero or a simplification failure

Always explain what you tried in the `evidence` field even for `UNCERTAIN` results.
