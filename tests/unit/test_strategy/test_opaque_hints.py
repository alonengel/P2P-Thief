"""Opaque hint mode: free language that leaks nothing (rule 27 + ch.4).

Our shipped templates narrate the heading ("Slipping south past the docks."
while moving south, flagged truthful) — against a rival whose own hints are
contentless taunts that is a one-way information gift, and it cost us the
2026-08-11 series. Free language is required; informative language is not.
"""

import random

from p2p_thief.strategy.hints import TAUNTS, TEMPLATES
from p2p_thief.strategy.talk_providers import TalkChain

DIRECTION_WORDS = ("north", "south", "east", "west", "uptown", "downtown",
                   "sunrise", "docks", "left", "right", "up", "down",
                   "staying", "moving", "not moving", "right where")


def _chain(opaque: bool) -> TalkChain:
    return TalkChain(None, 1, "New York", 15, random.Random(0), opaque=opaque)


def test_taunts_never_name_a_direction() -> None:
    for line in TAUNTS:
        lowered = line.lower()
        for word in DIRECTION_WORDS:
            assert word not in lowered, f"{line!r} leaks {word!r}"


def test_taunts_stay_inside_the_signed_word_cap() -> None:
    for line in TAUNTS:
        assert len(line.split()) <= 15, f"{line!r} is over the cap"


def test_opaque_mode_renders_the_same_text_for_every_claim() -> None:
    """The text must be independent of our real heading — otherwise a rival
    could invert it. Same seed, every claim, identical output."""
    rendered = {claim: _chain(True).render(claim, step=1) for claim in TEMPLATES}
    assert len(set(rendered.values())) == 1, rendered
    assert next(iter(rendered.values())) in TAUNTS


def test_candid_mode_is_untouched_and_still_the_default() -> None:
    """Friendlies keep the informative voice; only the counted overlay flips."""
    text = _chain(False).render("S", step=1)
    assert text in TEMPLATES["S"]
    from p2p_thief.shared.config import Config
    chain = TalkChain(None, 1, "NY", 15, random.Random(0))
    assert chain.opaque is False
    assert "hint_mode" not in str(Config.load("config").shared)  # never signed
