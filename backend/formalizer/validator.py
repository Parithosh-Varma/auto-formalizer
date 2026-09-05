from __future__ import annotations
import re

FORBIDDEN = [
    (re.compile(r"\bsorry\b"), "sorry is forbidden"),
    (re.compile(r"\badmit\b"), "admit is forbidden"),
    (re.compile(r"^\s*axiom\s+", re.MULTILINE), "axiom declaration is forbidden"),
]

TRIVIAL_THEOREM = re.compile(r"theorem\s+\w+[^:]*:\s*True\s*:=")

def validate_proof(code: str) -> list[str]:
    violations: list[str] = []
    for rx, msg in FORBIDDEN:
        if rx.search(code):
            violations.append(msg)
    if TRIVIAL_THEOREM.search(code):
        violations.append("theorem trivialized to True — semantic weakening suspected")
    if "theorem " not in code and "lemma " not in code:
        violations.append("no theorem/lemma declaration found")
    # detect unsafe escape hatches used as placeholders
    if re.search(r"native_decide\s*$", code):
        pass  # allowed; real tactic
    return violations
