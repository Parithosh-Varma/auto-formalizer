from __future__ import annotations
import json
import os
import re
import httpx

class LLMProvider:
    def generate(self, prompt: str, system: str = "", temperature: float = 0.2) -> str:
        raise NotImplementedError

class MockProvider(LLMProvider):
    """Deterministic mock that returns progressively better Lean code.
    Used for tests / offline demo. Simulates an LLM learning from errors."""

    def generate(self, prompt: str, system: str = "", temperature: float = 0.2) -> str:
        p = prompt.lower()
        # Refinement: if prompt contains compiler errors about 'unknown identifier foo', fix it
        if "unknown identifier" in p or "compiler errors" in p or "lean compiler result" in p:
            # If current code contains 'foo' bug, return fixed version
            if "foo" in prompt:
                return lean_ok("sum_first_n")
            # generic fix: return clean proof
            m = re.search(r"theorem\s+(\w+)\s*[\(:]", prompt)
            name = m.group(1) if m else "sum_first_n"
            if name == "prover":
                m2 = re.findall(r"theorem\s+(\w+)\s*[\(:]", prompt)
                name = next((x for x in m2 if x != "prover"), "sum_first_n")
            return lean_ok(name)
        # First attempt: intentionally buggy (unknown identifier) to exercise loop,
        # unless prompt asks for understanding JSON
        if "mathematical understanding task" in p:
            return json.dumps({
                "variables": [{"name": "n", "type": "Nat"}],
                "assumptions": [],
                "goal": "2 * sum_{k<n+1} k = n*(n+1)",
                "strategy": "induction",
                "relevant_facts": ["Finset.sum_range_succ", "Nat.add_comm"],
                "summary": "Induction on n."
            })
        # Initial generation with a bug so refinement loop is demonstrated
        return lean_buggy("sum_first_n")

def lean_ok(name: str = "sum_first_n") -> str:
    return f"""import Mathlib

theorem {name} (n : ℕ) :
    2 * (∑ k in Finset.range (n + 1), k) = n * (n + 1) := by
  induction n with
  | zero => simp
  | succ n ih =>
    rw [Finset.sum_range_succ]
    linarith
"""

def lean_buggy(name: str = "sum_first_n") -> str:
    return f"""import Mathlib

theorem {name} (n : ℕ) :
    2 * (∑ k in Finset.range (n + 1), k) = n * (n + 1) := by
  induction n with
  | zero => simp
  | succ n ih =>
    rw [Finset.sum_range_succ]
    exact foo n ih
"""

class OpenAICompatibleProvider(LLMProvider):
    """Works with OpenAI, DeepSeek, Qwen, Llama via OpenAI-compatible endpoints."""
    def __init__(self, base_url: str = "", api_key: str = "", model: str = ""):
        self.base_url = (base_url or os.getenv("LLM_BASE_URL", "") or "https://api.openai.com/v1").rstrip("/")
        self.api_key = api_key or os.getenv("LLM_API_KEY", "")
        self.model = model or os.getenv("LLM_MODEL", "gpt-4o-mini")

    def generate(self, prompt: str, system: str = "", temperature: float = 0.2) -> str:
        url = f"{self.base_url}/chat/completions"
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system or "You are an expert Lean 4 theorem prover."},
                {"role": "user", "content": prompt},
            ],
            "temperature": temperature,
        }
        with httpx.Client(timeout=120) as c:
            r = c.post(url, json=body, headers=headers)
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]

class HuggingFaceProvider(LLMProvider):
    """Inference Endpoints / Text Generation Inference compatible."""
    def __init__(self, base_url: str = "", api_key: str = "", model: str = ""):
        self.base_url = (base_url or os.getenv("LLM_BASE_URL", "")).rstrip("/")
        self.api_key = api_key or os.getenv("LLM_API_KEY", "")
        self.model = model or os.getenv("LLM_MODEL", "")

    def generate(self, prompt: str, system: str = "", temperature: float = 0.2) -> str:
        if not self.base_url:
            raise RuntimeError("LLM_BASE_URL required for HuggingFace provider")
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        body = {"inputs": f"{system}\n\n{prompt}", "parameters": {"temperature": temperature, "max_new_tokens": 2048}}
        with httpx.Client(timeout=180) as c:
            r = c.post(self.base_url, json=body, headers=headers)
            r.raise_for_status()
            data = r.json()
            if isinstance(data, list) and data:
                return data[0].get("generated_text", "")
            return str(data)

class ResponsesApiProvider(LLMProvider):
    """OpenAI Responses API (e.g. https://opencode.ai/zen/v1/responses)."""
    def __init__(self, endpoint: str = "", api_key: str = "", model: str = ""):
        self.endpoint = endpoint or os.getenv("LLM_BASE_URL", "") or "https://opencode.ai/zen/v1/responses"
        self.api_key = api_key or os.getenv("LLM_API_KEY", "")
        self.model = model or os.getenv("LLM_MODEL", "gpt-4o-mini")

    def generate(self, prompt: str, system: str = "", temperature: float = 0.2) -> str:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        body = {
            "model": self.model,
            "input": f"{system}\n\n{prompt}" if system else prompt,
            "temperature": temperature,
        }
        with httpx.Client(timeout=180) as c:
            r = c.post(self.endpoint, json=body, headers=headers)
            r.raise_for_status()
            data = r.json()
            if isinstance(data, dict):
                if isinstance(data.get("output_text"), str) and data["output_text"]:
                    return data["output_text"]
                # Responses API: output: [{content:[{text:...}]}]
                parts: list[str] = []
                for item in data.get("output", []) or []:
                    for blk in item.get("content", []) or []:
                        if isinstance(blk, dict) and blk.get("text"):
                            t = blk["text"]
                            parts.append(t if isinstance(t, str) else t.get("value", ""))
                if parts:
                    return "".join(parts)
                if isinstance(data.get("response"), str):
                    return data["response"]
            return str(data)

def get_provider(name: str = "", model: str = "") -> LLMProvider:
    name = (name or os.getenv("LLM_PROVIDER", "mock")).lower()
    if name in ("mock", "local-mock", "test"):
        return MockProvider()
    if name in ("hf", "huggingface", "tgi"):
        return HuggingFaceProvider(model=model)
    if name in ("opencode", "responses", "zen"):
        return ResponsesApiProvider(model=model)
    # auto-detect full /responses endpoint
    base = os.getenv("LLM_BASE_URL", "")
    if base.rstrip("/").endswith("/responses"):
        return ResponsesApiProvider(model=model)
    return OpenAICompatibleProvider(model=model)
