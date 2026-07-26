"""Anti-freeze doctrine over the stealth brain (config: [strategy.doctrine]).

Our own replayed losses exposed a belief-play death mode: the capped flee
term ties, stealth settles ties on STAY, the camp saturates our own trail
into a beacon, and a patient hunter walls the pocket shut. Config-gated
counter-measures (keep-gates: results/experiments/thief_counter.json):

1. fresh_flee — a live rival trail (reach 0/1) NEAR US widens the flee cap.
2. stay_cap — consecutive STAYs capped while the self-mirror says we glow.
3. pocket_escape — a new wall near us arms dominant cross-quadrant flight.
4. forecast — the one-ply worst-wall probe as a MIN over the top-k belief
   support cells (never the lone argmax a split posterior can aim wrong).
5. lethal_gate — a landing ANY support cell can end next turn (occupy it or
   wall it) ranks below every landing none of them can. A widened flee term
   otherwise reads the hunter's own cell as the farthest point of a sealed
   pocket and walks into it; distance must never outrank staying alive.
"""

import random
import tomllib
from pathlib import Path

from p2p_thief.domain.pathfind import UNREACHABLE, bfs_distances
from p2p_thief.domain.primitives import Move, Role
from p2p_thief.strategy.doctrine_signals import fresh_evidence, top_support
from p2p_thief.strategy.movement_deception import StealthThiefBrain

WORST = -(10 ** 9)
FAR = 10 ** 6
DEFAULTS: dict = {
    "fresh_flee": True,        # lift the flee cap on live evidence NEAR US
    "fresh_reach_max": 1,      # 'live' = a reading decoding to reach <= 1
    "fresh_alert_radius": 4,   # ...and the reading lies this close to us
    "stay_cap": True,          # hard-cap consecutive STAYs when exposed
    "max_consecutive_stays": 2,
    "stay_exposure_threshold": 0.35,  # mirror mass near us that arms the cap
    "stay_exposure_radius": 1,
    "pocket_escape": False,    # keep-gate: survival-neutral on both measured
    #                            hunters (only mean turns moved, which the
    #                            scoring does not pay) - capability stays
    #                            tested, default follows the measurement
    "barrier_alert_radius": 2,
    "escape_turns": 3,
    "forecast": True,          # one-ply worst-wall probe over the support
    "forecast_top_k": 3,       # belief support size the MIN runs over
    "lethal_gate": True,       # an end-able landing loses to any safe landing
}


def doctrine_settings(private: dict | None = None) -> dict:
    """[strategy.doctrine] merged over DEFAULTS (type-coerced); private=None
    reads config/game.toml so the seam-built brain stays config-driven."""
    if private is None:
        path = Path(__file__).resolve().parents[3] / "config" / "game.toml"
        private = tomllib.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    block = private.get("strategy", {}).get("doctrine", {})
    merged = dict(DEFAULTS)
    for key, default in DEFAULTS.items():
        if key in block:
            merged[key] = type(default)(block[key])
    return merged


class DoctrineThiefBrain(StealthThiefBrain):
    """StealthThiefBrain + the three counter-camping terms.

    Belief-play score: (flee, escape, stealth-tie) with a banned-STAY
    sentinel; exact-info arena play passes through to the parent untouched.
    """

    def __init__(self, role: Role, rng: random.Random,
                 tuning: dict | None = None, doctrine: dict | None = None) -> None:
        super().__init__(role, rng, tuning)
        self.doctrine = doctrine if doctrine is not None else doctrine_settings()
        self._stays = 0
        self._known_barriers: frozenset | None = None
        self._escape_until, self._escape_dist = -1, {}
        self._fresh = self._ban_stay = False
        self._support: list = []

    def _observe_threats(self, engine) -> None:
        """Pocket alert: a NEW rival wall within the alert radius of us arms
        flight toward the mirrored quadrant for the next escape_turns."""
        barriers = engine.board.barriers
        known, self._known_barriers = self._known_barriers, barriers
        if known is None or not self.doctrine["pocket_escape"]:
            return
        me, grid = engine.positions[self.role], engine.board.grid_size
        radius = self.doctrine["barrier_alert_radius"]
        if not any(abs(b[0] - me[0]) + abs(b[1] - me[1]) <= radius for b in barriers - known):
            return
        mirrored = (grid - 1 - me[0], grid - 1 - me[1])
        candidates = [mirrored] + [m.applied_to(mirrored) for m in
                      (Move.N, Move.S, Move.E, Move.W)]
        passable = [cell for cell in candidates if engine.board.is_passable(cell)]
        if passable:
            self._escape_until = engine.turns_completed + self.doctrine["escape_turns"]
            self._escape_dist = bfs_distances(engine.board, passable[0])

    def _stay_banned(self, engine) -> bool:
        if not self.doctrine["stay_cap"] or self._stays < self.doctrine["max_consecutive_stays"]:
            return False
        exposure = 1.0 if self.mirror is None else self.mirror.exposure(
            engine.positions[self.role], self.doctrine["stay_exposure_radius"])
        return exposure >= self.doctrine["stay_exposure_threshold"]

    def decide(self, engine, belief=None) -> dict:
        if belief is not None:
            if self.doctrine["stay_cap"]:
                self._sync_mirror(engine)  # exposure needed even if stealth off
            self._observe_threats(engine)
            self._fresh = self.doctrine["fresh_flee"] and fresh_evidence(
                engine.scent[self.role.rival], self.doctrine["fresh_reach_max"],
                engine.positions[self.role], self.doctrine["fresh_alert_radius"])
            self._ban_stay = self._stay_banned(engine)
            self._support = (top_support(belief, self.doctrine["forecast_top_k"])
                             if self.doctrine["forecast"] else [])
        action = super().decide(engine, belief)
        if belief is not None:
            self._stays = self._stays + 1 if action.get("move") == "STAY" else 0
        return action

    def _forecast(self, engine, cell) -> tuple:
        """Worst wall reply over the believed support cells (elementwise MIN
        of the parent's exact one-ply probe): room, not distance, is life."""
        worst = None
        for rival in self._support:
            escapes, region = self._after_best_wall(engine, cell, rival)
            worst = (escapes, region) if worst is None else (
                min(worst[0], escapes), min(worst[1], region))
        return worst if worst is not None else (0, 0)

    def _score(self, engine, cell, distances, cop, exact) -> tuple:
        base = super()._score(engine, cell, distances, cop, exact)
        if exact:
            return base  # full-information arena play: parent forecast rules
        flee, tie = base
        escaping = engine.turns_completed < self._escape_until
        if not (self._fresh or self._ban_stay or escaping or self._support):
            return base  # doctrine inert this turn: exactly the parent brain
        if self._ban_stay and cell == engine.positions[self.role]:
            return (WORST,) * 6
        if self._fresh:
            distance = distances.get(cell, UNREACHABLE)
            distance = FAR if distance == UNREACHABLE else distance
            flee = min(distance, 2 * self.safe_distance)  # real flight range
        escape = -self._escape_dist.get(cell, FAR) if escaping else 0
        escapes, region = self._forecast(engine, cell)
        # A (0, 0) forecast means some believed hunter ENDS us on this landing
        # next turn — it occupies the cell or walls it (rules 46/47). That is
        # not a tie-break, it is disqualifying: rank it under every landing no
        # support cell can reach, however much closer that landing looks.
        gated = self.doctrine["lethal_gate"] and (escapes, region) == (0, 0)
        # Armed escape DOMINATES (a forming seal makes distance-to-the-
        # believed-hunter the wrong metric — the far corner is the trap);
        # then survivability; then the flee term (widened, still bounded,
        # when the hunter is provably near), then the wall forecast as the
        # tie-break among equally-safe landings, then the stealth ties.
        return (escape, 0 if gated else 1, flee, escapes, region, tie)
