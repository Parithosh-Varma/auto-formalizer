import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

def test_extractor():
    from backend.formalizer.extractor import extract_lean
    raw = "Here:\n```lean\nimport Mathlib\ntheorem foo : True := trivial\n```"
    assert "theorem foo" in extract_lean(raw)

def test_validator_rejects_sorry():
    from backend.formalizer.validator import validate_proof
    assert validate_proof("theorem a : True := by sorry")

def test_validator_ok():
    from backend.formalizer.validator import validate_proof
    assert validate_proof("import Mathlib\ntheorem a : 1=1 := rfl") == []

def test_error_parser():
    from backend.lean.error_parser import parse_output
    errs = parse_output("", "Main.lean:9:11: error: unknown identifier 'foo'", 1)
    assert errs and errs[0].category == "UNKNOWN_IDENTIFIER"

def test_reward():
    from backend.refinement.reward import compute_reward
    assert compute_reward(True, 0, 3) == 100.0 - 3*0.5
    assert compute_reward(False, 3, 1) < 0

def test_e2e_mock_loop():
    from backend.llm.providers import MockProvider
    from backend.lean.runner import LeanRunner
    from backend.refinement.loop import run_job
    from backend.utils import db as store
    store.DB_PATH = "/tmp/test_jobs.db"
    try: os.remove("/tmp/test_jobs.db")
    except Exception: pass
    store.init_db()
    out = run_job("t1", "sum 1..n", "induction", "", MockProvider(), LeanRunner(mode="mock"), 4, 0.2)
    assert out["compiled"] and len(out["history"]) >= 2
    assert "sorry" not in out["final_code"]

def test_runner_mock_success():
    from backend.lean.runner import LeanRunner
    r = LeanRunner(mode="mock").check("import Mathlib\ntheorem a : 1=1 := rfl")
    assert r.success
