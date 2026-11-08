"""Amendment 05: actionable grouped findings, with all evidence retained.

Falsifiers: one review per width/page, lost occurrence evidence, grouping unrelated
surfaces/targets, or non-text review noise for unchanged native control appearance.
Inputs use only public language properties; rendered hooks locate observations.
"""

from io import BytesIO

import pytest
from PIL import Image

from tests.m1_support import contrast_ratio, findings, run_check, slot_properties, token
from tests.test_m1_design import solid_background
from tests.support import PAGES

pytestmark = [pytest.mark.browser, pytest.mark.browser_timeout(240)]


def rendered_places(page, site, scope, widths=(320, 768)):
    places = set()
    for width in widths:
        page.set_viewport_size({"width": width, "height": 900})
        for name in PAGES:
            page.goto((site / name).as_uri())
            slots = page.locator(f'[data-kd-slot="{scope}"]')
            if any(slots.nth(i).is_visible() and slots.nth(i).inner_text().strip()
                   for i in range(slots.count())):
                places.add((name, width))
    assert len(places) > 1, "Fixture must repeat the same issue"
    return places


@pytest.mark.parametrize("surface", ["solid", "image", "gradient"])
def test_repeated_contrast_issue_is_one_finding_with_all_places(library, language, tmp_path, page, surface):
    props = slot_properties(language, slot="price")
    props.update({"color": token(language, "probe", "faint", "color", "#777777"),
                  "background-color": "{color.paper}", "font-size": "{size.body}",
                  "font-weight": "{type.weight}"})
    if surface == "image":
        props["background-image"] = "asset:fixture-image:primary"
    elif surface == "gradient":
        props["background-image"] = token(language, "probe", "wash", "gradient", [
            {"color": "#ffffff", "position": 0}, {"color": "#000000", "position": 1}])
    library.write(language)
    site = library.build(tmp_path / "places")
    expected = rendered_places(page, site, "listing-card.price")
    report = run_check(library, tmp_path / "grouped", widths=(320, 768),
                       accepted=False if surface == "solid" else None)
    issues = findings(report, "contrast", "listing-card.price")
    assert len(issues) == 1, issues
    issue = issues[0]
    assert issue["type"] == ("violation" if surface == "solid" else "needs-review")
    assert issue["exception"] is None
    assert {(o["page"], o["width"]) for o in issue["occurrences"]} == expected
    # run_check requires needs_review to count report rows, not their occurrences.


def test_different_unresolved_surfaces_and_targets_remain_separate(library, language, tmp_path, page):
    first = token(language, "probe", "first", "gradient", [
        {"color": "#ffffff", "position": 0}, {"color": "#000000", "position": 1}])
    second = token(language, "probe", "second", "gradient", [
        {"color": "#123456", "position": 0}, {"color": "#654321", "position": 1}])
    slot_properties(language, slot="price")["background-image"] = first
    slot_properties(language, slot="title")["background-image"] = first
    language["overrides"].append({"scope": "listing-card.price@md",
                                  "properties": {"background-image": second},
                                  "reason": "Distinct unresolved surface at md"})
    library.write(language)
    site = library.build(tmp_path / "separate-places")
    expected_price = rendered_places(page, site, "listing-card.price")
    expected_title = rendered_places(page, site, "listing-card.title")
    report = run_check(library, tmp_path / "separate", widths=(320, 768))
    price = findings(report, "contrast", "listing-card.price", "needs-review")
    title = findings(report, "contrast", "listing-card.title", "needs-review")
    assert len(price) == 2 and len(title) == 1, (price, title)
    assert {frozenset(o["width"] for o in f["occurrences"]) for f in price} == {
        frozenset({320}), frozenset({768})}
    assert {(o["page"], o["width"]) for f in price for o in f["occurrences"]} == expected_price
    assert {(o["page"], o["width"]) for o in title[0]["occurrences"]} == expected_title


def control_pixels(control, native):
    """Compare painted pixels with a real UA input at the same size/state.

    Only the separate reference document is styled to match size and backdrop.
    Subpixel placement is preserved to avoid changing rasterization alignment.
    Ancestor colors set the reference backdrop; input appearance is still native.
    """
    control.scroll_into_view_if_needed(timeout=5000)
    state = control.evaluate("""e => {
      const r = e.getBoundingClientRect();
      // Paint ancestor backgrounds over the default white canvas. Exclude the
      // input's own background: copying it would hide authored paint changes.
      const canvas = document.createElement('canvas'); canvas.width = canvas.height = 1;
      const context = canvas.getContext('2d');
      context.fillStyle = '#ffffff'; context.fillRect(0, 0, 1, 1);
      const ancestors = [];
      for (let parent = e.parentElement; parent; parent = parent.parentElement) ancestors.push(parent);
      for (const parent of ancestors.reverse()) {
        const style = getComputedStyle(parent);
        if (style.backgroundImage !== 'none') throw new Error('Fixture requires a solid control backdrop');
        context.fillStyle = style.backgroundColor; context.fillRect(0, 0, 1, 1);
      }
      const pixel = context.getImageData(0, 0, 1, 1).data;
      return {type: e.type, checked: e.checked, disabled: e.disabled,
        indeterminate: e.indeterminate, readOnly: e.readOnly,
        value: e.value, placeholder: e.placeholder,
        backdrop: `rgb(${pixel[0]}, ${pixel[1]}, ${pixel[2]})`,
        width: r.width, height: r.height, x: r.x, y: r.y};
    }""")
    native.set_content('<!doctype html><input>')
    reference = native.locator("input")
    reference.evaluate("""(e, state) => {
      document.documentElement.style.backgroundColor = state.backdrop;
      for (const key of ['type','checked','disabled','indeterminate','readOnly','value','placeholder'])
        e[key] = state[key];
      Object.assign(e.style, {position: 'absolute', margin: '0', boxSizing: 'border-box',
        width: `${state.width}px`, height: `${state.height}px`,
        left: `${16 + ((state.x % 1 + 1) % 1)}px`, top: `${16 + ((state.y % 1 + 1) % 1)}px`});
    }""", state)

    def pixels(locator):
        data = locator.screenshot(timeout=5000, animations="disabled", caret="hide", scale="css")
        with Image.open(BytesIO(data)) as picture:
            rgba = picture.convert("RGBA")
            return rgba.size, rgba.tobytes()

    return pixels(control), pixels(reference)


def test_native_control_appearance_does_not_create_non_text_contrast_findings(
        library, language, tmp_path, page, browser_context):
    # Leave native boundary/appearance properties unauthored. Required role text
    # pairing stays black/white; no authored typography or control decoration.
    black = token(language, "probe", "black", "color", "#000000")
    for emphases in language["roles"].values():
        for properties in emphases.values():
            properties.clear()
            properties.update({"color": black, "surface": "{color.paper}"})
    library.write(language)
    site = library.build(tmp_path / "native-controls")
    page.set_viewport_size({"width": 320, "height": 900})
    native = browser_context.new_page()
    native.set_default_timeout(5000)
    native.set_default_navigation_timeout(5000)
    observed = set()
    modified = set()
    try:
        for name in ("search.html", "states.html"):
            page.goto((site / name).as_uri())
            controls = page.locator('input[type="checkbox"],input[type="radio"]')
            for i in range(controls.count()):
                control = controls.nth(i)
                if not control.is_visible() or not control.is_enabled():
                    continue
                scope = control.evaluate("e => e.closest('[data-kd-slot]')?.dataset.kdSlot")
                assert scope, "Native control needs its public slot annotation"
                actual, reference = control_pixels(control, native)
                if actual == reference:
                    observed.add((scope, name))
                else:
                    modified.add((scope, name))
        # Reports identify a slot/page, not an individual repeated control. Do
        # not exclude a scope containing both native and author-painted examples.
        observed -= modified
        assert observed, "Fixture must render a pixel-identical native control"
        report = run_check(library, tmp_path / "native-report")
        for scope, name in observed:
            assert not [f for f in findings(report, "non-text-contrast", scope)
                        if any(o["page"] == name for o in f["occurrences"])], report

        # Positive control: a visibly authored low-contrast text input must still
        # receive a non-text-contrast finding; excluding all controls is wrong.
        page.goto((site / "form.html").as_uri())
        selector = 'input:not([type]),input[type="text"],input[type="email"],input[type="search"]'
        inputs = page.locator(selector)
        eligible = [i for i in range(inputs.count())
                    if inputs.nth(i).is_visible() and inputs.nth(i).is_enabled()]
        assert eligible, "Fixture requires a text input for the authored positive control"
        index = eligible[0]
        scope = inputs.nth(index).evaluate("e => e.closest('[data-kd-slot]')?.dataset.kdSlot")
        assert scope
        construct, slot = scope.split(".")
        treatment = {"background-color": token(language, "probe", "faint", "color", "#eeeeee"),
                     "border-color": "{probe.faint}",
                     "border-style": "solid",
                     "border-width": token(language, "probe", "edge", "dimension", "2px")}
        slot_properties(language, construct, slot).update(treatment)
        for properties in language["roles"]["control"].values():
            properties.update(treatment)
        library.write(language)
        styled_site = library.build(tmp_path / "authored-controls")
        page.goto((styled_site / "form.html").as_uri())
        styled = page.locator(selector).nth(index)
        assert styled.evaluate("e => e.closest('[data-kd-slot]')?.dataset.kdSlot") == scope
        actual, reference = control_pixels(styled, native)
        assert actual != reference, "Positive control must change painted appearance"
        painted = styled.evaluate("""e => {
          const s = getComputedStyle(e);
          return {background: s.backgroundColor,
            borders: ['Top','Right','Bottom','Left'].map(side =>
              [s['border'+side+'Style'], s['border'+side+'Width'], s['border'+side+'Color']])};
        }""")
        assert painted["background"] == "rgb(238, 238, 238)"
        assert all(border == ["solid", "2px", "rgb(238, 238, 238)"] for border in painted["borders"]), painted
        adjacent = solid_background(styled.locator(".."))
        adjacent_hex = "#" + "".join(f"{channel:02x}" for channel in adjacent)
        ratio = contrast_ratio("#eeeeee", adjacent_hex)
        assert ratio < 3, (painted, adjacent, ratio)
        styled_report = run_check(library, tmp_path / "authored-report", accepted=False)
        violations = findings(styled_report, "non-text-contrast", scope, "violation")
        assert any(f["measured"] == ratio and f["threshold"] == 3 for f in violations), styled_report
    finally:
        native.close()
