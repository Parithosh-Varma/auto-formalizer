install:
	pip install -r requirements.txt
run:
	PYTHONPATH=. uvicorn backend.api.main:app --reload --port 8000
test:
	PYTHONPATH=. pytest -q
