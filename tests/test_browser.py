"""Normative B1/B3/B9/B15/B16. Real Chromium with page JavaScript disabled.

Falsifiers: CSS ignores removal or viewport boundaries; variant changes accessible
meaning or is ignored; gallery merely names states; fonts fall back; image URLs
404; focus outlines vanish; viewer width/page/upload controls require JavaScript.
No screenshots or snapshots are used as fixed aesthetic oracles.
"""

import hashlib
from urllib.parse import parse_qs, urlsplit

import pytest
from playwright.sync_api import expect

from tests.browser_support import assert_color, assert_visible_focus, focus_style, frame_at, form_at, link_at, reveal_preview_right_edge, semantic_view
from tests.support import FIXTURES, PAGES, package_asset
from tests.test_validation import VALID_VARIANT, set_variant
from tests.test_versions_assets import bind_font

pytestmark = pytest.mark.browser


def test_every_static_page_renders_and_links_to_every_other_without_js(library, language, tmp_path, page):
    preview = library.build(tmp_path / "site")
    for source in PAGES:
        for target in PAGES:
            if source == target:
                continue
            page.goto((preview / source).as_uri())
            assert page.locator("[data-kd-construct]").count() > 0
            expect(page.locator("body")).to_be_visible()
            assert page.locator("body").inner_text().strip()
            matching = []
            anchors = page.locator("a[href]")
            for i in range(anchors.count()):
                raw = anchors.nth(i).get_attribute("href")
                split = urlsplit(raw)
                if split.path in {target, "./" + target} and not split.scheme and not split.netloc:
                    matching.append(anchors.nth(i))
            assert matching, f"{source} has no relative navigation link to {target}"
            visible = [link for link in matching if link.is_visible()]
            assert visible, f"{source} -> {target} links are hidden"
            visible[0].click()
            assert urlsplit(page.url).path == urlsplit((preview / target).as_uri()).path


def test_gallery_depicts_each_declared_state_with_its_style(library, language, vocabulary, tmp_path, page):
    for construct, definition in vocabulary["constructs"].items():
        language["components"][construct]["properties"]["color"] = "{color.component}"
        language["components"][construct]["states"] = {
            state: {"color": "{color.hover}"} for state in definition["states"] if state != "default"
        }
    library.write(language)
    preview = library.build(tmp_path / "gallery")
    page.goto((preview / "states.html").as_uri())
    page.mouse.move(-10, -10)
    for construct, definition in vocabulary["constructs"].items():
        for state in definition["states"]:
            roots = page.locator(f'[data-kd-construct="{construct}"][data-kd-state="{state}"]')
            assert roots.count() > 0, (construct, state)
            assert_color(roots, "rgb(101, 67, 33)" if state == "default" else "rgb(102, 34, 68)")
            for i in range(roots.count()):
                root = roots.nth(i)
                assert root.evaluate("e => e.localName") == definition["root"]
                expect(root).to_be_visible()
                for slot in definition["slots"]:
                    rendered = root.locator(f'[data-kd-slot="{construct}.{slot["id"]}"]')
                    if slot["required"]:
                        assert rendered.count() == 1
                    else:
                        assert rendered.count() <= 1
                    if rendered.count():
                        expect(rendered).to_have_attribute("data-kd-role", slot["role"])
                        expect(rendered).to_have_attribute("data-kd-emphasis", slot["emphasis"])


def test_valid_variant_preserves_accessible_meaning_and_is_actually_applied(library, language, tmp_path, page):
    base = library.build(tmp_path / "default")
    before = {}
    for name in PAGES:
        page.goto((base / name).as_uri())
        before[name] = semantic_view(page)
    set_variant(language, VALID_VARIANT)
    language["components"]["listing-card"]["parts"] = {"stack": {"padding": "{space.small}"}}
    library.write(language)
    variant = library.build(tmp_path / "variant")
    applied = 0
    for name in PAGES:
        page.goto((variant / name).as_uri())
        assert semantic_view(page) == before[name], name
        wrappers = page.locator('[data-kd-construct="listing-card"] [data-kd-part="stack"]')
        applied += wrappers.count()
        for i in range(wrappers.count()):
            expect(wrappers.nth(i)).to_have_css("padding-top", "8px")
    assert applied > 0, "Variant was accepted but silently ignored by rendering"


def test_override_removal_reaches_computed_styles(library, language, tmp_path, page):
    component = language["components"]["listing-card"]
    component["slots"]["price"] = {"properties": {"color": "{color.component}"}}
    language["overrides"] = [{"scope": "listing-card.price", "reason": "temporary", "properties": {"color": "{color.override}"}}]
    expected = ["rgb(34, 102, 68)", "rgb(101, 67, 33)", "rgb(18, 52, 86)"]
    for index, color in enumerate(expected):
        if index == 1:
            language["overrides"] = []
        if index == 2:
            del component["slots"]["price"]["properties"]["color"]
        library.write(language)
        out = library.build(tmp_path / f"stage-{index}")
        page.goto((out / "search.html").as_uri())
        assert_color(page.locator('[data-kd-slot="listing-card.price"]'), color)


def test_breakpoint_styles_apply_at_exact_pixel_boundaries(library, language, tmp_path, page):
    language["overrides"] = [
        {"scope": "listing-card.price" + suffix, "reason": "width fixture", "properties": {"color": "{color." + token + "}"}}
        for suffix, token in [("", "override"), ("@md", "wide"), ("@lg", "widest")]
    ]
    library.write(language)
    out = library.build(tmp_path / "breakpoints")
    page.goto((out / "search.html").as_uri())
    for width, color in [(767, "rgb(34, 102, 68)"), (768, "rgb(68, 34, 102)"),
                         (769, "rgb(68, 34, 102)"), (1279, "rgb(68, 34, 102)"),
                         (1280, "rgb(34, 51, 102)"), (1281, "rgb(34, 51, 102)")]:
        page.set_viewport_size({"width": width, "height": 900})
        assert_color(page.locator('[data-kd-slot="listing-card.price"]'), color)


def test_real_hover_and_active_states_apply_component_treatment(library, language, vocabulary, tmp_path, page):
    """B9: a static depiction alone cannot prove real pointer states work."""
    examples = {}
    for state in ("hover", "active"):
        candidates = [name for name, contract in vocabulary["constructs"].items()
                      if state in contract["states"]]
        assert candidates, f"Interactive-state contract has no {state} example"
        examples[state] = candidates[0]
        component = language["components"][candidates[0]]
        component["properties"]["color"] = "{color.component}"
        token = "hover" if state == "hover" else "combined"
        component.setdefault("states", {})[state] = {"color": "{color." + token + "}"}
    library.write(language)
    out = library.build(tmp_path / "pointer-states")
    for state, construct in examples.items():
        page.goto((out / "states.html").as_uri())
        target = page.locator(f'[data-kd-construct="{construct}"][data-kd-state="default"]').first
        expect(target).to_be_visible()
        target.hover()
        if state == "active":
            page.mouse.down()
        try:
            # Active differs from hover, so a disabled :active rule cannot stay green.
            assert_color(target, "rgb(102, 34, 68)" if state == "hover" else "rgb(102, 51, 34)")
        finally:
            if state == "active":
                page.mouse.up()


def test_packaged_font_is_loaded_used_and_bound_images_decode(library, language, tmp_path, page, browser_context):
    font = bind_font(library, language, tmp_path)
    out = library.build(tmp_path / "assets-preview")
    assert (out / "assets" / "fixture-font-regular.ttf").read_bytes() == font.read_bytes()
    page.goto((out / "search.html").as_uri())
    page.evaluate("document.fonts.ready")
    faces = page.evaluate("Array.from(document.fonts, f => ({family:f.family,status:f.status,weight:f.weight}))")
    assert any(f["family"].strip('\"') == "Fixture Sans" and f["status"] == "loaded" and f["weight"] in {"400", "normal"} for f in faces), faces
    expect(page.locator('[data-kd-slot="listing-card.price"]').first).to_have_css("font-family", '"Fixture Sans"')
    # Chromium reports actual glyph-provider fonts, defeating the fallback-font false positive.
    session = browser_context.new_cdp_session(page)
    session.send("DOM.enable")
    session.send("CSS.enable")
    root = session.send("DOM.getDocument")["root"]["nodeId"]
    node = session.send("DOM.querySelector", {"nodeId": root, "selector": '[data-kd-slot="listing-card.price"]'})["nodeId"]
    fonts = session.send("CSS.getPlatformFontsForNode", {"nodeId": node})["fonts"]
    assert any(f["isCustomFont"] and f["glyphCount"] > 0 and f["familyName"] == "Fixture Sans" for f in fonts), fonts
    session.detach()
    for asset_id in ("fixture-logo", "fixture-image"):
        images = page.locator(f'img[src="assets/{asset_id}-primary.svg"]')
        assert images.count() > 0, asset_id
        for i in range(images.count()):
            image = images.nth(i)
            image.evaluate("e => e.decode()")
            assert image.evaluate("e => e.naturalWidth > 0 && e.naturalHeight > 0")
            expect(image).to_be_visible()


def test_viewbox_only_bound_image_has_visible_layout(library, language, tmp_path, page):
    """B16 regression from Validator: an SVG may decode yet occupy a zero-size media box."""
    package_asset(library, language, "viewbox-image", "image",
                  (FIXTURES / "viewbox-image.svg").read_bytes())
    language["components"]["listing-card"]["assets"]["media"] = "viewbox-image:primary"
    library.write(language)
    out = library.build(tmp_path / "viewbox-media")
    page.goto((out / "search.html").as_uri())
    images = page.locator('[data-kd-construct="listing-card"] img[src="assets/viewbox-image-primary.svg"]')
    assert images.count() > 0, "The bound listing-card image was not rendered"
    for index in range(images.count()):
        image = images.nth(index)
        image.evaluate("e => e.decode()")
        expect(image).to_be_visible()
        box = image.bounding_box()
        assert box is not None and box["width"] > 0 and box["height"] > 0, box


@pytest.mark.parametrize("window_width,preview_width", [(1280, 1280), (320, 320), (320, 1280)])
def test_viewer_preview_right_edge_is_reachable_at_selected_width(server, page, window_width, preview_width):
    """B15 regression: a fixed-width preview must not be permanently clipped by the viewer.

    Shrinking the iframe to fit is also wrong: the selected preview viewport is
    held exact while real, user-scrollable ancestors reveal its rightmost pixel.
    """
    page.set_viewport_size({"width": window_width, "height": 900})
    page.goto(server + f"/languages/tidal?page=search.html&width={preview_width}")
    frame = frame_at(page, "/preview/tidal/search.html")
    expect(frame).to_be_visible()
    preview = frame.element_handle().content_frame()
    expect(preview.locator("[data-kd-construct]").first).to_be_visible()
    assert preview.evaluate("window.innerWidth") == preview_width
    edge = reveal_preview_right_edge(frame)
    assert edge["clientWidth"] == preview_width, edge
    assert edge["edgeHitsFrame"], ("Selected preview's right edge is not reachable", edge)


def test_keyboard_focus_has_visible_treatment(library, language, tmp_path, page):
    out = library.build(tmp_path / "focus")
    page.goto((out / "form.html").as_uri())
    candidates = page.locator('a[href],button,input:not([type="hidden"]),select,textarea,[tabindex]')
    eligible = [(i, candidates.nth(i)) for i in range(candidates.count())
                if candidates.nth(i).is_visible() and candidates.nth(i).is_enabled()
                and candidates.nth(i).get_attribute("tabindex") != "-1"]
    assert eligible
    before = {i: focus_style(locator) for i, locator in eligible}
    visited = set()
    for _ in range(len(eligible) + 1):
        page.keyboard.press("Tab")
        for index, locator in eligible:
            if locator.evaluate("e => e === document.activeElement"):
                expect(locator).to_be_visible()
                assert_visible_focus(before[index], focus_style(locator))
                visited.add(index)
    # Radio groups intentionally share one native tab stop; other enabled controls must be reached.
    required = {index for index, locator in eligible if locator.get_attribute("type") != "radio"}
    assert required <= visited, (required - visited)
    assert visited


def test_workbench_page_width_compare_and_upload_without_js(server, library, page, tmp_path):
    page.goto(server + "/")
    for label in ("Tidal Test Language", "Coral Test Language"):
        assert label in page.locator("body").inner_text()
    for language_id in ("tidal", "coral"):
        # Find each card by its destination and content, not an implementation class/tag.
        status = link_at(page, f"/languages/{language_id}").evaluate("""anchor => {
          for (let node = anchor; node; node = node.parentElement) {
            const languageLinks = Array.from(node.querySelectorAll('a[href]'))
              .map(a => new URL(a.href).pathname).filter(p => p.startsWith('/languages/'));
            if (new Set(languageLinks).size === 1 && /kinbase/i.test(node.textContent))
              return node.textContent;
          }
          return null;
        }""")
        assert status is not None and "unknown" in status.lower(), (language_id, status)
    link_at(page, "/languages/tidal").click()
    for width in (320, 768, 1280):
        # Exercise rendered controls, accepting normal anchors or GET form controls.
        links = page.locator("a[href]")
        width_link = None
        for i in range(links.count()):
            query = parse_qs(urlsplit(links.nth(i).get_attribute("href")).query)
            if query.get("width") == [str(width)] and links.nth(i).is_visible():
                width_link = links.nth(i)
                break
        if width_link is not None:
            width_link.click()
        else:
            select = page.locator('select[name="width"]')
            assert select.count() == 1, "No no-JS width control"
            select.select_option(str(width))
            form = select.locator("xpath=ancestor::form")
            form.locator('button[type="submit"],input[type="submit"],button:not([type])').first.click()
        frame = page.locator("iframe").first
        expect(frame).to_be_visible()
        # clientWidth is the content viewport, avoiding arbitrary border styling assumptions.
        assert frame.evaluate("e => e.clientWidth") == width
        expect(frame.element_handle().content_frame().locator("[data-kd-construct]").first).to_be_visible()
    # Follow all of the viewer's page links; the frame must really switch, not just the URL label.
    for target in PAGES:
        page.goto(server + "/languages/tidal")
        links = page.locator("a[href]")
        choices = [links.nth(i) for i in range(links.count())
                   if parse_qs(urlsplit(links.nth(i).get_attribute("href")).query).get("page") == [target]]
        assert choices, target
        choices[0].click()
        frame = frame_at(page, f"/preview/tidal/{target}")
        expect(frame.element_handle().content_frame().locator("[data-kd-construct]").first).to_be_visible()
    page.goto(server + "/compare?a=tidal&b=coral&page=listing.html&width=768")
    for language_id in ("tidal", "coral"):
        frame = frame_at(page, f"/preview/{language_id}/listing.html")
        expect(frame).to_be_visible()
        assert frame.evaluate("e => e.clientWidth") == 768
        expect(frame.element_handle().content_frame().locator("[data-kd-construct]").first).to_be_visible()
    page.goto(server + "/languages/tidal")
    form = form_at(page, "/languages/tidal/assets")
    source = tmp_path / "browser-logo.svg"
    source.write_bytes((FIXTURES / "mark.svg").read_bytes())
    form.locator('input[type="file"][name="file"]').set_input_files(source)
    form.locator('[name="asset_id"]').fill("browser-logo")
    kind = form.locator('[name="kind"]')
    if kind.evaluate("e => e.localName") == "select":
        kind.select_option("logo")
    else:
        kind.fill("logo")
    form.locator('[name="variant"]').fill("primary")
    form.locator('button[type="submit"],input[type="submit"],button:not([type])').first.click()
    expect(page).to_have_url(server + "/languages/tidal")
    assert "browser-logo" in page.locator("body").inner_text()
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    assert library.read()["assets"]["browser-logo"]["variants"]["primary"]["file"] == f"sha256/{digest}"
    assert (library.path().parent / "assets" / "sha256" / digest).read_bytes() == source.read_bytes()
