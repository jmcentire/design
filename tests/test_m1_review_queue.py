"""Amendment 05: actionable grouped findings, with all evidence retained.

Falsifiers: one review per width/page, lost occurrence evidence, grouping unrelated
surfaces/targets, or non-text review noise for unchanged native control appearance.
Inputs use only public language properties; rendered hooks locate observations.
"""

import pytest

from tests.m1_support import findings, run_check, slot_properties, token
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
    page.goto((site / "form.html").as_uri())
    controls = page.locator('input[type="checkbox"],input[type="radio"]')
    # Compare to real Chromium UA defaults in a separate document, without
    # changing the preview or injecting CSS into the checker under test.
    native = browser_context.new_page()
    native.set_default_timeout(5000)
    native.set_default_navigation_timeout(5000)
    appearance = """e => {
      const s = getComputedStyle(e);
      return ['appearance','accent-color','background-color','background-image',
        'border-color','border-style','border-width','border-radius','box-shadow']
        .map(p => s.getPropertyValue(p));
    }"""
    scopes = set()
    try:
        for i in range(controls.count()):
            control = controls.nth(i)
            if not control.is_visible() or not control.is_enabled():
                continue
            kind = control.get_attribute("type")
            native.set_content(f'<input type="{kind}">')
            assert control.evaluate(appearance) == native.locator("input").evaluate(appearance), (
                "Fixture control appearance is author-modified", kind)
            scope = control.evaluate("e => e.closest('[data-kd-slot]')?.dataset.kdSlot")
            assert scope, "Native control needs its public slot annotation"
            scopes.add(scope)
    finally:
        native.close()
    assert scopes, "Fixture must render an unmodified native control"
    report = run_check(library, tmp_path / "native-report")
    for scope in scopes:
        assert not [f for f in findings(report, "non-text-contrast", scope)
                    if any(o["page"] == "form.html" for o in f["occurrences"])], report
