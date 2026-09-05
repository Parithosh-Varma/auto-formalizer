from __future__ import annotations
import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    llm_provider: str = os.getenv("LLM_PROVIDER", "mock")
    llm_model: str = os.getenv("LLM_MODEL", "mock-lean-expert")
    llm_base_url: str = os.getenv("LLM_BASE_URL", "")
    llm_api_key: str = os.getenv("LLM_API_KEY", "")
    llm_temperature: float = float(os.getenv("LLM_TEMPERATURE", "0.2"))
    lean_timeout_seconds: int = int(os.getenv("LEAN_TIMEOUT_SECONDS", "30"))
    lean_memory_limit: str = os.getenv("LEAN_MEMORY_LIMIT", "1g")
    lean_cpu_limit: str = os.getenv("LEAN_CPU_LIMIT", "1.0")
    max_refinement_iterations: int = int(os.getenv("MAX_REFINEMENT_ITERATIONS", "8"))
    lean_mode: str = os.getenv("LEAN_MODE", "auto")
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./jobs.db")

    class Config:
        env_file = ".env"

settings = Settings()
