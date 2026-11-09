"""Addendum 11a: viewport centring space must not squeeze saved-language prose."""
import re
from urllib.parse import urlsplit

import pytest

from tests.m2_support import capture, confined, draft, read_json, scalar_leaves
from tests.support import PAGES
from tests.test_composition_ingest import configure_capture, css
from tests.test_composition_measure_minimum import containing_column
from tests.test_composition_shipped import composition_report, assert_composition_passes
from tests.test_m2_capture import tree_hashes

pytestmark = [pytest.mark.browser, pytest.mark.browser_timeout(600)]
WIDTHS = (375, 768, 1280)
UNAVAILABLE_RULES = "cross-origin stylesheet rules unavailable"


def source_variant(fixture_site, cross_origin):
    source = fixture_site.root / "centred-prose" / "index.html"
    text = source.read_text()
    assert "margin: 24px auto" in text
    url = fixture_site.url + "/centred-prose/index.html"
    stylesheet = None
    if cross_origin:
        match = re.search(r"<style>(.*?)</style>", text, re.DOTALL)
        assert match is not None
        # The same real HTTP fixture responds to both hosts; different host
        # names make distinct origins. No crossorigin attribute or CORS header
        # grants CSSOM access, while the browser can still apply the stylesheet.
        endpoint = urlsplit(fixture_site.url)
        assert endpoint.hostname == "127.0.0.1"
        stylesheet = f"{endpoint.scheme}://localhost:{endpoint.port}/centred-prose/centred.css"
        assert urlsplit(url).netloc != urlsplit(stylesheet).netloc
        source.with_name("centred.css").write_text(match.group(1))
        source.write_text(text[:match.start()] + f'<link rel="stylesheet" href="{stylesheet}">' + text[match.end():])
        assert "<style>" not in source.read_text() and "auto" not in source.read_text()
    return url, stylesheet


def assert_capture_rule_access(captured, root, cross_origin):
    # The capture manifest and its per-width style samples are public evidence.
    # Accept diagnostic grouping at either level without pinning a private
    # warning container, but never infer unavailability merely from the URL.
    evidence = [captured]
    for entry in captured["pages"]:
        evidence.extend(read_json(confined(root, files["styles"])) for files in entry["widths"].values())
    unavailable = [value for record in evidence for _, value in scalar_leaves(record)
                   if isinstance(value, str) and UNAVAILABLE_RULES in value.casefold()]
    assert bool(unavailable) is cross_origin, ("Capture rule-access evidence did not match source", unavailable)
    unexpected = [problem for problem in captured["problems"]
                  if not cross_origin or UNAVAILABLE_RULES not in problem["message"].casefold()]
    assert not unexpected, unexpected


def prose_boxes(paragraphs):
    result = []
    for paragraph in paragraphs.all():
        box = paragraph.evaluate("""e=>({text:e.textContent.trim(),width:e.getBoundingClientRect().width,
          font:parseFloat(getComputedStyle(e).fontSize),visible:!!e.getClientRects().length})""")
        if len(box["text"]) >= 60:
            box["column"] = containing_column(paragraph)
            result.append(box)
    return result


def assert_readable_boxes(boxes, context):
    assert boxes, ("No long prose reached the minimum-measure assertion", context)
    for box in boxes:
        assert box["visible"] and box["font"] > 0 and box["width"] > 0, (context, box)
        assert box["column"]["width"] > 0, (context, box)
        minimum = min(15 * box["font"], 2 * box["column"]["width"] / 3)
        assert box["width"] >= minimum - 0.05, (context, box)


@pytest.mark.parametrize("cross_origin", [False, True], ids=["inline-rules", "cross-origin-computed-only"])
def test_viewport_auto_margins_do_not_become_insets_in_saved_container(
        library, fixture_site, ingest_config, tmp_path, page, cross_origin):
    configure_capture(library, ingest_config)
    # Capture all widths that will be inspected, including the largest viewport
    # where the authored auto margins resolve to 320px on each side.
    ingest_config["widths"] = list(WIDTHS)
    (library.project / "kinbase-design.toml").write_text(
        "[ingest]\n" + "\n".join(f"{key} = {value}" for key, value in ingest_config.items()) + "\n")
    url, stylesheet = source_variant(fixture_site, cross_origin)
    page.goto(url)
    access = page.evaluate("""()=>[...document.styleSheets].map(sheet=>{
      try {return {href:sheet.href,readable:true,rules:sheet.cssRules.length};}
      catch(error) {return {href:sheet.href,readable:false,error:error.name};}
    })""")
    assert len(access) == 1, access
    if cross_origin:
        assert access == [{"href": stylesheet, "readable": False, "error": "SecurityError"}], access
    else:
        assert access[0]["readable"] and access[0]["rules"] > 0, access
    for width in WIDTHS:
        page.set_viewport_size({"width": width, "height": 1000})
        expected_column = min(640, width - 32)
        expected_margin = (width - expected_column) / 2
        main = page.locator("main")
        box = main.bounding_box()
        assert box["width"] == expected_column and box["x"] == expected_margin, box
        margins = css(main, ["margin-left", "margin-right"])
        assert margins == {"margin-left": f"{expected_margin:g}px", "margin-right": f"{expected_margin:g}px"}
        for paragraph in page.locator("#article > p").all():
            assert paragraph.bounding_box()["x"] == box["x"]
            assert paragraph.bounding_box()["width"] == min(480, expected_column)
            assert css(paragraph, ["margin-left", "margin-right"]) == {"margin-left": "0px", "margin-right": "0px"}
        assert_readable_boxes(prose_boxes(page.locator("main p")), ("source", width))

    artifact, root, captured = capture(library, [url])
    assert len(captured["pages"]) == 1, captured
    assert_capture_rule_access(captured, root, cross_origin)
    captured_widths = tuple(sorted(int(width) for width in captured["pages"][0]["widths"]))
    assert set(WIDTHS) <= set(captured_widths), captured_widths
    immutable = tree_hashes(root)
    fixture_site.available = False
    requests = len(fixture_site.requests)
    _, document, summary = draft(library, [artifact], "centred-source")
    assert isinstance(summary["excluded"], list) and isinstance(summary["corrections"], list)
    assert len(fixture_site.requests) == requests, "draft revisited the source"
    assert tree_hashes(root) == immutable, "draft mutated capture evidence"
    library.cli("save-draft", document["id"], cwd=library.project, timeout=90)
    assert library.read(document["id"]) == document
    preview = library.build(tmp_path / "saved-preview", document["id"])
    seen_columns = set()
    for width in captured_widths:
        page.set_viewport_size({"width": width, "height": 1000})
        long_prose = []
        body_prose = []
        for name in PAGES:
            page.goto((preview / name).as_uri())
            page.evaluate("document.fonts.ready")
            boxes = prose_boxes(page.locator("p"))
            if boxes:
                assert_readable_boxes(boxes, (name, width))
                long_prose.extend(boxes)
            bodies = prose_boxes(page.locator('p[data-kd-role="body"], [data-kd-role="body"] p'))
            for body in bodies:
                assert body["font"] == pytest.approx(16, abs=1), (name, width, body)
            body_prose.extend(bodies)
            # State examples sit inside padded frames, not at page-container
            # scope. Their prose still participates in the checks above.
            if name == "states.html":
                continue
            for column in page.locator('[data-kd-construct="page-shell"]').all():
                if not column.is_visible():
                    continue
                actual = column.bounding_box()
                assert actual["x"] == pytest.approx((width - actual["width"]) / 2, abs=1), actual
                if width >= 672:
                    assert actual["width"] == pytest.approx(640, abs=1), actual
                # The source's 16px body gives a 240px floor; it never has a
                # narrower main column at these widths. Enlarging or shrinking
                # the saved container cannot disguise duplicated outer margins.
                assert actual["width"] >= 240, actual
                seen_columns.add(width)
        assert long_prose, ("Saved previews contained no long prose", width)
        assert any(box["column"]["width"] >= 15 * box["font"] for box in long_prose), (
            "No nonexempt column exercised the margin-transfer assertion", width, long_prose)
        assert body_prose, ("No body-role prose exercised the source's 16px size", width)
    assert seen_columns == set(captured_widths), seen_columns
    checked = composition_report(library, document["id"], tmp_path / "saved-check", widths=captured_widths)
    assert_composition_passes(checked)
    assert len(fixture_site.requests) == requests, "Saved-language operations revisited the source"
    assert tree_hashes(root) == immutable, "Saved-language operations mutated capture evidence"
