"""Amendment 11: authored geometry, public hooks, and real rendered checks."""
import pytest

from tests.composition_support import (language_for_content, content_fixture, open_content,
                                       hook_scope, common_hook_scope, scope_selector,
                                       scope_properties, assert_only_rule)
from tests.content_support import save_content
from tests.m1_support import token
from tests.test_composition_shipped import composition_report, assert_composition_passes

pytestmark = [pytest.mark.browser, pytest.mark.browser_timeout(420)]
WIDTHS = (375, 1280)


def heading_gaps(heading):
    """Measure the neighbouring visible blocks in this heading's own container."""
    return heading.evaluate("""e=>{
      const visible=n=>n.getClientRects().length && getComputedStyle(n).display!=='none'
        && getComputedStyle(n).visibility!=='hidden';
      let before=e.previousElementSibling, after=e.nextElementSibling;
      while(before && !visible(before)) before=before.previousElementSibling;
      while(after && !visible(after)) after=after.nextElementSibling;
      if(!before || !after) throw new Error('Heading fixture needs visible siblings on both sides');
      const h=e.getBoundingClientRect(), a=before.getBoundingClientRect(), b=after.getBoundingClientRect();
      return {before:h.top-a.bottom,after:b.top-h.bottom};
    }""")


@pytest.mark.parametrize("following_margin", [0, 16], ids=["equal-gaps", "farther-from-following"])
def test_heading_binds_to_following_block(library, language, tmp_path, page, following_margin):
    document = language_for_content(library, language)
    source = tmp_path / "content.json"
    content = content_fixture(source, paragraph="Short note")
    content["blocks"][0]["eyebrow"] = "Before heading"
    save_content(source, content)
    contract = open_content(library, document, source, tmp_path / "discover", page)
    heading = page.get_by_role("heading", name="Leading heading", exact=True)
    before = page.get_by_text("Before heading", exact=True)
    after = page.get_by_text("Short introduction", exact=True)
    scope = hook_scope(heading)
    for target in (heading, before, after):
        scope_selector(contract, hook_scope(target))
    parent_scope = common_hook_scope(before.or_(after))
    scope_selector(contract, parent_scope)
    scope_properties(document, parent_scope).update({
        "display": "flex", "flex-direction": "column", "gap": "{space.sixteen}"})
    scope_properties(document, hook_scope(after))["margin-block"] = token(
        document, "space", "following", "dimension", f"{following_margin}px")
    for label, preceding_margin in (("bad", 0), ("good", 32)):
        scope_properties(document, hook_scope(before))["margin-block"] = token(
            document, "space", "preceding", "dimension", f"{preceding_margin}px")
        open_content(library, document, source, tmp_path / label, page)
        for width in WIDTHS:
            page.set_viewport_size({"width": width, "height": 900})
            gaps = heading_gaps(heading)
            assert gaps == pytest.approx({"before": 16 + preceding_margin,
                                          "after": 16 + following_margin}, abs=0.05), gaps
            assert (gaps["after"] < gaps["before"]) is (label == "good"), gaps
        report = composition_report(library, document["id"], tmp_path / (label + "-check"), source, widths=WIDTHS)
        if label == "bad":
            assert_only_rule(report, "heading-binding", document, {scope}, WIDTHS)
        else:
            assert_composition_passes(report)


@pytest.mark.parametrize("direction", ["row", "column"], ids=["side-by-side", "stacked"])
def test_repeated_painted_items_require_eight_pixel_gutters(library, language, tmp_path, page, direction):
    document = language_for_content(library, language)
    source = tmp_path / "content.json"
    content = content_fixture(source, paragraph="Short note")
    content["blocks"].append({"type": "collection", "title": "Items", "items": [
        {"title": "One", "body": "Item note"}, {"title": "Two", "body": "Item note"}]})
    save_content(source, content)
    contract = open_content(library, document, source, tmp_path / "discover", page)
    item_scope = contract["content_pages"]["blocks"]["collection"]["item"]
    items = page.locator(scope_selector(contract, item_scope))
    assert items.count() == 2
    group_scope = common_hook_scope(items)
    scope_selector(contract, group_scope)
    scope_properties(document, item_scope).update({
        "background-color": "{color.panel}", "border-style": "solid",
        "border-width": "{space.one}", "border-color": "{color.ink}",
        "width": token(document, "probe", "itemwidth", "dimension", "96px"),
        "max-width": "{probe.itemwidth}", "margin-inline": "{space.zero}"})
    group = scope_properties(document, group_scope)
    group.update({"display": "flex", "flex-direction": direction, "align-items": "start",
                  "justify-content": "start", "flex-wrap": "nowrap"})
    for gap in (0, 7, 8):
        group["gap"] = token(document, "space", "gutter", "dimension", f"{gap}px")
        open_content(library, document, source, tmp_path / f"gap-{gap}", page)
        for width in WIDTHS:
            page.set_viewport_size({"width": width, "height": 900})
            a, b = [element.bounding_box() for element in items.all()]
            axis, extent = ("x", "width") if direction == "row" else ("y", "height")
            cross = "y" if direction == "row" else "x"
            assert a[cross] == pytest.approx(b[cross], abs=0.05), (a, b)
            assert b[axis] - a[axis] - a[extent] == pytest.approx(gap, abs=0.05), (a, b)
            assert all(element.evaluate("e=>getComputedStyle(e).borderLeftWidth") == "1px"
                       for element in items.all())
        report = composition_report(library, document["id"], tmp_path / f"check-{gap}", source, widths=WIDTHS)
        if gap < 8:
            assert_only_rule(report, "gutter", document, {item_scope, group_scope}, WIDTHS)
        else:
            assert_composition_passes(report)
