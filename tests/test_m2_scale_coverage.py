"""M2 real-site regression requirements, from the Validator's source-free review.

Falsifiers: sample only a DOM prefix/first screen, silently discard later palette
colors, emit negative spacing values, or inflate a large pill radius into millions.
"""

import pytest

from tests.m2_support import capture, color_distance, dereference, dimension_px, draft, token_values
from tests.test_m2_capture import opaque_color

pytestmark = [pytest.mark.browser, pytest.mark.browser_timeout(420)]


def test_large_page_late_colors_survive_capture_and_quantization(library, fixture_site, ingest_config, page):
    url = fixture_site.url + "/large/index.html"
    page.set_viewport_size({"width": 320, "height": 900})
    page.goto(url)
    assert page.locator("*").count() > 5000
    late = page.locator(".late")
    assert late.bounding_box()["y"] > page.viewport_size["height"]
    assert late.evaluate("e => [...document.querySelectorAll('*')].indexOf(e)") > 5000
    # Values are literal authored CSS, independent of the capture or draft output.
    colors = ("#e6c35c", "#0b6e4f", "#4b42b8", "#c64c8b")
    assert late.evaluate("e => getComputedStyle(e).backgroundColor") == "rgb(230, 195, 92)"
    artifact, _, captured = capture(library, [url])
    assert not captured["problems"], captured
    _, document, summary = draft(library, [artifact], "late-colors")
    palette = summary["measured"]["palette"]
    tokens = []
    for _, kind, value in token_values(document["style"]):
        if kind != "color":
            continue
        value = dereference(document["style"], value)
        if isinstance(value, dict) and value.get("alpha", 1) != 1:
            continue
        if isinstance(value, str) and len(value) == 9 and value[-2:].lower() != "ff":
            continue
        tokens.append(opaque_color(value))
    assert palette and tokens
    for color in colors:
        assert min(color_distance(color, entry["value"]) for entry in palette) <= ingest_config["color_delta_e"], color
        assert min(color_distance(color, value) for value in tokens) <= ingest_config["color_delta_e"], color


def radius_references(value):
    if isinstance(value, dict):
        for key, child in value.items():
            if key == "border-radius":
                yield child
            else:
                yield from radius_references(child)
    elif isinstance(value, list):
        for child in value:
            yield from radius_references(child)


def test_negative_margins_and_pill_radius_do_not_poison_measured_scales(library, fixture_site, ingest_config, page):
    url = fixture_site.url + "/scales/index.html"
    page.goto(url)
    assert page.locator(".overlap").evaluate("e => [getComputedStyle(e).marginTop,getComputedStyle(e).marginLeft]") == ["-8px", "-12px"]
    assert page.locator(".pill").evaluate("e => getComputedStyle(e).borderTopLeftRadius") == "9999px"
    artifact, _, captured = capture(library, [url])
    assert not captured["problems"], captured
    _, document, summary = draft(library, [artifact], "sane-scales")
    spacing = summary["measured"]["spacing"]
    assert spacing["base_px"] > 0 and spacing["steps_px"]
    assert all(step >= 0 for step in spacing["steps_px"]), spacing
    space_tokens = [dimension_px(dereference(document["style"], value))
                    for _, kind, value in token_values(document["style"]["space"]) if kind == "dimension"]
    assert space_tokens and all(value >= 0 for value in space_tokens), space_tokens
    radii = summary["measured"]["radii_px"]
    assert radii and any(abs(radius - 8) <= ingest_config["radius_px"] for radius in radii)
    # Both an effective geometric pill radius and retaining the authored 9999px
    # are acceptable. A value greater than the source plus its tolerance is not.
    ceiling = 9999 + ingest_config["radius_px"]
    assert all(0 <= radius <= ceiling for radius in radii), radii
    used_radii = [dimension_px(dereference(document["style"], reference))
                  for reference in radius_references(document)]
    assert all(0 <= radius <= ceiling for radius in used_radii), used_radii
