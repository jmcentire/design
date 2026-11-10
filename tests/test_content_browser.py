"""Normative amendments 01/02: delivered pages in real, JavaScript-disabled Chromium.

Falsifiers: hidden original text, unloaded lazy assets, page overflow, unreadable
solid-surface text, dead links, palette-only designs, or inert/badly scoped CSS.
Browser tests run by Validator; no screenshots/baselines from the candidate used
as expectations. Geometry comparisons use authored values or relations.
"""
import json
from urllib.parse import urlsplit, unquote

import pytest

from tests.content_support import content_library, write_content, render
from tests.content_browser_support import (loaded_images, assert_visible_text_and_controls,
                                           assert_text_contrast, visible_copy)
from tests.support import ROOT
from tests.test_content_hooks_mapping import allowed_elements

pytestmark = pytest.mark.browser
SHIPPED = sorted(p.name for p in (ROOT / "library" / "languages").iterdir() if (p / "working.json").is_file())


@pytest.mark.parametrize("language", SHIPPED)
@pytest.mark.parametrize("width", [375, 1280])
@pytest.mark.parametrize("collection", [False, True], ids=["guide", "cards"])
def test_content_page_is_readable_loaded_contained_and_offline(content_library, tmp_path, page, language, width, collection):
    source, content = write_content(tmp_path / "source", collection)
    out = tmp_path / "page"
    render(content_library, source, out, language)
    requests = []
    page.on("request", lambda request: requests.append(request.url))
    page.set_viewport_size({"width": width, "height": 900})
    page.goto((out / "index.html").as_uri())
    loaded_images(page)
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"), (language, width)
    assert_visible_text_and_controls(page)
    text = " ".join(page.locator("body").inner_text().split())
    assert all(" ".join(value.split()) in text for value in visible_copy(content)), text
    assert_text_contrast(page)
    anchors = page.locator("a[href]").evaluate_all("els => els.map(e => e.getAttribute('href'))")
    assert anchors
    for href in anchors:
        parts = urlsplit(href)
        if parts.fragment and not parts.path:
            assert page.evaluate("id => !!document.getElementById(id)", unquote(parts.fragment)), href
        elif not parts.scheme and not parts.netloc:
            assert (out / unquote(parts.path)).is_file(), href
    assert requests, "Browser request observer did not reach navigation"
    assert not [url for url in requests if urlsplit(url).scheme in {"http", "https"}], requests


def test_languages_change_layout_and_typography_preserving_reading_order(content_library, tmp_path, page):
    source, _ = write_content(tmp_path / "source")
    observations, htmls = [], []
    page.set_viewport_size({"width": 1280, "height": 900})
    for language in ("harbor", "lantern"):
        out = tmp_path / language
        render(content_library, source, out, language)
        htmls.append((out / "index.html").read_bytes())
        page.goto((out / "index.html").as_uri())
        loaded_images(page)
        assert_visible_text_and_controls(page)
        observations.append({"accessibility": page.locator("body").aria_snapshot(),
            "links": page.locator("a[href]").evaluate_all("els => els.map(e=>[e.textContent,e.getAttribute('href')])"),
            "geometry": page.locator("[data-kd-construct]").evaluate_all("els => els.map(e=>{const r=e.getBoundingClientRect();return [r.x,r.width];})"),
            "type": page.locator("h1,h2,h3,p").evaluate_all("els => els.map(e=>{const s=getComputedStyle(e);return [s.fontFamily,s.fontSize,s.fontWeight,s.lineHeight,s.letterSpacing];})")})
    first, second = observations
    assert htmls[0] == htmls[1]
    assert first["accessibility"] == second["accessibility"]
    assert first["links"] == second["links"]
    assert len(first["geometry"]) == len(second["geometry"]) > 0
    assert any(abs(a-b) > 1 for left,right in zip(first["geometry"],second["geometry"]) for a,b in zip(left,right)), (
        "No horizontal position/width change in the same constructs", observations)
    assert first["type"] != second["type"], "No typography change beyond color"


def test_hook_selectors_find_their_actual_elements(content_library, tmp_path, page):
    source, _ = write_content(tmp_path / "source")
    out = tmp_path / "page"
    render(content_library, source, out)
    contract = json.loads((out / "hooks.json").read_bytes())
    page.goto((out / "index.html").as_uri())
    main = page.locator(contract["content_pages"]["landmarks"]["main"])
    assert main.count() == 1 and main.evaluate("e=>e.localName") == "main"
    for identity, definition in contract["constructs"].items():
        roots = page.locator(definition["selector"])
        for index in range(roots.count()):
            root = roots.nth(index)
            assert root.get_attribute("data-kd-construct") == identity
            for slot, spec in definition["slots"].items():
                found = root.locator(spec["selector"])
                if spec["required"]:
                    assert found.count() > 0, (identity, slot)
                for i in range(found.count()):
                    assert found.nth(i).get_attribute("data-kd-slot") == f"{identity}.{slot}"
                    assert found.nth(i).evaluate("e=>e.localName") in allowed_elements(spec)


def test_remote_source_is_refused_without_contacting_it(content_library, fixture_site, tmp_path):
    """Observe the actual HTTP edge, with a real successful request as control.

    This proves no source fetch for this supplied URL, not universal syscall-level
    absence of all possible outbound traffic. Browser mark also gates socket use.
    """
    from urllib.request import urlopen
    from tests.content_support import save_content, content_findings
    url = fixture_site.url + "/editorial/logo.svg"
    with urlopen(url, timeout=5) as response:
        assert response.status == 200 and response.read()
    reached = len(fixture_site.requests)
    assert reached > 0
    source, content = write_content(tmp_path / "source")
    render(content_library, source, tmp_path / "valid")
    assert len(fixture_site.requests) == reached
    content["blocks"][0]["media"]["src"] = url
    save_content(source, content)
    report = content_library.json("render-page", "harbor", "--content", source, "--out", tmp_path / "invalid", code=1)
    content_findings(report, source, content, "/blocks/0/media/src")
    assert len(fixture_site.requests) == reached, "render-page fetched a prohibited remote source"
