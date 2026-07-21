"""Deception by movement: pick landings that keep the self-mirror flat.

For each candidate landing the estimator PREVIEWS the SelfMirror update
that landing would cause — our next emission + one diffusion step, applied
to COPIES of the mirror's BeliefMap and our own ScentField, never to live
state — and scores stealth = normalized entropy of the previewed mirror
minus its mass near our true next cell. Probe-verified direction: staying
or backtracking onto our own scent hotspot leaks the most (the mirror's
mass already sits there); stepping off a still-hot trail leaves the trail
behind as a decoy that anchors the rival's posterior away from us.

Own-side inputs ONLY: our scent field, our mirror, the candidate landings
the base brain already scores — never any rival position (guarded by
tests/unit/test_rule_guards.py). Tunables live in game.toml under
[deception.movement]; the brain loads via the [strategy] seam:
    [strategy] thief_class = "p2p_thief.strategy.movement_deception:StealthThiefBrain"
"""

import copy
import math
import random
from pathlib import Path

from p2p_thief.domain.belief import BeliefMap
from p2p_thief.domain.engine import GameEngine
from p2p_thief.domain.primitives import Cell, Role
from p2p_thief.strategy.deception import SelfMirror
from p2p_thief.strategy.thief_brain import ThiefBrain

_CONFIG_DIR = Path(__file__).resolve().parents[3] / "config"  # cwd-independent


def movement_tuning() -> dict:
    """[deception.movement] from the committed private config (seam default)."""
    from p2p_thief.shared.config import Config

    return Config.load(_CONFIG_DIR).deception()["movement"]


def entropy(belief: BeliefMap) -> float:
    """Shannon entropy of the belief grid, normalized to [0, 1] by log(cells):
    1.0 = uniform (the rival knows nothing), 0.0 = a single certain cell."""
    cells = belief.grid_size * belief.grid_size
    raw = -sum(p * math.log(p) for row in belief.values() for p in row if p > 0.0)
    return raw / math.log(cells)


def mass_near(belief: BeliefMap, cell: Cell, radius: int) -> float:
    """Probability mass within Manhattan `radius` of `cell` (exposure form)."""
    return sum(
        belief.value_at((row, col))
        for row in range(belief.grid_size)
        for col in range(belief.grid_size)
        if abs(row - cell[0]) + abs(col - cell[1]) <= radius
    )


class LeakageEstimator:
    """Preview what one candidate landing would teach the rival about us.

    Input: our SelfMirror, the live engine, a landing cell. Output: the
    previewed mirror (`preview`) or its scalar stealth score (`stealth`).
    Setup: our role + the exposure radius. Pure function of own-side state:
    every step runs on deep copies, so live physics is never touched.
    """

    def __init__(self, role: Role, exposure_radius: int) -> None:
        self.role = role
        self.exposure_radius = exposure_radius

    def preview(self, mirror: SelfMirror, engine: GameEngine, landing: Cell) -> BeliefMap:
        """The mirror as it WOULD read after we land: replay the receiving
        side's update (diffuse, then scent with our next emission applied)."""
        belief = copy.deepcopy(mirror.belief)
        scent = copy.deepcopy(engine.scent[self.role])
        scent.update(landing)  # the full-turn emission this landing causes
        belief.diffuse(engine.board)
        belief.observe_scent(scent, engine.board)
        return belief

    def stealth(self, mirror: SelfMirror, engine: GameEngine, landing: Cell) -> float:
        """Higher = leaks less: flat previewed mirror, little mass on us."""
        after = self.preview(mirror, engine, landing)
        return entropy(after) - mass_near(after, landing, self.exposure_radius)


class StealthThiefBrain(ThiefBrain):
    """ThiefBrain + a config-blended leakage term over the self-mirror.

    The brain owns a scent-only SelfMirror (claims ride the hint channel,
    owned by the Deceiver) and re-syncs it once per completed full turn.
    Scoring under belief play: the flee term is CAPPED at `safe_distance` —
    at knife range distance still rules absolutely, but among landings that
    all keep the believed hunter at least `safe_distance` away, stealth
    (blended into the openness tie-break) chooses the walk. Under
    exact-info arena play stealth is a pure final tie-break.
    """

    def __init__(self, role: Role, rng: random.Random, tuning: dict | None = None) -> None:
        super().__init__(role, rng)
        block = tuning if tuning is not None else movement_tuning()
        self.enabled = bool(block["enabled"])
        self.blend_weight = float(block["blend_weight"])
        self.safe_distance = int(block["safe_distance"])
        self.estimator = LeakageEstimator(role, int(block["exposure_radius"]))
        self.mirror: SelfMirror | None = None
        self._turns_seen = 0

    def _sync_mirror(self, engine: GameEngine) -> None:
        """Feed the mirror the boundary state exactly once per full turn."""
        if self.mirror is None or self.mirror.belief.grid_size != engine.board.grid_size:
            self.mirror = SelfMirror(self.role, engine.board.grid_size)
            self._turns_seen = 0
        if engine.turns_completed > self._turns_seen:
            self.mirror.observe_own_turn(engine, None)  # scent-only mirror
            self._turns_seen = engine.turns_completed

    def decide(self, engine: GameEngine, belief=None) -> dict:
        if self.enabled:
            self._sync_mirror(engine)
        return super().decide(engine, belief)

    def _score(self, engine: GameEngine, cell: Cell, distances: dict,
               cop: Cell, exact: bool) -> tuple:
        base = super()._score(engine, cell, distances, cop, exact)
        if not self.enabled:
            return base
        stealth = self.blend_weight * self.estimator.stealth(self.mirror, engine, cell)
        if exact:
            return (*base, stealth)  # never outranks the trap forecast
        # Belief play: cap the flee term so stealth governs once we are safe.
        return (min(base[0], self.safe_distance), base[1] + stealth)
