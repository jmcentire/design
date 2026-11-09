"""Amendments 09–11: both shipped languages pass the composition rules.

Real check CLI, including its --content boundary. The shipped languages are test
subjects, not expected-value snapshots. This is the positive regression increment;
isolated negative fixtures and ingest-transfer checks are separate obligations.
"""

import json
import math

import pytest

from tests.content_support import content_library, save_content, write_content
from tests.support import PAGES


pytestmark = [pytest.mark.browser, pytest.mark.browser_timeout(420)]
COMPOSITION_RULES = {"heading-scale", "text-inset", "control-separation", "measure",
                     "word-break", "label-proximity", "heading-binding", "gutter"}
WIDTHS = (375, 768, 1023, 1024, 1280)
PARAGRAPH = (
    "The observatory notebook records small changes in the garden throughout the year. "
    "Each entry describes an observation, gives its context, and invites the reader "
    "to compare it with the next visit. These are invented examples for a layout test."
)


def composition_report(library, language, out, content=None, widths=WIDTHS):
    args = ["check", language, "--out", out, "--widths", ",".join(map(str, widths))]
    if content is not None:
        args += ["--content", content]
    result = library.cli(*args, code=(0, 1), timeout=180)
    report_file = out / "report.json"
    assert report_file.is_file(), (
        "check produced no report", result.returncode, result.stdout, result.stderr)
    report = json.loads(report_file.read_text())
    assert report["language"] == language
    assert type(report["accepted"]) is bool
    assert result.returncode == (0 if report["accepted"] else 1), report
    assert set(report["checked"]["widths"]) == set(widths), report
    assert report["checked"]["pages"], "No page was checked"
    if content is None:
        assert set(report["checked"]["pages"]) == set(PAGES)
    return report


def assert_word_break_measurements(report):
    """Q-0074: advisory classification needs the reported smallest-width evidence."""
    for finding in report["findings"]:
        if finding["rule"] != "word-break" or finding["type"] not in {"violation", "needs-review"}:
            continue
        measured = finding["measured"]
        assert isinstance(measured, dict), finding
        assert {"word", "word_width", "available_width", "smallest_width", "line_boxes"} <= measured.keys(), finding
        assert isinstance(measured["word"], str) and measured["word"], finding
        for field in ("word_width", "available_width", "smallest_width", "line_boxes"):
            value = measured[field]
            assert type(value) in {int, float} and math.isfinite(value) and value > 0, finding
        assert measured["smallest_width"] == min(report["checked"]["widths"]), finding
        assert measured["line_boxes"] >= 2 and measured["line_boxes"] == int(measured["line_boxes"]), finding
        oversized = measured["word_width"] > measured["available_width"]
        assert oversized is (finding["type"] == "needs-review"), finding


def assert_composition_passes(report):
    # Advisory findings do not reject composition. An oversized-word advisory
    # still needs measured evidence; relabeling an avoidable split cannot pass.
    failures = [finding for finding in report["findings"]
                if finding["rule"] in COMPOSITION_RULES
                and finding["type"] in {"violation", "missing"}
                and not finding.get("exception")]
    assert not failures, failures
    assert_word_break_measurements(report)


@pytest.mark.parametrize("language", ["harbor", "lantern"])
def test_shipped_samples_pass_composition_at_each_checked_width(content_library, tmp_path, language):
    report = composition_report(content_library, language, tmp_path / "samples")
    assert_composition_passes(report)


@pytest.mark.parametrize("language", ["harbor", "lantern"])
def test_shipped_content_page_passes_composition_at_each_checked_width(content_library, tmp_path, language):
    source, document = write_content(tmp_path / "content")
    # Exercise the paragraph-length threshold, successive heading levels,
    # painted groups and adjacent action targets in a domain-neutral document.
    document["blocks"][0]["body"] = PARAGRAPH
    document["blocks"][0]["actions"].append({"text": "Browse entries", "href": "#entries"})
    document["blocks"][1]["content"].insert(0, {"paragraph": PARAGRAPH})
    for item in document["blocks"][2]["items"]:
        item["body"] = PARAGRAPH
        # More than one fact gives each nonfinal value a following label for
        # amendment 10's proximity comparison; a lone pair would be vacuous.
        item["facts"] = [{"label": "Category", "value": "Observation"},
                         {"label": "Season", "value": "Spring"},
                         {"label": "Method", "value": "Field notes"}]
    document["blocks"][3]["body"] = PARAGRAPH
    document["blocks"][3]["actions"].append({"text": "Read again", "href": "#guide"})
    save_content(source, document)
    report = composition_report(content_library, language, tmp_path / "content-check", source)
    assert_composition_passes(report)
