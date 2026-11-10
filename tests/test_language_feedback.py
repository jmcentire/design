"""Natural feedback crosses the configured process boundary before durable edits.

The recorder substitutes only the external model. Interpretation quality is not
claimed here: actual requests, canonical updates and subsequent renders are real.
"""

import copy
import json
import shlex
import sys
from urllib.parse import urlencode

import pytest

from tests.content_browser_support import loaded_images
from tests.support import request
from tests.test_language_revision import presentation_hashes
from tests.test_m2_capture import tree_hashes
from tests.test_versions_assets import expected_hash, mint


def model_command(library, tmp_path, monkeypatch, response):
    calls = tmp_path / "model-calls.jsonl"
    executable = tmp_path / "model recorder.py"
    executable.write_text("import json,sys\nfrom pathlib import Path\n"
        f"with Path({str(calls)!r}).open('a') as record:\n"
        "    record.write(json.dumps(json.load(sys.stdin))+'\\n')\n"
        f"json.dump({response!r},sys.stdout)\n")
    command = shlex.join([sys.executable, str(executable)])
    library.command_env["KINBASE_DESIGN_LLM_COMMAND"] = command
    monkeypatch.setenv("KINBASE_DESIGN_LLM_COMMAND", command)
    return calls


@pytest.mark.browser
def test_workbench_text_feedback_updates_current_then_renders_without_reinterpreting(library, language, tmp_path, monkeypatch, page):
    old = copy.deepcopy(language)
    old["style"]["archiveonly"] = {"$type": "color", "old": {"$value": "#0a0b0c"}}
    library.write(old)
    mint(library, old)
    library.write(language)
    before = expected_hash(language)
    feedback = "Make the text a cooler #345678 and use a more open line height of 1.75."
    changes = {"/style/color/ink/$value": "#345678", "/style/type/leading/$value": 1.75}
    calls = model_command(library, tmp_path, monkeypatch,
        {"changes": changes, "questions": [], "summary": "Cool the text and open the leading."})
    # Construct the normal public app after configuring its external boundary.
    from kinbase_design.workbench import create_app
    app = create_app(library.library, library.workspace)
    response = request(app, "/languages/tidal/feedback-language", "POST", urlencode({
        "feedback": feedback, "expected_version": before}).encode(), "application/x-www-form-urlencoded")
    assert response["status"] in (200, 302, 303), response
    expected = copy.deepcopy(language)
    expected["style"]["color"]["ink"]["$value"] = "#345678"
    expected["style"]["type"]["leading"]["$value"] = 1.75
    assert library.read() == expected
    prompts = [json.loads(line) for line in calls.read_text().splitlines()]
    assert len(prompts) == 1
    assert prompts[0]["task"] == "revise-language" and prompts[0]["feedback"] == feedback
    assert prompts[0]["version"] == before and prompts[0]["language"]["style"] == language["style"]
    assert "archiveonly" not in json.dumps(prompts[0])
    recorded, current = calls.read_bytes(), library.path().read_bytes()
    history = library.json("language-history", "tidal")
    assert history["current"] == expected_hash(expected)
    bundles, frames = [], []
    page.set_viewport_size({"width": 375, "height": 900})
    for iteration in range(3):
        output = library.build(tmp_path / f"repeat-{iteration}")
        bundles.append(presentation_hashes(output))
        page.goto((output / "index.html").as_uri())
        loaded_images(page)
        assert page.locator('[data-kd-slot="listing-card.price"]').first.evaluate(
            "e=>[getComputedStyle(e).color,getComputedStyle(e).lineHeight]") == ["rgb(52, 86, 120)", "28px"]
        frames.append(page.screenshot(full_page=True))
        assert calls.read_bytes() == recorded and library.path().read_bytes() == current
        assert library.json("language-history", "tidal") == history
    assert bundles[0] == bundles[1] == bundles[2]
    assert frames[0] == frames[1] == frames[2]


@pytest.mark.parametrize("outcome", ["clarification", "unavailable"])
def test_uncertain_or_unavailable_interpretation_never_mutates_current(library, language, tmp_path, monkeypatch, outcome):
    if outcome == "clarification":
        model_command(library, tmp_path, monkeypatch, {
            "changes": {"/style/color/ink/$value": "#654321"},
            "questions": ["Which text should change, and to which value?"],
            "summary": "The request needs a target and value."})
    else:
        library.command_env["KINBASE_DESIGN_LLM_COMMAND"] = ""
        monkeypatch.delenv("KINBASE_DESIGN_LLM_COMMAND", raising=False)
    original = tree_hashes(library.path().parent)
    history = library.json("language-history", "tidal")
    output = tmp_path / "not-generated"
    result = library.json("feedback-language", "tidal", "--feedback", "Change that one to the other value.",
        "--expected-version", expected_hash(language), "--out", output, code=1, cwd=library.project)
    assert result["status"] == outcome and result["changed"] is False
    if outcome == "clarification":
        assert result["summary"].strip()
        assert result["questions"] == ["Which text should change, and to which value?"]
    else:
        assert result["error"].strip()
    assert tree_hashes(library.path().parent) == original
    assert library.json("language-history", "tidal") == history
    assert not (output / "index.html").exists()
