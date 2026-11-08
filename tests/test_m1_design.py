"""Normative independent design loop: M1 Lantern brief and rendered role agreement.

All named design values are literal requirements from the brief. Shipped language
data is the subject, never the oracle. Falsifiers: incorrect CSS despite a green
checker, shared resolver/renderer mistakes, missing font use, wrong md boundary,
lost variant semantics, clipped titles without full content, or rejected Lantern.
"""

import pytest
from playwright.sync_api import expect

from tests.browser_support import semantic_view
from tests.m1_support import assert_full_text_available, findings, run_check, token
from tests.support import PAGES

pytestmark = [pytest.mark.browser, pytest.mark.browser_timeout(240)]


def rgb(hex_color):
    return "rgb(" + ", ".join(str(int(hex_color[i:i + 2], 16)) for i in (1, 3, 5)) + ")"


def solid_background(locator):
    return locator.evaluate("""element => {
      let result = [0,0,0], alpha = 0;
      for (let e = element; e; e = e.parentElement) {
        const style = getComputedStyle(e);
        // Check the authored background-color layers; image legibility is a separate check.
        const parts = style.backgroundColor.match(/[\\d.]+/g).map(Number);
        const a = parts.length === 4 ? parts[3] : 1;
        const contribution = (1-alpha)*a;
        result = result.map((c,i) => c + contribution*parts[i]);
        alpha += contribution;
        if (alpha === 1) break;
      }
      return result.map(c => Math.round(c + (1-alpha)*255));
    }""")


def title_lines(locator):
    return locator.evaluate("""element => {
      const box = element.getBoundingClientRect(), tops = new Set();
      const walker = document.createTreeWalker(element, NodeFilter.SHOW_TEXT);
      let node;
      while ((node = walker.nextNode())) {
        if (!node.textContent.trim()) continue;
        const range = document.createRange(); range.selectNodeContents(node);
        // Font ascent can overlap the clip edge without painting another line.
        // Require the rect's midpoint to be inside the visible title box.
        for (const r of range.getClientRects()) {
          const middle = (r.top + r.bottom) / 2;
          if (r.width > 0 && r.height > 0 && middle < box.bottom && middle >= box.top) tops.add(r.top);
        }
      }
      return {visibleLines: tops.size, clipped: element.scrollHeight > element.clientHeight ||
        element.scrollWidth > element.clientWidth};
    }""")


def test_every_authored_slot_agrees_with_independent_values_and_resolver(library, language, vocabulary, tmp_path, page):
    sizes = {"title": 22, "subtitle": 20, "body": 17, "subtext": 15, "label": 18, "caption": 14,
             "media": 16, "action": 16, "control": 16}
    colors = {"neutral": "#123456", "primary": "#226644", "attention": "#662244", "muted": "#654321"}
    expected = {}
    for role, emphases in language["roles"].items():
        size_ref = token(language, "probe", role, "dimension", f"{sizes[role]}px")
        for emphasis, properties in emphases.items():
            properties["font-size"] = size_ref
            properties["color"] = token(language, "probe", emphasis, "color", colors[emphasis])
    library.write(language)
    for construct, contract in vocabulary["constructs"].items():
        for slot in contract["slots"]:
            scope = construct + "." + slot["id"]
            size, color = sizes[slot["role"]], colors[slot["emphasis"]]
            resolved = library.json("resolve", "tidal", scope)["properties"]
            assert {key: entry["value"] for key, entry in resolved.items()} == {
                "color": color, "font-size": f"{size}px", "font-weight": 400,
                "font-family": "sans-serif", "line-height": 1.5}
            expected[scope] = {"color": rgb(color), "font-size": f"{size}px", "font-weight": "400",
                               "font-family": "sans-serif", "line-height": f"{size * 1.5:g}px"}
    site = library.build(tmp_path / "agreement-preview")
    seen = set()
    for width in (320, 768, 1280):
        page.set_viewport_size({"width": width, "height": 900})
        for name in PAGES:
            page.goto((site / name).as_uri())
            slots = page.locator("[data-kd-slot]")
            assert slots.count() > 0
            for i in range(slots.count()):
                slot = slots.nth(i)
                scope = slot.get_attribute("data-kd-slot")
                assert scope in expected
                seen.add(scope)
                for property, value in expected[scope].items():
                    expect(slot).to_have_css(property, value)
    assert {"listing-card.price", "listing-card.title", "nav.logo", "nav.links"} <= seen
    report = run_check(library, tmp_path / "agreement-report", widths=(320, 768, 1280))
    assert not findings(report, "role-conformance", kind="violation"), report


@pytest.mark.parametrize("width", [320, 767, 768, 1280])
def test_lantern_renders_the_design_brief(library, lantern, tmp_path, page, width):
    site = library.build(tmp_path / "lantern-preview", "lantern")
    page.set_viewport_size({"width": width, "height": 900})
    seen = set()
    action_uses_primary = False
    for name in (name for name in PAGES if name != "states.html"):
        page.goto((site / name).as_uri())
        shells = page.locator('[data-kd-construct="page-shell"]')
        for i in range(shells.count()):
            assert solid_background(shells.nth(i)) == [251, 246, 238]
            seen.add("page-shell")
        slots = page.locator("[data-kd-slot][data-kd-role]")
        for i in range(slots.count()):
            slot = slots.nth(i)
            role = slot.get_attribute("data-kd-role")
            emphasis = slot.get_attribute("data-kd-emphasis")
            seen.add(role)
            family = slot.evaluate("e => getComputedStyle(e).fontFamily")
            if role in {"body", "title", "label", "caption"}:
                assert "Instrument Sans" in family
            if role == "body":
                if emphasis == "neutral":
                    expect(slot).to_have_css("color", rgb("#2b2118"))
                expect(slot).to_have_css("font-size", "17px")
                # Direct arithmetic from the brief: 17px * 1.6 = 27.2px.
                expect(slot).to_have_css("line-height", "27.2px")
            elif role == "title":
                expect(slot).to_have_css("font-size", "28px" if width < 768 else "34px")
                expect(slot).to_have_css("font-weight", "600")
            elif role == "caption":
                expect(slot).to_have_css("font-size", "14px")
                expect(slot).to_have_css("color", rgb("#6b5a4b"))
            if role == "action":
                treatment = slot.evaluate("e => [getComputedStyle(e).color,getComputedStyle(e).backgroundColor]")
                action_uses_primary |= rgb("#9c3b1b") in treatment
        prices = page.locator('[data-kd-slot="listing-card.price"]')
        for i in range(prices.count()):
            expect(prices.nth(i)).to_have_css("color", rgb("#9c3b1b"))
            expect(prices.nth(i)).to_have_css("font-size", "18px")
            expect(prices.nth(i)).to_have_css("font-weight", "600")
        cards = page.locator('[data-kd-construct="listing-card"]')
        for i in range(cards.count()):
            card = cards.nth(i)
            expect(card).to_have_css("background-color", rgb("#ffffff"))
            for side in ("top", "right", "bottom", "left"):
                expect(card).to_have_css(f"border-{side}-color", rgb("#e6d9c8"))
            for corner in ("top-left", "top-right", "bottom-left", "bottom-right"):
                expect(card).to_have_css(f"border-{corner}-radius", "12px")
    assert {"page-shell", "body", "title", "label", "caption"} <= seen
    assert action_uses_primary, "No action renders the brief's primary/action color"


def test_lantern_variant_layout_and_truncated_title_semantics(library, lantern, tmp_path, page):
    assert lantern["components"]["listing-card"]["variant"] != "default"
    site = library.build(tmp_path / "declared-variant", "lantern")
    clipped_titles = set()
    semantic = {}
    for width in (320, 768):
        page.set_viewport_size({"width": width, "height": 900})
        for name in PAGES:
            page.goto((site / name).as_uri())
            semantic[width, name] = semantic_view(page)
            if name == "states.html":
                continue
            cards = page.locator('[data-kd-construct="listing-card"]')
            for i in range(cards.count()):
                card = cards.nth(i)
                media = card.locator('[data-kd-slot="listing-card.media"]').bounding_box()
                title = card.locator('[data-kd-slot="listing-card.title"]')
                text = title.bounding_box()
                assert media and text
                if width < 768:
                    assert media["y"] + media["height"] <= text["y"], (media, text)
                else:
                    assert media["x"] + media["width"] <= text["x"] or text["x"] + text["width"] <= media["x"], (media, text)
                    assert min(media["y"] + media["height"], text["y"] + text["height"]) > max(media["y"], text["y"])
                lines = title_lines(title)
                assert 0 < lines["visibleLines"] <= 2, lines
                if lines["clipped"]:
                    clipped_titles.add(" ".join(title.text_content().split()))
        page.goto((site / "listing.html").as_uri())
        for title in clipped_titles:
            assert_full_text_available(page, title)
    assert clipped_titles, "The sample never demonstrates the brief's two-line truncation"
    lantern["components"]["listing-card"]["variant"] = "default"
    library.write(lantern)
    default = library.build(tmp_path / "default-comparison", "lantern")
    for width in (320, 768):
        page.set_viewport_size({"width": width, "height": 900})
        for name in PAGES:
            page.goto((default / name).as_uri())
            assert semantic_view(page) == semantic[width, name], (width, name)


def test_shipped_lantern_is_accepted_and_uses_its_packaged_font(library, lantern, tmp_path, page, browser_context):
    report = run_check(library, tmp_path / "lantern-check", "lantern", widths=(320, 768, 1280), accepted=True)
    for rule in ("role-conformance", "asset-load", "no-js", "keyboard", "focus-visible"):
        assert not findings(report, rule, kind="violation"), report
    site = library.build(tmp_path / "lantern-font", "lantern")
    page.goto((site / "index.html").as_uri())
    page.evaluate("document.fonts.ready")
    text = page.locator('[data-kd-role="body"]').first
    expect(text).to_be_visible()
    session = browser_context.new_cdp_session(page)
    session.send("DOM.enable")
    session.send("CSS.enable")
    root = session.send("DOM.getDocument")["root"]["nodeId"]
    node = session.send("DOM.querySelector", {"nodeId": root, "selector": '[data-kd-role="body"]'})["nodeId"]
    faces = session.send("CSS.getPlatformFontsForNode", {"nodeId": node})["fonts"]
    assert any(f["isCustomFont"] and f["glyphCount"] > 0 and f["familyName"] == "Instrument Sans" for f in faces), faces
    session.detach()
