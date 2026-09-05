from __future__ import annotations

SUCCESS_REWARD = 100.0
ERROR_PENALTY = 1.0
ITERATION_PENALTY = 0.5
WARNING_PENALTY = 0.2

def compute_reward(compiled: bool, error_count: int, iteration: int, warnings: int = 0) -> float:
    if compiled:
        return SUCCESS_REWARD - iteration * ITERATION_PENALTY
    return -(error_count * ERROR_PENALTY + iteration * ITERATION_PENALTY + warnings * WARNING_PENALTY)
