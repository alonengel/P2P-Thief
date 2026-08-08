# P2P-Thief — the Thief agent

Autonomous **Thief** agent for the distributed Cops-and-Robbers game, played
peer-to-peer over FastMCP with **no central server and no judge**. Integrity comes from
mathematics: a SHA-256 commit-reveal protocol seals every half-turn, and a mutual
end-of-game audit exposes any rewriting of history.

> **Sibling repository** (the Police/Cop agent of team `anrbj666`):
> **https://github.com/alonengel/P2P-Police**

Team: Alon Engel, Renat Karimov · Course: Orchestration of AI Agents (Univ. of Haifa)

---

## Part I — User manual

### Installation

Requirements: Python ≥3.13, [uv](https://docs.astral.sh/uv/). Two supported setups:

```bash
# A) fresh machine
git clone https://github.com/alonengel/P2P-Thief && cd P2P-Thief
uv sync                      # creates .venv, installs locked deps

# B) full twin-repo workspace (recommended for development)
git clone https://github.com/alonengel/P2P-Thief
git clone https://github.com/alonengel/P2P-Police  # side by side
```

Troubleshooting: `port 8801 is busy` → another peer instance is alive; stop it or
change `[network].my_port` in `config/game.toml`. `unsupported schema_version` →
your `game.json` generation is unknown to `shared/version.py` — negotiate a
supported one. Gmail errors → see `docs/DEPLOYMENT.md` (tokens expire!).

### Usage

```bash
uv run p2p-thief peer                 # play one game vs the configured opponent
uv run p2p-thief peer --gui           # + live local-truth view (belief heatmap)
uv run p2p-thief peer --gui --gui-screenshot assets/live.png
uv run p2p-thief verify-log --log results/log_<game>.json   # Verified OK / TAMPERED
uv run p2p-thief replay --log results/log_<game>.json       # visual replay witness
uv run p2p-thief replay --log ... --screenshot out.png      # save the witness PNG, then exit
uv run p2p-thief --version

# Series / league operations (docs/LEAGUE_RUNBOOK.md; wire shape from config or --wire-shape):
uv run p2p-thief peer --sub-game N [--resume|--sparring|--counted]
uv run p2p-thief series-result --game-id <id> --results-dir results --results-dir ../P2P-Police/results
uv run python scripts/league_series.py --sub-games "2,4,6" [--counted]   # our windows + auto-close
uv run python scripts/verify_pair.py <log_a.json> <log_b.json>           # third-party pair verdict

# Research reproduction (RL campaign - see Part II section 3 + PRD_08):
uv run python scripts/train_rl.py          # linear Q-learning, both curves
uv run python scripts/train_deep_rl.py     # Double-DQN evader vs learned trap cop
uv run python scripts/finetune_deep_rl.py  # gated warm-start fine-tune (knife-edge)
uv run python scripts/run_sensitivity.py   # OAT sensitivity experiments
```

Cross-repo match on one machine: `powershell -File ../run_cross_match.ps1`.
Public play + Gmail setup: `docs/DEPLOYMENT.md`. League duties: `docs/LEAGUE_RUNBOOK.md`. Rival teams: start at `docs/ONBOARDING.md` — play against us in 30 minutes.

### Configuration

| File | Role |
|---|---|
| `config/game.json` | THE signed constitution — every agreed value (Appendix ו). Byte-identical on both sides, SHA-256-locked at negotiation; fixed values enforced at load |
| `config/game.toml` | Private: identity, ports, opponent URL, `[strategy]` brain override, `[trash_talk]` provider, `[email]` mode. JSON always overrides TOML |
| `config/rate_limits.json` | Gatekeeper triad limits per service (versioned) |
| `config/games/` | Archived per-game configs (rules 3-4) |

### Quality gates & contribution

TDD; ruff zero-violations; coverage ≥85% (branch); **≤150 code lines per file**
(`scripts/check_line_cap.py`); twin physics parity (`scripts/check_physics_parity.py`);
conventional commits; pre-commit hooks + CI enforce all of it. Five
disqualification-class book rules are additionally enforced as CI
invariants (`tests/unit/test_rule_guards.py`), and every substantive claim
in this README regenerates from a committed script into a committed
artifact — the narratives live in [docs/evidence/](docs/evidence/)
(setup / provenance / observed / what-it-does-NOT-prove, per experiment). Secrets never enter
the repo (`.gitignore` + gitleaks in CI; `.env-example` shows the shape).

---

## Part II — Academic report

### 1. The Dec-POMDP model

The race is a decentralized partially observable Markov decision process
⟨n, S, {Aᵢ}, P, R, {Ωᵢ}, O, γ⟩:

- **n = 2** — every decision is weighed against a single *rational rival*, not nature.
- **S** — cop and thief coordinates, the barrier layout, and both dynamic scent
  fields. Brute-force enumeration is infeasible — the fact that drove our
  algorithm choices (§3).
- **{Aᵢ}** — movement (orthogonal + STAY), *construction* (the cop's barriers),
  and *communication* (≤15-word hints that may lie): physics and psychology in
  one action space.
- **P** — deterministic physics that both sides must compute identically; with no
  server, P **is** the signed `game.json` + the parity-locked `domain/` code.
- **R** — the fixed scoring table (capture 20/5, survival 5/10, tie 2).
- **{Ωᵢ}** — each side observes only its own state, the rival's decaying scent
  field, and the rival's hint. Our belief map (§3) lives here.
- **O** — the observation function is **the only channel of deception**: hints
  bend O, scent cannot (it is an unforgeable byproduct of movement).
- **γ** — implicit long-horizon patience: barrier traps pay off many turns later.

### 2. FastMCP orchestration dilemmas

Each peer is simultaneously an MCP **server** (four dumb-door tools: `negotiate`,
`receive_turn`, `submit_audit`, `receive_control` → thread-safe inboxes) and a
**client** to the opponent's single known URL. Design decisions and their whys:

- **Replicated engines, lockstep application.** Both sides run the same physics
  and apply both half-turns locally; end-state digests prove convergence.
- **Persistent sessions.** Per-call MCP sessions die through tunnels
  ("Session terminated" — learned live, `docs/DEPLOYMENT.md`); one long-lived
  session per opponent, rebuilt only on failure.
- **Deadlines everywhere** (rule 6): every awaited message and every in-flight
  call is bounded; lapses route the strict turn state machine
  (WAITING→COMPUTING→COMMITTING→AWAITING_REVEAL→VERIFYING) into terminal
  TECHNICAL_LOSS instead of deadlock.
- **Gatekeeper + Orchestrator** (ch. 8/9): ALL external calls (LLM, Gmail) pass
  one doorway — token bucket, daily quota, DOS circuit breaker; the SDK facade
  is the single entry to business logic.
- **Commit order is negotiated** — an explicit agreement field, because two
  correct-but-different implementations would deadlock forever.
- **One client, two registered wire shapes** (`[network] wire_shape` /
  `--wire-shape`). The book self-contradicts: ch. 5's per-step reveal hands
  both replicated engines the rival's true position, while the formal
  model's Ωᵢ excludes it from observations (documented: ADR-0006/0007). We
  ship both readings behind one negotiated lock — the default **bookletter
  lockstep** (replicated engines, per-step reveals, `config_sha256`
  agreement) and the **reference-v3 hidden mode** (`src/p2p_thief/wire/`,
  PRD_09): one commit-only TurnMessage per half-turn, the move sealed until
  the audit, the rival's position structurally absent (`OwnState` carries
  no field for it), capture claim-mediated, and the audit replayed on Board
  physics because an engine replay would false-flag honest hidden games
  (ADR-0008). Each shape speaks its own REGISTERED handshake — bookletter
  by config hash, reference-v3 by the literal flat-terms form (14-key
  `terms` + `nonce` + `signature = SHA256(canonical(terms)|nonce)`) — and
  the choice itself is a locked model: `wire_shape_sha256` over the
  published `config/wire_shape_lock.json`, refusal only when both peers
  declare and differ.
- **Hostile reality, drilled not hoped.** Chaos drills D1-D4 plus a LIVE
  tunnel kill/heal with committed JSONL evidence
  (`docs/evidence/chaos-drills.md`, `docs/evidence/drills/`);
  per-half-turn crash-resume on BOTH wire shapes (`peer --resume`; drill
  recoveries 0.044 s geometric / 0.066 s hidden, mutual audits Verified OK
  after the restart); anti-stall rails for shared-address reality —
  dedup-safe agreement re-push, bystander-tolerant pairing (a wrong-window
  or same-role greeting is "wrong game, not you": logged and tolerated
  while the one overall deadline still judges), post-settlement inbound
  refusal (a dying peer must not swallow the rival's next greeting) and a
  connect-probe orphan-port guard; and structural email interlocks — the
  league/lecturer address is reachable only when a counted game is doubly
  armed (`[email] counted = true` AND `--counted`), a send posture proves
  OAuth-token deliverability BEFORE window 1, and `--sparring` refuses a
  warm-up file carrying tuned play or an armed email path
  (`shared/interlock.py`).
- **The three classic orchestration failures** (course L09 framing) and our
  antidotes: *task duplication* — impossible, roles are disjoint by
  construction; *contradictory outputs* — replicated engines + end-state
  digests + mutual audit force one truth; *convergence failure* — strict
  turn alternation with deadlines makes unbounded loops unrepresentable.
  (MCP is the project's mandated protocol; A2A and ACP are the complementary
  standards worth knowing for lifecycle handoff and zero-trust fleets.)
- **A cross-team protocol contribution.** Reviewing a rival league team's
  draft interop protocol, we identified that per-step commits — strong
  against editing one step — leave a whole log re-forgeable offline, and
  designed the fix: a `prev`/`prev_recv` hash interlock chaining both
  sides' records into one tamper-evident DAG, making earliest divergence
  provable from the two committed logs. The draft adopted it as its flagship
  opt-in enhancement (design credited to `anrbj666`). We deliberately do NOT run
  it in counted games: it modifies the sealed record — the most
  disqualification-sensitive layer (rule 19) — for a guarantee the book does
  not require and only an opting-in opponent benefits from. The same review
  exchange surfaced the reference's byte-forms we aligned to (ADR-0004) and
  its settlement-signature quirk our conformance suite now pins.

#### Cross-team verification

- **The pair verifier** (`report/pair_verify.py`, CLI
  `scripts/verify_pair.py`) — league tooling for ANY third party: given
  both sides' log artifacts of one game it re-runs the ch. 7 replay per
  side, then cross-checks that the two sealed views describe a single game
  (same `game_uid`, same end digest, every record one side sealed
  byte-equal to what the other received — commit equality is the anchor).
  Re-verifiable on the committed twin logs of the hidden-wire game g03:

  ```bash
  uv run python scripts/verify_pair.py results/log_anrbj666-vs-anrbj666_g03.json \
    ../P2P-Police/results/log_anrbj666-vs-anrbj666_g03.json    # overall : Verified OK
  ```

- **League record: TWO counted games, both filed, both won** (rule 52's
  minimum of two counted games vs different teams — satisfied):
  - `anrbj666-vs-imreeyal` — **90-30, 6-0**, filed 2026-08-04
    (league report `19fc9a53c7f458f9`; evidence commit
    [`602a4c2`](https://github.com/alonengel/P2P-Thief/commit/602a4c2));
  - `anrbj666-vs-vibecode` — **75-35, 5-1**, filed 2026-08-08
    (league report `19fe2cdf49a26b0d`; evidence commit
    [`8a0f97a`](https://github.com/alonengel/P2P-Thief/commit/8a0f97a)), after six uncounted
    friendlies that converged both stacks to zero-delta artifact diffs.
  Both series: 6/6 audits `Verified OK`, `mutual_agreement.confirmed:
  true` with byte-identical hashes across the two teams' independently
  emitted results, diversity flag earned on both first meetings. Browse
  the artifacts: working set in [results/](results/) +
  [config/games/](config/games/); immutable per-team archives with byte
  manifests in [docs/evidence/counted_games/](docs/evidence/counted_games/)
  (archive commit [`9f41b7a`](https://github.com/alonengel/P2P-Thief/commit/9f41b7a)).

- **Real games against a rival league team** (2026-07-24, T-protocol
  window): warm-up games over the public tunnels ran the full 35 turns to
  survival with audits **Verified OK on both sides** — the registered
  flat-terms handshake, the per-sender cadence, commit-aligned reveals
  with the rival's step-0 spec record tolerated, and the reference-exact
  audit envelope, all live; `digest_match` reports `null` between two
  per-team digest constructions (not-comparable — never falsely false). A
  full six-sub-game rehearsal of the counted format followed — roles
  alternating, truthful declarations, every audit Verified OK, the
  predicted 47-47 structural tie (`series_tie: true`), and the ONE
  series-report email fired through the gatekeeper. The rehearsal was
  mutually discarded (never counted), so its evidence lives outside the
  aggregation path by construction —
  [docs/evidence/discarded-series/](docs/evidence/discarded-series/)
  (sub-game logs + declaration + the reference-conformant series result) —
  and stays re-verifiable per side:

  ```bash
  uv run p2p-thief verify-log \
    --log docs/evidence/discarded-series/log_anrbj666-vs-imreeyal_g01.json   # Verified OK
  ```

  (The byte-level PAIR cross-check is defined over two logs sealed under
  ONE schema, like our committed twin pairs; a rival half sealed under its
  own per-team schema is judged by the schema-agnostic commit criterion
  plus the derivable-rule tiers instead — never called tampered for its
  schema.)

- **Convergence day against the rival team (2026-08-03).** Four full
  six-window friendly series over the public tunnels in a single day,
  every audit **Verified OK on both sides**, the two teams' report mails
  cross-diffed after each window until the final diff returned **zero
  findings**. What converged, per the book's attached example set and the
  grader's Moodle instructions (ADR-0012 + its three addenda): a sealed
  `step_zero` record opens every log (the commit id declared through TWO
  channels — negotiate identity and sealed record — with any mismatch a
  recorded finding); commit columns are role-aware per window; the
  `final_result` carries the book-attached league fields keyed on the
  counted arming (a friendly fabricates no counted record); the ONE
  series email attaches the result file per the course chatbot's ruling;
  and `mutual_agreement.sha256` uses the reference's symmetric-outcome
  scope — **byte-identical across the two teams' independently emitted
  files, verified live**. The full negotiation record: `docs/PROMPTS.md`
  rounds 1-6.

- **The settlement guard (rule 35).** `series-result` folds sub-game logs
  (pooling BOTH role repos' results dirs) into the reference-conformant
  series result and **refuses** to emit unless every sub-game
  1..num_games is covered by a settled, audit-clean log under one
  consensus `game_uid` — wrong-window or wrong-`num_games` logs are
  excluded BY NAME, never silently, and a refused series never emails
  (`sdk/series.py`, `report/series_doc.py`, ADR-0009).

### 3. The chosen strategy

Moves are **always pure Python** (the LLM only writes banter). The evasion
core, `strategy/thief_brain.py` — the base of the shipped brain stack (see
the inventory at the end of this section):

1. **Bayesian belief map** over the cop (parity-locked `domain/belief.py`):
   per turn — movement diffusion × scent likelihood × hint likelihood.
2. **Scent-grounded lie detection** (book ch. 4): a claimed region whose
   freshest trail falls below the (1−ρ)·0.9 ≈ 0.81 expectation flips the hint's
   weight — belief re-aims at the *evidence*, not the words.
3. **Survival-clock evasion**: maximize the barrier-aware BFS distance from the
   cop's believed position — true escape distance, not Manhattan optimism.
4. **Corner aversion**: ties break toward open ground (more passable
   neighbors), because a cornered thief is a captured thief (rule 47) and
   every barrier shrinks the safe area.
5. **One-ply adversarial wall forecast** (exact-information play only): the
   book limits barrier placement to one step from the cop's own cell (p. 37),
   so every candidate landing is scored by the escapes/region surviving the
   cop's BEST legal wall next turn, plus wall-distance aversion (trap cops
   harvest wall-huggers). Measured effect: survival vs the learned trap cop
   0.50 → **1.00** over 100 games with zero regressions
   (`results/experiments/thief_forecast_benchmark.json`). The forecast is
   deliberately GATED to exact information — fed a stale believed cell it
   dodges phantom walls and dies (measured 1.00 → 0.00 vs the heuristic trap
   cop) — so belief-mode play stays conservative: an information-aware
   strategy, not a blanket one.

6. **Dwell-plateau localization** (`domain/evidence.py`, PRD 10): the book's
   own update rule drives a re-emitted cell to `delta / rho`, so 21 of the 25
   kernel offsets saturate at the clamp and 4 never do — an agent that stands
   still stamps its own kernel window on the board. Per-cell reach-decoding
   cannot read it (every saturated cell decodes reach 0, so the likelihood ties
   flat and the peak drifts); fitting the *shape* back inverts it to the
   emitter's own cell, taking localization from **7% exact / 2.42 cells** to
   **89% exact / 0.11 cells**. It abstains unless the shape is unambiguous.
7. **`lethal_gate`** (`strategy/doctrine.py`): a landing that *any* believed
   hunter can end next turn — occupy it, or wall it under the law of barriers
   — ranks below every landing none of them can, however much farther the
   doomed one looks. This closed the one line that was still killing us: herded
   into a corner with the exits walled, the widened flee term ranked the
   hunter's *own cell* as the farthest landing, because inside a seal distance
   is measured the long way round. Survival **0.900 → 1.000** over 150 games.

**The mirror obligation.** PRD 10 cuts both ways: the decode we run on a rival
runs on us, and our own trail saturates identically. That is why
`[strategy.doctrine] stay_cap` stays enabled although its keep-gate measures
*neutral* — we hold a proof that camping is readable, so a neutral knob today
is cheap insurance against an opponent who implements the same decode
tomorrow. Symmetric analysis of one's own observability is the most
transferable idea in this project: **camping is self-reporting.**

Measured: evasion survives a random cop ≥20/25 (blind: ≥15/25) and, in the
blind cross-repo match, ran the full 35-turn clock against the pursuit twin
that had captured it in 13 turns under full information — **uncertainty is the
thief's best weapon, working exactly as the rulebook intends**.

**Reinforcement learning (optional path, implemented):** a linear-FA
Q-learner (`strategy/rl_brain.py`, TD(0), ε-greedy) exposes a genuinely
interesting asymmetry, and BOTH sides of it are now recorded runs in
`results/experiments/rl_training.json` and overlaid in the curve below:
**from-scratch evasion fails** (flat 0% survival across all 600 episodes,
red — one corner mistake is terminal and capture ends every episode before
the first +1 is ever observed: a classic hard-exploration problem), while
from an informed prior encoding the heuristic's features RL **maintains 1.00
survival and amplifies exactly the right weights** (distance 1.0→2.4,
escape-openness 0.5→1.5; 50-game evals, dedicated eval RNG). Pursuit, by
contrast, trains from zero to 1.00 (see the twin repo) — chasing is easy to
learn, escaping must be taught:

![RL learning curve](assets/rl_learning_curve.png)

Loadable via `[strategy] thief_class = "p2p_thief.strategy.rl_brain:LinearQBrain"`
(exercised end-to-end by `tests/unit/test_strategy/test_rl_brain.py`);
the league default is the stealth-scored heuristic stack, not the RL path
(see the inventory below).

**Deep RL closes the arms race (`strategy/rl_deep.py`).** The twin repo's
Double-DQN cop *learns barrier trapping* — 0.74 capture vs a perfect
movement-evader, tying its hand-engineered tactics (0.73). That makes the
linear evasion brain's training regime obsolete: it never faced a barrier in
training. So the thief now trains a **Double-DQN evasion MLP
(9→tanh(12)→1, pure Python) against exactly that learned trap cop** —
`strategy/arena_cop.py` replays the twin's trained cop from copied weight
*data* with locally duplicated logic (mirrored-twin rule: no cross-repo
imports, no shared live state; static duplication is the sanctioned
mechanism). Features track precisely what traps destroy: escape routes,
reachable region, wall distance, barrier density, chase parity. Result,
100 held-out games vs the learned trap cop:

| Policy | Survival vs learned trap cop |
|---|---|
| Random-init net (episode 0) | **0.00** |
| Hand-coded ThiefBrain | **0.49** |
| **Learned Double-DQN thief (best checkpoint)** | **1.00** |

![Deep RL curve](assets/deep_rl_curve.png)

The learned evader **fully neutralizes** the adversary that halves the
hand-coded brain's survival — with the honest caveats recorded in
`results/experiments/deep_rl_training.json`: the 1.00 is against a *fixed*
deterministic adversary (counter-policy exploitation, not a universal
guarantee), and the training curve collapses late (1.00 → 0.20, catastrophic
forgetting) which is why the shipped weights are the best-eval checkpoint.
The heuristic stack stays the league default; the deep brain loads via
`[strategy] thief_class = "p2p_thief.strategy.rl_deep:DeepQBrain"`.

**Round 2 — the specialist beats the generalist.** The twin retrained its
cop against our counter-evader (ensemble + belief-noise, its v3): it kept
0.74 vs the perfect evader but **still captures our v1 evader 0.00** —
verified independently from this repo: **v1 survives cop v3 at 1.00 over
100 games**. Our own attempt to make the evader *robust* the same way
(ensemble of trap cops + belief-noise,
`results/experiments/deep_rl_training_v2_ensemble.json`) **collapsed to
0.06** — a deliberately recorded negative result: robustness training is
not a free lunch, and the shipped weights remain the v1 specialist. A
follow-up warm-start fine-tune (from v1, lr 0.003, hard promotion gate —
`results/experiments/deep_rl_finetune.json`) sharpened the finding into a
knife-edge theorem-in-practice: v1 survives **1.00 with exact opponent
information and 0.00 under radius-2 belief noise**, and even the gentlest
retraining collapses the specialist within ~100 episodes. A third gated
attempt — lag-1-NATIVE training on the actual hidden-play signal
(`deep_rl_hidden_training.json`) — peaked at 0.21 and failed its gate too:
three independent regimes now agree the gap is structural. Evasion at this
level *requires* exact information — which is the evidence-backed reason
the robust hand-coded heuristic stack stays league default. Net outcome of
the two-round arms race: the evader holds the structural advantage at this
barrier budget, exactly as pursuit-evasion theory predicts.

**What actually ships (the committed `config/game.toml`).** The `[strategy]`
seam points at `p2p_thief.strategy.endgame:CertifiedThiefBrain` — a
survival-certificate pre-check wrapped around `StealthThiefBrain`
(`strategy/movement_deception.py`), which extends the hand-tuned ThiefBrain
with leakage-aware move scoring (`[deception.movement] enabled = true`). So
the league default is the **stealth-scored brain**: it previews what each
candidate landing would teach the rival's belief filter and walks where it
leaks least. The certificate pre-check was first keep-gated **OFF**
(0 certificates fired across 180 measured games — the scent-floor
cop-belief never sharpened inside the final-turns window); after the
dwell-plateau pin sharpened the cop-belief it was **re-measured and
re-opened: ships ON** (`[strategy.endgame] enabled = true`) — 120
certificates across 90 games, survival unchanged (0.611 both arms), kept
because a *proven* escape beats a heuristic that merely agrees, against
unknown hunters (both readings preserved in
`docs/evidence/thief-certificate.md`). The loadable-brain inventory:

| Module (`[strategy] thief_class = ...`) | Brain | What it does · measured | Status |
|---|---|---|---|
| `strategy/thief_brain.py` | `ThiefBrain` | hand-tuned evasion core: belief map + BFS flee + wall forecast | base of the default stack |
| `strategy/movement_deception.py` | `StealthThiefBrain` | deception by movement — the trail as a decoy; survival vs the strongest in-repo cop 0.00 → **1.00** (`docs/evidence/movement-deception.md`) | **ON** (inside the default stack) |
| `strategy/endgame.py` | `CertifiedThiefBrain` | exact worst-case survival certificate over the cop-belief support, run as a pre-check | default entry point; certificate **ON** (re-opened: 120 fires / 90 games post-plateau-pin) |
| `strategy/rl_brain.py` | `LinearQBrain` | linear-FA Q-learning evasion (informed prior) | opt-in |
| `strategy/rl_deep.py` | `DeepQBrain` | Double-DQN evader trained vs the learned trap cop | opt-in |

### 4. Screenshots (mandatory evidence, from real cross-repo games)

| Live GUI — local truth only | Replay witness |
|---|---|
| ![Live belief map](assets/live_belief_map.png) | ![Verified OK](assets/replay_verified_ok.png) |
| Belief heatmap (deeper red = higher P(cop)), ME marker, turn banner, rival's hint | Green **Verified OK (70 sealed steps)** over the reconstructed game |

`verify-log` on the same log: genuine → `Verified OK`; one rewritten move →
`TAMPERED` (exit 1).

The same witness over the **hidden wire**: the reference-v3 self-play game
g03 (`results/log_anrbj666-vs-anrbj666_g03.json`, `"wire_shape":
"reference"`) replayed and re-verified — the reconstruction applies both
revealed halves on Board physics (ADR-0008), and the twin repos' two logs
of this one game pair-verify `Verified OK` (§2, Cross-team verification):

![Hidden-wire replay Verified OK](assets/replay_hidden_verified.png)

### 5. Quality mapping (ISO/IEC 25010)

Functional suitability — milestone-gated PRDs 01-09, 770 tests, branch
coverage 94.1%. Reliability — deadlines, watchdog-style FSM exits, session
rebuilds, chaos drills + crash-resume on both wire shapes,
bystander-tolerant pairing, orphan-port guard, 20-seed self-play.
Performance — template provider plays whole series at 0 LLM tokens. Security —
send-only OAuth scope, secrets outside the repo, gitleaks CI, commit-reveal
integrity, doubly-armed lecturer-address interlock. Maintainability — SDK layering, ≤150-line files, per-mechanism PRDs,
ADRs incl. documented book contradictions. Portability — uv-locked, stdlib+httpx
core. Compatibility — byte-locked shared config + golden physics vectors across
twins. Usability — one-command flows, local-truth GUI, actionable errors.

### 6. Course anchors

L09 (two agents over MCP calling external tools) → the peer architecture;
L11 (stigmergy, no central control) → the scent/belief loop; L05 (orchestrator,
skills, observability) → SDK + gatekeeper + GUI/replay; L02/L04/L08 → the
verbal-layer providers (template/Ollama/Claude/OpenRouter).

## License & credits

MIT — see [LICENSE](LICENSE). Architectural patterns studied from the official
course example repo (rmisegal/Game-P2P-Cop-Chase) under its educational terms;
where they differ, the rulebook and its Appendix ו govern.
