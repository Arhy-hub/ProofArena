# Example Proofs

Reference examples for calibrating the Proof Committee pipeline.
Each example includes the expected verdict and key features to test.

---

## VALID PROOFS

### V1 — Parity of n² + n

**Conjecture:** For all integers n, n² + n is even.

**Proof:**
n² + n = n(n+1). One of any two consecutive integers is even, so their product is even.
Therefore n² + n is even. □

**Expected verdict:** `valid`, confidence ≥ 0.88
**Key features:** Factoring identity, parity of consecutive integers.

---

### V2 — Square of an odd number is odd

**Conjecture:** If n is odd, then n² is odd.

**Proof:**
Let n = 2k + 1 for some integer k. Then n² = (2k+1)² = 4k² + 4k + 1 = 2(2k² + 2k) + 1.
This is of the form 2m + 1 with m = 2k² + 2k, so n² is odd. □

**Expected verdict:** `valid`, confidence ≥ 0.90
**Key features:** Direct algebraic expansion. All steps testable.

---

### V3 — Sum of first n integers

**Conjecture:** For all n ≥ 1, 1 + 2 + ... + n = n(n+1)/2.

**Proof (by induction):**
Base case: n = 1. LHS = 1. RHS = 1(2)/2 = 1. ✓
Inductive step: Assume 1 + ... + k = k(k+1)/2. Then
  1 + ... + k + (k+1) = k(k+1)/2 + (k+1) = (k+1)(k/2 + 1) = (k+1)(k+2)/2.
This is the formula for n = k+1. By induction, the formula holds for all n ≥ 1. □

**Expected verdict:** `valid`, confidence ≥ 0.85
**Key features:** Induction structure; algebraic manipulation in inductive step.

---

### V4 — Product of three consecutive integers divisible by 6

**Conjecture:** For all integers n, n(n+1)(n+2) is divisible by 6.

**Proof:**
Among any three consecutive integers, at least one is divisible by 2 and at least
one is divisible by 3 (since every third integer is a multiple of 3). Therefore
their product is divisible by lcm(2,3) = 6. □

**Expected verdict:** `valid`, confidence ≥ 0.80
**Key features:** Pigeonhole-style argument. Step 2 (about divisibility by 3) is
a CLAIM that is testable but not proven in full — expect `PASS_WITH_GAPS` from
Skeptic; Judge should note it as `WEAK` but still `valid`.

---

## INCOMPLETE PROOFS

### I1 — Missing base case in induction

**Conjecture:** For all n ≥ 0, 2^n > n.

**Proof:**
Assume 2^k > k for some k ≥ 0. Then 2^(k+1) = 2 · 2^k > 2k ≥ k + 1 for k ≥ 1.
By induction, 2^n > n for all n ≥ 0. □

**Expected verdict:** `incomplete`, issue_step = 1
**Key feature:** Base case is never verified (n = 0 and n = 1 need checking).
Also: the inductive step uses "≥ k + 1 for k ≥ 1" which implicitly excludes k = 0.

---

### I2 — Circular reasoning

**Conjecture:** √2 is irrational.

**Proof:**
Suppose √2 = p/q in lowest terms. Then 2 = p²/q², so p² = 2q², so p is even.
Write p = 2r. Then 4r² = 2q², so 2r² = q², so q is even.
But p and q can't both be even if p/q is in lowest terms. Contradiction. □

**Expected verdict:** `valid`, confidence ≥ 0.85
**Note for testing:** This proof is actually correct but Skeptic cannot test it
numerically (it's a proof about irrationals). Expect `UNCERTAIN` on most steps.
Judge should recognise the classic structure and note the domain limitation.

---

## INVALID PROOFS

### X1 — False conjecture (direct counterexample)

**Conjecture:** For all integers n ≥ 1, n² + n + 41 is prime.

**Proof:**
This polynomial produces primes for small values. For n = 1: 43 (prime).
For n = 2: 47 (prime). For n = 3: 53 (prime). Therefore it always produces primes.

**Expected verdict:** `invalid`, counterexample at n = 40
**Key feature:** n = 40 gives 40² + 40 + 41 = 1681 = 41². Skeptic should find this.
Proof is also logically invalid (checking finite cases doesn't prove universality).

---

### X2 — Division by zero hidden

**Conjecture:** All positive integers are equal.

**Proof:**
Let a and b be positive integers. Set c = a = b. Then a - c = 0 and b - c = 0.
Dividing: (a-c)/(b-c) = 0/0 = 1, so a/b... [argument breaks down]

**Expected verdict:** `invalid`, issue_step = 3 (division by zero)
**Key feature:** Classic invalid step. Skeptic should flag the division-by-zero.

---

### X3 — Wrong algebraic step

**Conjecture:** (a + b)² = a² + b² for all real a, b.

**Proof:**
Expand (a + b)² = a² + ab + ba + b² = a² + 2ab + b². 
Since multiplication is commutative, 2ab = 0. Therefore (a + b)² = a² + b². □

**Expected verdict:** `invalid`, issue_step = 2 (2ab = 0 is false)
**Key feature:** The claim "2ab = 0" is obviously false. Counterexample: a = 1, b = 1.

---

## Usage Notes

- Use V1–V4 to sanity-check the Prover and Skeptic for correct proofs
- Use I1–I2 to verify the pipeline catches incomplete arguments
- Use X1–X3 to verify the Skeptic finds counterexamples and the Judge renders `invalid`
- All examples are in the scope of the prototype (algebra / number theory)
