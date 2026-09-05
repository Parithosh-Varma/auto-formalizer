import Mathlib

theorem sum_first_n (n : ℕ) :
    2 * (∑ k in Finset.range (n + 1), k) = n * (n + 1) := by
  induction n with
  | zero => simp
  | succ n ih =>
    rw [Finset.sum_range_succ]
    linarith
