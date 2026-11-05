# Changelog

## 0.2.0

- `book(phase, seconds) -> float`: move already-measured seconds from the innermost open phase into `phase`, capped at
  what the donor owns; the totals still add up to `wall()`. For hosts that time a wait after the fact (task-loop `Budget.wait`).

## 0.1.0

- `PhaseClock`: nested phases, per-phase totals, limits, exempt phases and a budget.
