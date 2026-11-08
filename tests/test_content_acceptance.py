"""Normative amendment 06: static validity cannot impersonate rendered acceptance.

Real render/check CLI and persisted reports. Falsifiers: unchecked accepted=true,
acceptance retained after rejection, stale-version status reuse, or check --out
outside the default directory disappearing from status. No fabricated reports.
"""
import copy

import pytest

from tests.content_support import (content_library, write_content, save_content,
                                   render_result, content_findings)
from tests.m1_support import token, run_check, findings


def status(library, source, out, expected, language="lantern"):
    report = render_result(library, source, out, language)
    assert report["rendered_check"] == expected, report
    # Static validity writes an inspectable bundle with exit 0, even when the
    # rendered evidence is absent or rejected. render_result checks those files.
    assert report["validated"] is True
    assert report["accepted"] is (expected == "accepted")
    return report["version"]


def test_fresh_valid_bundle_is_unchecked_and_invalid_content_is_not_accepted(content_library, tmp_path):
    source, content = write_content(tmp_path / "source")
    status(content_library, source, tmp_path / "unchecked", "unchecked")
    content["blocks"][0]["title"] = 42
    save_content(source, content)
    report = content_library.json("render-page", "lantern", "--content", source, "--out", tmp_path / "invalid", code=1)
    assert report["validated"] is False and report["accepted"] is False
    content_findings(report, source, content, "/blocks/0/title")


@pytest.mark.browser
@pytest.mark.browser_timeout(360)
def test_render_status_tracks_latest_check_and_exact_language_version(content_library, tmp_path):
    source, _ = write_content(tmp_path / "source")
    document = content_library.read("lantern")
    # The shipped Lantern has an accepted narrow baseline (M1). A wide-only
    # white-on-white slot creates a real rendered rejection while remaining
    # statically valid. Both outcomes therefore concern the SAME minted version.
    white = token(document, "statusprobe", "white", "color", "#ffffff")
    scope = "listing-card.price@lg"
    document["overrides"] = [o for o in document.get("overrides", []) if o["scope"] != scope]
    document["overrides"].append({"scope": scope, "reason": "Independent wide-only contrast failure",
                                  "properties": {"color": white, "background-color": white}})
    original = copy.deepcopy(document)
    content_library.write(document)
    version = status(content_library, source, tmp_path / "before-check", "unchecked")
    # Custom output locations exercise the library's status tracking independently
    # of where the caller asked the actual report/screenshot files to be written.
    run_check(content_library, tmp_path / "external-reports" / "narrow", "lantern", widths=(320,), accepted=True)
    assert status(content_library, source, tmp_path / "after-pass", "accepted") == version

    document["style"]["statusprobe"]["white"]["$value"] = "#fefefe"
    content_library.write(document)
    changed_version = status(content_library, source, tmp_path / "changed-unchecked", "unchecked")
    assert changed_version != version
    content_library.write(original)
    assert status(content_library, source, tmp_path / "restored-pass", "accepted") == version

    rejected = run_check(content_library, tmp_path / "external-reports" / "wide", "lantern", widths=(1280,), accepted=False)
    assert findings(rejected, "contrast", "listing-card.price", "violation"), rejected
    assert status(content_library, source, tmp_path / "after-rejection", "rejected") == version

    # A newer check of another version must not resurrect an older matching report
    # when the working language is restored: amendment 06 explicitly says unchecked
    # when the latest check belongs to a different version.
    content_library.write(document)
    run_check(content_library, tmp_path / "external-reports" / "changed-narrow", "lantern", widths=(320,), accepted=True)
    assert status(content_library, source, tmp_path / "changed-accepted", "accepted") == changed_version
    content_library.write(original)
    assert status(content_library, source, tmp_path / "old-version-stale", "unchecked") == version
