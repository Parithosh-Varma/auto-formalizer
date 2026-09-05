from __future__ import annotations
import re

FENCED_RE = re.compile(r"```(?:lean)?\s*\n(.*?)```", re.DOTALL | re.IGNORECASE)

def extract_lean(raw: str) -> str:
    """Robustly extract Lean source from LLM output."""
    if not raw:
        return ""
    blocks = FENCED_RE.findall(raw)
    if blocks:
        # prefer block containing 'theorem' or 'import'
        for b in blocks:
            if "theorem" in b or "lemma" in b:
                return b.strip() + "\n"
        # else longest block
        return max(blocks, key=len).strip() + "\n"
    text = raw.strip()
    # strip explanatory preamble lines before first import/theorem
    lines = text.splitlines()
    start = 0
    for i, ln in enumerate(lines):
        if ln.strip().startswith("import ") or ln.strip().startswith("theorem ") or ln.strip().startswith("lemma "):
            start = i
            break
    return "\n".join(lines[start:]).strip() + "\n"

def ensure_import(code: str) -> str:
    if "import " not in code:
        return "import Mathlib\n\n" + code
    return code
