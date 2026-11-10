"""M2 imports/B8: exact source bytes and values, honest provenance, usable originals.

Falsifiers: mutate a token while importing, relabel it inferred, reference a live
export directory instead of copying it, or retain private source paths when saving.
"""

import hashlib
import json
import shutil

import pytest

from tests.m2_support import (assert_provenance, assert_shared_privacy, draft, provenance_at,
                              read_json, scalar_leaves, token_values)
from tests.support import FIXTURES, pointer_value
from tests.test_m2_capture import tree_hashes
from tests.test_versions_assets import expected_hash, make_font


@pytest.mark.parametrize("kind", ["image", "mock", "wireframe", "asset", "brief", "dtcg"])
def test_import_kind_copies_an_immutable_original(library, tmp_path, kind):
    if kind == "dtcg":
        data, suffix = (FIXTURES / "ingest-tokens.json").read_bytes(), ".json"
    elif kind == "brief":
        data, suffix = b"A warm reading room; retain this original verbatim.\n", ".txt"
    else:
        data, suffix = (FIXTURES / "mark.svg").read_bytes(), ".svg"
    original = tmp_path / ("source" + suffix)
    original.write_bytes(data)
    artifact = library.json("import-artifact", "--file", original, "--kind", kind)["artifact"]
    root = library.workspace / "artifacts" / artifact
    assert root.resolve().is_relative_to(library.workspace.resolve())
    assert any(p.read_bytes() == data for p in root.rglob("*") if p.is_file())
    immutable = tree_hashes(root)
    original.write_bytes(b"changed after import")
    assert tree_hashes(root) == immutable


def assert_source_tokens(library, document, provenance, expected):
    for name, _, value in token_values(expected):
        pointer = "/style/" + "/".join(name.split(".")) + "/$value"
        assert pointer_value(document, pointer) == value, (name, value)
        for leaf, _ in scalar_leaves(value, pointer):
            record = provenance_at(provenance, leaf)
            assert record["kind"] == "source", record
            source = library.workspace / "artifacts" / record["artifact"]
            assert source.resolve().is_relative_to(library.workspace.resolve()) and source.is_dir()
            matches = []
            for path in source.rglob("*"):
                if path.is_file():
                    try:
                        matches.append(json.loads(path.read_bytes()) == expected)
                    except (ValueError, UnicodeDecodeError):
                        pass
            assert any(matches), ("Source provenance does not point to the imported tokens", record)


@pytest.mark.browser
@pytest.mark.browser_timeout(240)
@pytest.mark.parametrize("missing_browser", [False, True], ids=["browser-available", "browser-unavailable"])
def test_dtcg_values_and_source_provenance_survive_draft_and_save(library, tmp_path, ingest_config, missing_browser):
    source = tmp_path / "private-original.json"
    shutil.copyfile(FIXTURES / "ingest-tokens.json", source)
    expected = read_json(source)
    artifact = library.json("import-artifact", "--file", source, "--kind", "dtcg")["artifact"]
    artifact_root = library.workspace / "artifacts" / artifact
    immutable = tree_hashes(artifact_root)
    source.unlink()
    if missing_browser:
        # P3 unavailable-preview contract: imported data still yields a valid
        # draft, but unverified visual choices cannot be advertised as usable.
        # Force the real Playwright boundary; do not replace the browser code.
        empty_installation = tmp_path / "empty-playwright-installation"
        empty_installation.mkdir()
        library.command_env["PLAYWRIGHT_BROWSERS_PATH"] = str(empty_installation)
    root, document, summary = draft(library, [artifact], "from-tokens")
    if missing_browser:
        assert summary["questions"] == 0 and summary["question_items"] == []
        assert library.json("questions", "from-tokens", cwd=library.project) == []
        evidence = [f for f in summary["findings"] if f["rule"] == "ingest-question-preview"]
        assert evidence and all(f["type"] == "coverage" and f["observed"] and f["message"] for f in evidence)
        assert read_json(root / "questions.json"), "Private question evidence must survive unavailable verification"
    provenance = read_json(root / "provenance.json")
    assert_provenance(document, provenance)
    assert_source_tokens(library, document, provenance, expected)
    library.cli("save-draft", "from-tokens", cwd=library.project, timeout=90)
    saved = library.read("from-tokens")
    assert saved == document
    shared = read_json(library.path("from-tokens").parent / "provenance" / (expected_hash(saved) + ".json"))
    assert_provenance(saved, shared, shared=True)
    assert_source_tokens(library, saved, shared, expected)
    assert_shared_privacy(library)
    assert tree_hashes(artifact_root) == immutable


@pytest.mark.browser
@pytest.mark.browser_timeout(240)
def test_figma_export_variables_images_and_fonts_are_usable_originals(library, language, tmp_path, ingest_config):
    source = tmp_path / "private-figma-export"
    source.mkdir()
    shutil.copyfile(FIXTURES / "ingest-tokens.json", source / "variables.json")
    shutil.copyfile(FIXTURES / "mark.svg", source / "logo.svg")
    make_font(source / "font.ttf")
    originals = {p.name: p.read_bytes() for p in source.iterdir()}
    artifact = library.json("import-artifact", "--file", source, "--kind", "figma-export")["artifact"]
    artifact_root = library.workspace / "artifacts" / artifact
    files = [p for p in artifact_root.rglob("*") if p.is_file()]
    for name, data in originals.items():
        assert any(p.read_bytes() == data for p in files), name
    immutable = tree_hashes(artifact_root)
    shutil.rmtree(source)
    root, document, _ = draft(library, [artifact], "from-figma")
    expected = json.loads(originals["variables.json"])
    provenance = read_json(root / "provenance.json")
    assert_provenance(document, provenance)
    assert_source_tokens(library, document, provenance, expected)
    # The existing import/promote boundary makes retained originals usable even
    # after the external export folder is gone; no private importer is invoked.
    for filename, asset_id, kind, options in (
        ("logo.svg", "figma-logo", "logo", []),
        ("font.ttf", "figma-font", "font", ["--family", "Fixture Sans", "--weight", "400", "--style", "normal"]),
    ):
        data = originals[filename]
        original = next(p for p in files if p.read_bytes() == data)
        single = library.json("import-artifact", "--file", original, "--kind", "asset")["artifact"]
        library.cli("promote", "tidal", "--artifact", single, "--asset-id", asset_id,
                    "--kind", kind, "--variant", "primary", *options)
        digest = hashlib.sha256(data).hexdigest()
        assert (library.path().parent / "assets" / "sha256" / digest).read_bytes() == data
    assert tree_hashes(artifact_root) == immutable
