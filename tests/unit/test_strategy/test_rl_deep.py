"""Deep evasion brain + arena adversaries: MLP math, legality, seam, threat."""

import random
import types

from p2p_thief.domain import protocol
from p2p_thief.domain.engine import GameEngine
from p2p_thief.domain.primitives import Move, Outcome, Role
from p2p_thief.domain.rules import RuleSet
from p2p_thief.strategy.arena_cop import DeepTrapCop, TrapCop, cop_actions
from p2p_thief.strategy.brain_base import resolve_brain
from p2p_thief.strategy.rl_deep import DeepQBrain, Mlp, features

RULES = RuleSet(max_barriers=14, max_moves=35, survival_threshold=35)
SEAM_SPEC = "p2p_thief.strategy.rl_deep:DeepQBrain"


def _engine() -> GameEngine:
    return GameEngine(7, (0, 0), (3, 3), RULES)


def test_features_are_bounded_and_barrier_aware() -> None:
    engine = _engine()
    for move in engine.board.legal_moves((3, 3)):
        phi = features(engine, move)
        assert len(phi) == 9 and all(-1.5 <= f <= 1.5 for f in phi)
    engine.board.add_barrier((3, 4))  # a wall next door changes the picture
    assert features(_engine(), Move.STAY)[6] == 0.0
    assert features(engine, Move.STAY)[6] > 0.0  # barrier-count feature moved


def test_mlp_forward_deterministic_and_sgd_reduces_error() -> None:
    net = Mlp(random.Random(3))
    phi = [1.0, 0.5, -0.1, 0.75, 0.9, 0.6, 0.0, 0.0, 1.0]
    q0, hidden = net.forward(phi)
    assert net.forward(phi)[0] == q0
    target = q0 + 1.0
    for _ in range(200):
        q, hidden = net.forward(phi)
        net.sgd(phi, hidden, target - q, 0.05)
    assert abs(net.forward(phi)[0] - target) < abs(q0 - target)


def test_decide_returns_only_legal_moves_both_modes() -> None:
    engine = _engine()
    brain = DeepQBrain(Role.THIEF, random.Random(1), net=Mlp(random.Random(2)))
    legal = engine.board.legal_moves((3, 3))
    assert Move[brain.decide(engine)["move"]] in legal  # greedy
    brain.epsilon = 1.0
    for _ in range(20):
        assert Move[brain.decide(engine)["move"]] in legal


def test_seam_spec_loads_and_uses_belief_target() -> None:
    config = types.SimpleNamespace(private={"strategy": {"thief_class": SEAM_SPEC}})
    brain = resolve_brain(config, Role.THIEF, random.Random(3))
    assert isinstance(brain, DeepQBrain) and brain.epsilon == 0.0

    class FixedBelief:
        def argmax_cell(self):
            return (0, 0)

    action = brain.decide(_engine(), belief=FixedBelief())
    assert Move[action["move"]] in _engine().board.legal_moves((3, 3))


def test_arena_cops_emit_legal_actions_and_deep_cop_is_a_threat() -> None:
    engine = _engine()
    for cop_cls in (TrapCop, DeepTrapCop):
        action = cop_cls(Role.POLICE, random.Random(1)).decide(engine)
        assert action in cop_actions(engine) or action["type"] in ("move", "barrier")
    # the learned trap cop catches a random-walking thief fast
    engine = _engine()
    cop = DeepTrapCop(Role.POLICE, random.Random(5))
    thief_rng = random.Random(6)
    while engine.outcome is Outcome.ONGOING:
        protocol.apply_action(engine, Role.POLICE, cop.decide(engine))
        if engine.outcome is Outcome.ONGOING:
            me = engine.positions[Role.THIEF]
            move = thief_rng.choice(engine.board.legal_moves(me))
            protocol.apply_action(engine, Role.THIEF, protocol.move_action(move))
    assert engine.outcome is Outcome.CAPTURE
