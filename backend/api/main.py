from __future__ import annotations
import asyncio, uuid
from fastapi import FastAPI, BackgroundTasks
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import json, os

from backend.models.schemas import settings
from backend.llm.providers import get_provider
from backend.lean.runner import LeanRunner
from backend.refinement.loop import run_job
from backend.utils import db as store

store.init_db()
app = FastAPI(title="Neuro-Symbolic Auto-Formalizer")
JOBS: dict[str, dict] = {}

FRONT = os.path.join(os.path.dirname(__file__), "../../../frontend")
FRONT = os.path.abspath(FRONT)

class FormalizeReq(BaseModel):
    problem: str
    reference_proof: str = ""
    context: str = ""
    model: str = ""
    max_iterations: int = 8
    temperature: float = 0.2
    lean_timeout: int = 30

EXAMPLES = [
    {"id": "induction_sum", "title": "Sum 1..n = n(n+1)/2", "difficulty": "beginner",
     "problem": "Prove that the sum of the first n positive integers is n(n+1)/2.",
     "reference_proof": "By induction. Base n=1 trivial. Assume true for k, then sum to k+1 = k(k+1)/2 + (k+1) = (k+1)(k+2)/2."},
    {"id": "pythagoras", "title": "Pythagorean theorem", "difficulty": "beginner",
     "problem": "Prove that for a right triangle with legs a, b and hypotenuse c, a^2 + b^2 = c^2.",
     "reference_proof": "Classical geometric proof via similar triangles."},
    {"id": "add_comm", "title": "Nat add commutativity", "difficulty": "beginner",
     "problem": "Prove that for all natural numbers a b, a + b = b + a.",
     "reference_proof": "By induction on a."},
]

@app.post("/api/formalize")
def formalize(req: FormalizeReq, bg: BackgroundTasks):
    jid = uuid.uuid4().hex[:8]
    job = {"id": jid, "problem": req.problem, "reference_proof": req.reference_proof,
           "context": req.context, "model": req.model or settings.llm_model,
           "status": "running", "max_iterations": min(req.max_iterations, 12),
           "compiled": False, "final_code": "", "iterations": 0}
    JOBS[jid] = job; store.save_job(job)
    bg.add_task(_run, jid, req)
    return {"job_id": jid}

def _run(jid: str, req: FormalizeReq):
    llm = get_provider(os.getenv("LLM_PROVIDER", settings.llm_provider), req.model or settings.llm_model)
    runner = LeanRunner(timeout=req.lean_timeout or settings.lean_timeout_seconds, mode=settings.lean_mode)
    out = run_job(jid, req.problem, req.reference_proof, req.context, llm, runner,
                  max_iterations=min(req.max_iterations, 12), temperature=req.temperature)
    job = JOBS[jid]
    job.update({"status": "completed", "compiled": out["compiled"], "final_code": out["final_code"],
                "iterations": len(out["history"]), "understanding": out["understanding"],
                "total_time": out["total_time"]})
    store.save_job(job)

@app.get("/api/jobs/{jid}")
def get_job(jid: str):
    job = JOBS.get(jid, {"id": jid, "status": "unknown"})
    return {**job, "history": store.get_iterations(jid)}

@app.get("/api/jobs/{jid}/stream")
async def stream(jid: str):
    async def gen():
        seen = 0
        while True:
            evs = store.get_events(jid, seen)
            for e in evs:
                seen = e["id"]
                yield f"event: {e['type']}\ndata: {json.dumps(e['data'])}\n\n"
                if e["type"] == "completed":
                    return
            job = JOBS.get(jid)
            if job and job.get("status") == "completed" and not evs:
                # ensure terminal event was flushed
                await asyncio.sleep(0.2)
                evs2 = store.get_events(jid, seen)
                if not evs2:
                    yield f"event: completed\ndata: {json.dumps({'success': job.get('compiled')})}\n\n"
                    return
            await asyncio.sleep(0.5)
    return StreamingResponse(gen(), media_type="text/event-stream")

@app.get("/api/examples")
def examples():
    return EXAMPLES

@app.get("/api/health")
def health():
    return {"ok": True, "lean_mode": settings.lean_mode, "provider": settings.llm_provider}

if os.path.isdir(FRONT):
    app.mount("/", StaticFiles(directory=FRONT, html=True), name="front")
