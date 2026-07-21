# Deception by movement: leakage-aware move scoring

Extends the self-mirror lie policy (`docs/evidence/deception.md`) from the
hint channel to the MOVEMENT channel: the thief now also chooses WHERE to
walk by how little the landing would teach the rival.

## Mechanism

- **LeakageEstimator** (`strategy/movement_deception.py`): for each candidate
  legal landing it PREVIEWS the SelfMirror update that landing would cause —
  our next 5×5 emission plus one diffusion step, applied to deep COPIES of
  the mirror's `BeliefMap` and our own `ScentField`, never to live state.
  Stealth score = normalized entropy of the previewed mirror − its mass
  within `exposure_radius` of our true next cell.
- **Probe-verified physics** (not the naive intuition): staying or
  backtracking onto our own scent hotspot leaks the MOST — the mirror's mass
  already sits there. Stepping off a still-hot trail leaves the trail behind
  as a decoy that anchors the rival's posterior away from us.
- **StealthThiefBrain** extends the shipped `ThiefBrain`. Under belief play
  the flee term is capped at `safe_distance`: at knife range distance rules
  absolutely; among landings that keep the believed hunter at least that far,
  stealth (weighted `blend_weight`, blended into the openness tie-break)
  chooses the walk. Under exact-info arena play stealth is a pure final
  tie-break below the trap forecast. The brain's mirror is scent-only (hint
  claims stay owned by the `Deceiver`) and re-syncs once per full turn.
- **Rule compliance is tested, not asserted**: the module consumes own-side
  information only — our scent, our mirror, our belief of the rival —
  never a rival position (`test_movement_deception_consumes_own_side_information_only`,
  AST guard; `test_stealth_score_ignores_the_rival_position`, runtime
  invariance), and every emitted action stays a legal orthogonal step or
  STAY (`test_movement_deception_emits_only_legal_orthogonal_or_stay`).

## Configuration (private `config/game.toml`, `[deception.movement]`)

`enabled=true`, `blend_weight=8.0`, `safe_distance=3`, `exposure_radius=1` —
read via `Config.deception()["movement"]`; the brain loads through the
`[strategy]` seam (`p2p_thief.strategy.movement_deception:StealthThiefBrain`).
Defaults follow the measurement below; `enabled=false` restores the base
brain byte-for-byte (`test_disabled_brain_decides_exactly_like_the_base_brain`).

## Measurement (`scripts/measure_movement_deception.py`, 60 games/arm, same seeds)

Both arms run the full lie policy; ONLY `[deception.movement] enabled`
varies. The cop is BLIND — it hunts through a `BeliefMap` fed by the
thief's scent + hint claims and its brain sees the believed thief cell only.
Results: `results/experiments/movement_deception.json`.

**Primary opposition — belief-driven TrapCop** (the strongest in-repo cop:
BFS pursuit + room-shrinking barriers; captures the base brain 60/60):

| metric | off | on |
|---|---|---|
| survival rate | **0.00** | **1.00** |
| mean turns survived | 16.4 | 35.0 |
| cop tracking error | 1.47 | 1.58 |
| mean mirror exposure | 0.410 | 0.340 |
| lies spent / game | 0.0 | 2.58 |

The off-arm thief flees to maximum distance, pins itself against walls and
is barriered into a pocket before the lie policy ever arms (hence 0 lies —
it dies first). The on-arm keeps mirror mass off its true cell, so the
cop's room-shrinking barriers wall phantom pockets and the clock runs out.

**Secondary opposition — pursuit-only arena cop** (honesty check):
survival dips 1.00 → 0.95 (3 captures/60) because the capped flee term
tolerates a believed distance of 3 against a hunter that never wastes
turns on barriers. In exchange the composition effect is confirmed:
**lies spent fall 3.00 → 1.72 per game** (an already-ambiguous trail
crosses the lie policy's exposure threshold less often), tracking error
1.85 → 1.73, exposure 0.427 → 0.344.

## Verdict — default ON, trade-off recorded

Against the strongest opposition the feature converts certain capture
(0/60) into certain survival (60/60, +10 pts/game); against the weakest it
costs 3 games in 60. Expected league value is clearly positive, so
`enabled = true` ships. The honest caveat stays on record: versus
pursuit-only rivals the cap gives back ~5 pp of survival; if the league
turns out barrier-shy, flip `[deception.movement] enabled = false` (one
config line, no code).

## Tests

`tests/unit/test_strategy/test_movement_deception.py` — entropy extremes;
preview entropy rises moving / mirror concentrates settling; staying on the
hotspot most exposing; backtracking beats leaving the trail is FALSE (and
tested in the true direction); preview mutates nothing; rival-position
invariance; disabled == base brain; `[strategy]` seam load; full-game
integration with the feature ON. Guards in `tests/unit/test_rule_guards.py`
(own-side-only AST + legal-emission runtime); `movement_deception.py` also
joined `DECISION_MODULES` for the rule-25 no-LLM guard.
