"""M2 B5 / amendment 12: inspect the reconstruction, not just its palette report.

Oracle: our own two-page source, six distinct cards and authored accent colors.
Falsifiers: generic vocabulary copy substituted for captured content, one page
reused for all pairs, cards flattened/reordered, or green prices rendered grey.
"""

import re
from urllib.parse import quote

import pytest

from tests.m2_support import capture, color_distance, confined, draft, png, read_json
from tests.test_m1_design import solid_background
from tests.test_m2_capture import tree_hashes

pytestmark = [pytest.mark.browser, pytest.mark.browser_timeout(420)]

PAGES = {
    "coast.html": {
        "heading": "Seagrass coastal notebook",
        "section": "Places beside the tide pools",
        "intro": "Three salt-air hideaways chosen for slow mornings.",
        "cards": [("Zinnia Pier cottage", "North jetty, four guests", "$289 per night"),
                  ("Amber Dune studio", "West dunes, two guests", "$173 per night"),
                  ("Kestrel Cove house", "Sheltered cove, six guests", "$331 per night")],
    },
    "estuary.html": {
        "heading": "Estuary weekend ledger",
        "section": "Rooms along the reed beds",
        "intro": "Three reed-side retreats for watching the changing water.",
        "cards": [("Willow Ferry loft", "Old ferry, three guests", "$247 per night"),
                  ("Bracken Marsh hut", "Reed marsh, two guests", "$195 per night"),
                  ("Otter Reach lodge", "River bend, five guests", "$364 per night")],
    },
}


def normalized(text):
    return " ".join(text.split())


def visible_fragments(locator):
    """Observe visible text nodes rather than regexing HTML or using OCR as proof."""
    return locator.evaluate("""root => {
      const result = [], walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
      let node;
      while ((node = walker.nextNode())) {
        const text = node.textContent.trim().replace(/\\s+/g, ' ');
        if (!text) continue;
        const style = getComputedStyle(node.parentElement);
        if (style.visibility === 'hidden' || style.display === 'none' || Number(style.opacity) === 0) continue;
        const range = document.createRange(); range.selectNodeContents(node);
        if ([...range.getClientRects()].some(r => r.width > 0 && r.height > 0 && r.right > 0 && r.bottom > 0))
          result.push({text, color: style.color});
      }
      return result;
    }""")


def assert_accent(locator, expected, tolerance):
    fragments = visible_fragments(locator)
    assert fragments, "Accent assertion reached no painted text"
    surface = solid_background(locator)
    for fragment in fragments:
        channels = [float(value) for value in re.findall(r"[\d.]+", fragment["color"])]
        assert fragment["color"].startswith("rgb") and len(channels) in (3, 4), fragment
        alpha = channels[3] if len(channels) == 4 else 1
        composed = [round(channels[i] * alpha + surface[i] * (1 - alpha)) for i in range(3)]
        observed = "#" + "".join(f"{channel:02x}" for channel in composed)
        assert color_distance(expected, observed) <= tolerance, (fragment["text"], expected, observed)


def assert_media_visible(card):
    media = card.locator('[data-kd-slot="listing-card.media"]')
    assert media.count() == 1 and media.is_visible()
    box = media.bounding_box()
    assert box and box["width"] > 0 and box["height"] > 0
    images = card.locator('[data-kd-slot="listing-card.media"] img, img[data-kd-slot="listing-card.media"]')
    if images.count():
        for image in images.all():
            assert image.is_visible()
            assert image.evaluate("e => e.complete && e.naturalWidth > 0 && e.naturalHeight > 0")
    else:
        assert media.locator("svg").count() or media.evaluate(
            "e => e.tagName.toLowerCase() === 'svg' || getComputedStyle(e).backgroundImage !== 'none'"), (
                "A media wrapper with no rendered image is not a reconstructed card image")


def test_fidelity_rebuilds_each_pages_text_cards_and_accent_paint(
        library, server, fixture_site, ingest_config, page):
    sources = {}
    for filename, expected in PAGES.items():
        url = fixture_site.url + "/cards/" + filename
        page.goto(url)
        assert normalized(page.locator("h1").inner_text()) == expected["heading"]
        assert page.locator("article h3").all_text_contents() == [card[0] for card in expected["cards"]]
        for price in page.locator(".price").all():
            assert_accent(price, "#0b6e4f", 0.01)
        sources[url] = {**expected, "text": normalized(page.locator("body").inner_text())}
    artifact, artifact_root, captured = capture(library, list(sources))
    assert not captured["problems"], captured
    for entry in captured["pages"]:
        assert {*ingest_config["widths"], 768} <= {int(width) for width in entry["widths"]}
    immutable = tree_hashes(artifact_root)
    fixture_site.available = False
    source_request_count = len(fixture_site.requests)
    root, _, _ = draft(library, [artifact], "seagrass-reconstruction")
    library.cli("fidelity", "seagrass-reconstruction", cwd=library.project, timeout=90)
    report_root = root / "fidelity"
    report = read_json(report_root / "report.json")
    expected_pairs = {(entry["name"], int(width)) for entry in captured["pages"] for width in entry["widths"]}
    assert {(pair["page"], pair["width"]) for pair in report["pairs"]} == expected_pairs
    assert len(report["pairs"]) == len(expected_pairs)
    by_page = {entry["name"]: sources[entry["url"]] for entry in captured["pages"]}
    for pair in report["pairs"]:
        expected = by_page[pair["page"]]
        html = confined(report_root, pair["html"])
        png(report_root / pair["reconstruction"])
        page.set_viewport_size({"width": pair["width"], "height": 900})
        response = page.goto(server + "/ingest/drafts/seagrass-reconstruction/fidelity/" + quote(pair["html"], safe="/"))
        assert response and response.ok and response.body() == html.read_bytes()
        assert page.evaluate("innerWidth") == pair["width"]
        for text in (expected["heading"], expected["section"], expected["intro"]):
            assert page.get_by_text(text, exact=True).first.is_visible(), (pair["page"], pair["width"], text)
        # This catches lorem and vocabulary example copy without hard-coding
        # implementation sample names. Every visible fragment must come from
        # this authored page; text captured on the other page is not sufficient.
        fragments = visible_fragments(page.locator("body"))
        assert fragments
        assert all(normalized(fragment["text"]) in expected["text"] for fragment in fragments), (
            "Reconstruction introduced copy absent from its source", pair["page"],
            [fragment["text"] for fragment in fragments if normalized(fragment["text"]) not in expected["text"]])
        cards = page.locator('[data-kd-construct="listing-card"]')
        assert cards.count() == len(expected["cards"]), (pair, cards.count())
        titles = cards.locator('[data-kd-slot="listing-card.title"]')
        assert [normalized(title) for title in titles.all_text_contents()] == [card[0] for card in expected["cards"]]
        for index, (title, meta, price_text) in enumerate(expected["cards"]):
            card = cards.nth(index)
            assert card.evaluate("e => e.tagName") == "ARTICLE"
            assert card.is_visible() and card.get_by_text(title, exact=True).first.is_visible()
            assert card.get_by_text(meta, exact=True).first.is_visible()
            assert_media_visible(card)
            price = card.locator('[data-kd-slot="listing-card.price"]')
            assert price.count() == 1 and normalized(price.inner_text()) == price_text
            assert_accent(price, "#0b6e4f", ingest_config["color_delta_e"])
        section = page.get_by_text(expected["section"], exact=True).first
        assert_accent(section, "#a14524", ingest_config["color_delta_e"])
    assert len(fixture_site.requests) == source_request_count, "Fidelity HTML fetched the unavailable live source"
    assert tree_hashes(artifact_root) == immutable
