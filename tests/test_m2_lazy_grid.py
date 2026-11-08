"""Real blog-page regressions: below-fold media and responsive repeated groups.

Oracle: authored six distinct image colors and CSS grid, verified on the live
fixture. A grey placeholder, omitted late image or one-column wide reconstruction
must fail. No commerce terms, domain construct ids or source implementation hooks.
"""

import hashlib
from io import BytesIO
from urllib.parse import quote

import pytest
from PIL import Image

from tests.m2_support import capture, color_distance, confined, draft, read_json
from tests.test_m2_capture import tree_hashes
from tests.test_m2_fidelity_content import assert_media_visible, decoded_samples, repeated_groups

pytestmark = [pytest.mark.browser, pytest.mark.browser_timeout(420)]

ITEMS = [
    ("Still water at the inlet", "Morning field notes", "Study the reflections"),
    ("The green reed corridor", "Marsh field notes", "Listen to the wind"),
    ("Clay beside the footpath", "Ground field notes", "Notice the texture"),
    ("Irises by the small bridge", "Garden field notes", "Keep to the path"),
    ("Golden grasses on the dunes", "Headland field notes", "Follow the marked trail"),
    ("A rose-colored evening sky", "Evening field notes", "Pause before returning"),
]
MEDIA = [("inlet.svg", "#205a74"), ("reeds.svg", "#4b7138"), ("clay.svg", "#b46238"),
         ("iris.svg", "#75539a"), ("dunes.svg", "#a78b24"), ("rose.svg", "#ad4962")]


def box(locator):
    """Document coordinates; allow semantic wrappers using display:contents."""
    return locator.evaluate("""e => {
      let r=e.getBoundingClientRect();
      if (!(r.width && r.height)) {
        const rects=[...e.querySelectorAll('*')].map(n=>n.getBoundingClientRect()).filter(r=>r.width && r.height);
        if (!rects.length) throw Error('No visible group box');
        r={left:Math.min(...rects.map(r=>r.left)), top:Math.min(...rects.map(r=>r.top)),
           right:Math.max(...rects.map(r=>r.right)), bottom:Math.max(...rects.map(r=>r.bottom))};
      }
      return {x:r.left+scrollX, y:r.top+scrollY, width:r.right-r.left, height:r.bottom-r.top};
    }""")


def row_members(boxes, tolerance=2):
    """Compare row membership, not exact pixels or a required layout mechanism.

    Two CSS px accommodates fractional box rounding; the fixture's 16px gap
    separates rows unambiguously. Horizontal overlap cannot masquerade as columns.
    """
    rows = []
    for index, current in enumerate(boxes):
        assert current["width"] > 0 and current["height"] > 0
        if rows and abs(current["y"] - boxes[rows[-1][0]]["y"]) <= tolerance:
            previous = boxes[rows[-1][-1]]
            assert current["x"] >= previous["x"] + previous["width"] - tolerance, "Overlapping or reordered columns"
            rows[-1].append(index)
        else:
            if rows:
                assert current["y"] >= max(boxes[i]["y"] + boxes[i]["height"] for i in rows[-1]) - tolerance, "Overlapping rows"
            rows.append([index])
    return rows


def color_at(picture, x, y, expected, tolerance):
    assert 0 <= x < picture.width and 0 <= y < picture.height, "Full-page capture omitted late media"
    actual = "#" + "".join(f"{v:02x}" for v in picture.convert("RGB").getpixel((x, y)))
    assert color_distance(expected, actual) <= tolerance, ("Wrong image or unloaded placeholder", expected, actual)


def observe_source(source, url, width, mode):
    source.set_viewport_size({"width": width, "height": 900})
    source.goto(url)
    assert source.locator(".item h3").all_text_contents() == [item[0] for item in ITEMS]
    assert box(source.locator(".cards"))["y"] > 4000, "Fixture no longer exercises below-fold content"
    if mode == "scroll":
        assert all(image.get_attribute("src") == "placeholder.svg" for image in source.locator(".item img").all())
    else:
        assert all(image.get_attribute("loading") == "lazy" for image in source.locator(".item img").all())
    samples = []
    for index, (filename, color) in enumerate(MEDIA):
        image = source.locator(".item img").nth(index)
        image.scroll_into_view_if_needed(timeout=5000)
        source.wait_for_function("""({index, filename}) => {
          const image=document.querySelectorAll('.item img')[index];
          return image.currentSrc.endsWith('/'+filename) && image.complete && image.naturalWidth>0;
        }""", arg={"index": index, "filename": filename}, timeout=5000)
        pixels = decoded_samples(image)
        expected = [int(color[i:i+2], 16) for i in (1, 3, 5)]
        assert all(pixel == expected for pixel in pixels), "Authored image oracle does not match rendered source"
        samples.append(pixels)
    source.evaluate("scrollTo({top:0,behavior:'instant'})")
    boxes = [box(item) for item in source.locator(".item").all()]
    rows = row_members(boxes)
    assert rows == ([[0], [1], [2], [3], [4], [5]] if width < 768 else [[0, 1, 2], [3, 4, 5]])
    return {"rows": rows, "media": samples, "image_boxes": [box(image) for image in source.locator(".item img").all()]}


@pytest.mark.parametrize("mode", ["native", "scroll"])
def test_lazy_media_is_captured_and_reconstructed_with_responsive_card_rows(
        library, server, fixture_site, ingest_config, browser_context, page, mode):
    ingest_config.update(widths=[390, 1280], capture_timeout_s=20)
    (library.project / "kinbase-design.toml").write_text(
        "[ingest]\n" + "\n".join(f"{key} = {value}" for key, value in ingest_config.items()) + "\n")
    url = fixture_site.url + f"/lazy/{mode}.html"
    # Capture is a separate Chromium invocation with no access to this browser's
    # scroll or cache. Source observation merely establishes independent oracles.
    context = browser_context.browser.new_context(java_script_enabled=True)
    try:
        source = context.new_page()
        source.set_default_timeout(5000)
        source.set_default_navigation_timeout(5000)
        observed = {width: observe_source(source, url, width, mode) for width in (390, 768, 1280)}
        artifact, artifact_root, captured = capture(library, [url])
        assert not captured["problems"], captured
        entry, = captured["pages"]
        assert {390, 768, 1280} <= {int(width) for width in entry["widths"]}
        for width in entry["widths"]:
            if int(width) not in observed:
                observed[int(width)] = observe_source(source, url, int(width), mode)
    finally:
        context.close()
    tolerance = ingest_config["color_delta_e"]
    # Both the capture's offered originals and its actual full-page paint must
    # contain the late images; finding data-src URLs alone is insufficient.
    captured_hashes = {hashlib.sha256(confined(artifact_root, asset["file"]).read_bytes()).hexdigest()
                       for asset in captured["assets"]}
    for filename, _ in MEDIA:
        assert hashlib.sha256((fixture_site.root / "lazy" / filename).read_bytes()).hexdigest() in captured_hashes
    for width, files in entry["widths"].items():
        with Image.open(confined(artifact_root, files["screenshot"])) as picture:
            scale = picture.width / int(width)
            for image_box, (_, color) in zip(observed[int(width)]["image_boxes"], MEDIA):
                x = round((image_box["x"] + image_box["width"] / 2) * scale)
                y = round((image_box["y"] + image_box["height"] / 2) * scale)
                color_at(picture, x, y, color, tolerance)
    immutable = tree_hashes(artifact_root)
    fixture_site.available = False
    request_count = len(fixture_site.requests)
    identity = "lazy-" + mode
    root, _, _ = draft(library, [artifact], identity)
    library.cli("fidelity", identity, cwd=library.project, timeout=90)
    report_root = root / "fidelity"
    report = read_json(report_root / "report.json")
    assert {(pair["page"], pair["width"]) for pair in report["pairs"]} == {(entry["name"], int(w)) for w in entry["widths"]}
    vocabulary = library.json("vocabulary")
    for pair in report["pairs"]:
        html = confined(report_root, pair["html"])
        page.set_viewport_size({"width": pair["width"], "height": 900})
        response = page.goto(server + f"/ingest/drafts/{identity}/fidelity/" + quote(pair["html"], safe="/"))
        assert response and response.ok and response.body() == html.read_bytes()
        groups = repeated_groups(page, ITEMS, vocabulary)
        assert row_members([box(group) for group in groups]) == observed[pair["width"]]["rows"], (
            "Reconstruction changed the captured number/order of cards per row", pair["width"])
        for index, group in enumerate(groups):
            assert_media_visible(group, observed[pair["width"]]["media"][index], tolerance)
            media = group.locator('[data-kd-role="media"]')
            # Sample actual rendered media as well as decoding; this also covers
            # valid inline SVG/background-image output without permitting grey.
            painted = group.locator("img, svg").first if group.locator("img, svg").count() else media
            data = painted.screenshot(timeout=5000, animations="disabled")
            with Image.open(BytesIO(data)) as picture:
                color_at(picture, picture.width // 2, picture.height // 2, MEDIA[index][1], tolerance)
    assert len(fixture_site.requests) == request_count, "Reconstruction refetched the unavailable source"
    assert tree_hashes(artifact_root) == immutable
