"""Normative M1 B4/asset-load. Real checker Chromium and independently authored input.

Falsifiers: always-green contrast, wrong normal/large threshold, ignore alpha,
classify image/gradient-backed text as measured-pass, or trust an asset manifest
without attempting to load its correctly hashed bytes. Report artifacts are checked.
"""

import pytest

from tests.m1_support import contrast_ratio, findings, replace_asset_bytes, run_check, slot_properties, token
from tests.test_versions_assets import bind_font

pytestmark = [pytest.mark.browser, pytest.mark.browser_timeout(240)]


@pytest.mark.parametrize("size,bad,good,threshold", [(16, "#777777", "#767676", 4.5),
                                                    (24, "#999999", "#949494", 3.0)])
def test_contrast_threshold_has_measured_negative_and_positive_control(library, language, tmp_path, size, bad, good, threshold):
    properties = slot_properties(language, slot="price")
    properties.update({"color": token(language, "probe", "foreground", "color", bad),
                       "background-color": "{color.paper}", "font-weight": "{type.weight}",
                       "font-size": token(language, "probe", "size", "dimension", f"{size}px")})
    library.write(language)
    report = run_check(library, tmp_path / "low-contrast", accepted=False)
    failures = findings(report, "contrast", "listing-card.price", "violation")
    assert failures, report
    for finding in failures:
        assert "1.4.3" in finding["criterion"]
        assert finding["measured"] == contrast_ratio(bad, "#ffffff")
        assert finding["threshold"] == threshold
        assert finding["exception"] is None
    language["style"]["probe"]["foreground"]["$value"] = good
    library.write(language)
    report = run_check(library, tmp_path / "legible-contrast")
    assert not findings(report, "contrast", "listing-card.price", "violation"), report
    assert not findings(report, "contrast", "listing-card.price", "needs-review"), report


def test_contrast_uses_alpha_composed_background(library, language, tmp_path):
    language["components"]["listing-card"]["properties"]["background-color"] = token(language, "probe", "black", "color", "#000000")
    slot_properties(language, slot="price").update({
        "color": "{color.paper}", "font-size": "{size.body}", "font-weight": "{type.weight}",
        "background-color": token(language, "probe", "translucent", "color", "#ffffff80")})
    library.write(language)
    report = run_check(library, tmp_path / "alpha", accepted=False)
    failures = findings(report, "contrast", "listing-card.price", "violation")
    assert failures
    # Alpha 128/255 white over opaque black yields exactly sRGB (128,128,128).
    for finding in failures:
        assert finding["measured"] == contrast_ratio("#ffffff", "#808080")
        assert finding["threshold"] == 4.5


@pytest.mark.parametrize("background", ["image", "gradient"])
def test_text_on_image_or_gradient_is_unresolved_review(library, language, tmp_path, background):
    value = "asset:fixture-image:primary"
    if background == "gradient":
        value = token(language, "probe", "gradient", "gradient", [
            {"color": "{color.ink}", "position": 0}, {"color": "{color.paper}", "position": 1}])
    slot_properties(language, slot="price")["background-image"] = value
    library.write(language)
    report = run_check(library, tmp_path / background)
    uncertain = findings(report, "contrast", "listing-card.price")
    assert uncertain and all(f["type"] == "needs-review" for f in uncertain), report
    assert report["needs_review"] >= len(uncertain)
    assert all(f["exception"] is None for f in uncertain)


@pytest.mark.parametrize("kind", ["font", "image"])
def test_corrupt_bound_asset_is_a_load_violation(library, language, tmp_path, kind):
    if kind == "font":
        bind_font(library, language, tmp_path)
        asset_id, variant = "fixture-font", "regular"
    else:
        asset_id, variant = "fixture-image", "primary"
    working = run_check(library, tmp_path / "working-assets")
    assert not findings(working, "asset-load", kind="violation"), working
    replace_asset_bytes(library, language, asset_id, variant, b"deliberately corrupt asset bytes")
    library.write(language)
    broken = run_check(library, tmp_path / "broken-assets", accepted=False)
    assert findings(broken, "asset-load", kind="violation"), broken
