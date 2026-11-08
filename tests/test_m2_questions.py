"""M2 B7/B8: missing design values become real choices, then private/shared provenance.

Falsifiers: unrendered candidate placeholders, choices that do not change the draft,
first-answer-wins bugs, absent provenance, or capture URLs leaking into a saved library.
"""

import hashlib
import json
from pathlib import Path

import pytest
from PIL import Image

from tests.m2_support import (assert_provenance, assert_shared_privacy, capture, draft,
                              png, provenance_at, read_json, scalar_leaves)
from tests.support import pointer_value
from tests.test_m2_capture import tree_hashes
from tests.test_versions_assets import expected_hash

pytestmark = [pytest.mark.browser, pytest.mark.browser_timeout(420)]


def preview_path(library, root, value):
    path = Path(value)
    # The public contract calls this a path in the workspace, without pinning a
    # relative base. Accept workspace-relative, draft-relative or absolute paths;
    # every supported interpretation must stay inside the workspace.
    possibilities = {path.resolve()} if path.is_absolute() else {
        (library.workspace / path).resolve(), (root / path).resolve()}
    matches = [p for p in possibilities if p.is_file() and p.is_relative_to(library.workspace.resolve())]
    assert len(matches) == 1, (value, matches)
    return matches[0]


def assert_rendered_questions(library, root, questions, vocabulary, page):
    assert questions and len({q["id"] for q in questions}) == len(questions)
    for question in questions:
        assert question["construct"] in vocabulary["constructs"]
        assert question["state"] in vocabulary["states"]
        assert question["pointer"].startswith("/")
        candidates = question["candidates"]
        assert 2 <= len(candidates) <= 4
        assert len({candidate["id"] for candidate in candidates}) == len(candidates)
        assert len({json.dumps(candidate["value"], sort_keys=True) for candidate in candidates}) >= 2
        appearances = set()
        for candidate in candidates:
            path = preview_path(library, root, candidate["preview"])
            if path.suffix.lower() in {".html", ".htm", ".svg"}:
                page.goto(path.as_uri())
                if path.suffix.lower() == ".svg":
                    visual = page.locator("svg").first
                else:
                    visual = page.locator(f'[data-kd-construct="{question["construct"]}"]').first
                assert visual.is_visible(), (question["id"], candidate["id"])
                state = visual.get_attribute("data-kd-state")
                if state is not None:
                    assert state == question["state"]
                data = visual.screenshot(timeout=5000, animations="disabled", caret="hide")
                from io import BytesIO
                picture = Image.open(BytesIO(data))
            else:
                picture = Image.open(path)
            with picture:
                assert picture.width > 0 and picture.height > 0
                picture.load()
                appearances.add(hashlib.sha256(picture.convert("RGBA").tobytes()).hexdigest())
        assert len(appearances) >= 2, "Visual candidates all render identically"


def test_missing_value_candidates_answer_supersession_and_private_save(
        library, fixture_site, ingest_config, vocabulary, page):
    url = fixture_site.url + "/missing/index.html"
    artifact, artifact_root, captured = capture(library, [url])
    immutable = tree_hashes(artifact_root)
    fixture_site.available = False
    request_count = len(fixture_site.requests)
    root, document, summary = draft(library, [artifact], "partial")
    initial_questions = library.json("questions", "partial", cwd=library.project)
    assert initial_questions and summary["questions"] == len(initial_questions)
    # Even before any answer, the sparse capture must produce a valid language
    # (checked by draft()) that can be reconstructed, rather than an invalid shell.
    library.cli("fidelity", "partial", cwd=library.project, timeout=90)
    fidelity = read_json(root / "fidelity" / "report.json")
    assert {(pair["page"], pair["width"]) for pair in fidelity["pairs"]} == {
        (entry["name"], int(width)) for entry in captured["pages"] for width in entry["widths"]}
    for pair in fidelity["pairs"]:
        for key in ("capture", "reconstruction"):
            path = root / "fidelity" / pair[key]
            assert path.resolve().is_relative_to(library.workspace.resolve())
            png(path)
    questions = library.json("questions", "partial", cwd=library.project)
    assert_rendered_questions(library, root, questions, vocabulary, page)
    provenance = read_json(root / "provenance.json")
    assert_provenance(document, provenance)
    assert artifact in json.dumps(provenance), "Workspace provenance lost its capture source"
    assert read_json(artifact_root / "capture.json")["pages"][0]["url"] == url
    question = questions[0]
    try:
        initial = pointer_value(document, question["pointer"])
    except (KeyError, IndexError):
        initial = object()  # An intentionally missing property need not exist yet.
    first = next(c for c in question["candidates"] if c["value"] != initial)
    second = next(c for c in question["candidates"] if c["value"] != first["value"])
    for candidate in (first, second):
        library.cli("answer", "partial", question["id"], candidate["id"], cwd=library.project, timeout=90)
        document = read_json(root / "working.json")
        assert pointer_value(document, question["pointer"]) == candidate["value"]
        provenance = read_json(root / "provenance.json")
        assert_provenance(document, provenance)
        for pointer, _ in scalar_leaves(candidate["value"], question["pointer"]):
            chosen = provenance_at(provenance, pointer)
            assert chosen["kind"] == "chosen" and chosen["choice"]
    library.cli("save-draft", "partial", cwd=library.project, timeout=90)
    saved = library.read("partial")
    assert saved == document
    assert pointer_value(saved, question["pointer"]) == second["value"]
    shared = read_json(library.path("partial").parent / "provenance" / (expected_hash(saved) + ".json"))
    assert_provenance(saved, shared, shared=True)
    for pointer, _ in scalar_leaves(second["value"], question["pointer"]):
        assert provenance_at(shared, pointer)["kind"] == "chosen"
    assert_shared_privacy(library)
    assert artifact in json.dumps(read_json(root / "provenance.json"))
    assert tree_hashes(artifact_root) == immutable
    assert len(fixture_site.requests) == request_count, "Answering or saving reread the live source"
