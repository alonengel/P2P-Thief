# Survival certificate: exact escape proof over the cop-belief support (keep-gate)

An endgame booster for the thief, built under a hard keep-gate: **it stays
enabled only if it measurably improves survival.** It failed the gate for a
structural reason mirrored on the cop side; the module ships tested and
correct, default OFF, and this document records the negative result honestly.

## Mechanism (`strategy/endgame.py`, `[strategy.endgame]`)

- **SurvivalCertificate**: memoized worst-case search over (thief cell,
  candidate cop cell, hypothetical-barrier delta, turns left). BELIEF-
  CORRECT: a move is certified only when it survives ALL remaining turns
  against every cop action (moves AND barrier placements, quota-aware) from
  EVERY cop cell holding belief mass ≥ `support_mass_threshold` — the
  rival's true cell is never read (guard-tested). A certificate covering
  fewer than the remaining turns proves nothing, so the horizon gate
  requires `turns_left <= max_horizon_turns`. Compute is hard-capped
  (`node_cap`, `time_cap_ms`); any cap hit defers to the shipped brain.
- **Wiring without touching `thief_brain.py`** (owned elsewhere): the
  `[strategy]` seam points at `CertifiedThiefBrain`, a wrapper that runs the
  certificate as a pre-check and otherwise composes the shipped `ThiefBrain`
  via inheritance. With `enabled = false` the wrapper plays EXACTLY the
  shipped brain. Tunables are read from the private TOML inside the module
  (`certificate_settings`), keeping concurrently-owned files untouched.
- Soundness is engine-adjudicated in `test_endgame_soundness.py`: from a
  certified state, every legal cop reply line must stay certified and end in
  SURVIVAL — the physics, not the search, is the referee.

## Measurement (`scripts/measure_certificate.py`)

90 seeded games/arm (30 seeds x 3-cop pool), same seeds across arms; the
thief always blind (scent-fed `BeliefMap` of the cop). Pool: blind pursuit
cop (the realistic league condition) plus TrapCop and the twin-trained
DeepTrapCop (full information — training ceiling). Results:
`results/experiments/thief_certificate.json` (2026-07-21).

| arm         | survival rate | mean turns survived | certified |
|-------------|---------------|---------------------|-----------|
| shipped     | 0.333         | 20.84               | –         |
| certificate | 0.333         | 20.84               | **0 turns** |

Per cop (identical in both arms): blind_pursuit 1.000 / 35.0 turns; trap
0.000 / 14.0; deep_trap 0.000 / 13.53.

## Why it never fires (root cause)

Two windows must overlap and never do: (1) the certificate only runs in the
last `max_horizon_turns = 5` turns, but the full-information hunters end
games by turn ~14, while against the blind cop the thief survives without
help; (2) the scent-floor belief keeps the cop-belief support at 7–10 cells
(mass ≥ 0.05) essentially every turn (probed on the cop side, same
pipeline), so the `support <= 3` sharpness gate never opens. This is
structural under the current belief pipeline, not a bug.

## Keep-gate verdict

- `[strategy.endgame] enabled = false` (default; module `DEFAULTS` agree).
- The `[strategy] thief_class` seam stays pointed at `CertifiedThiefBrain`:
  with the certificate disabled it is move-for-move the shipped brain, and
  one boolean re-arms an exact, physics-proven escape lock if the belief
  pipeline ever sharpens.

Re-run: `uv run python scripts/measure_certificate.py 30`
