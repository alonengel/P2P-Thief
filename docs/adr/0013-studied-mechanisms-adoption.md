# ADR-0013: Cross-team studied mechanisms — adoption with attribution

Date: 2026-08-22 · Status: accepted

## Context

The league's strongest team (imreeyal — Imree; nine counted 90-30
sweeps) granted us read access to their private cop and thief repos.
Their own code credits OUR doctrine layer as "studied, no code copied"
(their endgame and wall-forecast modules) — the league norm both teams
now follow: **mechanisms may be studied and re-implemented with
attribution; code is never copied; repos are never imported** (course
attribution requirement; ADR-0001's separation rule untouched).

Independently, the 2026-08-22 najamjad series exposed a latch hazard in
our scent trust boundary: their serializer floors sub-0.005 residues to
zero, and consecutive floored frames could latch our gate off for a
whole game (three consecutive law-breaks latch by design, ADR-0010).

## Decision

Three mechanisms adopted, each re-implemented in our own idiom:

1. **Floored-residue tolerance** (`peer/floor_tolerance.py`, ours from
   our own forensics): a transition unsolvable ONLY because cells at or
   under `floor_tolerance_eps` (0.006) read zero is re-solved with
   lawful decay restored; accepted frames record `floored_steps`
   evidence beside `refused_steps`. Validated on the day's sealed data:
   the four live refusals become four floored-notes, zero refusals.
2. **Safe-region compression term** (`strategy/region_race.py`,
   mechanism studied from imreeyal's mobility/containment leaf): the
   pursuit score prices the believed thief's safe ground (two-front BFS
   race) beside distance. `[strategy.pursuit] w_safe_region` — **kept
   DEFAULT OFF (0.0)**. The recorded-tape sweep measured it strongly
   positive on runner classes (55/55 kept, mean conversion t15.7 ->
   t12.0 at 0.15), but the percher mimics collapse under it (0/10, was
   10/10) and the live-dodger drill drops to 6/15: against a stationary
   thief the term rewards containment hovering over walking the landing
   in. Same verdict shape as imreeyal's own w_intercept (positive on two
   classes, negative on a third -> default 0.0, per-pairing option).
   Never arm it against a parking endgame (najamjad parks).
3. **Barrier reserve** (`[strategy.trap] reserve`, studied from their
   contain_reserve): the trap gate never spends the last N walls; the
   endgame solver's proven finishing seal stays affordable. Default 0
   in code; armed at 2 in game.toml — full strategy suite green with it
   (every drill, mimic and tape).

## Addendum (2026-08-22 evening): the k-wall cage forecast — adopted and armed

The one mechanism the original triage skipped ("no observed failure
mode") acquired its failure mode the same day: najamjad's cop now runs
an 11-wall quadrant-cage script (column 3 top-down, then row 3 across —
byte-identical across three revealed games, provably open-loop) that
converted our fielded thief at t27, 0/15 seeds in replay. Adopted as
`strategy/cage_forecast.py` (imreeyal's k-wall pocket forecast,
re-implemented): enumerate every wall-SET of size min(k, live quota)
within `reach` of each believed cop cell — sites near the cop plus
ANCHORED cells (barrier-adjacent or rim: cuts accrete and end at rims),
capped at the 14 nearest the landing — and price the landing by its
worst reachable region. Measured: reach 2 and 3 still die to the script
(belief lag + line-building put the seals beyond them); **k=4 reach=4
survives 5/5** at ~0.9s/turn. Armed in game.toml; the full strategy
suite (every chaser rehearsal, mimic and drill) is green armed — the
doctrine's flee/lethal ranks above the cage term avoid imreeyal's
measured k4-vs-interceptor trade. A plumbing bug found by the red
fixture is fixed alongside: CertifiedThiefBrain now threads its private
table to the doctrine layer (explicit overrides previously fell back to
the config file silently).

## Second addendum (2026-08-23): line-completion + builder-escape

The counted g02 (t31 capture, twice live) taught what the k-forecast
alone cannot see: a LINE-builder's seal cells sit far from the believed
cop until the cop arrives to guard them, and the fresh-flee widening
herds the evader into the very pocket being built. Two mechanisms,
kit-neutral (they read only the public board):

1. **Line completion** (`cage_forecast.line_completion_region`): a run
   of 3+ colinear walls is a DECLARED CUT; every landing is priced as
   if all such runs complete to both rims, quota-clamped. Floors the
   k-forecast from the cut's third wall.
2. **Builder escape** (`cage_forecast.arm_builder_escape`, doctrine
   knob `builder_escape`, default off, armed in game.toml): while a
   declared cut stands, the rank-1 dominant escape re-aims each turn at
   the best cell of the largest completed-projection room. Non-builders
   never trigger it — chaser behavior untouched by construction; the
   full armed strategy suite is green.

Measured: the counted tape that killed the fielded thief 0/15 (old) and
live (twice) now survives 5/5 armed, full clock. HONESTY: offline
replays are open-loop (their chase adapts live); these pin capability,
not the live outcome — recorded beside the fixture. Ordering
experiments that traded separation for room were tried and REVERTED
(each shifted the death by two turns; the committed tuple stands).

## Consequences

- Attribution recorded here and in module docstrings; no code crossed
  repos; parity scope (domain/) untouched.
- Both knobs are config-armed with the sweep evidence quoted beside the
  value — the keep-gate discipline (docs/evidence/cop-strength.md).
- The thief repo carries the floor tolerance identically (twin
  perception); the cop-side pursuit knobs do not apply there.
