"""B13/B15: missing Kinbase is visible uncertainty, not a dependency failure.

No real Kinbase executable is invoked. Cases use a nonexistent binary or
a test-owned executable whose fsck fails for a Git-only repository. Preview,
ingest and generate still exercise the real product and Chromium.
"""

import json
import re

import pytest

from tests.m2_support import capture, draft
from tests.m3_support import start, pair
from tests.m4_workbench_support import submit, workbench
from tests.m4_kinbase_support import (assert_read_calls, calls, configure, executable_seam,
                                     machine_fact, seam_environment, update_responses)
from tests.m4_support import site_repository
from tests.test_m2_workbench import visible
from tests.test_m3_derive import derive
from tests.test_versions_assets import expected_hash

pytestmark = [pytest.mark.browser, pytest.mark.browser_timeout(420)]


@pytest.fixture(params=["missing-binary", "uninitialized-repository", "uninitialized-zero-exit"])
def unavailable(library, tmp_path, request):
    unknown = {"state": "unknown", "current": None, "trusted": True, "unknowns": []}
    seam = executable_seam(tmp_path / "kinbase-seam", {
        "fixture.direction": unknown, "fixture.standard": unknown}, initialized=False)
    if request.param == "uninitialized-zero-exit":
        # Live fsck receipt: process success does not imply an initialized repo.
        # B13/B17 require unknown standards and no fixed facts or submission.
        update_responses(seam, fsck={"exit_code": 0, "stdout": {
            "status": "unverified", "reason": "repo-uninitialized", "event_count": 0}},
            explain={"fixture.direction": unknown, "fixture.standard": machine_fact(
                dimensions={"hue-family": 200}, scope="site")})
    library.command_env.update(seam_environment(seam))
    if request.param == "missing-binary":
        binary = library.project / "no-such-kinbase"
        assert not binary.exists()
        configure(library, binary, library.project)
    else:
        # Git initialization alone is not Kinbase initialization. The executable
        # returns the amendment-20 fsck failure rather than relying on an
        # invented on-disk initialization marker.
        repo = site_repository(tmp_path)
        configure(library, seam / "kinbase", repo)
    return request.param


def unknown_badges(page, reason):
    text = page.locator("body").inner_text()
    assert re.search(r"direction|standard", text, re.I), "Standards/direction status is absent"
    notices = visible(page.get_by_text(re.compile(r"Kinbase unavailable", re.I)))
    assert notices, "Unavailable Kinbase needs an explicit reason, not an invented standard"
    for notice in notices:
        # Text may be nested in a badge with its status in a sibling span.
        value = notice.inner_text()
        if "unknown" not in value.lower():
            value = notice.locator("..").inner_text()
        assert re.search(r"unknown\s*\(\s*Kinbase unavailable:\s*[^)\s][^)]*\)", value, re.I), value
        if reason.startswith("uninitialized"):
            assert re.search(r"initiali[sz]|repository|repo|fsck", value, re.I), value
        else:
            assert re.search(r"binary|executable|not found|no such file|missing", value, re.I), value
    # Catch a second badge claiming current/conflict while another correctly says
    # unknown. Restrict this to compact status lines, not explanatory prose.
    for line in text.splitlines():
        if re.search(r"^(?:direction|standards?)\s*[:–—-]?\s*(?:current|conflict)\b", line.strip(), re.I):
            pytest.fail("Unavailable Kinbase invented a badge: " + line)


def test_unavailable_kinbase_keeps_preview_ingest_generate_and_export_working(library, language, fixture_site, tmp_path, page, unavailable):
    output = tmp_path / "preview"
    library.cli("build-preview", "tidal", "--out", output, cwd=library.project)
    page.goto((output / "index.html").as_uri())
    assert page.locator("[data-kd-construct]").count() > 0
    for adapter in ("generic", "dtcg-tailwind"):
        exported = tmp_path / adapter
        library.cli("export", "tidal", "--adapter", adapter, "--out", exported, cwd=library.project)
        assert (exported / ("roles.css" if adapter == "generic" else "theme.css")).is_file()
    artifact, _, captured = capture(library, [fixture_site.url + "/editorial/index.html"])
    assert not captured["problems"]
    _, document, _ = draft(library, [artifact], "unconnected-capture")
    assert document["id"] == "unconnected-capture"
    session, root, _ = start(library)
    settled = library.json("generate", "settled", session, cwd=library.project)
    assert "hue-family" in settled["unsettled"] and "hue-family" not in settled["settled"], \
        "An unavailable repository cannot supply a fixed design fact"
    offered = pair(library, session, root)
    assert not offered.get("done")
    _, generated, _ = derive(library, session, "unconnected-generated")
    assert generated["id"] == "unconnected-generated"
    with workbench(library) as server:
        for path in ("/", "/languages/tidal"):
            page.goto(server + path)
            unknown_badges(page, unavailable)


def test_feedback_without_kinbase_is_recorded_locally_and_never_changes_validation(library, language, page, unavailable, tmp_path):
    before = library.path().read_bytes()
    validation = library.json("validate", "tidal", cwd=library.project)
    feedback = library.workspace / "feedback.jsonl"
    previous = feedback.read_bytes() if feedback.exists() else b""
    comment = "Independent feedback: consider a larger card title, without treating this as a decision."
    reference = "tidal@" + expected_hash(language)
    with workbench(library) as server:
        page.goto(server + "/languages/tidal")
        unknown_badges(page, unavailable)
        comments = visible(page.get_by_role("textbox", name=re.compile(r"feedback|comment|message|observation", re.I)))
        if not comments:
            comments = visible(page.locator("textarea"))
        assert comments, "Viewer has no no-JS feedback field"
        control = comments[0]
        form = control.locator("xpath=ancestor::form[1]")
        assert form.count()
        control.fill(comment)
        authors = visible(form.get_by_role("textbox", name=re.compile(r"author|your name|^name$", re.I)))
        for author in authors:
            author.fill("Independent Fixture Reviewer")
        target_chosen = False
        for select in visible(form.locator("select")):
            options = select.locator("option").evaluate_all("els => els.map(e => e.value)")
            if "card" in options:
                select.select_option("card")
                target_chosen = True
        for target in visible(form.get_by_role("textbox", name=re.compile(r"construct", re.I))):
            target.fill("card")
            target_chosen = True
        submit(page, form)
        assert "not sent (kinbase unavailable)" in page.locator("body").inner_text().lower()
    updated = feedback.read_bytes()
    assert updated.startswith(previous)
    records = [json.loads(line) for line in updated[len(previous):].splitlines() if line.strip()]
    assert len(records) == 1
    record = records[0]
    assert record["text"] == comment and record["author"] and record["ts"]
    if authors:
        assert record["author"] == "Independent Fixture Reviewer"
    assert record["target"].startswith(reference + "#") and record["target"] != reference + "#"
    if target_chosen:
        assert record["target"] == reference + "#card"
    assert library.path().read_bytes() == before, "Feedback silently edited the language"
    assert library.json("validate", "tidal", cwd=library.project) == validation, "Unsent feedback changed a validation outcome"

    assert not [call for call in calls(tmp_path / "kinbase-seam") if call["executable"] == "kin"], \
        "Feedback was submitted while Kinbase was unavailable"
    if unavailable.startswith("uninitialized"):
        assert_read_calls(tmp_path / "kinbase-seam", tmp_path / "independent-target",
                          {"fixture.standard", "fixture.direction"}, required_keys=())
