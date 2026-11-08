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
    for finding in report["findings"]:
        if finding["rule"] not in RENDERED_RULES:
            continue
        assert finding["page"] in PAGES
        assert finding["width"] in widths
        assert isinstance(finding["target"], str) and finding["target"]
        assert isinstance(finding["criterion"], str) and finding["criterion"]
        assert {"measured", "threshold", "exception", "screenshot"} <= finding.keys()
        relative = Path(finding["screenshot"])
        assert not relative.is_absolute()
        screenshot = out / relative
        assert screenshot.resolve().is_relative_to(out.resolve())
        with Image.open(screenshot) as rendered:
            assert rendered.format == "PNG"
            assert rendered.width == finding["width"] and rendered.height > 0
            rendered.verify()
    return report


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
