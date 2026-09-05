from __future__ import annotations
import json
from backend.llm.providers import LLMProvider
from backend.formalizer.prompts import understanding_prompt

def parse_understanding(llm: LLMProvider, problem: str, reference_proof: str = "", context: str = "", temperature: float = 0.2) -> dict:
    prompt = understanding_prompt(problem, reference_proof, context)
    raw = llm.generate(prompt, system="You are a mathematician. Return ONLY valid JSON.", temperature=temperature)
    # extract JSON substring
    start = raw.find("{")
    end = raw.rfind("}")
    if start >= 0 and end > start:
        try:
            return json.loads(raw[start:end+1])
        except Exception:
            pass
    return {"variables": [], "assumptions": [], "goal": problem[:500], "strategy": "unknown", "summary": raw[:500]}
