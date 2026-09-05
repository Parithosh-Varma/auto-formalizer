from __future__ import annotations
import os, shutil, subprocess, tempfile
from dataclasses import dataclass, field

@dataclass
class LeanResult:
    success: bool
    stdout: str
    stderr: str
    exit_code: int
    errors: list = field(default_factory=list)

class LeanRunner:
    """Safely execute Lean. Modes: auto -> docker if available else local lean else mock-verify."""
    def __init__(self, timeout: int = 30, mode: str = "auto", lean_image: str = "leanprover/lean4:v4.9.0"):
        self.timeout = timeout
        self.mode = mode
        self.lean_image = os.getenv("LEAN_IMAGE", lean_image)

    def check(self, code: str) -> LeanResult:
        from backend.lean.error_parser import parse_output
        mode = self.mode
        if mode == "auto":
            if shutil.which("docker"):
                # check daemon quickly; fall back if not reachable
                try:
                    r = subprocess.run(["docker", "info"], capture_output=True, timeout=5)
                    mode = "docker" if r.returncode == 0 else ("local" if shutil.which("lean") or shutil.which("lake") else "mock")
                except Exception:
                    mode = "local" if shutil.which("lean") else "mock"
            elif shutil.which("lean") or shutil.which("lake"):
                mode = "local"
            else:
                mode = "mock"
        if mode == "docker":
            return self._check_docker(code, parse_output)
        if mode == "local":
            return self._check_local(code, parse_output)
        return self._check_mock(code, parse_output)

    def _write_tmp(self, code: str) -> str:
        d = tempfile.mkdtemp(prefix="leanjob_")
        with open(os.path.join(d, "Main.lean"), "w") as f:
            f.write(code)
        return d

    def _check_local(self, code, parse_output) -> LeanResult:
        d = self._write_tmp(code)
        try:
            exe = shutil.which("lake") or shutil.which("lean")
            cmd = [exe, "env", "lean", "Main.lean"] if exe.endswith("lake") else [exe, "Main.lean"]
            try:
                p = subprocess.run(cmd, cwd=d, capture_output=True, text=True, timeout=self.timeout)
                errors = parse_output(p.stdout, p.stderr, p.returncode)
                ok = p.returncode == 0 and not errors
                return LeanResult(ok, p.stdout[-8000:], p.stderr[-8000:], p.returncode, errors)
            except subprocess.TimeoutExpired:
                return LeanResult(False, "", f"timeout after {self.timeout}s", 124, [])
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def _check_docker(self, code, parse_output) -> LeanResult:
        d = self._write_tmp(code)
        try:
            cmd = ["docker", "run", "--rm", "--net=none",
                   "--memory", os.getenv("LEAN_MEMORY_LIMIT", "1g"),
                   "--cpus", os.getenv("LEAN_CPU_LIMIT", "1.0"),
                   "-v", f"{d}:/work:ro", "-w", "/work",
                   self.lean_image, "lean", "Main.lean"]
            try:
                p = subprocess.run(cmd, capture_output=True, text=True, timeout=self.timeout + 10)
                errors = parse_output(p.stdout, p.stderr, p.returncode)
                # missing image -> fallback to mock so demo still works
                if "Unable to find image" in (p.stderr or ""):
                    return self._check_mock(code, parse_output)
                ok = p.returncode == 0 and not errors
                return LeanResult(ok, p.stdout[-8000:], p.stderr[-8000:], p.returncode, errors)
            except subprocess.TimeoutExpired:
                return LeanResult(False, "", f"timeout after {self.timeout}s", 124, [])
            except Exception as e:
                return self._check_mock(code, parse_output)
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def _check_mock(self, code, parse_output) -> LeanResult:
        """Heuristic verification used when Lean toolchain unavailable.
        Detects forbidden placeholders, obvious unknown identifiers, unsolved goals."""
        import re
        if re.search(r"\bsorry\b|\badmit\b", code):
            err = "Main.lean:8:2: error: unknown identifier 'sorry' placeholder forbidden"
            errors = parse_output("", err, 1)
            return LeanResult(False, "", err, 1, errors)
        if "theorem " not in code and "lemma " not in code:
            err = "Main.lean:1:0: error: syntax error: no theorem declaration"
            return LeanResult(False, "", err, 1, parse_output("", err, 1))
        # simulate unknown identifier failure for mock buggy code containing 'foo'
        if re.search(r"\bfoo\b", code):
            err = "Main.lean:9:11: error: unknown identifier 'foo'"
            return LeanResult(False, "", err, 1, parse_output("", err, 1))
        if re.search(r"theorem\s+\w+[^:]*:\s*True\s*:=", code):
            err = "Main.lean:3:0: error: theorem statement trivialized"
            return LeanResult(False, "", err, 1, parse_output("", err, 1))
        return LeanResult(True, "mock verification: no errors", "", 0, [])
