from __future__ import annotations
import time, uuid
from backend.llm.providers import LLMProvider
from backend.lean.runner import LeanRunner
from backend.lean.error_parser import errors_to_text
from backend.formalizer import prompts
from backend.formalizer.extractor import extract_lean, ensure_import
from backend.formalizer.validator import validate_proof
from backend.formalizer.understanding import parse_understanding
from backend.refinement.reward import compute_reward
from backend.utils import db as store

def summarize_fix(prev_errors: list, new_code: str) -> str:
    cats = sorted({e.get("category", "OTHER") for e in prev_errors}) if prev_errors else []
    if not cats:
        return "Initial proof generation."
    return f"Fixed {', '.join(cats).lower().replace('_',' ')}; revised tactics/imports."

def run_job(job_id: str, problem: str, reference_proof: str, context: str,
            llm: LLMProvider, runner: LeanRunner, max_iterations: int, temperature: float,
            emit=None):
    def fire(typ: str, data: dict):
        store.push_event(job_id, typ, data)
        if emit:
            try: emit(typ, data)
            except Exception: pass
    t0 = time.time()
    fire("generation_started", {"job_id": job_id})
    understanding = parse_understanding(llm, problem, reference_proof, context, temperature)
    fire("understanding_done", {"understanding": understanding})
    history: list[dict] = []
    final_code, compiled = "", False
    for i in range(1, max_iterations + 1):
        fire("refinement_started" if i > 1 else "proof_generation_started", {"iteration": i})
        t = time.time()
        if i == 1:
            prompt = prompts.generation_prompt(problem, reference_proof, context, str(understanding))
            raw = llm.generate(prompt, system=prompts.SYSTEM_LEAN_EXPERT, temperature=temperature)
        else:
            prev = history[-1]
            ctext = errors_to_text([]) if False else prev["compiler_text"]
            prompt = prompts.refinement_prompt(problem, reference_proof, prev["code"], ctext, prev["violations"])
            raw = llm.generate(prompt, system=prompts.SYSTEM_LEAN_EXPERT, temperature=temperature)
        code = ensure_import(extract_lean(raw))
        violations = validate_proof(code)
        fire("proof_generated", {"iteration": i})
        # if forbidden constructs, treat as failed verification without compiling
        if violations and any("sorry" in v or "admit" in v for v in violations):
            res_text = "VALIDATION FAILED: " + "; ".join(violations)
            errs = [{"line": None, "column": None, "message": res_text, "category": "TACTIC_FAILURE"}]
            reward = compute_reward(False, 1, i)
            dur = time.time() - t
            it = {"n": i, "code": code, "stdout": "", "stderr": res_text,
                  "errors": errs, "reward": reward, "duration": dur,
                  "summary": "Rejected forbidden placeholder.", "compiler_text": res_text, "violations": violations}
            history.append(it); store.save_iteration(job_id, it)
            fire("compiler_result", {"iteration": i, "success": False, "errors": errs, "reward": reward})
            continue
        result = runner.check(code)
        errs = [{"line": e.line, "column": e.column, "message": e.message, "category": e.category} for e in result.errors]
        ctext = errors_to_text(result.errors) or (result.stdout + "\n" + result.stderr)[-3000:]
        reward = compute_reward(result.success, len(errs), i)
        dur = time.time() - t
        it = {"n": i, "code": code, "stdout": result.stdout, "stderr": result.stderr,
              "errors": errs, "reward": reward, "duration": dur,
              "summary": ("Compilation successful." if result.success else summarize_fix(errs, code)),
              "compiler_text": ctext, "violations": violations}
        history.append(it); store.save_iteration(job_id, it)
        fire("compiler_result", {"iteration": i, "success": result.success, "errors": errs, "reward": reward})
        if result.success and not violations:
            final_code, compiled = code, True
            break
        final_code = code
    total = time.time() - t0
    fire("completed", {"success": compiled, "iterations": len(history), "total_time": round(total, 2)})
    return {"compiled": compiled, "final_code": final_code, "history": history, "understanding": understanding, "total_time": round(total, 2)}
