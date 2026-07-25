# Thief counter-build: anti-freeze doctrine + belief-native forecast (keep-gate A/B)

**Question.** A replayed-loss review of our own logs exposed a belief-play
death family: the capped flee term ties, stealth settles ties on STAY, the
camp saturates our own trail into a max-intensity beacon, and a patient
wall-builder seals the pocket over the quiet turns. Do the four
counter-measures — fresh-flee, stay-cap, pocket-escape, top-k wall
forecast — actually buy survival, each on its own?

**Rig.** `scripts/measure_thief_counter.py`, seeds shared per cop across
arms, 60 games per cop per arm, thief always blind (scent + declared walls
feed its BeliefMap through the real perception order). Cop pool:

- `aged_trap` — AgedBeliefTrapCop: reach-decoded belief, early pounce,
  gain-gated surgical walls (blind; the hunting pattern the counter-build
  targets);
- `blind_pursuit` — CopForArena (blind BFS pursuit of the belief peak);
- `trap` — TrapCop (full-information wall-builder);
- `deep_trap` — DeepTrapCop (full-information Double-DQN, the ceiling).

Arms: `old` = previously shipped StealthThiefBrain; `new` =
DoctrineThiefBrain, all four knobs ON; plus leave-one-out ablations vs the
two wall-capable hunters. Output: `results/experiments/thief_counter.json`.

## Survival (rate / mean turns of 35)

| arm | aged_trap | blind_pursuit | trap | deep_trap |
|---|---|---|---|---|
| old | 0.80 / 28.6 | 0.883 / 31.3 | 0.00 / 15.0 | 0.00 / 8.7 |
| **new** | **1.00 / 35.0** | **1.00 / 35.0** | **0.45 / 28.1** | **0.05 / 13.4** |
| delta | +0.20 | +0.117 | +0.45 | +0.05 |

No regressions anywhere; the new stack survives the belief-led hunter and
the blind pursuer perfectly on these seeds and converts an unwinnable
full-information TrapCop matchup (0.00) into 0.45. The full-information
Double-DQN remains the honest ceiling (0.05): it sees our true cell, which
no amount of belief-side counter-play can fully answer.

## Keep-gates (new minus leave-one-out, survival)

| knob | vs aged_trap | vs trap | verdict |
|---|---|---|---|
| fresh_flee | **+0.50** | **+0.167** | ON — the single biggest lever |
| stay_cap | 0.00 (ceiling) | **+0.35** | ON |
| forecast | 0.00 (ceiling) | **+0.10** | ON |
| pocket_escape | 0.00 | 0.00 | **OFF** — survival-neutral both hunters |

- `fresh_flee` had to be corrected mid-session before it paid: some live
  reading always exists (the rival's own vicinity burns fresh every turn),
  so an unconditional cap-lift fired every turn and the uncapped flee
  corner-chased — max distance from the believed hunter is the far corner,
  exactly where wall cops harvest. Freshness now must sit near US
  (`fresh_alert_radius`) and the widened cap is bounded at 2×safe_distance.
  The smoke A/B that caught this (5 seeds: 1.0 with vs 0.4 without, after
  the same knob measured *negative* in its first form) is why the keep-gate
  loop exists.
- `pocket_escape` is the honest negative: survival identical with and
  without on both wall-capable hunters. It does raise mean turns vs trap
  (28.1 → 23.8 without), but dying later scores exactly like dying early
  under the agreed table, so the default follows the survival currency:
  OFF. The capability stays in the code, config-gated and pinned by the
  pocket-seal juncture test, for a future metagame where seals dominate.

## Decision-point regressions (from the replayed losses)

Two kill junctures are reconstructed as permanent tests
(`tests/unit/test_strategy/test_doctrine.py`):

1. nine camped rounds at (5,1) while the hunter closes (3,2)→(4,2)→(5,2)
   on a live trail — the doctrine brain must move out, never inward;
2. corner camp at (1,5) with walls landing at (2,4) then (1,3) — the
   doctrine brain must leave the pocket (never STAY, never deeper).

Both pin the CAPABILITY (all knobs explicitly ON), so they stay valid
whatever the config defaults say.

**Regenerate.** `uv run python scripts/measure_thief_counter.py 60`
