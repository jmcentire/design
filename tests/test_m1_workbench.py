"""Normative M1 report/workbench: submit the real no-JS form and see the newest evidence.

Falsifiers: inert check button, stale report panel, omitted unresolved review,
fabricated counts, or screenshot links that do not serve the report's actual PNG.
"""

from collections import Counter
import hashlib
import json
import re
from urllib.parse import urlsplit

import pytest
from playwright.sync_api import expect

from tests.browser_support import form_at, link_at
from tests.m1_support import contrast_ratio, findings, slot_properties, token
from tests.support import PAGES
from tests.test_versions_assets import expected_hash

pytestmark = [pytest.mark.browser, pytest.mark.browser_timeout(240)]


def submit_check(page, server):
    page.goto(server + "/languages/tidal")
    form = form_at(page, "/languages/tidal/check")
    assert form.get_attribute("method").lower() == "post"
    with page.expect_navigation(wait_until="load", timeout=90000):
        form.locator('button[type="submit"],input[type="submit"],button:not([type])').first.click(no_wait_after=True)
    expect(page).to_have_url(server + "/languages/tidal")
    # Native disclosure controls remain usable without JavaScript.
    details = page.locator("details")
    for i in range(details.count()):
        if details.nth(i).get_attribute("open") is None:
            details.nth(i).locator("summary").first.click()


def persisted_report(library, document):
    directory = library.library / "generated" / "tidal" / "checks" / expected_hash(document)
    report = json.loads((directory / "report.json").read_text())
    assert set(report["checked"]["pages"]) == set(PAGES)
    assert set(report["checked"]["widths"]) == {320, 768, 1280}
    assert report["needs_review"] == sum(f["type"] == "needs-review" for f in report["findings"])
    return directory, report


def test_check_form_latest_findings_and_screenshots_without_javascript(server, library, language, page, browser_context):
    props = slot_properties(language, slot="price")
    props.update({"color": token(language, "probe", "foreground", "color", "#777777"),
                  "background-color": "{color.paper}", "font-size": "{size.body}", "font-weight": "{type.weight}"})
    slot_properties(language)["background-image"] = "asset:fixture-image:primary"
    library.write(language)
    submit_check(page, server)
    directory, report = persisted_report(library, language)
    low_contrast = findings(report, "contrast", "listing-card.price", "violation")
    assert len(low_contrast) == 1 and report["accepted"] is False, report
    assert report["needs_review"] > 0
    body = page.locator("body").inner_text()
    assert "1.4.3" in body and str(contrast_ratio("#777777", "#ffffff")) in body and "4.5" in body
    assert re.search(r"needs[\s_-]*review|unresolved", body, re.I)
    expected_images = {hashlib.sha256((directory / f["screenshot"]).read_bytes()).hexdigest() for f in low_contrast}
    linked_images = set()
    urls = set(page.locator("a[href]").evaluate_all("anchors => anchors.map(a => a.href)"))
    for url in urls:
        if urlsplit(url).netloc != urlsplit(server).netloc:
            continue
        response = browser_context.request.get(url, timeout=5000)
        if response.ok and "image/png" in response.headers.get("content-type", ""):
            linked_images.add(hashlib.sha256(response.body()).hexdigest())
    assert expected_images <= linked_images, "The findings panel does not link its real screenshots"
    language["style"]["probe"]["foreground"]["$value"] = "#000000"
    library.write(language)
    submit_check(page, server)
    _, latest = persisted_report(library, language)
    assert not findings(latest, "contrast", "listing-card.price", "violation"), latest
    assert str(contrast_ratio("#777777", "#ffffff")) not in page.locator("body").inner_text()
    assert latest["needs_review"] > 0
    page.goto(server + "/")
    summary = link_at(page, "/languages/tidal").evaluate("""anchor => {
      for (let node = anchor; node; node = node.parentElement) {
        const destinations = Array.from(node.querySelectorAll('a[href]')).map(a => new URL(a.href).pathname)
          .filter(p => p.startsWith('/languages/'));
        if (new Set(destinations).size === 1 && /kinbase/i.test(node.textContent)) return node.textContent;
      }
      return null;
    }""")
    assert summary is not None
    normalized = re.sub(r"[\s_-]+", " ", summary.lower())
    for kind, count in Counter(f["type"] for f in latest["findings"]).items():
        assert kind.replace("-", " ") in normalized
        assert re.search(rf"(?<!\d){count}(?!\d)", summary), (kind, count, summary)
