"""Independent M1 oracles and public-boundary report helpers. No production imports."""

import hashlib
import json
from pathlib import Path

from PIL import Image

from tests.support import PAGES

RENDERED_RULES = {
    "contrast", "non-text-contrast", "role-conformance", "clipping", "reflow",
    "target-size", "asset-load", "focus-visible", "keyboard", "no-js",
}


def luminance(hex_color):
    """WCAG sRGB linearization and luminance coefficients, independent of checker/axe."""
    channels = [int(hex_color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    linear = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return sum(c * weight for c, weight in zip(linear, (0.2126, 0.7152, 0.0722)))


def contrast_ratio(foreground, background):
    high, low = sorted((luminance(foreground), luminance(background)), reverse=True)
    return round((high + 0.05) / (low + 0.05), 2)


def token(document, group, name, type, value):
    document["style"].setdefault(group, {})[name] = {"$type": type, "$value": value}
    return "{" + group + "." + name + "}"


def slot_properties(document, construct="listing-card", slot="title"):
    return document["components"][construct].setdefault("slots", {}).setdefault(slot, {}).setdefault("properties", {})


def findings(report, rule, target=None, kind=None):
    return [f for f in report["findings"] if f["rule"] == rule
            and (target is None or f.get("target") == target)
            and (kind is None or f["type"] == kind)]


def run_check(library, out, language="tidal", widths=(320,), accepted=None):
    """Real check command. Exit/report agreement cannot substitute for a seeded-finding assertion."""
    result = library.cli("check", language, "--out", out, "--widths", ",".join(map(str, widths)),
                         code=(0, 1) if accepted is None else 0 if accepted else 1, timeout=90)
    report_path = out / "report.json"
    assert report_path.is_file(), "check did not persist its report"
    report = json.loads(report_path.read_text())
    assert report["language"] == language
    assert isinstance(report["accepted"], bool)
    if accepted is not None:
        assert report["accepted"] is accepted, report
    assert result.returncode == (0 if report["accepted"] else 1), report
    uncovered = [f for f in report["findings"] if f["type"] in {"violation", "missing"} and not f.get("exception")]
    assert report["accepted"] == (not uncovered), report
    assert report["needs_review"] == sum(f["type"] == "needs-review" for f in report["findings"])
    assert set(report["checked"]["pages"]) == set(PAGES)
    assert set(report["checked"]["widths"]) == set(widths)
    verified_screenshots = set()
    for finding in report["findings"]:
        assert {"type", "rule", "file", "pointer", "observed", "expected", "message"} <= finding.keys()
        assert finding["type"] in {"violation", "missing", "needs-review", "coverage"}
        if finding["rule"] not in RENDERED_RULES:
            continue
        if finding["type"] == "coverage" and not finding.get("exception") and "page" not in finding:
            continue
        assert finding["page"] in PAGES
        assert finding["width"] in widths
        assert isinstance(finding["target"], str) and finding["target"]
        assert isinstance(finding["criterion"], str) and finding["criterion"]
        assert {"measured", "threshold", "exception", "screenshot"} <= finding.keys()
        occurrences = finding["occurrences"]
        assert isinstance(occurrences, list) and occurrences
        assert {key: finding[key] for key in ("page", "width", "screenshot")} == {
            key: occurrences[0][key] for key in ("page", "width", "screenshot")}
        for occurrence in occurrences:
            assert occurrence["page"] in PAGES and occurrence["width"] in widths
            relative = Path(occurrence["screenshot"])
            assert not relative.is_absolute()
            screenshot = out / relative
            assert screenshot.resolve().is_relative_to(out.resolve())
            identity = (screenshot, occurrence["width"])
            if identity in verified_screenshots:
                continue
            with Image.open(screenshot) as rendered:
                assert rendered.format == "PNG"
                # Full-page overflow and device scale can enlarge the pixel capture.
                assert rendered.width >= occurrence["width"] and rendered.height > 0
                rendered.verify()
            with Image.open(screenshot) as rendered:
                rendered.load()
            verified_screenshots.add(identity)
    return report


def assert_full_text_available(page, text):
    """A clipped DOM string is not evidence of full-content availability on the detail page."""
    candidates = page.get_by_text(text, exact=True)
    for index in range(candidates.count()):
        candidate = candidates.nth(index)
        if not candidate.is_visible():
            continue
        if candidate.evaluate("""element => {
          const range = document.createRange(); range.selectNodeContents(element);
          const rects = [...range.getClientRects()].filter(r => r.width > 0 && r.height > 0);
          if (!rects.length) return false;
          for (let e = element; e; e = e.parentElement) {
            const style = getComputedStyle(e), box = e.getBoundingClientRect();
            const left = box.left + e.clientLeft, top = box.top + e.clientTop;
            if (['hidden','clip'].includes(style.overflowX) &&
                rects.some(r => r.left < left - 1 || r.right > left + e.clientWidth + 1)) return false;
            if (['hidden','clip'].includes(style.overflowY) &&
                rects.some(r => r.top < top - 1 || r.bottom > top + e.clientHeight + 1)) return false;
          }
          return true;
        }"""):
            return
    raise AssertionError(f"Full title is absent, hidden or clipped on the detail page: {text!r}")


def replace_asset_bytes(library, document, asset_id, variant, data):
    """Author a corrupt but correctly content-addressed input, retaining manifest metadata."""
    digest = hashlib.sha256(data).hexdigest()
    destination = library.path(document["id"]).parent / "assets" / "sha256" / digest
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(data)
    document["assets"][asset_id]["variants"][variant]["file"] = f"sha256/{digest}"


def remove_behaviors(document, scope, kind):
    document["behaviors"] = [b for b in document.get("behaviors", []) if
                             not (b["scope"] == scope and b["kind"] == kind)]


def add_behavior(document, behavior):
    entries = document.setdefault("behaviors", [])
    entries.append(behavior)
    return f"/behaviors/{len(entries) - 1}"
