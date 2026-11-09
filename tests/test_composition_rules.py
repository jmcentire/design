"""Amendment 09 isolated defects and boundary controls through render/check.

Expected bounds come from the amendment, never candidate findings. A direct
Chromium observation first proves the authored input actually reaches the bound.
Only the seeded composition rule may fail; counterparts must pass all four.
"""
import pytest

from tests.composition_support import (language_for_content, content_fixture, open_content,
                                       hook_scope, common_hook_scope, scope_selector,
                                       scope_properties, assert_only_rule)
from tests.content_support import save_content
from tests.m1_support import token
from tests.test_composition_shipped import composition_report, assert_composition_passes, PARAGRAPH

pytestmark = [pytest.mark.browser, pytest.mark.browser_timeout(420)]


@pytest.mark.parametrize("bad_size,good_size", [(17, 16), (15, 16)],
                         ids=["successive-level-inversion", "below-paragraph-size"])
def test_heading_scale_has_both_bounds(library, language, tmp_path, page, bad_size, good_size):
    document = language_for_content(library, language)
    source = tmp_path / "content.json"
    content_fixture(source)
    open_content(library, document, source, tmp_path / "discover", page)
    heading = page.get_by_role("heading", name="Second heading", exact=True)
    scope = hook_scope(heading)
    for label, size in (("bad", bad_size), ("good", good_size)):
        scope_properties(document, scope)["font-size"] = token(document, "probe", "heading", "dimension", f"{size}px")
        open_content(library, document, source, tmp_path / label, page)
        assert float(heading.evaluate("e=>getComputedStyle(e).fontSize").removesuffix("px")) == size
        assert page.get_by_role("heading", name="Leading heading").evaluate("e=>getComputedStyle(e).fontSize") == "16px"
        assert page.get_by_text(PARAGRAPH, exact=True).evaluate("e=>getComputedStyle(e).fontSize") == "16px"
        report = composition_report(library, document["id"], tmp_path / (label + "-report"), source, widths=(375, 1280))
        if label == "bad":
            assert_only_rule(report, "heading-scale", document, {scope}, (375, 1280))
        else:
            assert_composition_passes(report)


@pytest.mark.parametrize("paint", ["background", "border"])
def test_text_inset_uses_line_boxes_and_eight_pixel_boundary(library, language, tmp_path, page, paint):
    document = language_for_content(library, language)
    source = tmp_path / "content.json"
    content_fixture(source, paragraph="Inset probe")
    open_content(library, document, source, tmp_path / "discover", page)
    scope = hook_scope(page.get_by_text("Inset probe", exact=True))
    props = scope_properties(document, scope)
    if paint == "background":
        props.update({"background-color": "{color.panel}", "border-width": "{space.zero}"})
    else:
        props.update({"border-style": "solid", "border-color": "{color.ink}", "border-width": "{space.one}"})
    for inset in (7, 8):
        # The border edge is one pixel outside its content edge in the bordered
        # case; the specification constrains the total horizontal inset.
        padding = inset - (1 if paint == "border" else 0)
        props["padding-inline"] = token(document, "space", "inset", "dimension", f"{padding}px")
        open_content(library, document, source, tmp_path / f"inset-{inset}", page)
        observed = page.get_by_text("Inset probe", exact=True).evaluate("""e=>{
          const box=e.closest('[data-kd-slot]'), r=box.getBoundingClientRect();
          const range=document.createRange(); range.selectNodeContents(e);
          const lines=[...range.getClientRects()].filter(x=>x.width && x.height);
          return {left:Math.min(...lines.map(x=>x.left))-r.left,
                  background:getComputedStyle(box).backgroundColor,
                  border:getComputedStyle(box).borderLeftWidth,
                  style:getComputedStyle(box).borderLeftStyle};
        }""")
        assert observed["left"] == pytest.approx(inset, abs=0.05), observed
        if paint == "background":
            assert observed["background"] == "rgb(232, 232, 232)"
        else:
            assert observed["border"] == "1px" and observed["style"] == "solid", observed
        report = composition_report(library, document["id"], tmp_path / f"check-{inset}", source, widths=(375, 1280))
        if inset == 7:
            assert_only_rule(report, "text-inset", document, {scope}, (375, 1280))
        else:
            assert_composition_passes(report)


@pytest.mark.parametrize("direction", ["row", "column"])
def test_control_separation_requires_four_pixels_between_painted_targets(library, language, tmp_path, page, direction):
    document = language_for_content(library, language)
    source = tmp_path / "content.json"
    content_fixture(source, actions=True)
    contract = open_content(library, document, source, tmp_path / "discover", page)
    links = page.get_by_role("link", name="One", exact=True).or_(page.get_by_role("link", name="Two", exact=True))
    assert links.count() == 2
    group_scope = common_hook_scope(links)
    # The review pins a published actions part for section action links. Discover
    # its owning construct from the real page instead of assuming a construct id.
    assert group_scope.endswith("~actions"), group_scope
    scope_selector(contract, group_scope)
    scopes = {hook_scope(links.nth(i)) for i in range(2)} | {group_scope, group_scope.split("~", 1)[0]}
    props = scope_properties(document, group_scope)
    props.update({"display": "flex", "flex-direction": direction})
    for gap in (3, 4):
        props["gap"] = token(document, "space", "separation", "dimension", f"{gap}px")
        open_content(library, document, source, tmp_path / f"gap-{gap}", page)
        boxes = [link.bounding_box() for link in links.all()]
        assert all(box and box["width"] >= 24 and box["height"] >= 24 for box in boxes), boxes
        a, b = boxes
        separation = max(b["x"] - a["x"] - a["width"], a["x"] - b["x"] - b["width"],
                         b["y"] - a["y"] - a["height"], a["y"] - b["y"] - b["height"])
        assert separation == pytest.approx(gap, abs=0.05), boxes
        paint = links.evaluate_all("""els=>els.map(e=>{const s=getComputedStyle(e);return {
          background:s.backgroundColor, border:parseFloat(s.borderTopWidth), style:s.borderTopStyle};})""")
        assert any(p["background"] == "rgb(232, 232, 232)" or
                   (p["border"] > 0 and p["style"] not in {"none", "hidden"}) for p in paint), paint
        report = composition_report(library, document["id"], tmp_path / f"check-{gap}", source, widths=(375, 1280))
        if gap == 3:
            assert_only_rule(report, "control-separation", document, scopes, (375, 1280))
        else:
            assert_composition_passes(report)


@pytest.mark.parametrize("characters", [59, 60])
@pytest.mark.parametrize("font_size", [16, 20])
def test_measure_respects_character_width_and_viewport_boundaries(library, language, tmp_path, page, characters, font_size):
    document = language_for_content(library, language)
    document["style"]["size"]["body"]["$value"] = {"value": font_size, "unit": "px"}
    source = tmp_path / "content.json"
    text = ("A short note " * 6)[:characters - 1] + "."
    assert len(text.strip()) == characters
    content = content_fixture(source, paragraph="Short section text")
    # Use a directly hooked paragraph. A section's body slot may wrap several
    # paragraphs; max-width on that wrapper does not override a child's 40em cap.
    content["blocks"][0]["body"] = text
    save_content(source, content)
    contract = open_content(library, document, source, tmp_path / "discover", page)
    paragraph = page.get_by_text(text, exact=True)
    scope = hook_scope(paragraph)
    assert paragraph.evaluate("(e, selector)=>e.localName==='p' && e.matches(selector)", scope_selector(contract, scope)), (
        "Measure fixture must style the paragraph itself through its published hook", scope)
    props = scope_properties(document, scope)
    limit = 40 * font_size
    if characters == 60:
        # Positive control for the documented default: width alone cannot defeat
        # the paragraph's own 40em max-width. Remove the fixture's explicit cap.
        props["width"] = token(document, "probe", "prosewidth", "dimension", f"{limit + 16}px")
        props.pop("max-width", None)
        open_content(library, document, source, tmp_path / "default-cap", page, width=1024)
        assert paragraph.bounding_box()["width"] == limit
        report = composition_report(library, document["id"], tmp_path / "check-default-cap", source, widths=(1023, 1024, 1280))
        assert_composition_passes(report)
    for width in (limit + 16, limit):
        props.update({"width": token(document, "probe", "prosewidth", "dimension", f"{width}px"),
                      "max-width": "{probe.prosewidth}"})
        open_content(library, document, source, tmp_path / f"measure-{width}", page, width=1024)
        observed = paragraph.evaluate("""e=>({width:e.getBoundingClientRect().width,
          size:parseFloat(getComputedStyle(e).fontSize),maxWidth:parseFloat(getComputedStyle(e).maxWidth)})""")
        assert observed == {"width": width, "size": font_size, "maxWidth": width}, observed
        report = composition_report(library, document["id"], tmp_path / f"check-{width}", source, widths=(1023, 1024, 1280))
        if width > limit and characters == 60:
            assert_only_rule(report, "measure", document, {scope}, (1024, 1280))
        else:
            assert_composition_passes(report)


def test_body_size_is_weighted_by_paragraph_characters(library, language, tmp_path, page):
    document = language_for_content(library, language)
    source = tmp_path / "content.json"
    content_fixture(source)
    open_content(library, document, source, tmp_path / "discover", page)
    title = page.get_by_role("heading", name="Leading heading", exact=True)
    target = page.get_by_role("heading", name="Second heading", exact=True)
    intro = page.get_by_text("Short introduction", exact=True)
    scope_properties(document, hook_scope(title))["font-size"] = token(document, "probe", "top", "dimension", "32px")
    scope_properties(document, hook_scope(intro))["font-size"] = token(document, "probe", "short", "dimension", "20px")
    scope = hook_scope(target)
    for size in (15, 18):
        scope_properties(document, scope)["font-size"] = token(document, "probe", "second", "dimension", f"{size}px")
        open_content(library, document, source, tmp_path / f"weighted-{size}", page)
        weights = page.locator("p").evaluate_all("""els=>{
          const totals={}; for(const e of els){if(!e.getClientRects().length) continue;
            const size=parseFloat(getComputedStyle(e).fontSize);
            totals[size]=(totals[size]||0)+e.textContent.trim().length;
          } return totals;
        }""")
        assert weights["16"] > sum(count for font, count in weights.items() if font != "16"), weights
        assert weights["20"] > 0, weights
        assert target.evaluate("e=>getComputedStyle(e).fontSize") == f"{size}px"
        report = composition_report(library, document["id"], tmp_path / f"check-{size}", source, widths=(375, 1280))
        if size == 15:
            assert_only_rule(report, "heading-scale", document, {scope}, (375, 1280))
        else:
            # 18px is above the dominant 16px, though below a short 20px
            # paragraph. Using the maximum paragraph size is an incorrect rule.
            assert_composition_passes(report)
