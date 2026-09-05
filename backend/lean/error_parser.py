from __future__ import annotations
import re
from dataclasses import dataclass

@dataclass
class LeanError:
    line: int | None
    column: int | None
    message: str
    category: str
    file: str = "Main.lean"

PATTERNS = [
    (re.compile(r"unknown identifier", re.I), "UNKNOWN_IDENTIFIER"),
    (re.compile(r"unknown constant", re.I), "UNKNOWN_CONSTANT"),
    (re.compile(r"type mismatch", re.I), "TYPE_MISMATCH"),
    (re.compile(r"tactic .* failed|tactic failure", re.I), "TACTIC_FAILURE"),
    (re.compile(r"unsolved goals", re.I), "UNSOLVED_GOAL"),
    (re.compile(r"missing|no such file|unknown import", re.I), "MISSING_IMPORT"),
    (re.compile(r"syntax error|unexpected|parse error", re.I), "SYNTAX_ERROR"),
    (re.compile(r"application.*mismatch|invalid application|function expected", re.I), "INVALID_APPLICATION"),
    (re.compile(r"declaration.*already|theorem.*statement", re.I), "THEOREM_STATEMENT_ERROR"),
]

POS_RE = re.compile(r"(?:Main\.lean|\.lean):(\d+):(\d+)?")

def categorize(msg: str) -> str:
    for rx, cat in PATTERNS:
        if rx.search(msg):
            return cat
    return "OTHER"

def parse_output(stdout: str, stderr: str, exit_code: int) -> list[LeanError]:
    text = (stdout or "") + "\n" + (stderr or "")
    errors: list[LeanError] = []
    for line in text.splitlines():
        low = line.lower()
        if "error" in low or "failed" in low or "unknown" in low or "mismatch" in low or "unsolved" in low:
            m = POS_RE.search(line)
            errors.append(LeanError(
                line=int(m.group(1)) if m else None,
                column=int(m.group(2)) if m and m.group(2) else None,
                message=line.strip()[:2000],
                category=categorize(line),
            ))
    # dedupe preserve order
    seen, out = set(), []
    for e in errors:
        key = (e.line, e.message)
        if key not in seen:
            seen.add(key)
            out.append(e)
    return out

def errors_to_text(errors: list[LeanError]) -> str:
    if not errors:
        return ""
    return "\n".join(f"[{e.category}] line={e.line} col={e.column}: {e.message}" for e in errors)
