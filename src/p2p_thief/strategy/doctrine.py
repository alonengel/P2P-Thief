"""Anti-freeze doctrine over the stealth brain (config: [strategy.doctrine]).

Our own replayed losses exposed a belief-play death mode: with the flee term
capped at safe_distance every distant landing ties, stealth settles the tie
on STAY, the camp saturates our own trail into a max-intensity beacon, and a
patient hunter walls the pocket shut. Three config-gated counter-measures
(keep-gates measured in results/experiments/thief_counter.json):

1. fresh_flee — a LIVE rival trail (reach-decoded age 0/1) lifts the flee
   cap: when the hunter is provably close, real distance outranks stealth.
2. stay_cap — consecutive STAYs are hard-capped while the self-mirror says
   we glow: camping re-pins our own beacon, so exposure + stillness = move.
3. pocket_escape — a NEW rival wall landing near us arms cross-quadrant
   flight for the next turns: seals take several placements; movement wins.
4. forecast — the parent's one-ply worst-wall probe, previously exact-info
   only, runs in belief play as a MIN over the TOP-K belief support cells
   (never the lone argmax, which a split posterior can aim wrong).
"""

import random
import tomllib
from pathlib import Path

from p2p_thief.domain.evidence import decoded_reach
from p2p_thief.domain.pathfind import UNREACHABLE, bfs_distances
from p2p_thief.domain.primitives import Move, Role
from p2p_thief.strategy.movement_deception import StealthThiefBrain

WORST = -(10 ** 9)
FAR = 10 ** 6
KNIFE_RANGE = 2  # inside this believed distance, distance rules absolutely
DEFAULTS: dict = {
    "fresh_flee": True,        # lift the flee cap on live evidence
    "fresh_reach_max": 1,      # 'live' = a reading decoding to reach <= 1
    "stay_cap": True,          # hard-cap consecutive STAYs when exposed
    "max_consecutive_stays": 2,
    "stay_exposure_threshold": 0.35,  # mirror mass near us that arms the cap
    "stay_exposure_radius": 1,
    "pocket_escape": True,     # cross-quadrant flight on a nearby new wall
    "barrier_alert_radius": 2,
    "escape_turns": 3,
    "forecast": True,          # one-ply worst-wall probe over the support
    "forecast_top_k": 3,       # belief support size the MIN runs over
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


def fresh_evidence(scent, fresh_reach_max: int) -> bool:
    """Does the rival's transmitted trail carry a live (reach<=max) reading?"""
    return any(
        (reach := decoded_reach(value)) is not None and reach <= fresh_reach_max
        for row in scent.values()
        for value in row
    )


def top_support(belief, k: int) -> list:
    """The k highest-mass belief cells, mass-then-cell ordered (mass only
    RANKS the support; the forecast MIN below is deliberately unweighted —
    a kill line through any plausible cell disqualifies the landing)."""
    values = belief.values()  # snapshot read: works for any belief-shaped view
    cells = sorted(
        (((row, col), mass) for row, masses in enumerate(values)
         for col, mass in enumerate(masses)),
        key=lambda item: (-item[1], item[0]),
    )
    return [cell for cell, mass in cells[:k] if mass > 0.0]


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
                engine.scent[self.role.rival], self.doctrine["fresh_reach_max"])
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
            flee = FAR if distance == UNREACHABLE else distance
        escape = -self._escape_dist.get(cell, FAR) if escaping else 0
        escapes, region = self._forecast(engine, cell)
        # Knife range first (distance is absolute there), then the wall
        # forecast (a doomed landing loses regardless of distance), then the
        # armed escape steer, then the (possibly uncapped) flee, then ties.
        return (min(flee, KNIFE_RANGE), escapes, region, escape, flee, tie)
