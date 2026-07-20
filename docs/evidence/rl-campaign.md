# Evidence — the RL campaign (evasion side)

> Status: complete. Every number regenerates from a committed script into a
> committed artifact; four promotion gates were coded BEFORE their results
> existed and every one of them held. Twin doc (pursuit side): the sibling
> repo's `docs/evidence/rl-campaign.md`.

## Setup / provenance

| Item | Value |
|---|---|
| Board | 7x7, starts (0,0)/(3,3), 14 barriers, 35 moves (signed constitution) |
| Adversaries | `strategy/arena_cop.py`: heuristic TrapCop + DeepTrapCop — the twin's TRAINED cop replayed from copied weight DATA (no cross-repo imports, ADR-0001) |
| Scripts | `scripts/train_rl.py`, `train_deep_rl.py`, `finetune_deep_rl.py`, `train_deep_rl_hidden.py`, `balance_run.py` |
| Artifacts | `results/experiments/{rl_training, deep_rl_training, deep_rl_training_v2_ensemble, deep_rl_finetune, deep_rl_hidden_training, thief_forecast_benchmark, wire_shape_balance}.json` |

## Observed (chronological)

1. **Linear Q-learning**: from-scratch evasion fails flat (0.00 across 600
   episodes — hard exploration: capture ends every episode before the
   first +1); an informed prior amplifies to 1.00. Both curves recorded.
2. **Double-DQN evader v1** vs the twin's learned trap cop: random init
   0.00 -> **1.00/100** (hand-coded ThiefBrain then: 0.49) — full
   counter-policy neutralization of the strongest available adversary.
3. **The knife-edge**: v1 is 1.00 with exact opponent information and
   **0.00 under radius-2 belief noise**; even lr-0.003 warm-start
   fine-tuning collapses the specialist within ~100 episodes (gate held,
   v1 shipped untouched).
4. **Robustness attempts, all gated, all failed**: jitter ensemble
   retrain 0.06; warm-start fine-tune never left 0.00 noisy; lag-1-NATIVE
   training (the actual hidden-play signal) peaked at 0.21 and failed its
   gate. **Three regimes agree: the hidden-information evasion gap is
   structural**, not a training deficiency.
5. **The forecast upgrade (hand brain)**: the book limits barrier
   placement to one step from the cop (p. 37, validated verbatim), making
   the trap game exactly computable one ply ahead. Information-GATED
   adversarial wall forecast: survival vs the learned trap cop **0.50 ->
   1.00/100** with zero regressions; an intermediate ungated version fed
   stale positions collapsed 1.00 -> 0.00 (recorded) — the gate is the
   design, not a caveat.
6. **Wire-shape balance (thief side)**: every cell 32/32 EXCEPT vs the
   learned trap cop at lag-1: **5/32 for both thief brains** — the wire
   shape moves exactly one thing, and it is this.

## Findings

- **Information is the evader's decisive resource**: near-optimal evasion
  runs on exact opponent position; one-move-stale is structurally
  insufficient against near-optimal trapping on this board.
- This is the evidence-backed reason the robust hand-coded ThiefBrain is
  the league default and the deep evader + forecast are exact-information
  weapons (bookletter-locked series, `[strategy] info_mode = "exact"`).
- Gates > judgment: four exciting intermediate results would have shipped
  worse models; the coded gates rejected all four.

## What this does NOT prove

No cross-team brain evaluation (separation rule); the trap cops here are
our own family. Whether a rival's trap cop is stronger or weaker moves the
absolute numbers, not the structural findings.
