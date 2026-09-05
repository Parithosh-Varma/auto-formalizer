from __future__ import annotations

SYSTEM_LEAN_EXPERT = """You are an expert Lean 4 theorem prover with full knowledge of Mathlib.
Convert the mathematical problem into a correct Lean 4 theorem and proof.
Rules:
- Use Lean 4 syntax.
- Use Mathlib where appropriate.
- The theorem must represent the original mathematical statement.
- Never use `sorry`.
- Never use `admit`.
- Never fabricate theorem names.
- Do not assume unavailable imports.
- Produce code that compiles in the provided Lean environment.
- Return a complete Lean file starting with `import Mathlib`."""

def understanding_prompt(problem: str, reference_proof: str, context: str) -> str:
    return f"""Mathematical Understanding task. Return ONLY valid JSON.

Problem:
{problem}

Reference proof:
{reference_proof or '(none)'}

Context:
{context or '(none)'}

Identify: variables, types, assumptions, definitions, goal, relevant mathematical facts, suggested proof strategy.
Schema: {{"variables":[{{"name":..,"type":..}}],"assumptions":[],"goal":"..","strategy":"..","relevant_facts":[],"summary":".."}}"""

def generation_prompt(problem: str, reference_proof: str, context: str, understanding: str) -> str:
    return f"""{SYSTEM_LEAN_EXPERT}

Mathematical understanding:
{understanding}

Original Problem:
{problem}

Reference Proof:
{reference_proof or '(none)'}

Additional context:
{context or '(none)'}

Task: Write the complete Lean 4 file. Return only the Lean file (fenced ```lean block allowed)."""

def refinement_prompt(problem: str, reference_proof: str, code: str, compiler_text: str, violations: list[str]) -> str:
    v = "\n".join(f"- {x}" for x in violations) if violations else "(none)"
    return f"""{SYSTEM_LEAN_EXPERT}

Original Problem:
{problem}

Reference Proof:
{reference_proof or '(none)'}

Current Lean Proof:
```lean
{code}
```

Lean Compiler Result:
FAILED

Compiler Errors:
{compiler_text or '(no parseable errors, see stdout/stderr)'}

Validation violations:
{v}

Task:
Repair the Lean proof.
Requirements:
1. Preserve the original mathematical meaning.
2. Fix the compiler errors.
3. Do not remove the theorem merely to make it compile.
4. Do not use `sorry`.
5. Do not use unsafe shortcuts.
6. Return the complete corrected Lean file."""

def semantic_check_prompt(problem: str, code: str) -> str:
    return f"""Does this Lean theorem faithfully represent the problem? Answer JSON {{"faithful": true/false, "reason": ".."}}.

Problem: {problem}

Lean:
```lean
{code}
```"""
