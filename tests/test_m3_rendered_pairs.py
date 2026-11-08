"""M3 amendments 10/11: independently observe the screen behind every offered pair.

Falsifiers: JSON-only differences, invalid/unserved candidate packages, changed
copy or semantics, hidden third dimensions, wrong type hierarchy, or ineffective
color/spacing/shape choices. No candidate implementation or resolver is the oracle.
"""

import hashlib
from io import BytesIO
import shutil

import pytest
from PIL import Image

from tests.m3_render_support import (assert_dimension_effects, assert_formality, assert_known_font_genres, hsl,
                                     paint_snapshot, primary)
from tests.m3_support import BEACH, candidate_directory, candidate_library, choose, pair, settled, start
from tests.test_m1_design import solid_background
from tests.test_m3_derive import source_assets, supplied_sources

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
    isolated, document = candidate_library(library, root)
    isolated.validate(document["id"], accepted=True)
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


def test_asset_bearing_candidates_validate_and_rebuild_without_original_workspace(library, tmp_path, page):
    """Amendment 14: a copied language must not depend on session-private originals."""
    originals = tmp_path / "portable-supplied"
    sources = supplied_sources(library, originals)
    session, session_root, _ = start(library, BEACH, [source["artifact"] for source in sources.values()])
    offered = pair(library, session, session_root)
    assert not offered.get("done"), "No rendered choices for the supplied design constraints"
    copies = []
    for side in ("a", "b"):
        directory = candidate_directory(library, session, offered[side])
        case, document = candidate_library(library, directory)
        source_assets(case.path(document["id"]).parent, document, sources)
        copies.append((side, case, document))
    # Only this test's temporary inputs are moved/removed. Public validation and
    # rebuild use a new workspace with no session/artifact history to fall back on.
    shutil.rmtree(originals)
    unavailable = tmp_path / "unavailable-session-workspace"
    library.workspace.rename(unavailable)
    try:
        for side, case, document in copies:
            case.validate(document["id"], accepted=True)
            preview = case.build(tmp_path / ("portable-preview-" + side), document["id"])
            page.goto((preview / "index.html").as_uri())
            page.wait_for_function("document.fonts.status === 'loaded'", timeout=5000)
            assert page.evaluate("document.fonts.check('16px \"Fixture Sans\"')")
            assert page.locator("[data-kd-slot]").evaluate_all("""els => els.some(e =>
              e.textContent.trim() && getComputedStyle(e).fontFamily.includes('Fixture Sans'))""")
            logo = page.locator('[data-kd-slot="nav.logo"] img, img[data-kd-slot="nav.logo"]').first
            assert logo.is_visible()
            assert logo.evaluate("e => e.complete && e.naturalWidth > 0 && e.getBoundingClientRect().width > 0 && e.getBoundingClientRect().height > 0")
    finally:
        # A command recreating the old path would itself reveal a hidden source
        # dependency; preserve that evidence and still restore the test fixture.
        if library.workspace.exists():
            library.workspace.rename(tmp_path / "unexpected-recreated-workspace")
        unavailable.rename(library.workspace)
