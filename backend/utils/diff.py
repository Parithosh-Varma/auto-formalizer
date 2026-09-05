from __future__ import annotations
import difflib

def unified_diff(old: str, new: str, n: int = 3) -> str:
    return "".join(difflib.unified_diff(
        old.splitlines(keepends=True), new.splitlines(keepends=True),
        fromfile="iteration_prev", tofile="iteration_next", n=n))
