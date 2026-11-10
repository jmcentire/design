"""Durable feedback precedes generation; archived states never steer live output.

Oracles are authored presentation values, canonical hashes and repeated public
outputs. No production implementation, model calls or historical-output oracle.
"""

import copy
import hashlib
import json
import re
import shutil
from urllib.parse import urlencode

import kinbase_design
import pytest
import rfc8785

from tests.content_browser_support import loaded_images
from tests.content_support import content_library, render_result, write_content
from tests.m1_support import slot_properties, token
from tests.support import LibraryCase, ROOT, pointer_value, request
from tests.test_m2_capture import tree_hashes
from tests.test_versions_assets import expected_hash, mint


def presentation_hashes(output):
    return {name: digest for name, digest in tree_hashes(output).items()
            if name.endswith((".html", ".css")) or name.startswith(("assets/", "content-assets/"))}


@pytest.mark.browser
def test_revision_is_current_before_three_identical_content_renders(content_library, tmp_path, page):
    document = content_library.read("harbor")
    title = slot_properties(document, "hero", "title")
    title.pop("letter-spacing", None)  # Feedback must also add a valid property leaf.
    token(document, "feedback", "tracking", "dimension", "1px")
    title["color"] = token(document, "feedback", "tone", "color", "#123456")
    slot_properties(document, "hero", "body")["line-height"] = token(
        document, "feedback", "leading", "number", 1.5)
    document["components"]["hero"]["properties"]["gap"] = token(
        document, "space", "feedback-spacing", "dimension", "16px")
    content_library.write(document)
    content_library.validate("harbor")
    before = expected_hash(document)
    changes = {"/style/feedback/tracking/$value": "2px",
               "/components/hero/slots/title/properties/letter-spacing": "{feedback.tracking}",
               "/style/feedback/tone/$value": "#345678",
               "/style/feedback/leading/$value": 1.75,
               "/style/space/feedback-spacing/$value": "24px"}
    expected = copy.deepcopy(document)
    for pointer, value in changes.items():
        parent, key = pointer.rsplit("/", 1)
        pointer_value(expected, parent)[key] = value
    version = expected_hash(expected)
    source, _ = write_content(tmp_path / "content")
    blocked = tmp_path / "occupied-output"
    blocked.write_text("This existing file cannot be a render directory.")
    receipt = content_library.json("revise-language", "harbor", "--changes", json.dumps(changes),
        "--reason", "Increase tracking, leading and spacing; cool the text tone", "--expected-version", before,
        "--out", blocked, "--content", source, code=1)
    assert receipt["changed"] is True and receipt["previous"] == before
    assert receipt["version"] == version and receipt["ref"] == "harbor@" + version
    assert receipt["revision"] is not None
    assert receipt["rendered"]["built"] is False and receipt["rendered"]["error"].strip()
    assert blocked.is_file()
    # Generation failed, but the accepted feedback is already durable. A
    # render-first/backfill-on-success implementation loses this update.
    assert content_library.read("harbor") == expected
    assert content_library.json("resolve", "harbor", "hero.title")["properties"]["letter-spacing"]["value"] == "2px"
    current = content_library.path("harbor").read_bytes()
    history = content_library.json("language-history", "harbor")
    vocabulary = content_library.library / "vocabulary" / expected["vocabulary"]
    declared = {key: hashlib.sha256(rfc8785.dumps(json.loads((vocabulary / filename).read_text()))).hexdigest()
                for key, filename in (("vocabulary", "vocabulary.json"), ("samples", "samples.json"))}
    code = hashlib.sha256()
    package = ROOT / "kinbase_design"
    for path in sorted(p for p in package.rglob("*") if p.is_file() and p.suffix in {".py", ".css", ".html"}):
        code.update(path.relative_to(package).as_posix().encode() + b"\0" + hashlib.sha256(path.read_bytes()).digest())
    bundles, pictures, identities = [], [], []
    for iteration in range(3):
        output = tmp_path / f"render-{iteration}"
        result = render_result(content_library, source, output, "harbor")
        assert result["version"] == version
        bundles.append(presentation_hashes(output))
        inputs = result["render_inputs"]
        assert inputs["language"] == version
        assert all(inputs[key] == value for key, value in declared.items())
        assert inputs["renderer"] == {"name": "Kinbase Design", "version": kinbase_design.__version__, "code": code.hexdigest()}
        assert inputs["assets"] == {name: digest for name, digest in bundles[-1].items()
                                     if name.startswith(("assets/", "content-assets/"))}
        assert re.fullmatch(r"[0-9a-f]{64}", inputs["content"])
        identities.append(inputs)
        frames = []
        for width in (375, 1280):
            page.set_viewport_size({"width": width, "height": 900})
            page.goto((output / "index.html").as_uri())
            loaded_images(page)
            title = page.locator('[data-kd-slot="hero.title"]')
            assert title.evaluate("e=>[getComputedStyle(e).letterSpacing,getComputedStyle(e).color]") == ["2px", "rgb(52, 86, 120)"]
            body = page.locator('[data-kd-slot="hero.body"]').evaluate(
                "e=>[parseFloat(getComputedStyle(e).fontSize),parseFloat(getComputedStyle(e).lineHeight)]")
            assert body[1] == pytest.approx(body[0] * 1.75)
            assert page.locator('[data-kd-construct="hero"]').evaluate("e=>getComputedStyle(e).gap") == "24px"
            frames.append(page.screenshot(full_page=True))
        pictures.append(frames)
        assert content_library.path("harbor").read_bytes() == current
        assert content_library.json("language-history", "harbor") == history
    assert bundles[0] == bundles[1] == bundles[2]
    assert pictures[0] == pictures[1] == pictures[2]
    assert identities[0] == identities[1] == identities[2]


def test_workbench_revision_ignores_archives_until_explicit_restore(app, content_library, tmp_path):
    original = content_library.read("harbor")
    slot_properties(original, "hero", "eyebrow")
    content_library.write(original)
    before = expected_hash(original)
    archived = mint(content_library, original)
    immutable = archived.read_bytes()
    source, _ = write_content(tmp_path / "content")
    first = render_result(content_library, source, tmp_path / "original", "harbor")
    version = before
    for share_with, color in (("title", "#345678"), ("eyebrow", "#456789"), (None, "#234567")):
        response = request(app, "/languages/harbor/revise", "POST", urlencode({
            "scope": "hero.body", "property": "color", "value": color,
            "reason": "Refine the body tone", "expected_version": version}).encode(), "application/x-www-form-urlencoded")
        assert response["status"] in (200, 302, 303), response
        current = content_library.read("harbor")
        version = expected_hash(current)
        if share_with:
            reference = current["components"]["hero"]["slots"]["body"]["properties"]["color"]
            shared = content_library.json("revise-language", "harbor", "--changes", json.dumps({
                f"/components/hero/slots/{share_with}/properties/color": reference}),
                "--reason", "Share the accepted tone", "--expected-version", version)
            version = shared["version"]
    current = content_library.read("harbor")
    after = expected_hash(current)
    assert after != before
    for slot, color in (("title", "#345678"), ("eyebrow", "#456789"), ("body", "#234567")):
        assert content_library.json("resolve", "harbor", "hero." + slot)["properties"]["color"]["value"] == color
    history = content_library.json("language-history", "harbor")
    assert history["current"] == after
    revisions = history["revisions"]
    assert len(revisions) == 5
    assert revisions[0]["before"] == before and revisions[-1]["after"] == after
    assert all(a["after"] == b["before"] and a["sequence"] < b["sequence"]
               for a, b in zip(revisions, revisions[1:]))
    explicit = request(app, "/languages/harbor/history")
    assert explicit["status"] == 200 and before.encode() in explicit["body"]
    changed = render_result(content_library, source, tmp_path / "current", "harbor")
    # Reuse the portable-library pattern: no archive, feedback or private session
    # data is available to this fresh CLI invocation, only the current inputs.
    clean = LibraryCase(content_library.project, tmp_path / "current-only", tmp_path / "empty-workspace")
    clean.workspace.mkdir()
    shutil.copytree(content_library.library / "vocabulary" / current["vocabulary"],
                    clean.library / "vocabulary" / current["vocabulary"])
    clean.write(current)
    shutil.copytree(content_library.path("harbor").parent / "assets", clean.path("harbor").parent / "assets")
    isolated = render_result(clean, source, tmp_path / "isolated", "harbor")
    assert presentation_hashes(tmp_path / "current") == presentation_hashes(tmp_path / "isolated")
    assert changed["render_inputs"] == isolated["render_inputs"]
    restored = content_library.json("restore-language", "harbor", before, "--reason", "The earlier tone was better",
                                   "--expected-version", after)
    assert restored["changed"] is True and restored["previous"] == after
    assert restored["version"] == before and restored["ref"] == "harbor@" + before
    assert content_library.read("harbor") == original
    final = render_result(content_library, source, tmp_path / "restored", "harbor")
    assert presentation_hashes(tmp_path / "original") == presentation_hashes(tmp_path / "restored")
    assert first["render_inputs"] == final["render_inputs"]
    assert first["render_inputs"]["content"] == changed["render_inputs"]["content"]
    history = content_library.json("language-history", "harbor")
    assert len(history["revisions"]) == 6 and history["revisions"][:-1] == revisions
    assert history["revisions"][-1]["sequence"] > revisions[-1]["sequence"]
    assert history["revisions"][-1]["restored_from"] == before
    noop = content_library.json("restore-language", "harbor", before, "--reason", "Keep the current tone",
                               "--expected-version", before)
    assert noop["changed"] is False and noop["revision"] is None
    assert content_library.json("language-history", "harbor") == history
    assert archived.read_bytes() == immutable


@pytest.mark.parametrize("failure", ["invalid-value", "stale-version"])
def test_rejected_revision_leaves_current_and_history_unchanged(library, language, tmp_path, failure):
    before = tree_hashes(library.path().parent)
    history = library.json("language-history", "tidal")
    changes = {"/style/color/ink/$value": "not-a-color" if failure == "invalid-value" else "#345678"}
    version = expected_hash(language) if failure == "invalid-value" else "0" * 64
    output = tmp_path / "rejected-generation"
    result = library.cli("revise-language", "tidal", "--changes", json.dumps(changes),
        "--reason", "Independent rejected feedback", "--expected-version", version, "--out", output, code=(1, 2))
    assert result.stdout.strip() or result.stderr.strip()
    assert "Traceback" not in result.stderr
    assert tree_hashes(library.path().parent) == before
    assert library.json("language-history", "tidal") == history
    assert not (output / "index.html").exists()
