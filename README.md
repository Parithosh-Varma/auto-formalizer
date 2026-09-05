# Neuro-Symbolic Auto-Formalizer

NL → Lean 4 with compiler-in-the-loop refinement.

## Run
```bash
cp .env.example .env
pip install -r requirements.txt
PYTHONPATH=. uvicorn backend.api.main:app --port 8000
# open http://localhost:8000
```
Or `docker compose up` / `make run`.

## Config
`LLM_PROVIDER=mock|openai-compatible|hf`, `LLM_MODEL`, `LLM_BASE_URL`, `LLM_API_KEY`, `LEAN_MODE=auto|docker|local|mock`, `LEAN_TIMEOUT_SECONDS`, `MAX_REFINEMENT_ITERATIONS`.

## Pipeline
Problem → understanding JSON → Lean generation → LeanRunner.check → error parse → reward → refinement → compile.

## Tests
`PYTHONPATH=. pytest -q`
