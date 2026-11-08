"""Amendment 11 rendered relations, independent of the candidate renderer/resolver.

Compare computed treatments, not used widths/positions: text reflow and box widths
can change as a consequence of a permitted font or spacing change. Color wheel
relations use ordinary sRGB HSL; byte quantization gets 1 degree / 0.015 tolerance.
"""

import colorsys
import re

import pytest

from tests.m3_support import distance
from tests.test_resolution import CSS_PROPERTIES

COLORS = {"color", "background-color", "border-color", "outline-color", "background-image"}
PADDINGS = {"padding-top", "padding-right", "padding-bottom", "padding-left"}
SPACING = {"padding", "padding-block", "padding-inline", "gap", "row-gap", "column-gap"} | PADDINGS
TYPOGRAPHY = {"font-family"}
SIZES = {"font-size", "line-height"}
# Shorthand expansion is observed explicitly to include asymmetric treatments.
RADII = {"border-radius", "border-top-left-radius", "border-top-right-radius",
         "border-bottom-left-radius", "border-bottom-right-radius"}
PROPERTIES = CSS_PROPERTIES | COLORS | SPACING | RADII | {"opacity", "transform", "filter"}
ALLOWED = {
    "hue-family": COLORS, "saturation": COLORS, "value-contrast": COLORS,
    "type-pairing": TYPOGRAPHY, "type-scale": SIZES, "density": SPACING,
    "shape": RADII, "formality": {"text-transform", "letter-spacing"}, "whimsy": COLORS,
}


def paint_snapshot(page):
    return page.locator("body").evaluate("""(body, properties) => {
      const elements = [...new Set([body, ...body.querySelectorAll(
        '[data-kd-construct],[data-kd-slot],[data-kd-part],input,select,textarea,button')])];
      const rows = [];
      for (const e of elements) {
        const s = getComputedStyle(e), box = e.getBoundingClientRect();
        if (box.width <= 0 || box.height <= 0 || s.display === 'none' || s.visibility === 'hidden') continue;
        const slot = e.closest('[data-kd-slot]');
        const css = Object.fromEntries(properties.map(p => [p, s.getPropertyValue(p)]));
        // Typed OM preserves computed auto/percentage widths. CSSOM's used px
        // width changes with reflow even when no width treatment changed.
        css.width = String(e.computedStyleMap().get('width'));
        rows.push({tag: e.tagName, construct: e.getAttribute('data-kd-construct'),
          slot: e.getAttribute('data-kd-slot'), part: e.getAttribute('data-kd-part'),
          role: e.getAttribute('data-kd-role') || (slot && slot.getAttribute('data-kd-role')),
          emphasis: e.getAttribute('data-kd-emphasis') || (slot && slot.getAttribute('data-kd-emphasis')),
          text: e.textContent.trim().replace(/\\s+/g, ' '),
          css});
      }
      return rows;
    }""", sorted(PROPERTIES))


def rgba(value):
    numbers = [float(part) for part in re.findall(r"[\d.]+", value)]
    assert value.startswith("rgb") and len(numbers) in (3, 4), value
    return numbers if len(numbers) == 4 else [*numbers, 1]


def hsl(value):
    numbers = rgba(value)
    assert numbers[3] > 0, "A transparent foreground has no observable hue"
    hue, lightness, saturation = colorsys.rgb_to_hls(*(channel / 255 for channel in numbers[:3]))
    return hue * 360, saturation, lightness


def role(rows, name, emphasis="neutral"):
    candidates = [row for row in rows if row["slot"] and row["role"] == name and row["emphasis"] == emphasis]
    assert candidates, ("The offered dimension lacks a rendered role specimen", name, emphasis)
    return candidates[0]


def primary(rows):
    candidates = [row for row in rows if row["slot"] and row["emphasis"] == "primary"]
    assert candidates, "No primary-emphasis specimen on the sample screen"
    # Price is a text foreground in the public vocabulary. Prefer it over an
    # action button whose foreground may intentionally contrast with its fill.
    return next((row for row in candidates if row["role"] == "label"), candidates[0])


def attention(rows):
    candidates = [row for row in rows if row["slot"] and row["emphasis"] == "attention"]
    assert candidates, "Whimsy needs a rendered attention-emphasis specimen"
    return candidates[0]


def pixels(value):
    return 0.0 if value == "normal" else float(value.removesuffix("px"))


def numeric_values(value):
    return (0.0,) if value == "normal" else tuple(float(part) for part in re.findall(r"-?[\d.]+", value))


def assert_isolated_styles(first, second, dimensions):
    assert len(first) == len(second)
    allowed = set().union(*(ALLOWED[dimension] for dimension in dimensions))
    changes = set()
    for before, after in zip(first, second):
        metadata = {"css", "surface_lightness", "surface_rgb"}
        assert {key: value for key, value in before.items() if key not in metadata} == {
            key: value for key, value in after.items() if key not in metadata}, "Candidate content/semantics changed"
        for prop in PROPERTIES:
            if before["css"][prop] == after["css"][prop]:
                continue
            if prop == "margin-block" and "type-scale" in dimensions:
                # UA heading margins can be em-based: unchanged relative
                # margins are a consequence of font-size, not a density change.
                a, b = numeric_values(before["css"][prop]), numeric_values(after["css"][prop])
                if len(a) == len(b) and all(x / pixels(before["css"]["font-size"]) == pytest.approx(
                        y / pixels(after["css"]["font-size"]), abs=0.001) for x, y in zip(a, b)):
                    continue
            assert prop in allowed, ("An unrelated computed treatment changed", dimensions, before["slot"],
                                     prop, before["css"][prop], after["css"][prop])
            changes.add(prop)
            if prop in COLORS and set(dimensions) & {"whimsy"} and not set(dimensions) & {
                    "hue-family", "saturation", "value-contrast"}:
                old_attention, new_attention = attention(first)["css"]["color"], attention(second)["css"]["color"]
                assert before["emphasis"] == "attention" or (
                    before["css"][prop] == old_attention and after["css"][prop] == new_attention
                ), ("Whimsy changed paint unrelated to the attention color", before["slot"], prop)
            if prop == "text-transform":
                assert before["role"] == "label", "Formality changed a non-label text transform"
            if prop == "letter-spacing":
                assert before["role"] == "title", "Formality changed non-title tracking"
    return changes


def assert_formality(rows, value):
    labels = [row for row in rows if row["slot"] and row["role"] == "label"]
    assert labels, "Formality has no rendered label specimen"
    assert all(row["css"]["text-transform"] == ("uppercase" if value >= 0.5 else "none") for row in labels)


def assert_whimsy(rows, value):
    primary_hue, primary_saturation, _ = hsl(primary(rows)["css"]["color"])
    attention_hue, attention_saturation, _ = hsl(attention(rows)["css"]["color"])
    assert min(primary_saturation, attention_saturation) > 0.01, "Hue variation is not visible in achromatic specimens"
    gap = distance("hue-family", primary_hue, attention_hue)
    if value >= 0.5:
        assert gap >= 59, ("Whimsy >= 0.5 requires at least 60 degrees", value, gap)
    return gap


def assert_type_scale(rows, ratio):
    title, subtitle, body = (pixels(role(rows, name)["css"]["font-size"]) for name in ("title", "subtitle", "body"))
    # Normal CSS/font-size rounding can introduce subpixel error, but cannot
    # justify a different hierarchy ratio or a constant ratio across choices.
    assert title / subtitle == pytest.approx(ratio, abs=0.02)
    assert subtitle / body == pytest.approx(ratio, abs=0.02)


def contrast_gap(rows):
    body = role(rows, "body")
    foreground = rgba(body["css"]["color"])
    composed = [foreground[i] * foreground[3] + rows[0]["surface_rgb"][i] * (1 - foreground[3]) for i in range(3)]
    foreground_lightness = hsl('rgb(' + ','.join(map(str, composed)) + ')')[2]
    return abs(foreground_lightness - rows[0]["surface_lightness"])


def assert_dimension_effects(first, second, first_values, second_values, dimensions):
    changed = assert_isolated_styles(first, second, dimensions)
    assert changed, "The advertised pair has identical computed treatments"
    for dimension in dimensions:
        a, b = first_values[dimension], second_values[dimension]
        low, high = (first, second) if a < b else (second, first)
        if dimension == "hue-family":
            hue_a, sat_a, _ = hsl(primary(first)["css"]["color"])
            hue_b, sat_b, _ = hsl(primary(second)["css"]["color"])
            assert min(sat_a, sat_b) > 0.01
            assert distance("hue-family", hue_a, hue_b) > 1, "Hue choices produced the same primary hue"
        elif dimension == "saturation":
            assert hsl(primary(high)["css"]["color"])[1] > hsl(primary(low)["css"]["color"])[1], (
                "Saturation choices did not increase rendered chroma")
        elif dimension == "value-contrast":
            # The page background may be on body or page-shell. Alpha-composed
            # surface observations are supplied separately by the browser driver.
            assert contrast_gap(high) > contrast_gap(low), "Value-contrast did not increase text/surface lightness difference"
        elif dimension == "type-pairing":
            assert any(role(first, name)["css"]["font-family"] != role(second, name)["css"]["font-family"]
                       for name in ("title", "body")), "Type pairings use the same computed families"
        elif dimension == "type-scale":
            assert_type_scale(first, a)
            assert_type_scale(second, b)
            assert "font-size" in changed
        elif dimension in {"density", "shape"}:
            properties = PADDINGS | {"row-gap", "column-gap"} if dimension == "density" else RADII - {"border-radius"}
            increased = False
            for low_row, high_row in zip(low, high):
                for prop in properties:
                    small, large = numeric_values(low_row["css"][prop]), numeric_values(high_row["css"][prop])
                    if dimension == "shape" and max(len(small), len(large)) == 2:
                        small = small * 2 if len(small) == 1 else small
                        large = large * 2 if len(large) == 1 else large
                    assert len(small) == len(large), (prop, small, large)
                    assert all(y >= x for x, y in zip(small, large)), (dimension, prop, small, large)
                    increased |= any(y > x for x, y in zip(small, large))
            assert increased, ("Dimension has no visible numeric effect", dimension)
        elif dimension == "formality":
            assert_formality(first, a)
            assert_formality(second, b)
            assert pixels(role(high, "title")["css"]["letter-spacing"]) >= pixels(role(low, "title")["css"]["letter-spacing"])
        elif dimension == "whimsy":
            gap_a, gap_b = assert_whimsy(first, a), assert_whimsy(second, b)
            assert (gap_b - gap_a) * (b - a) >= -abs(b - a), "Attention/primary hue distance decreased with whimsy"
    # Primary color coordinates belonging to fixed dimensions stay fixed too;
    # merely allowing all color CSS to vary would miss hidden changes of saturation
    # or lightness during a hue-only comparison.
    if set(dimensions) & {"hue-family", "saturation", "value-contrast", "whimsy"}:
        before, after = hsl(primary(first)["css"]["color"]), hsl(primary(second)["css"]["color"])
        if "hue-family" not in dimensions and min(before[1], after[1]) > 0.01:
            assert distance("hue-family", before[0], after[0]) <= 1
        if "saturation" not in dimensions:
            assert before[1] == pytest.approx(after[1], abs=0.015)
        assert before[2] == pytest.approx(after[2], abs=0.015)
    if "value-contrast" not in dimensions and all("surface_rgb" in rows[0] for rows in (first, second)):
        assert contrast_gap(first) == pytest.approx(contrast_gap(second), abs=0.015), "An unrelated text/surface contrast dimension changed"


def declared_font_genre(family):
    """Classify explicit generic/common system stacks without guessing font names.

    This is evidence about the declared family/stack. Unknown custom families are
    returned as unresolved, not misclassified from a substring in their names.
    Actual font loading/use is separately exercised by the supplied-font tests.
    """
    serif = {"serif", "ui-serif", "times", "times new roman", "georgia", "palatino",
             "palatino linotype", "book antiqua", "baskerville", "charter", "didot", "rockwell"}
    sans = {"sans-serif", "ui-sans-serif", "system-ui", "arial", "helvetica", "helvetica neue",
            "verdana", "tahoma", "trebuchet ms", "segoe ui", "arial rounded mt bold", "-apple-system"}
    for name in family.split(","):
        name = name.strip().strip("\"'").lower()
        if name in serif:
            return "serif"
        if name in sans:
            return "sans"
    return None


def assert_known_font_genres(rows, pairing):
    expected = "serif" if pairing in {"serif", "slab"} else "sans"
    unresolved = []
    for name in ("title", "body"):
        family = role(rows, name)["css"]["font-family"]
        genre = declared_font_genre(family)
        if genre is None:
            unresolved.append(family)
        else:
            assert genre == expected, (pairing, name, family)
    return unresolved
