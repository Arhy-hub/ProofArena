# Proof Formats

How to handle different proof writing styles. The Prover reads this to know how to
parse non-standard input. Load this file when the submitted proof uses LaTeX,
structured notation, or an unusual format.

---

## 1. Plain English (default)

No special handling needed. Parse directly into steps.

Example:
```
"n² + n = n(n+1). One of n or n+1 is always even, so their product is even."
```

---

## 2. LaTeX / Mathematical Notation

Strip LaTeX commands to extract mathematical meaning. Do not preserve LaTeX in output
steps — rewrite in clear English with inline math where helpful.

### Common LaTeX patterns

| LaTeX | Plain meaning |
|---|---|
| `n^{2}` or `n^2` | n² |
| `\forall n \in \mathbb{Z}` | for all integers n |
| `\exists k \in \mathbb{N}` | there exists a natural number k |
| `n \equiv 0 \pmod{2}` | n ≡ 0 (mod 2), i.e. n is even |
| `\mid` | divides (as in "2 \mid n" = "2 divides n") |
| `\Rightarrow` | implies |
| `\iff` or `\Leftrightarrow` | if and only if |
| `\square` or `\blacksquare` | QED marker |
| `\therefore` | therefore |
| `\sum_{i=1}^{n}` | sum from i=1 to n |

### Handling
1. Identify math environments (`$...$`, `$$...$$`, `\[...\]`, `equation`)
2. Extract the mathematical expression and restate in English
3. Preserve variable names exactly as written (n, k, m, p, etc.)

---

## 3. Structured / Numbered Proof

Some proofs are already numbered. Map them directly to steps:

```
1. Let n be any integer.
2. Factor: n² + n = n(n+1).
3. Consecutive integers n and n+1 have opposite parity.
4. Hence n(n+1) is even. □
```

Handling: Use the author's numbering as `step` indices. Infer `type` from content:
- "Let..." / "Assume..." → ASSUMPTION
- "Factor" / "Write" / "Define" → DEFINITION
- "Since" / "Hence" / "Therefore" → DEDUCTION
- "By [Theorem name]..." → LEMMA_USE
- "□" / "QED" → QED
- Any stated fact without justification → CLAIM

---

## 4. Two-Column Proof

Common in geometry / formal proofs:

```
Statement                        | Reason
---------------------------------|----------------------------------
n = 2k+1 for some integer k      | Definition of odd
n² = (2k+1)² = 4k²+4k+1         | Expansion
4k²+4k+1 = 2(2k²+2k)+1          | Algebraic manipulation
n² is odd                        | Definition of odd (form 2m+1)
```

Handling:
- Left column → `content` of step
- Right column → include in `content` as justification
- Reason "Definition of X" → DEFINITION or ASSUMPTION
- Reason "By Theorem Y" → LEMMA_USE

---

## 5. Proof by Contradiction

Identify the structure:
```
Assume for contradiction that [negation of conjecture].
... [derive contradiction] ...
Therefore the assumption is false, and [conjecture] holds.
```

Step mapping:
- "Assume for contradiction..." → `ASSUMPTION` (mark with `parse_warning`: "Proof by contradiction: assumption is negation of conjecture")
- Intermediate steps → `DEDUCTION`
- "This contradicts..." → `CLAIM` or `DEDUCTION`
- Final conclusion → `QED`

Note in `parse_warnings`: `"Proof by contradiction structure detected."`

---

## 6. Proof by Induction

Identify the two parts explicitly:

```
Base case: n = 1. [show P(1)]
Inductive step: Assume P(k). Show P(k+1). [derivation]
By induction, P(n) holds for all n ≥ 1.
```

Step mapping:
- Base case → one or two steps: `ASSUMPTION` (base) + `DEDUCTION` (P(base) verified)
- Inductive hypothesis → `ASSUMPTION` (mark: "inductive hypothesis")
- Inductive step derivation → `DEDUCTION` steps
- Conclusion → `QED`

Add `parse_warning`: `"Induction proof: Skeptic should verify base case numerically and check inductive step structure."`

---

## 7. Lean 4 / Mathlib

If the user submits Lean 4 code, extract the informal meaning:

```lean
theorem n_sq_add_n_even (n : ℤ) : 2 ∣ n ^ 2 + n := by
  have h : n ^ 2 + n = n * (n + 1) := by ring
  rw [h]
  exact Int.even_mul_succ_self n
```

Parsing:
- Theorem statement → conjecture
- `by ring` / `by simp` / `by norm_num` → single DEDUCTION step ("Verified computationally by Lean tactic")
- `have h : ...` → DEFINITION / CLAIM
- `exact ...` → LEMMA_USE (name the lemma: `Int.even_mul_succ_self`)
- `rw [h]` → DEDUCTION (rewriting using h)

Note: Lean proofs that type-check are almost certainly correct. Add to `parse_warnings`:
`"Input is Lean 4 code. If it type-checks, high confidence of correctness."` and
set Judge confidence floor to 0.95.

---

## 8. Informal / Sketch Proofs

Some inputs are partial or informal:

```
"It's easy to see that n² + n factors as n(n+1), and since one of any two
consecutive integers is even, the product is even."
```

Handling:
- Parse as best you can
- Flag vague phrases: "it's easy to see", "clearly", "obviously", "trivially"
  → add to `parse_warnings`: `"Step N: vague justification ('it is easy to see...')"`
- Ask the Judge to penalise confidence for each flagged phrase

---

## Output language

Regardless of input format, all `content` fields in `ProverOutput` must be written in
clear mathematical English. Do not preserve LaTeX commands, two-column layout, or
Lean syntax in the output. The Skeptic and Judge work from English descriptions.
