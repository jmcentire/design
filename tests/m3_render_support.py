"""Amendment 11 rendered relations, independent of the candidate renderer/resolver.

Compare computed treatments, not used widths/positions: text reflow and box widths
can change as a consequence of a permitted font or spacing change. Color wheel
relations use ordinary sRGB HSL; byte quantization gets 1 degree / 0.015 tolerance.
"""

import colorsys
import math
import re

import pytest

from tests.m3_support import distance
from tests.test_resolution import CSS_PROPERTIES

DECORATIVE_PAINT = {"background-color", "background-image", "border-color"}
COLORS = {"color", "background-color", "border-color", "outline-color", "background-image"}
PADDINGS = {"padding-top", "padding-right", "padding-bottom", "padding-left"}
SPACING = {"padding", "padding-block", "padding-inline", "margin-block", "gap", "row-gap", "column-gap"} | PADDINGS
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
      const widgets = ['button','link','checkbox','radio','combobox','listbox','option',
        'menuitem','menuitemcheckbox','menuitemradio','slider','spinbutton','switch','tab','textbox','treeitem'];
      const interactiveSelector = 'a[href],area[href],input,select,textarea,button,summary,' +
        widgets.map(role => '[role~="' + role + '"]').join(',');
      const elements = [...new Set([body, ...body.querySelectorAll(
        '[data-kd-construct],[data-kd-slot],[data-kd-part],' + interactiveSelector)])];
      const rows = [];
      for (const e of elements) {
        const s = getComputedStyle(e), box = e.getBoundingClientRect();
        if (box.width <= 0 || box.height <= 0 || s.display === 'none' || s.visibility === 'hidden') continue;
        const slot = e.closest('[data-kd-slot]');
        const css = Object.fromEntries(properties.map(p => [p, s.getPropertyValue(p)]));
        // Typed OM preserves computed auto/percentage widths. CSSOM's used px
        // width changes with reflow even when no width treatment changed.
        const computed = e.computedStyleMap();
        css.width = String(computed.get('width'));
        // Grid CSSOM exposes used track pixels, which follow padding/container
        // width even with an unchanged 1fr treatment. Typed OM exposes computed
        // track definitions, retaining the leak check for actual grid changes.
        // https://drafts.css-houdini.org/css-typed-om/#computed-stylepropertymapreadonly-objects
        css['grid-template-columns'] = String(computed.get('grid-template-columns'));
        rows.push({tag: e.tagName, construct: e.getAttribute('data-kd-construct'),
          slot: e.getAttribute('data-kd-slot'), part: e.getAttribute('data-kd-part'),
          role: e.getAttribute('data-kd-role') || (slot && slot.getAttribute('data-kd-role')),
          emphasis: e.getAttribute('data-kd-emphasis') || (slot && slot.getAttribute('data-kd-emphasis')),
          interactive: e.matches(interactiveSelector), content_slot: Boolean(slot),
          contains_content: Boolean(e.querySelector('[data-kd-slot],' + interactiveSelector)),
          text: e.textContent.trim().replace(/\\s+/g, ' '),
          box: {x:box.x+scrollX, y:box.y+scrollY, width:box.width, height:box.height},
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


def attention_family_change(before, after, old_attention, new_attention):
    """11e: tints/washes track attention hue, not its exact RGB/lightness.

    Chromium serializes sRGB computed colors as rgb/rgba. For gradients, allow
    unchanged stops (including neutral/transparent ones), while every changed
    stop must belong to its respective attention family. Non-color structure
    remains equal so unrelated gradient-angle/image changes do not gain access.
    """
    color = r"rgba?\([^()]+\)"
    old_colors, new_colors = re.findall(color, before), re.findall(color, after)
    if not old_colors or len(old_colors) != len(new_colors):
        return False
    if re.sub(color, "COLOR", before) != re.sub(color, "COLOR", after):
        return False
    old_hue, new_hue = hsl(old_attention)[0], hsl(new_attention)[0]
    changed = False
    for old, new in zip(old_colors, new_colors):
        if old == new:
            continue
        changed = True
        for value, reference in ((old, old_hue), (new, new_hue)):
            channels = rgba(value)
            # Achromatic/fully transparent paint has no hue to compare.
            if channels[3] <= 0 or max(channels[:3]) == min(channels[:3]):
                return False
            if distance("hue-family", hsl(value)[0], reference) > 2 + 1e-9:
                return False
    return changed


def role(rows, name, emphasis="neutral"):
    candidates = [row for row in rows if row["slot"] and row["role"] == name and row["emphasis"] == emphasis]
    assert candidates, ("The offered dimension lacks a rendered role specimen", name, emphasis)
    return candidates[0]


def primary(rows):
    candidates = [row for row in rows if row["slot"] and row["emphasis"] == "primary"]
    assert candidates, "No primary-emphasis specimen on the sample screen"
    # A primary label supplies a text foreground in the vocabulary. Prefer it over an
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


def decorative(row):
    """11d excludes text, content slots and native/ARIA controls or links.

    A text-free wrapper around a control or slot is content, too; it cannot gain
    the decorative exemption merely by placing its semantics on a child.
    """
    return not (row["text"] or row["slot"] or row.get("content_slot") or row.get("interactive")
                or row.get("contains_content") or row["role"] in {"action", "control", "link"}
                or row["tag"] in {"A", "AREA", "INPUT", "SELECT", "TEXTAREA", "BUTTON", "SUMMARY"})


def assert_isolated_styles(first, second, dimensions):
    assert len(first) == len(second)
    allowed = set().union(*(ALLOWED[dimension] for dimension in dimensions))
    changes = set()
    for before, after in zip(first, second):
        metadata = {"css", "surface_lightness", "surface_rgb", "box"}
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
                if not (prop in DECORATIVE_PAINT and decorative(before) and decorative(after)):
                    old_attention, new_attention = attention(first)["css"]["color"], attention(second)["css"]["color"]
                    assert before["emphasis"] == "attention" or attention_family_change(
                        before["css"][prop], after["css"][prop], old_attention, new_attention
                    ), ("Whimsy changed content paint outside the attention hue family", before["slot"], prop)
            if prop == "text-transform":
                # Amendment 11c includes small caption/eyebrow labelling text;
                # title, subtitle and body transforms remain outside formality.
                assert before["role"] in {"label", "caption"}, "Formality changed text-transform outside label/caption roles"
            # Tracking is formality's property. The title has a required positive
            # relation below; tracking on other typography is not a cross-dimension
            # leak (11d). Text-transform retains 11c's explicit role restriction.
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
    # Amendment 11b: subtitle/body is one modular step; title/subtitle may
    # skip whole steps. Infer k from measured sizes, never from implementation.
    assert subtitle / body == pytest.approx(ratio, abs=0.02)
    observed = title / subtitle
    exponent = round(math.log(observed) / math.log(ratio))
    assert exponent >= 1, ("Title must be at least one modular step above subtitle", observed, ratio)
    assert observed == pytest.approx(ratio ** exponent, rel=0.02), ("Title skipped a fractional modular step", observed, ratio, exponent)
    return exponent


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
            first_steps = assert_type_scale(first, a)
            second_steps = assert_type_scale(second, b)
            assert first_steps == second_steps, ("A/B changed the number of modular title steps", first_steps, second_steps)
            assert "font-size" in changed
        elif dimension in {"density", "shape"}:
            properties = PADDINGS | {"row-gap", "column-gap", "margin-block"} if dimension == "density" else RADII - {"border-radius"}
            increased = False
            for low_row, high_row in zip(low, high):
                for prop in properties:
                    small, large = numeric_values(low_row["css"][prop]), numeric_values(high_row["css"][prop])
                    if prop == "margin-block" and "type-scale" in dimensions and len(small) == len(large) and all(
                            x / pixels(low_row["css"]["font-size"]) == pytest.approx(
                                y / pixels(high_row["css"]["font-size"]), abs=0.001) for x, y in zip(small, large)):
                        continue  # UA em margins may follow the independent type-scale change.
                    if dimension == "shape" and max(len(small), len(large)) == 2:
                        small = small * 2 if len(small) == 1 else small
                        large = large * 2 if len(large) == 1 else large
                    assert len(small) == len(large), (prop, small, large)
                    # The dimensional input must produce an increasing specimen;
                    # it need not scale every radius/space uniformly. Responsive
                    # treatments may redistribute spacing or shape within that same
                    # dimension without leaking into another property family (11d).
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
        if "value-contrast" not in dimensions:
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
