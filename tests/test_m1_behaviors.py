"""Normative M1 clipping/reflow/targets and SPEC 6.7 acceptance.

Falsifiers: detect nothing, waive every defect, ignore the behavior's scope,
lose full content, hide covered findings, or gate
advisory coverage. Inputs are public language data; no patched CSS or checker.
"""

import json

import pytest

from tests.m1_support import add_behavior, findings, remove_behaviors, run_check, slot_properties, token
from tests.support import pointer_value

pytestmark = [pytest.mark.browser, pytest.mark.browser_timeout(240)]


def test_clipping_requires_declared_truncation_and_available_full_content(library, lantern, tmp_path, page):
    remove_behaviors(lantern, "listing-card.title", "truncate")
    props = slot_properties(lantern)
    props.update({"display": "block", "width": token(lantern, "probe", "narrow", "dimension", "48px"),
                  "overflow": "hidden", "white-space": "nowrap", "text-overflow": "ellipsis"})
    library.write(lantern)
    site = library.build(tmp_path / "clipped-preview", "lantern")
    page.goto((site / "search.html").as_uri())
    titles = page.locator('[data-kd-slot="listing-card.title"]')
    assert titles.count() > 0
    assert any(titles.nth(i).evaluate("e => e.scrollWidth > e.clientWidth || e.scrollHeight > e.clientHeight")
               for i in range(titles.count())), "Fixture did not create clipped text"
    original_titles = [" ".join(text.split()) for text in titles.all_text_contents()]
    failed = run_check(library, tmp_path / "clipped-report", "lantern", accepted=False)
    assert findings(failed, "clipping", "listing-card.title", "violation"), failed
    pointer = add_behavior(lantern, {"scope": "listing-card.title", "kind": "truncate", "lines": 2,
                                    "full-content": "listing.html", "reason": "Full title on detail page"})
    library.write(lantern)
    accepted = run_check(library, tmp_path / "covered-report", "lantern", accepted=True)
    covered = findings(accepted, "clipping", "listing-card.title")
    assert covered and all(f["exception"] == pointer for f in covered), accepted
    site = library.build(tmp_path / "covered-preview", "lantern")
    page.goto((site / "listing.html").as_uri())
    visible_text = " ".join(page.locator("body").inner_text().split())
    assert all(title in visible_text for title in original_titles)


def test_page_overflow_is_confined_by_a_declared_horizontal_scroll_scope(library, lantern, vocabulary, tmp_path, page):
    remove_behaviors(lantern, "gallery", "horizontal-scroll")
    gallery = vocabulary["constructs"]["gallery"]
    placeholders = "".join("{{slot:" + slot["id"] + "}}" for slot in gallery["slots"])
    template = f'<{gallery["root"]}><div data-kd-part="wide-strip">{placeholders}</div></{gallery["root"]}>'
    lantern["layout"].setdefault("variants", {})["gallery"] = {"wide-fixture": {"template": template}}
    component = lantern["components"]["gallery"]
    component["variant"] = "wide-fixture"
    component.setdefault("properties", {}).pop("overflow", None)
    component.setdefault("parts", {})["wide-strip"] = {
        "width": token(lantern, "probe", "wide", "dimension", "800px")}
    library.write(lantern)
    site = library.build(tmp_path / "wide-preview", "lantern")
    page.set_viewport_size({"width": 320, "height": 900})
    page.goto((site / "listing.html").as_uri())
    assert page.evaluate("document.documentElement.scrollWidth > document.documentElement.clientWidth"), "Fixture did not overflow the page"
    failed = run_check(library, tmp_path / "wide-report", "lantern", accepted=False)
    assert findings(failed, "reflow", kind="violation"), failed
    pointer = add_behavior(lantern, {"scope": "gallery", "kind": "horizontal-scroll", "reason": "Gallery strip scrolls independently"})
    library.write(lantern)
    covered = run_check(library, tmp_path / "scroll-report", "lantern", accepted=True)
    exempt = findings(covered, "reflow")
    assert exempt and any(f["exception"] == pointer for f in exempt), covered
    assert not [f for f in exempt if f["type"] == "violation" and f["exception"] is None]


def test_crowded_small_targets_need_a_named_exception(library, language, tmp_path, page):
    props = slot_properties(language, "nav", "links")
    props.update({"display": "flex", "flex-wrap": "nowrap", "font-size": token(language, "probe", "tiny", "dimension", "2px"),
                  "line-height": token(language, "probe", "tight", "number", 1),
                  "padding": token(language, "space", "zero", "dimension", "0px"), "gap": "{space.zero}"})
    library.write(language)
    site = library.build(tmp_path / "tiny-targets")
    page.goto((site / "index.html").as_uri())
    targets = page.locator('[data-kd-slot="nav.links"] a, a[data-kd-slot="nav.links"]')
    boxes = [targets.nth(i).bounding_box() for i in range(targets.count()) if targets.nth(i).is_visible()]
    assert len(boxes) >= 2, "Fixture needs adjacent navigation targets"
    small = [b for b in boxes if b and b["width"] < 24 and b["height"] < 24]
    assert len(small) >= 2
    # 24px circles around centers overlap; the automatic spacing exception cannot excuse this pair.
    assert any((a["x"] + a["width"] / 2 - b["x"] - b["width"] / 2) ** 2 +
               (a["y"] + a["height"] / 2 - b["y"] - b["height"] / 2) ** 2 < 24 ** 2
               for i, a in enumerate(small) for b in small[i + 1:])
    failed = run_check(library, tmp_path / "small-report", accepted=False)
    assert findings(failed, "target-size", "nav.links", "violation"), failed
    pointer = add_behavior(language, {"scope": "nav.links", "kind": "target-exception",
                                      "exception": "essential", "reason": "Explicit essential-size fixture"})
    library.write(language)
    covered = run_check(library, tmp_path / "essential-report")
    cases = findings(covered, "target-size", "nav.links")
    assert cases and all(f["exception"] in {pointer, "essential"} for f in cases), covered
    assert pointer_value(language, pointer)["exception"] == "essential"


def test_unused_behavior_is_advisory_coverage(library, lantern, tmp_path):
    pointer = add_behavior(lantern, {"scope": "listing-card.price", "kind": "truncate", "lines": 999,
                                    "full-content": "listing.html", "reason": "Deliberately inactive coverage fixture"})
    library.write(lantern)
    report = run_check(library, tmp_path / "coverage-only", "lantern", accepted=True)
    assert any(f["type"] == "coverage" and f["pointer"] == pointer for f in report["findings"]), report


def test_required_missing_asset_fails_check_acceptance(library, lantern, tmp_path):
    lantern["components"]["nav"].setdefault("assets", {})["logo"] = "absent-logo:primary"
    library.write(lantern)
    out = tmp_path / "missing"
    library.cli("check", "lantern", "--out", out, "--widths", "320", code=1, timeout=90)
    report = json.loads((out / "report.json").read_text())
    assert report["accepted"] is False
    assert any(f["type"] == "missing" and f["rule"] == "R1" and
               f["pointer"] == "/components/nav/assets/logo" and f["observed"] == "absent-logo:primary"
               for f in report["findings"]), report
