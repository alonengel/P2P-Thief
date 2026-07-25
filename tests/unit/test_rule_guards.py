"""Disqualification-class rules enforced as tests, not asserted in prose.

Each guard turns a rulebook MUST/FORBIDDEN into a machine-checked invariant:
a violating edit - ours or a panicked league-day patch - fails CI with the
rule number in the message instead of failing the project at audit.
"""

import ast
import json
import random
import re
from pathlib import Path

from p2p_thief.domain import negotiation
from p2p_thief.domain.engine import GameEngine
from p2p_thief.domain.primitives import Move, Role
from p2p_thief.domain.rules import RuleSet
from p2p_thief.peer.sealing import SealedExchange
from p2p_thief.strategy.hints import build_hint

STRATEGY = Path("src/p2p_thief/strategy")
DECISION_MODULES = ["brain_base.py", "thief_brain.py", "rl_brain.py", "rl_deep.py",
                    "arena_cop.py", "movement_deception.py", "endgame.py", "doctrine.py",
                    "arena_aged_cop.py"]
LLM_PATHS = {"p2p_thief.infra.llm_provider", "p2p_thief.strategy.talk_providers"}


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found = {name.name for node in ast.walk(tree)
             if isinstance(node, ast.Import) for name in node.names}
    found |= {node.module for node in ast.walk(tree)
              if isinstance(node, ast.ImportFrom) and node.module}
    return found


def test_rule_25_no_llm_reachable_from_move_decisions() -> None:
    """Moves are ALWAYS pure Python - no brain module may import an LLM path."""
    for name in DECISION_MODULES:
        hits = _imports(STRATEGY / name) & LLM_PATHS
        assert not hits, f"rule 25 violated: {name} imports LLM path {hits}"


def test_rule_30_send_only_gmail_scope() -> None:
    """The ONLY gmail scope anywhere in the codebase is gmail.send."""
    scopes = set()
    for path in Path("src").rglob("*.py"):
        scopes |= set(re.findall(r"auth/gmail\.\w+", path.read_text(encoding="utf-8")))
    for path in Path("scripts").glob("*.py"):
        scopes |= set(re.findall(r"auth/gmail\.\w+", path.read_text(encoding="utf-8")))
    assert scopes == {"auth/gmail.send"}, f"rule 30 violated: scopes found {scopes}"


def test_rule_18_wire_secrecy_nonce_and_verdict_sealed() -> None:
    """Neither the nonce nor the intent verdict ever rides a live message."""
    sent: list[dict] = []
    exchange = SealedExchange(Role.POLICE, 1, sent.append, None)
    engine = GameEngine(7, (0, 0), (3, 3), RuleSet(14, 35, 35))
    exchange.send_sealed(engine, 1, {"type": "move", "move": "E"}, "hint", True)
    commit_msg, reveal_msg = sent
    assert set(commit_msg) == {"kind", "turn", "actor", "commit"}
    assert "nonce" not in json.dumps(reveal_msg)
    assert "verdict" not in reveal_msg["payload"], "rule 18/deception: lie bit leaked"


def test_rule_27_hints_never_contain_coordinates() -> None:
    """Free language only: no coordinate-shaped tokens in any generated hint."""
    coordinate = re.compile(r"[\[\(]\s*\d\s*,\s*\d\s*[\]\)]|\b\d\s*,\s*\d\b")
    rng = random.Random(3)
    for move in Move:
        for truth in (True, False):
            for _ in range(20):
                text, _claim, _intent = build_hint(move, truth, 15, rng)
                assert not coordinate.search(text), f"rule 27 violated: {text!r}"


def test_movement_deception_consumes_own_side_information_only() -> None:
    """Deception-by-movement may read OUR scent, OUR mirror, OUR belief —
    never the rival's true cell. The module must not touch `positions`,
    `Role.POLICE`, or `.rival` anywhere (own cell arrives as a plain
    candidate-landing argument from the base brain)."""
    tree = ast.parse((STRATEGY / "movement_deception.py").read_text(encoding="utf-8"))
    touched = {node.attr for node in ast.walk(tree)
               if isinstance(node, ast.Attribute)
               and node.attr in {"positions", "POLICE", "rival"}}
    assert not touched, f"movement deception reads rival-side state: {touched}"


def test_movement_deception_emits_only_legal_orthogonal_or_stay() -> None:
    """With the stealth term ON, every emitted action is still a legal
    orthogonal step or STAY on the live board (rules 13-14) — walls and
    freshly placed barriers included."""
    from p2p_thief.domain import protocol
    from p2p_thief.strategy.movement_deception import StealthThiefBrain

    engine = GameEngine(7, (0, 0), (3, 3), RuleSet(14, 35, 35))
    engine.board.add_barrier((3, 4))
    engine.board.add_barrier((2, 3))
    brain = StealthThiefBrain(Role.THIEF, random.Random(2), tuning={
        "enabled": True, "blend_weight": 5.0, "safe_distance": 3,
        "exposure_radius": 1})
    for _ in range(12):
        engine.police_move(Move.STAY)
        action = brain.decide(engine)
        assert action["type"] == "move"
        legal = engine.board.legal_moves(engine.positions[Role.THIEF])
        assert Move[action["move"]] in legal, f"illegal emit: {action}"
        protocol.apply_action(engine, Role.THIEF, action)


def test_rules_11_12_committed_constitution_is_legal() -> None:
    """Our committed game.json passes the Appendix-VI fixed/minimum gate."""
    shared = json.loads(Path("config/game.json").read_text(encoding="utf-8"))
    negotiation.validate_shared_terms(shared)  # raises on any violation
