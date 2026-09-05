# Neuro-Symbolic Auto-Formalizer

Natural language → machine-checkable **Lean 4** proofs, with a **compiler-in-the-loop** refinement cycle.

You write a math problem in English (plus an optional textbook proof). The system understands the math, writes Lean 4 + Mathlib code, compiles it with real Lean, reads the compiler errors, fixes its own proof, and repeats until Lean says `✓ VERIFIED`.

```
Human Mathematics → LLM → Lean Proof → Lean Compiler → Objective Feedback → LLM → Better Proof → ✓ VERIFIED
```

## Architecture

```
frontend/            static UI (index.html, app.js, styles.css)
  input panel, config, live pipeline log, Lean viewer,
  compiler output, iteration timeline with diffs
backend/
  api/main.py        FastAPI: POST /api/formalize, GET /api/jobs/:id,
                     GET /api/jobs/:id/stream (SSE), GET /api/examples
  llm/providers.py   LLMProvider abstraction: mock, OpenAI-compatible,
                     Responses API (opencode zen), HuggingFace
  formalizer/        prompts, understanding parser, Lean extractor, sorry/admit validator
  lean/              LeanRunner (docker/local/mock) + error parser + categories
  refinement/        compiler-feedback loop + reward model
  utils/             SQLite persistence, diff helper
lean/                pinned Lean/Mathlib project (lean-toolchain, lakefile, Main.lean)
benchmarks/          bench.json problem set
tests/               pytest unit + integration + e2e
docker/              Dockerfiles for backend and Lean sandbox
```

## Requirements

- Python 3.12+, `pip`
- Optional: Docker (for Lean sandbox), Lean 4 toolchain + Mathlib (for real verification)
- An LLM key: OpenAI-compatible endpoint or opencode zen (`/v1/responses`)

## Quickstart

```bash
cp .env.example .env   # then fill in LLM_* below
pip install -r requirements.txt
PYTHONPATH=. uvicorn backend.api.main:app --port 8000
# open http://localhost:8000
```

Single-command Docker dev:

```bash
docker compose up
```

Or via Make:

```bash
make install
make run     # backend on :8000
make test
```

## Configuring the LLM

`.env` keys:

```env
LLM_PROVIDER=opencode      # mock | openai-compatible | opencode/responses | hf
LLM_MODEL=muse-spark-1.3-contributor-free
LLM_BASE_URL=https://opencode.ai/zen/v1/responses
LLM_API_KEY=sk-...
LLM_TEMPERATURE=0.2
```

- `mock`: deterministic offline provider (buggy first proof → fixed proof), used by tests.
- `openai-compatible`: any `/v1/chat/completions` endpoint (OpenAI, DeepSeek, Qwen, Llama).
- `opencode`/`responses`: OpenAI Responses API at `/v1/responses` (opencode zen). Free models such as `muse-spark-1.3-contributor-free` work without billing; paid models need a payment method.
- `hf`: HuggingFace/TGI endpoint (`LLM_BASE_URL` required).

Swap models without touching pipeline code — everything goes through `LLMProvider.generate(prompt, system, temperature)`.

## Running the backend

```bash
PYTHONPATH=. uvicorn backend.api.main:app --port 8000 --reload
```

Endpoints:

- `POST /api/formalize` → `{problem, reference_proof?, context?, model?, max_iterations?, temperature?, lean_timeout?}` → `{job_id}`
- `GET /api/jobs/:id` → status + `history` (code, errors, reward per iteration)
- `GET /api/jobs/:id/stream` → SSE events: `generation_started`, `understanding_done`, `proof_generated`, `compiler_result`, `refinement_started`, `completed`
- `GET /api/examples`, `GET /api/health`

Example:

```bash
curl -X POST localhost:8000/api/formalize \
  -H 'Content-Type: application/json' \
  -d '{"problem":"Prove sum 1..n = n(n+1)/2","reference_proof":"induction"}'
```

## Running the frontend

No build step — static files in `frontend/` are served by the backend at `/`. Open `http://localhost:8000`, type a problem, hit **Formalize Proof**, and watch the live pipeline, compiler output, iteration timeline, and proof diffs.

## Running the sandbox (Lean execution)

`LeanRunner.check(code)` isolates every proof in a temp dir and runs one command only:

- `docker run --rm --net=none --memory 1g --cpus 1 leanprover/lean4:vX lean Main.lean`, or
- local `lake env lean Main.lean` if Docker is unavailable, or
- heuristic `mock` verification (forbidden-placeholder + unknown-identifier checks) for offline demos.

Limits via env: `LEAN_TIMEOUT_SECONDS=30`, `LEAN_MEMORY_LIMIT=1g`, `LEAN_CPU_LIMIT=1.0`, `MAX_REFINEMENT_ITERATIONS=8`. Set `LEAN_MODE=auto|docker|local|mock`.

## Installing Lean 4 + Mathlib

The pinned project lives in `lean/` (`lean-toolchain`, `lakefile.toml`, `Main.lean`). With [elan](https://github.com/leanprover/elan) installed:

```bash
cd lean
lake update
lake build
lake env lean Main.lean   # should print nothing = success
```

Or use the sandbox image: `docker build -f docker/Dockerfile.lean .`

## Running tests

```bash
PYTHONPATH=. pytest -q
```

Covers: prompt construction, Lean extraction, `sorry`/`admit` validation, error parsing/categories, reward math, mock LeanRunner, and a full e2e loop (buggy proof → compiler error → fixed proof → compiles).

## Running benchmarks

```bash
PYTHONPATH=. python3 - <<'PY'
import json
from backend.llm.providers import MockProvider
from backend.lean.runner import LeanRunner
from backend.refinement.loop import run_job
from backend.utils import db as s
s.DB_PATH = '/tmp/bench.db'
s.init_db()
bench = json.load(open('benchmarks/bench.json'))
ok = 0
for b in bench:
    out = run_job(b['id'], b['problem'], b.get('reference_proof',''), '', MockProvider(), LeanRunner(mode='mock'), 4, 0.2)
    ok += out['compiled']
    print(b['id'], 'COMPILED' if out['compiled'] else 'FAILED', len(out['history']), 'iters')
print(f'Success rate: {ok}/{len(bench)}')
PY
```

Add problems to `benchmarks/bench.json` with `{id, problem, reference_proof, difficulty}`.

## How the loop works (example)

Input: `Prove sum 1..n = n(n+1)/2`, reference: `induction`.

- Understanding → `{goal: "2*sum = n*(n+1)", strategy: "induction"}`
- Iter 1 generates `exact foo n ih` → `[UNKNOWN_IDENTIFIER] line 9: unknown identifier 'foo'`, reward `-1.5`
- Iter 2 fixes to `linarith` → compiles, reward `99.0` → `✓ VERIFIED`

Final proof:

```lean
import Mathlib

theorem sum_first_n (n : ℕ) :
    2 * (∑ k in Finset.range (n + 1), k) = n * (n + 1) := by
  induction n with
  | zero => simp
  | succ n ih =>
    rw [Finset.sum_range_succ]
    linarith
```

## Security notes

- Generated Lean is untrusted: sandboxed (no network, memory/CPU/time limits, temp dirs, cleanup, single compiler command).
- Secrets live only in local `.env` (git-ignored) — never logged or committed.
