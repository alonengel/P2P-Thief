# Deception engineering: the self-mirror lie policy

Replaces the stage-2 honesty coin (`TRUTH_PROBABILITY = 0.5` in
`peer/runtime.py`) with a policy that lies **exactly when it pays**.

## Mechanism

- **SelfMirror** (`strategy/deception.py`): a second belief filter fed ONLY
  by what we ourselves transmit — our own scent trail and our own hint
  claims. It reuses the rival's exact `BeliefMap` pipeline (diffuse → scent
  → hint, the same order `peer/perception.py` applies) pointed at our own
  role, so it estimates what the rival can currently infer about OUR cell.
  `exposure()` = probability mass the mirror puts within a configured
  Manhattan radius of our true cell.
- **DeceptionClock**: lie budget per sub-game + cooldown between lies.
- **DeceptionPolicy.decide_truth**: lie only under the full conjunction —
  exposure ≥ threshold AND the rival (estimated by OUR belief map, never its
  true cell) within the distance threshold AND budget/cooldown allow.
  Otherwise tell the truth: truthful hints keep our credibility priced high
  in the rival's honesty profiler, which is precisely what makes the rare
  lie land (reputation economy). A lie's decoy claim points AWAY from the
  true heading (`decoy_claim`, wired through `build_hint(decoy=...)`).
- Intent flags stay sealed until the end-of-game audit (ch. 5): lying is
  legal and audit-honest; the sealed verdict trail equals the policy's
  decision log exactly.

## Configuration (private `config/game.toml`, `[deception]`)

`max_lies=3`, `cooldown_turns=4`, `exposure_threshold=0.35`,
`opponent_distance_threshold=3`, `exposure_radius=1`,
`baseline_truth_probability=0.5` (control arm for the experiment). Read via
`Config.deception()` — never part of the signed `game.json`.

## Counter-deception

The receiving side is unchanged: the scent-grounded per-hint lie check plus
the cross-game honesty profiler still down-weight a profiled liar's claims
(`test_profiled_liar_hints_get_down_weighted`).

## Tests

- `tests/unit/test_strategy/test_deception.py` — mirror tracks own
  emissions; exposure rises standing still / falls after moving away; decoy
  lie cuts exposure vs a truthful claim; clock budget + cooldown; policy
  lies only under the configured conjunction; config defaults/overrides;
  profiled-liar down-weighting.
- `tests/unit/test_peer/test_runtime.py::test_verdicts_recorded_match_policy_decisions`
  — a full lockstep game completes and the sealed verdicts equal the policy
  decisions on both peers.

## Measurement (`scripts/measure_deception.py`, 60 games/arm, same seeds)

`results/experiments/deception_policy.json`: survival vs the belief-driven
arena cop stays 1.00 in both arms, while the policy spends **3.0 lies/game
against the coin's 17.8** (lies_saved_per_game = 14.82) and even tightens
honest-turn tracking (cop error 1.85 vs 2.19). Same evasion at one-sixth the
lie spend — the credibility we keep is the asset the league profiler prices.
