"""M3 B6/B8: fixed supplied originals, early stopping and accepted derivation.

The pale source palette has insufficient internal text contrast by independent
WCAG arithmetic. A readable result must supply other values without changing
these sources. Falsifiers: recolored source tokens, rewritten logo/font bytes,
unused supplied assets, incomplete provenance, invalid or unreadable drafts.
"""

import hashlib
import json
import shutil

import pytest
from PIL import Image, ImageDraw

from tests.m1_support import contrast_ratio, run_check
from tests.m2_support import (assert_provenance, assert_shared_privacy, assert_valid_draft,
                              provenance_at, read_json, token_values)
from tests.m3_support import BEACH, choose, generate, log_records, pair, start
from tests.support import FIXTURES, LibraryCase
from tests.test_m2_capture import tree_hashes
from tests.test_versions_assets import expected_hash, make_font

pytestmark = [pytest.mark.browser, pytest.mark.browser_timeout(600)]


def supplied_sources(library, directory):
    directory.mkdir()
    logo = directory / "logo.png"
    with Image.new("RGB", (64, 32), "#10364f") as picture:
        painter = ImageDraw.Draw(picture)
        painter.polygon([(4, 24), (20, 6), (32, 21), (44, 11), (60, 24)], fill="#ffffff")
        picture.save(logo)
    font = directory / "fixture.ttf"
    make_font(font)
    palette = directory / "palette.json"
    shutil.copyfile(FIXTURES / "generate-palette.json", palette)
    files = {"logo": logo, "font": font, "palette": palette}
    records = {}
    for kind, file in files.items():
        data = file.read_bytes()
        artifact = library.json("import-artifact", "--file", file,
                                "--kind", "dtcg" if kind == "palette" else "asset")["artifact"]
        records[kind] = {"artifact": artifact, "bytes": data, "hash": hashlib.sha256(data).hexdigest()}
    return records


def source_palette(document, provenance, source):
    expected = [value for _, kind, value in token_values(json.loads(source["bytes"])) if kind == "color"]
    for value in expected:
        matches = [name for name, kind, observed in token_values(document["style"])
                   if kind == "color" and observed == value]
        assert matches, ("Supplied color changed or disappeared", value)
        records = [provenance_at(provenance, "/style/" + name.replace(".", "/") + "/$value") for name in matches]
        assert any(record["kind"] == "source" and record["artifact"] == source["artifact"] for record in records)


def source_assets(root, document, sources):
    for kind in ("logo", "font"):
        source = sources[kind]
        matching = []
        for identity, asset in document["assets"].items():
            if asset["kind"] != kind:
                continue
            for variant, details in asset["variants"].items():
                if details["file"] == "sha256/" + source["hash"]:
                    assert (root / "assets" / details["file"]).read_bytes() == source["bytes"]
                    matching.append((identity, variant))
        assert matching, ("Supplied asset was not promoted unchanged", kind)
        if kind == "logo":
            bindings = [binding for treatment in document["components"].values()
                        for binding in treatment.get("assets", {}).values()]
            assert any(f"{identity}:{variant}" in bindings for identity, variant in matching)
        else:
            # A packaged but unbound font is not use of the supplied constraint.
            tokens = []
            for name, token_kind, _ in token_values(document["style"]):
                if token_kind != "fontFamily":
                    continue
                node = document["style"]
                for segment in name.split("."):
                    node = node[segment]
                if node.get("$extensions", {}).get("kinbase-design", {}).get("asset") in {item[0] for item in matching}:
                    tokens.append("{" + name + "}")
            assert tokens
            # The use can be inherited through aliases, roles or component
            # treatments; the browser below verifies actual rendered family use.


def derive(library, session, identity):
    summary = generate(library, "derive", session, "--language", identity, timeout=180)
    root = library.workspace / "drafts" / identity
    document, provenance = read_json(root / "working.json"), read_json(root / "provenance.json")
    assert summary["draft"] == identity
    assert document["id"] == identity
    assert_valid_draft(library, document, root)
    assert_provenance(document, provenance)
    return root, document, provenance


def check_draft(library, root, document, out):
    # Exercise the public checker independently of derive's acceptance claim,
    # before save. Assets and working.json are copied as delivered, never repaired.
    destination = library.project / "generate-check" / document["id"]
    shutil.copytree(library.library / "vocabulary", destination / "vocabulary")
    case = LibraryCase(library.project, destination, library.workspace)
    case.write(document)
    if (root / "assets").is_dir():
        shutil.copytree(root / "assets", case.path(document["id"]).parent / "assets")
    run_check(case, out, document["id"], widths=(320, 768, 1280), accepted=True)
    return case


@pytest.mark.parametrize("rounds", [0, 1])
def test_supplied_constraints_survive_early_derive_repair_and_save(library, tmp_path, page, rounds):
    sources = supplied_sources(library, tmp_path / "private-supplied")
    colors = [value for _, _, value in token_values(json.loads(sources["palette"]["bytes"]))]
    assert all(contrast_ratio(a, b) < 3 for a in colors for b in colors)
    immutable = {kind: tree_hashes(library.workspace / "artifacts" / source["artifact"])
                 for kind, source in sources.items()}
    session, session_root, _ = start(library, BEACH, [source["artifact"] for source in sources.values()])
    if rounds:
        offered = pair(library, session, session_root)
        assert not offered.get("done")
        decision = choose(library, session, session_root, offered, "A", comment="Stop after this comparison")
    else:
        decision = None
    identity = "supplied-early-" + str(rounds)
    # Removing external originals forces use of immutable imported artifacts.
    shutil.rmtree(tmp_path / "private-supplied")
    root, document, provenance = derive(library, session, identity)
    source_palette(document, provenance, sources["palette"])
    source_assets(root, document, sources)
    if decision:
        assert any(record["kind"] == "chosen" and record["choice"] == decision["id"]
                   for record in provenance.values()), "Derived values lost the user's choice"
    effective = {entry["id"] for entry in log_records(session_root)}
    assert all(record["choice"] in effective for record in provenance.values() if record["kind"] == "chosen")
    case = check_draft(library, root, document, tmp_path / "derived-check")
    preview = case.build(tmp_path / "derived-preview", identity)
    page.goto((preview / "index.html").as_uri())
    page.wait_for_function("document.fonts.status === 'loaded'", timeout=5000)
    assert page.evaluate("document.fonts.check('16px \"Fixture Sans\"')")
    assert page.locator("[data-kd-slot]").evaluate_all("""els => els.some(e =>
      e.textContent.trim() && getComputedStyle(e).fontFamily.includes('Fixture Sans'))""")
    logo = page.locator('[data-kd-slot="nav.logo"] img, img[data-kd-slot="nav.logo"]').first
    assert logo.is_visible()
    assert logo.evaluate("e => e.complete && e.naturalWidth > 0 && e.getBoundingClientRect().width > 0 && e.getBoundingClientRect().height > 0")
    library.cli("save-draft", identity, cwd=library.project, timeout=90)
    saved = library.read(identity)
    assert saved == document
    shared = read_json(library.path(identity).parent / "provenance" / (expected_hash(saved) + ".json"))
    assert_provenance(saved, shared, shared=True)
    source_palette(saved, shared, sources["palette"])
    source_assets(library.path(identity).parent, saved, sources)
    assert_shared_privacy(library)
    for kind, source in sources.items():
        assert tree_hashes(library.workspace / "artifacts" / source["artifact"]) == immutable[kind]
