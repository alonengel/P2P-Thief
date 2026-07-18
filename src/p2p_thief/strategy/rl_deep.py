"""Deep-RL evasion brain: a tiny MLP Q-network, barrier-threat aware.

The linear evasion brain was trained against a MOVEMENT-ONLY cop; a
barrier-building rival changes the game (the twin repo's DQN cop captures
the perfect evader 0.74 by trapping). This module learns evasion against
exactly that threat: features track escape routes, reachable region and
wall distance - the quantities barrier traps destroy. The thief's action
space is moves+STAY only (barriers are cop-only physics, ch. 3). Pure
Python (rule 25: moves are algorithmic), no new dependencies.
Seam: [strategy] thief_class = "p2p_thief.strategy.rl_deep:DeepQBrain".
"""

import json
import logging
import math
import random
from pathlib import Path

from p2p_thief.domain import protocol
from p2p_thief.domain.engine import GameEngine
from p2p_thief.domain.pathfind import UNREACHABLE, bfs_distances
from p2p_thief.domain.primitives import Move, Role

_LOG = logging.getLogger(__name__)
REPO_ROOT = Path(__file__).resolve().parents[3]
WEIGHTS_PATH = REPO_ROOT / "results" / "deep_rl_weights.json"
N_FEATURES, HIDDEN = 9, 12


def features(engine: GameEngine, move: Move, cop=None) -> list[float]:
    """phi(s,a) AFTER the move: what a barrier trap would take away.
    `cop` overrides the threat cell (belief argmax in blind games)."""
    me = engine.positions[Role.THIEF]
    cop = cop or engine.positions[Role.POLICE]
    landing = move.applied_to(me)
    if move is not Move.STAY and not engine.board.is_passable(landing):
        landing = me  # illegal probes are never chosen; keep phi defined
    from_cop = bfs_distances(engine.board, cop)
    grid, horizon = engine.board.grid_size, 2.0 * engine.board.grid_size
    d_after = from_cop.get(landing, UNREACHABLE)
    d_after = 1.0 if d_after == UNREACHABLE else d_after / horizon
    d_before = from_cop.get(me, UNREACHABLE)
    d_before = 1.0 if d_before == UNREACHABLE else d_before / horizon
    escapes = sum(
        1 for m in (Move.N, Move.S, Move.E, Move.W)
        if engine.board.is_passable(m.applied_to(landing))
    )
    my_region = bfs_distances(engine.board, landing)
    wall = min(landing[0], landing[1], grid - 1 - landing[0], grid - 1 - landing[1])
    return [
        1.0, d_after, d_after - d_before, escapes / 4.0,
        len(my_region) / float(grid * grid),   # room to run - traps shrink it
        wall / (grid / 2.0),                   # walls are half a trap already
        len(engine.board.barriers) / max(1, engine.rules.max_barriers),
        float(move is Move.STAY),
        float((landing[0] + landing[1] + cop[0] + cop[1]) % 2),  # chase parity
    ]


class Mlp:
    """9 -> tanh(12) -> 1, hand-rolled: forward, gradients, SGD step."""

    def __init__(self, rng: random.Random) -> None:
        scale = 1.0 / math.sqrt(N_FEATURES)
        self.w1 = [[rng.uniform(-scale, scale) for _ in range(N_FEATURES)]
                   for _ in range(HIDDEN)]
        self.b1 = [0.0] * HIDDEN
        self.w2 = [rng.uniform(-scale, scale) for _ in range(HIDDEN)]
        self.b2 = 0.0

    def forward(self, phi: list[float]) -> tuple[float, list[float]]:
        hidden = [math.tanh(sum(w * f for w, f in zip(row, phi, strict=True)) + b)
                  for row, b in zip(self.w1, self.b1, strict=True)]
        q = sum(w * h for w, h in zip(self.w2, hidden, strict=True)) + self.b2
        return q, hidden

    def sgd(self, phi: list[float], hidden: list[float], delta: float, lr: float) -> None:
        """One gradient step pushing Q(phi) by delta (TD error), lr-scaled."""
        for j, h in enumerate(hidden):
            grad_h = delta * self.w2[j] * (1.0 - h * h)
            self.w2[j] += lr * delta * h
            for i, f in enumerate(phi):
                self.w1[j][i] += lr * grad_h * f
            self.b1[j] += lr * grad_h
        self.b2 += lr * delta

    def state(self) -> dict:
        return {"w1": self.w1, "b1": self.b1, "w2": self.w2, "b2": self.b2}

    def load_state(self, state: dict) -> None:
        self.w1, self.b1 = state["w1"], state["b1"]
        self.w2, self.b2 = state["w2"], state["b2"]


class DeepQBrain:
    """Greedy over legal moves at play time; epsilon only while training."""

    def __init__(self, role: Role, rng: random.Random, net: Mlp | None = None) -> None:
        self.role, self.rng, self.epsilon = role, rng, 0.0
        self.net = net or self._load(rng)

    def _load(self, rng: random.Random) -> Mlp:
        net = Mlp(rng)
        if WEIGHTS_PATH.is_file():
            net.load_state(json.loads(WEIGHTS_PATH.read_text(encoding="utf-8"))["net"])
        else:  # loud, not silent: an untrained net is a valid but weak brain
            _LOG.warning("deep-RL weights missing at %s - random init", WEIGHTS_PATH)
        return net

    def q(self, engine: GameEngine, move: Move, cop=None) -> float:
        return self.net.forward(features(engine, move, cop))[0]

    def decide(self, engine: GameEngine, belief=None) -> dict:
        cop = belief.argmax_cell() if belief is not None else None
        me = engine.positions[Role.THIEF]
        legal = engine.board.legal_moves(me)
        if self.rng.random() < self.epsilon:
            return protocol.move_action(self.rng.choice(legal))
        shuffled = self.rng.sample(legal, k=len(legal))  # random tie-break
        return protocol.move_action(max(shuffled, key=lambda m: self.q(engine, m, cop)))
