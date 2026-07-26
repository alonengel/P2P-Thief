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

## The gate re-opened (2026-07-26)

Two corrections, in order.

**The harness was measuring the wrong belief.** `measure_certificate.py` built
its own `BeliefMap` and called `diffuse` + `observe_scent` directly, bypassing
`Perception` - so the belief being scored was not the belief the live peer
decides on. It now observes through `Perception`. The arms were also unequal:
`shipped` ran a bare `ThiefBrain` while `certificate` ran the wrapper over the
doctrine brain, so the old delta conflated two changes. Both arms now use the
shipped class and differ only in the gate.

**The original verdict was about the belief, not the certificate.** It failed
because the cop-belief never sharpened to a provable support inside the
final-turns window (0 certificates / 180 games). With the dwell-plateau pin
(PRD 10) the support sharpens and the proof fires **120 times / 90 games**.

| arm | pool survival | blind pursuit | trap | deep trap | certificates |
|---|---|---|---|---|---|
| certificate OFF | 0.611 | 1.00 | 0.83 | 0.00 | 0 |
| certificate ON | 0.611 | 1.00 | 0.83 | 0.00 | 120 |

**Survival is unchanged, and that is stated rather than dressed up.** The
doctrine brain was already choosing survivable lines on those turns. The gate
is nonetheless flipped ON (`[strategy.endgame] enabled = true`) for what the
measurement cannot show: on the turns it fires, survival is *proven* against
worst-case play - every cop move AND every legal barrier, from every cell
carrying belief mass - instead of merely coinciding with a heuristic. Our arena
pool is three cops we wrote ourselves; the hunter that decides the league is
not in it, and a proof is the only part of the stack that does not care.

Cost is bounded by construction: `node_cap` 20000 and `time_cap_ms` 150.0, and
a cap hit defers to the brain rather than risking the turn deadline.

## Trust boundary: the trail is ASSERTED on the reference wire (ADR-0010)

PRD 10 consumes the rival's transmitted field and boosts one cell 25x, so the
new dependency was audited before it shipped. `smell_grid` rides in the turn
message as a plaintext sibling of `commit`, never inside the sealed payload,
and the end-of-game audit recomputes hashes of SEALED records - so a forged
grid is outside what the audit can see even in principle. The rulebook's
"scent cannot lie" is a property of the replicated-engine wire, where the
field is derived rather than transmitted.

Measured with no check: a decoy plateau drove capture 1.000 -> 0.000; a
saturating flood did the same with zero pins fired. That second case pre-dates
PRD 10 - `observe_scent` alone was already enough to be blinded.

The mitigation holds an asserted trail to the movement model and refuses an
impossible reading whole, latching (`peer/perception.py`). Both directions are
measured (`scripts/measure_trail_forgery.py`):

| arm | detected | false positives |
|---|---|---|
| honest | - | **0.000** |
| decoy stamped where the rival cannot be | 1.000 | - |
| field saturating every cell | 1.000 | - |
| decoy that starts legal and walks a step per turn | **0.000** | - |

Two findings are worth more than the table. First, soundness had to be ranked
above sensitivity twice, because the tighter version measured worse: a rolling
anchor took pool capture 0.983 -> 0.358, and a barrier-aware reachability test
produced 22.5% false refusals on a wall-filled late board (walls arrive during
the game; the rival walked there before the wall existed). The refusal latches,
so one false positive blinds the peer for a whole game.

Second, the last row is a limit, not a gap: a forgery that obeys the movement
model is indistinguishable from a legal trail from the scent channel alone.
The structural fix is protocol-level - seal the grid inside the commit - and
is recorded as a proposal rather than adopted unilaterally, since the wire
shape is a negotiated, hash-locked term.
