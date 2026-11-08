"""Beach seeds must survive derivation as visible design; default copy is generic."""

import pytest

from tests.m3_perceptual_support import assert_beach_paint, assert_neutral_default_copy, screenshot_image
from tests.m3_render_support import paint_snapshot
from tests.m3_support import BEACH, start
from tests.support import PAGES
from tests.test_m3_derive import check_draft, derive

pytestmark = [pytest.mark.browser, pytest.mark.browser_timeout(600)]


def test_beach_brief_derives_prominent_color_and_casual_whimsy_before_any_choices(library, page, tmp_path):
    # No supplied palette or user answer overrides the brief's seeds. Early
    # derivation is permitted and must not silently fall back to a grey default.
    session, _, _ = start(library, BEACH)
    root, document, _ = derive(library, session, "beach-perception")
    case = check_draft(library, root, document, tmp_path / "beach-report")
    site = case.build(tmp_path / "beach-site", document["id"])
    page.set_viewport_size({"width": 1280, "height": 900})
    page.goto((site / "index.html").as_uri())
    page.wait_for_function("document.fonts.status === 'loaded'", timeout=5000)
    picture = screenshot_image(page.screenshot(full_page=True, timeout=5000, animations="disabled", caret="hide"))
    assert_beach_paint(paint_snapshot(page), picture, 1280 * 900)
    for filename in PAGES:
        page.goto((site / filename).as_uri())
        assert_neutral_default_copy(page)


def test_default_preview_copy_is_domain_neutral_on_every_page(library, language, page, tmp_path):
    # The independently authored language changes treatment only; all prose here
    # is default preview copy. Ingested/user-authored text is deliberately outside
    # this test, as its source content must be preserved even when specialized.
    site = library.build(tmp_path / "neutral-copy", language["id"])
    for filename in PAGES:
        page.goto((site / filename).as_uri())
        assert_neutral_default_copy(page)
