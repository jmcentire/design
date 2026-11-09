"""Addenda 11c/11d: container transfer at and between captured widths."""
import pytest

from tests.m2_support import capture, draft
from tests.support import PAGES
from tests.test_composition_ingest import configure_capture, css
from tests.test_composition_shipped import composition_report, assert_composition_passes
from tests.test_m2_capture import tree_hashes

pytestmark = [pytest.mark.browser, pytest.mark.browser_timeout(600)]

# Authored source CSS, independent of draft summaries or resolved output.
STEPS = ((576, 540), (768, 720), (992, 960), (1200, 1140), (1400, 1320))
REQUESTED_WIDTHS = (375, 576, 768, 992, 1200, 1400, 1600)
INLINE_PADDING = 24
# states.html embeds construct examples inside padded demonstration frames.
# Container transfer concerns the page itself, not those framed examples.
CONTAINER_PAGES = tuple(name for name in PAGES if name != "states.html")


def expected_width(viewport):
    return next((width for breakpoint, width in reversed(STEPS) if viewport >= breakpoint), viewport - 32)


def assert_container(column, viewport, context, tolerance=2):
    assert column.is_visible(), context
    box = column.bounding_box()
    expected = expected_width(viewport)
    assert box["width"] == pytest.approx(expected, abs=tolerance), (context, viewport, expected, box)
    assert box["x"] + box["width"] / 2 == pytest.approx(viewport / 2, abs=tolerance), (
        "Container is not centred", context, viewport, box)
    inset = css(column, ["padding-left", "padding-right"])
    for value in inset.values():
        assert float(value.removesuffix("px")) == pytest.approx(INLINE_PADDING, abs=1), (context, viewport, inset)
    return box


def test_saved_container_matches_source_at_every_captured_breakpoint(
        library, fixture_site, ingest_config, tmp_path, page):
    configure_capture(library, ingest_config)
    ingest_config["widths"] = list(REQUESTED_WIDTHS)
    (library.project / "kinbase-design.toml").write_text(
        "[ingest]\n" + "\n".join(f"{key} = {value}" for key, value in ingest_config.items()) + "\n")
    url = fixture_site.url + "/stepped-container/index.html"
    page.goto(url)
    for width in REQUESTED_WIDTHS:
        page.set_viewport_size({"width": width, "height": 1000})
        assert_container(page.locator("main"), width, "authored source", tolerance=0.05)

    artifact, root, captured = capture(library, [url])
    assert not captured["problems"], captured
    assert len(captured["pages"]) == 1, captured
    widths = tuple(sorted(int(width) for width in captured["pages"][0]["widths"]))
    assert set(REQUESTED_WIDTHS) <= set(widths), widths
    # Discovery may add widths; establish source geometry for those as well.
    # The page remains loaded from the local HTTP source, with only inline CSS.
    for width in widths:
        page.set_viewport_size({"width": width, "height": 1000})
        assert_container(page.locator("main"), width, "captured source width", tolerance=0.05)
    assert {expected_width(width) for width in widths} >= {540, 720, 960, 1140, 1320}
    immutable = tree_hashes(root)
    fixture_site.available = False
    requests = len(fixture_site.requests)
    _, document, summary = draft(library, [artifact], "stepped-container")
    assert isinstance(summary["excluded"], list) and isinstance(summary["corrections"], list)
    library.cli("save-draft", document["id"], cwd=library.project, timeout=90)
    assert library.read(document["id"]) == document

    # Ordinary saved-language previews must carry the treatment; styling only
    # source-specific fidelity contexts cannot satisfy this transfer assertion.
    preview = library.build(tmp_path / "saved-preview", document["id"])
    seen = set()
    for width in widths:
        page.set_viewport_size({"width": width, "height": 1000})
        for name in CONTAINER_PAGES:
            page.goto((preview / name).as_uri())
            page.evaluate("document.fonts.ready")
            for column in page.locator('[data-kd-construct="page-shell"]').all():
                assert_container(column, width, ("saved preview", name))
                seen.add(width)
    assert seen == set(widths), ("No saved page container was measured at a captured width", seen, widths)
    assert max(widths) in seen
    checked = composition_report(library, document["id"], tmp_path / "saved-check", widths=widths)
    assert_composition_passes(checked)
    assert len(fixture_site.requests) == requests, "Saved-language operations revisited the source"
    assert tree_hashes(root) == immutable, "Saved-language operations mutated capture evidence"


def test_container_grows_between_captures_with_lower_margins_and_upper_cap(
        library, fixture_site, ingest_config, tmp_path, page):
    captured_viewports = (375, 768)
    uncaptured_viewports = (576, 720)
    configure_capture(library, ingest_config)
    ingest_config["widths"] = list(captured_viewports)
    (library.project / "kinbase-design.toml").write_text(
        "[ingest]\n" + "\n".join(f"{key} = {value}" for key, value in ingest_config.items()) + "\n")
    # A percentage width with a fixed max-width gives fluid/fixed endpoints
    # without a media query that could add another captured breakpoint.
    url = fixture_site.url + "/fluid-to-fixed-container/index.html"
    page.goto(url)
    source_boxes = {}
    for viewport in captured_viewports:
        page.set_viewport_size({"width": viewport, "height": 1000})
        main = page.locator("main")
        box = main.bounding_box()
        authored_width = min(0.9 * viewport, 640)
        assert box["width"] == pytest.approx(authored_width, abs=0.05), (viewport, box)
        assert box["x"] == pytest.approx((viewport - authored_width) / 2, abs=0.05), (viewport, box)
        assert css(main, ["padding-left", "padding-right"]) == {"padding-left": "16px", "padding-right": "16px"}
        source_boxes[viewport] = box
    lower = source_boxes[375]
    lower_margins = (lower["x"], 375 - lower["x"] - lower["width"])
    upper_cap = source_boxes[768]["width"]
    assert lower_margins == pytest.approx((18.75, 18.75), abs=0.05)

    artifact, root, captured = capture(library, [url])
    assert not captured["problems"] and len(captured["pages"]) == 1, captured
    recorded = {int(width) for width in captured["pages"][0]["widths"]}
    assert recorded == set(captured_viewports), ("This fixture must have exactly two captured endpoints", recorded)
    assert recorded.isdisjoint(uncaptured_viewports)
    immutable = tree_hashes(root)
    fixture_site.available = False
    requests = len(fixture_site.requests)
    _, document, summary = draft(library, [artifact], "fluid-to-fixed")
    assert isinstance(summary["excluded"], list) and isinstance(summary["corrections"], list)
    library.cli("save-draft", document["id"], cwd=library.project, timeout=90)
    assert library.read(document["id"]) == document
    preview = library.build(tmp_path / "saved-preview", document["id"])
    checked_widths = tuple(sorted((*captured_viewports, *uncaptured_viewports)))
    seen = set()
    for viewport in checked_widths:
        page.set_viewport_size({"width": viewport, "height": 1000})
        # This is the addendum's inference from the captured endpoints, not the
        # source's uncaptured percentage width or a value read from the draft.
        expected = min(viewport - sum(lower_margins), upper_cap)
        for name in CONTAINER_PAGES:
            page.goto((preview / name).as_uri())
            page.evaluate("document.fonts.ready")
            for column in page.locator('[data-kd-construct="page-shell"]').all():
                assert column.is_visible(), (name, viewport)
                box = column.bounding_box()
                assert box["width"] == pytest.approx(expected, abs=2), (name, viewport, expected, box)
                assert box["x"] + box["width"] / 2 == pytest.approx(viewport / 2, abs=2), (name, viewport, box)
                inset = css(column, ["padding-left", "padding-right"])
                assert all(float(value.removesuffix("px")) == pytest.approx(16, abs=1) for value in inset.values()), inset
                if viewport == 576:
                    actual_margins = (box["x"], viewport - box["x"] - box["width"])
                    assert actual_margins == pytest.approx(lower_margins, abs=2), (name, actual_margins, lower_margins)
                    assert box["width"] > lower["width"] + 190, "Container froze at its lower captured width"
                if viewport == 720:
                    assert box["width"] == pytest.approx(upper_cap, abs=2), "Growth exceeded the next captured container"
                seen.add(viewport)
    assert seen == set(checked_widths), seen
    checked = composition_report(library, document["id"], tmp_path / "saved-check", widths=checked_widths)
    assert_composition_passes(checked)
    assert len(fixture_site.requests) == requests, "Saved-language operations revisited the source"
    assert tree_hashes(root) == immutable, "Saved-language operations mutated capture evidence"
