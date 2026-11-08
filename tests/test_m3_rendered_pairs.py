"""M3 amendments 10/11: independently observe the screen behind every offered pair.

Falsifiers: JSON-only differences, invalid/unserved candidate packages, changed
copy or semantics, hidden third dimensions, wrong type hierarchy, or ineffective
color/spacing/shape choices. No candidate implementation or resolver is the oracle.
"""

import hashlib
from io import BytesIO

import pytest
from PIL import Image

from tests.m2_support import assert_valid_draft, read_json
from tests.m3_render_support import (assert_dimension_effects, assert_formality, assert_known_font_genres, hsl,
                                     paint_snapshot, primary)
from tests.m3_support import BEACH, candidate_directory, choose, pair, settled, start
from tests.test_m1_design import solid_background

pytestmark = [pytest.mark.browser, pytest.mark.browser_timeout(600)]


def same_default_bindings(first, second):
    components = [doc["components"] for doc in (first, second)]
    if any(treatment.get("variant", "default") != "default" for group in components for treatment in group.values()):
        return False
    bindings = [{name: treatment.get("assets", {}) for name, treatment in group.items()} for group in components]
    if bindings[0] != bindings[1]:
        return False
    for name, slots in bindings[0].items():
        for binding in slots.values():
            identity, variant = binding.split(":")
            if first["assets"][identity]["variants"][variant]["format"] != second["assets"][identity]["variants"][variant]["format"]:
                return False
    return True


def observe_candidate(library, server, page, session, candidate, tmp_path):
    root = candidate_directory(library, session, candidate)
    document = read_json(root / "working.json")
    assert_valid_draft(library, document, root)
    url = f'{server}/generate/{session}/candidates/{candidate["hash"]}/sample.html'
    response = page.goto(url)
    assert response and response.ok and response.body() == (root / "sample.html").read_bytes()
    assert page.locator("[data-kd-construct]").count() and page.locator("[data-kd-slot]").count()
    # Screenshots serve an explicit oracle: the candidate pair must visibly
    # differ. Compare decoded pixels, not PNG encoding/timestamps or OCR text.
    screenshot = page.screenshot(path=tmp_path / (candidate["hash"] + ".png"),
                                 full_page=True, timeout=5000, animations="disabled", caret="hide")
    with Image.open(BytesIO(screenshot)) as picture:
        pixels = (picture.size, hashlib.sha256(picture.convert("RGBA").tobytes()).hexdigest())
    rows = paint_snapshot(page)
    body = page.locator('[data-kd-slot][data-kd-role="body"][data-kd-emphasis="neutral"]')
    visible_body = next((body.nth(i) for i in range(body.count()) if body.nth(i).is_visible()), None)
    if visible_body is not None:
        surface = solid_background(visible_body)
        rows[0]["surface_rgb"] = surface
        rows[0]["surface_lightness"] = hsl("rgb(" + ",".join(map(str, surface)) + ")")[2]
    labels = [row for row in rows if row["slot"] and row["role"] == "label"]
    if labels:
        assert_formality(rows, candidate["values"]["formality"])
    return root, document, rows, pixels


def test_all_offered_pairs_render_same_screen_with_only_advertised_dimension_effects(
        library, server, page, tmp_path, record_property):
    session, root, _ = start(library, BEACH)
    observed_dimensions = set()
    unclassified_families = set()
    offered = 0
    # Do not prescribe scheduling or require nine dimensions in eight rounds.
    # Every pair actually offered must satisfy the same rendering relation.
    for _ in range(8):
        before = settled(library, session, root)
        current = pair(library, session, root)
        if current.get("done"):
            break
        offered += 1
        assert set(current["dimensions"]) <= set(before["unsettled"])
        a_root, a_doc, a, a_pixels = observe_candidate(library, server, page, session, current["a"], tmp_path)
        b_root, b_doc, b, b_pixels = observe_candidate(library, server, page, session, current["b"], tmp_path)
        for rows in (a, b):
            hue, saturation, _ = hsl(primary(rows)["css"]["color"])
            assert saturation > 0.01 and 90 <= hue <= 255, (
                "The beach brief's base color must actually render blue/green/turquoise", hue, saturation)
        if same_default_bindings(a_doc, b_doc):
            assert (a_root / "sample.html").read_bytes() == (b_root / "sample.html").read_bytes()
        assert_dimension_effects(a, b, current["a"]["values"], current["b"]["values"], current["dimensions"])
        if "type-pairing" in current["dimensions"]:
            for rows, side in ((a, "a"), (b, "b")):
                unclassified_families.update(assert_known_font_genres(rows, current[side]["values"]["type-pairing"]))
        assert a_pixels != b_pixels, "A/B options have identical visible paint"
        observed_dimensions.update(current["dimensions"])
        choose(library, session, root, current, "A", comment="Keep this direction and compare the next dimensions")
    assert offered > 0
    record_property("rendered_dimensions", ",".join(sorted(observed_dimensions)))
    record_property("font_genres_needing_review", ",".join(sorted(unclassified_families)))
    assert pair(library, session, root)["done"] is True
