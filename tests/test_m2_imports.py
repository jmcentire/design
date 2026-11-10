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
from tests.test_composition_binding_gutter import heading_gaps
from tests.test_composition_shipped import composition_report
from tests.test_m2_fidelity_content import assert_title_prominence


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


@pytest.mark.browser
@pytest.mark.browser_timeout(240)
def test_token_only_draft_defaults_bind_headings_and_inset_card_text(library, tmp_path, ingest_config, page):
    # Amendments 09/11: even without captured DOM or manual choices, the saved
    # defaults must satisfy the published 8px inset and after < before rules.
    expected = read_json(FIXTURES / "ingest-tokens.json")
    # Imported names are arbitrary source data, including names an inference
    # might otherwise generate; deriving spacing must not overwrite this value.
    expected["space"]["flow-binding-hero-base"] = {"$value": "53px"}
    source = tmp_path / "tokens.json"
    source.write_text(json.dumps(expected))
    artifact = library.json("import-artifact", "--file", source,
                            "--kind", "dtcg")["artifact"]
    root, document, _ = draft(library, [artifact], "token-defaults")
    assert_source_tokens(library, document, read_json(root / "provenance.json"), expected)
    library.cli("save-draft", document["id"], cwd=library.project)
    assert library.read(document["id"]) == document
    site = library.build(tmp_path / "token-preview", document["id"])
    measurements = []
    for width in (375, 1280):
        page.set_viewport_size({"width": width, "height": 900})
        page.goto((site / "index.html").as_uri())
        page.evaluate("document.fonts.ready")
        gaps = heading_gaps(page.locator('[data-kd-slot="hero.title"]'))
        cards = page.locator('[data-kd-construct="listing-card"]')
        assert cards.count() > 0
        insets = cards.evaluate_all("""cards => cards.flatMap(card => {
          const box=card.getBoundingClientRect(), style=getComputedStyle(card);
          const painted=style.backgroundColor!=='rgba(0, 0, 0, 0)' ||
            (parseFloat(style.borderLeftWidth)>0 && style.borderLeftStyle!=='none');
          return ['title','location','rating','price'].map(name => {
            const slot=card.querySelector('[data-kd-slot="listing-card.'+name+'"]');
            const range=document.createRange(); range.selectNodeContents(slot);
            const lines=[...range.getClientRects()].filter(r=>r.width && r.height);
            return {painted, left:Math.min(...lines.map(r=>r.left))-box.left,
                    right:box.right-Math.max(...lines.map(r=>r.right))};
          });
        })""")
        measurements.append({"width": width, "gaps": gaps, "insets": insets})
    report = composition_report(library, document["id"], tmp_path / "token-check", widths=(375, 1280))
    assert all(m["gaps"]["after"] < m["gaps"]["before"] for m in measurements), measurements
    assert all(i["painted"] and min(i["left"], i["right"]) >= 8
               for m in measurements for i in m["insets"]), measurements
    assert not [f for f in report["findings"] if f["rule"] in {"heading-binding", "text-inset"}
                and f["type"] in {"violation", "missing"}], report["findings"]


@pytest.mark.browser
@pytest.mark.browser_timeout(240)
def test_sparse_token_inspiration_has_hierarchy_fallback_and_honest_coverage(library, tmp_path, ingest_config, page):
    expected = read_json(FIXTURES / "ingest-tokens.json")
    del expected["size"]["title"]  # No source heading mapping: hierarchy must be inferred.
    expected["type"]["family"]["$value"] = ["Unavailable Fixture Typeface"]
    source = tmp_path / "sparse-tokens.json"
    source.write_text(json.dumps(expected))
    artifact = library.json("import-artifact", "--file", source, "--kind", "dtcg")["artifact"]
    root, document, summary = draft(library, [artifact], "sparse-inspiration")
    assert_source_tokens(library, document, read_json(root / "provenance.json"), expected)
    assert any(f["type"] == "coverage" and f["rule"] in {"ingest-assets", "ingest-media"}
               for f in summary["findings"]), summary
    fidelity = library.json("fidelity", document["id"], cwd=library.project)
    assert fidelity["pairs"] == [] and any(f["type"] == "coverage" for f in fidelity["findings"])
    library.cli("save-draft", document["id"], cwd=library.project)
    assert library.read(document["id"]) == document
    assert not any(asset["kind"] == "font" for asset in document["assets"].values())
    site = library.build(tmp_path / "sparse-preview", document["id"])
    for width in (375, 1280):
        page.set_viewport_size({"width": width, "height": 900})
        page.goto((site / "index.html").as_uri())
        page.evaluate("document.fonts.ready")
        title, body = (page.locator(f'[data-kd-slot="hero.{slot}"]') for slot in ("title", "body"))
        assert_title_prominence(title, body)
        family = body.evaluate("e=>getComputedStyle(e).fontFamily").split(",")[-1].strip().strip('"').lower()
        assert family in {"serif", "sans-serif", "monospace", "cursive", "fantasy", "system-ui",
                          "ui-serif", "ui-sans-serif", "ui-monospace", "ui-rounded"}, family
        assert not page.evaluate("document.documentElement.scrollWidth > innerWidth")
