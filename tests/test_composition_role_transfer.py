"""Amendment 11: distinct source surfaces and semantic typography survive ingest.

The source owns all expected values. Capture, draft, fidelity, save, preview and
check are real public commands. Context-only fidelity styling cannot substitute
for transferring the same treatment into the saved language's sample pages.
"""
import json

import pytest

from tests.content_browser_support import rgba
from tests.m2_support import color_distance, confined
from tests.support import PAGES
from tests.test_composition_binding_gutter import heading_gaps
from tests.test_composition_ingest import configure_capture, css, derive
from tests.test_composition_shipped import composition_report, assert_composition_passes
from tests.test_m2_fidelity_content import repeated_groups

pytestmark = [pytest.mark.browser, pytest.mark.browser_timeout(600)]
BODY = "#182534"
MUTED = "#687888"
ITEMS = [
    ["Morning light crossed the stone path while a small bird rested beside the gate.",
     "Recorded on the first visit"],
    ["Quiet branches moved above the bench as the afternoon breeze reached the orchard.",
     "Recorded on the second visit"],
]
LEAD = "A larger introduction invites the reader to observe small changes and keep a careful record of each visit."
SURFACE_KEYS = ["background-color", "border-top-color", "border-top-width", "border-top-style",
                "border-top-left-radius", "box-shadow", "padding-top", "padding-right",
                "padding-bottom", "padding-left"]


def assert_color(actual, expected, tolerance):
    channels, alpha = rgba(actual)
    assert alpha == 1, (actual, expected)
    hex_color = "#" + "".join(f"{round(channel):02x}" for channel in channels)
    assert color_distance(hex_color, expected) <= tolerance, (actual, expected)


def assert_surface(element, expected, tolerance):
    observed = css(element, SURFACE_KEYS)
    for key in SURFACE_KEYS:
        if key.endswith("color"):
            channels, _ = rgba(expected[key])
            source_color = "#" + "".join(f"{round(channel):02x}" for channel in channels)
            assert_color(observed[key], source_color, tolerance)
        elif key in {"border-top-style", "box-shadow"}:
            assert observed[key] == expected[key], (key, observed, expected)
        else:
            assert float(observed[key].removesuffix("px")) == pytest.approx(
                float(expected[key].removesuffix("px")), abs=1), (key, observed, expected)


def assert_unpainted(element):
    values = css(element, ["background-color", "background-image", "border-top-width",
                           "border-right-width", "border-bottom-width", "border-left-width", "box-shadow"])
    assert rgba(values["background-color"])[1] == 0, values
    assert values["background-image"] == "none" and values["box-shadow"] == "none", values
    assert all(values[f"border-{side}-width"] == "0px" for side in ("top", "right", "bottom", "left")), values


def assert_prose(element, size, color, tolerance):
    assert element.is_visible()
    values = css(element, ["font-size", "color", "background-color", "background-image"])
    assert float(values["font-size"].removesuffix("px")) == pytest.approx(size, abs=1), values
    assert_color(values["color"], color, tolerance)
    assert rgba(values["background-color"])[1] == 0 and values["background-image"] == "none", values


def text_start(text):
    return text.evaluate("""e=>{
      const walker=document.createTreeWalker(e,NodeFilter.SHOW_TEXT); let n;
      while(n=walker.nextNode()) if(n.textContent.trim()) {
        const r=document.createRange();r.selectNodeContents(n);
        const boxes=[...r.getClientRects()].filter(b=>b.width && b.height);
        if(boxes.length) return boxes[0].left;
      } throw new Error('No visible text reaches the inset assertion');
    }""")


def assert_insets(card, padding, *, body=None, media_required=False, facts_required=False, full_bleed=False):
    """Check actual starts, including nested wrappers; padding tokens alone cannot pass."""
    edge = card.evaluate("e=>e.getBoundingClientRect().left+parseFloat(getComputedStyle(e).borderLeftWidth)")
    text = body if body is not None else card.locator('[data-kd-slot="card.body"]').first
    assert text.count() and text.is_visible(), "No item body reaches the inset assertion"
    start = text_start(text)
    assert start - edge == pytest.approx(padding, abs=1), (start, edge, padding)
    images = card.locator('img')
    if media_required:
        assert images.count(), "Source inset media disappeared"
    for image in images.all():
        if image.is_visible():
            image_box = image.bounding_box()
            assert image_box["x"] - edge == pytest.approx(0 if full_bleed else padding, abs=1)
            if full_bleed:
                right = card.evaluate("e=>e.getBoundingClientRect().right-parseFloat(getComputedStyle(e).borderRightWidth)")
                assert image_box["x"] + image_box["width"] == pytest.approx(right, abs=1)
    facts = card.locator('dl')
    if facts_required:
        assert facts.count(), "Source label/value group disappeared"
    for group in facts.all():
        assert group.bounding_box()["x"] - edge == pytest.approx(padding, abs=1)
        for cell in group.locator('dt, dd').all():
            assert text_start(cell) - edge == pytest.approx(padding, abs=1)
        assert_unpainted(group)
        # A transparent dl inside a second painted wrapper still violates the
        # source's single surface, so inspect the ancestor chain up to the item.
        values = group.evaluate("""(e, item)=>{
          const nodes=[...e.querySelectorAll('div,[data-kd-part]')];
          for(let n=e.parentElement;n && n!==item;n=n.parentElement) nodes.push(n);
          return nodes.map(n=>{const s=getComputedStyle(n);return {
            background:s.backgroundColor,image:s.backgroundImage,shadow:s.boxShadow,
            borders:[s.borderTopWidth,s.borderRightWidth,s.borderBottomWidth,s.borderLeftWidth]};});
        }""", card.element_handle())
        for value in values:
            assert rgba(value["background"])[1] == 0, value
            assert value["image"] == value["shadow"] == "none", value
            assert value["borders"] == ["0px"] * 4, value
    links = card.locator('a[href], button')
    if facts_required:
        assert links.count() >= 2, "Source action group disappeared"
    if links.count():
        first = links.first.bounding_box()
        assert first["x"] - edge == pytest.approx(padding, abs=1)
        if links.count() >= 2:
            values = links.evaluate_all("""(els,item)=>{
              let common=els[0].parentElement; while(!common.contains(els[1])) common=common.parentElement;
              if(common===item) return null;
              const s=getComputedStyle(common); return [s.backgroundColor,s.borderTopWidth,s.boxShadow];
            }""", card.element_handle())
            if values is not None:
                assert rgba(values[0])[1] == 0 and values[1:] == ["0px", "none"], values


def assert_column_gutter(items, expected):
    assert len(items) >= 2
    a, b = [item.bounding_box() for item in items[:2]]
    assert a["y"] == pytest.approx(b["y"], abs=1), ("Source columns were lost", a, b)
    assert b["x"] - a["x"] - a["width"] == pytest.approx(expected, abs=1), (a, b, expected)


def observe_source(page, url, padding, gutter, full_bleed):
    page.set_viewport_size({"width": 1280, "height": 1000})
    page.goto(url)
    page.evaluate("document.fonts.ready")
    items = page.locator('.item')
    assert items.count() == 2 and items.locator('h1,h2,h3,h4,h5,h6').count() == 0
    assert_column_gutter(items.all(), gutter)
    assert_prose(page.locator('#lead'), 20, BODY, 0.01)
    for card in items.all():
        assert_prose(card.locator('.body'), 16, BODY, 0.01)
        assert_prose(card.locator('.meta'), 14, MUTED, 0.01)
        assert_insets(card, padding, body=card.locator('.body'), media_required=True,
                      facts_required=True, full_bleed=full_bleed)
    for heading in page.locator('#notes > h2, #article > h2, #article > h3').all():
        assert heading_gaps(heading) == pytest.approx({"before": 32, "after": 8}, abs=0.05)
    return {"item": css(items, SURFACE_KEYS), "hero": css(page.locator('#leading'), SURFACE_KEYS),
            "prose": page.locator('#article > p:not(.meta), #article li').all_text_contents()}


@pytest.mark.parametrize("padding,gutter,full_bleed", [(16, 24, False), (24, 16, False), (16, 24, True)],
                         ids=["inset-16-gutter-24", "inset-24-gutter-16", "full-bleed-text-inset-16"])
def test_ingest_keeps_item_surfaces_insets_and_text_roles(
        library, fixture_site, ingest_config, tmp_path, page, padding, gutter, full_bleed):
    configure_capture(library, ingest_config)
    source = fixture_site.root / "role-surfaces" / "index.html"
    text = source.read_text().replace("gap: 12px; padding: 16px", f"gap: 12px; padding: {padding}px")
    text = text.replace("column-gap: 24px", f"column-gap: {gutter}px")
    if full_bleed:
        text = text.replace("width: 100%; height: auto", f"width: calc(100% + {2 * padding}px); margin-inline: -{padding}px; height: auto")
    source.write_text(text)
    expected = observe_source(page, fixture_site.url + "/role-surfaces/index.html", padding, gutter, full_bleed)
    root, document, _, requests = derive(
        library, fixture_site, fixture_site.url + "/role-surfaces/index.html", "surface-roles")
    library.cli("save-draft", document["id"], cwd=library.project, timeout=90)
    assert library.read(document["id"]) == document
    vocabulary = library.json("vocabulary", "--vocabulary", document["vocabulary"])
    tolerance = ingest_config["color_delta_e"]

    library.cli("fidelity", document["id"], cwd=library.project, timeout=120)
    fidelity = root / "fidelity"
    report = json.loads((fidelity / "report.json").read_text())
    pairs = [pair for pair in report["pairs"] if pair["width"] == 1280]
    assert len(pairs) == 1, report
    page.goto(confined(fidelity, pairs[0]["html"]).as_uri())
    page.evaluate("document.fonts.ready")
    cards = repeated_groups(page, ITEMS, vocabulary)
    assert_column_gutter(cards, gutter)
    for card, (body, meta) in zip(cards, ITEMS):
        assert_surface(card, expected["item"], tolerance)
        assert card.get_by_role("heading").count() == 0, "Absent source item titles must remain absent in reconstruction"
        body_node, meta_node = card.get_by_text(body, exact=True), card.get_by_text(meta, exact=True)
        assert_prose(body_node, 16, BODY, tolerance)
        assert_prose(meta_node, 14, MUTED, tolerance)
        assert_insets(card, padding, body=body_node, media_required=True,
                      facts_required=True, full_bleed=full_bleed)
    assert_prose(page.get_by_text(LEAD, exact=True), 20, BODY, tolerance)
    for prose in expected["prose"]:
        assert_prose(page.get_by_text(prose, exact=True), 16, BODY, tolerance)

    # Saved sample pages contain generated item headings even though the source
    # items did not. Their binding must derive from measured heading margins,
    # not merely copy the item's uniform 12px slot gap.
    preview = library.build(tmp_path / "saved-preview", document["id"])
    seen = set()
    for name in PAGES:
        page.goto((preview / name).as_uri())
        page.evaluate("document.fonts.ready")
        for hero in page.locator('[data-kd-construct="hero"]').all():
            assert_surface(hero, expected["hero"], tolerance)
            for lead in hero.locator('[data-kd-slot="hero.body"]').all():
                assert_prose(lead, 20, BODY, tolerance)
                seen.add("lead")
        for card in page.locator('[data-kd-construct="card"]').all():
            assert_surface(card, expected["item"], tolerance)
            assert_insets(card, padding, full_bleed=full_bleed)
            assert_prose(card.locator('[data-kd-slot="card.body"]').first, 16, BODY, tolerance)
            for meta in card.locator('[data-kd-slot="card.meta"], [data-kd-slot="card.eyebrow"]').all():
                assert_prose(meta, 14, MUTED, tolerance)
                seen.add("metadata")
            for heading in card.get_by_role("heading").all():
                if not heading.evaluate("e=>Boolean(e.previousElementSibling && e.nextElementSibling)"):
                    continue
                gaps = heading_gaps(heading)
                assert gaps["before"] > gaps["after"], gaps
                # Source margins supply 32px before and 8px after at every
                # heading level. Layout gaps can add space; do not prescribe
                # which wrapper/property implements that inset. Merely using
                # the item's 12px slot gap (or correcting it to 13px) fails.
                assert gaps["before"] >= 31 and gaps["after"] >= 7, gaps
                seen.add("inferred-heading")
            seen.add("item")
        for paragraph in page.locator('[data-kd-construct="content-section"] p, [data-kd-slot="page-shell.body"]').all():
            role = paragraph.get_attribute("data-kd-role")
            if role == "body":
                assert_prose(paragraph, 16, BODY, tolerance)
                seen.add("prose")
    assert {"lead", "item", "metadata", "inferred-heading", "prose"} <= seen, seen
    checked = composition_report(library, document["id"], tmp_path / "saved-check", widths=(375, 1280))
    assert_composition_passes(checked)
    assert len(fixture_site.requests) == requests, "Saved-language operations revisited the source"
