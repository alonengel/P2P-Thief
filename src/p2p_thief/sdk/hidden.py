"""Hidden-mode (reference-v3) SDK assembly — run_peer's wire-shape seam.

Keeps sdk.py the single thin entry: when config/game.toml [network]
wire_shape = "reference", run_peer builds a HiddenRuntime here instead of a
GeometricRuntime. OwnState starts from MY OWN signed start cell only — the
rival's start feeds the belief prior inside Perception, never a position
field (rules 8-9 are structural on this wire). Crash-resume routes to
wire/hidden_resume.py (same attach/discard surface as peer/resume.py).
"""

from p2p_thief.domain.primitives import Role
from p2p_thief.wire.hidden_resume import attach, discard  # noqa: F401  (sdk seam)
from p2p_thief.wire.hidden_runtime import HiddenRuntime
from p2p_thief.wire.own_state import OwnState

MY_ROLE = Role.THIEF  # this repo IS the thief agent (twin repo: police)


def build_runtime(config, transport, inboxes, brain, gatekeeper=None) -> HiddenRuntime:
    """Assemble the hidden-mode loop from the loaded config (no game logic)."""
    pheromones = config.pheromones
    own = OwnState(
        MY_ROLE,
        config.grid_size,
        config.thief_start,
        config.rule_set(),
        center_intensity=pheromones["pheromone_center_intensity"],
        decay=pheromones["pheromone_decay"],
        kernel_size=pheromones["pheromone_grid_size"],
    )
    return HiddenRuntime(
        MY_ROLE, config, own, transport, inboxes, brain, gatekeeper=gatekeeper
    )
