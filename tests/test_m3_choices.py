"""M3 choice sequences, using amendment 10 rather than generator internals.

Falsifiers: mutable history, cached settled values after revision, unrelated
candidate changes, or brief colors ignored by both candidates.
"""

import pytest

from tests.m3_support import (BEACH, choose, log_bytes, log_records, pair, settled, start)

pytestmark = [pytest.mark.browser, pytest.mark.browser_timeout(420)]


def test_superseding_choice_recomputes_settled_values_and_preserves_history(library):
    session, root, _ = start(library)
    assert not settled(library, session, root)["settled"]
    first = pair(library, session, root)
    assert not first.get("done")
    a = choose(library, session, root, first, "A", comment="Prefer the first direction")
    after_a = settled(library, session, root)
    for dimension in first["dimensions"]:
        assert after_a["settled"][dimension] == {"value": first["a"]["values"][dimension], "choices": [a["id"]]}
    b = choose(library, session, root, first, "B", supersedes=a["id"], comment="Revise after comparing again")
    after_b = settled(library, session, root)
    for dimension in first["dimensions"]:
        assert after_b["settled"][dimension] == {"value": first["b"]["values"][dimension], "choices": [b["id"]]}
    assert len(log_records(root)) == 2
    following = pair(library, session, root)
    assert not following.get("done"), "Unsettled dimensions remain below the round cap"
    assert not set(following["dimensions"]) & set(after_b["settled"])
    for dimension, result in after_b["settled"].items():
        assert following["a"]["values"][dimension] == following["b"]["values"][dimension] == result["value"]
    history = log_bytes(root)
    settled(library, session, root)
    assert log_bytes(root) == history, "Reading derived state changed the choice log"


def test_beach_brief_candidates_stay_in_requested_hue_families(library):
    session, root, _ = start(library, BEACH)
    # Independent broad hue interval: green 90–165, turquoise 165–195,
    # blue 195–255. This permits variation without pinning an authored palette.
    current = pair(library, session, root)
    assert not current.get("done")
    for side in ("a", "b"):
        assert 90 <= current[side]["values"]["hue-family"] <= 255


def test_neither_immediately_widens_until_exhaustion_and_cap_ends_rounds(library):
    from tests.m3_support import distance

    session, root, _ = start(library)
    previous, pairs = None, []
    for _ in range(8):  # Public default round cap, with no dimensions settled.
        current = pair(library, session, root)
        assert not current.get("done"), "Neither must not settle dimensions or terminate rounds early"
        pairs.append(current)
        if previous:
            # Amendment 10.6: the public usable-range boundary supersedes the
            # abstract domain maximum, including mixed two-dimension pairs.
            exhausted = {d for d in previous["dimensions"] if previous["variation"][d]["widest"]}
            widening = set(previous["dimensions"]) - exhausted
            assert widening <= set(current["dimensions"]), ("Non-widest dimensions must return immediately", widening, current)
            assert not exhausted & set(current["dimensions"]), ("Widest rejected dimensions must be left unsettled", exhausted, current)
            for dimension in widening:
                a, b = (current[side]["values"][dimension] for side in ("a", "b"))
                old_a, old_b = (previous[side]["values"][dimension] for side in ("a", "b"))
                assert distance(dimension, a, b) > distance(dimension, old_a, old_b)
        choose(library, session, root, current, "neither", comment="Explore further apart")
        assert not settled(library, session, root)["settled"]
        previous = current
    assert len({p["pair"] for p in pairs}) == 8
    history = log_bytes(root)
    assert pair(library, session, root)["done"] is True
    assert pair(library, session, root)["done"] is True
    assert log_bytes(root) == history


def test_superseding_neither_restores_normal_unsettled_sequence(library):
    session, root, _ = start(library)
    first = pair(library, session, root)
    assert not first.get("done")
    rejection = choose(library, session, root, first, "neither", comment="Initially neither")
    revision = choose(library, session, root, first, "B", supersedes=rejection["id"], comment="B works after all")
    resolved = settled(library, session, root)
    for dimension in first["dimensions"]:
        assert resolved["settled"][dimension]["value"] == first["b"]["values"][dimension]
        assert resolved["settled"][dimension]["choices"] == [revision["id"]]
    following = pair(library, session, root)
    assert not following.get("done")
    assert not set(first["dimensions"]) & set(following["dimensions"])
