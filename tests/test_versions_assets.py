"""Normative: B16, M0 Versions and packages. Real CLI and persisted bytes.

Falsifiers: hash raw JSON/name, omit presentation/manifest from hash, overwrite a
minted version, move the original, re-encode assets, leak private paths, or ignore
missing font faces. No candidate-generated hash supplies the expected digest.
"""

import copy
import hashlib
import json

import pytest
import rfc8785

from tests.support import FIXTURES, assert_finding, package_asset

MEMBERS = ("vocabulary", "style", "roles", "layout", "components", "overrides", "behaviors", "assets")


def expected_hash(document):
    selected = {key: document.get(key, [] if key in {"overrides", "behaviors"} else {}) for key in MEMBERS}
    return hashlib.sha256(rfc8785.dumps(selected)).hexdigest()


def mint(library, document):
    digest = expected_hash(document)
    assert library.json("mint", document["id"]) == {"ref": f"{document['id']}@{digest}"}
    path = library.path(document["id"]).parent / "versions" / f"{digest}.json"
    assert path.is_file()
    return path


def test_mint_uses_canonical_presentation_and_retains_previous_version(library, language):
    first = mint(library, language)
    original_bytes = first.read_bytes()
    # Same semantic JSON with different whitespace/order must address the same version.
    library.path().write_text(json.dumps(language, sort_keys=True, separators=(",", ":")))
    assert mint(library, language) == first
    language["name"] = "A different display name"
    language["provenance"] = {"kind": "chosen", "artifact": "opaque-choice-2"}
    library.write(language)
    assert mint(library, language) == first
    language["style"]["color"]["ink"]["$value"] = "#010203"
    library.write(language)
    second = mint(library, language)
    assert second != first
    assert first.read_bytes() == original_bytes, "Minting later work mutated an immutable version"


def test_absent_optional_members_have_contract_hash_defaults(library, language):
    for key in ("overrides", "behaviors"):
        del language[key]
    library.write(language)
    mint(library, language)


def promote(library, source, asset_id="uploaded-logo", variant="primary"):
    artifact = library.json("import-artifact", "--file", source)["artifact"]
    result = library.json("promote", "tidal", "--artifact", artifact, "--asset-id", asset_id,
                          "--kind", "logo", "--variant", variant)
    return artifact, result


def assert_no_private_paths(library):
    """Inspect actual shared serialized data, not docs/source spellings or binary asset bytes."""
    forbidden = [str(library.workspace), str(library.project), str(library.workspace.parent)]
    for path in (library.library / "languages").rglob("*.json"):
        data = json.loads(path.read_text())

        def inspect(value):
            if isinstance(value, str):
                assert not value.startswith(("/", "file://")), (path, value)
                assert not any(private in value for private in forbidden), (path, value)
            elif isinstance(value, dict):
                for key, child in value.items():
                    inspect(key)
                    inspect(child)
            elif isinstance(value, list):
                for child in value:
                    inspect(child)

        inspect(data)


def test_promotion_copies_exact_bytes_retains_original_and_changes_version(library, language, tmp_path):
    data = (FIXTURES / "mark.svg").read_bytes()
    source = tmp_path / "private-logo.svg"
    source.write_bytes(data)
    first = mint(library, language)
    artifact, entry = promote(library, source)
    digest = hashlib.sha256(data).hexdigest()
    updated = library.read()
    variant = updated["assets"]["uploaded-logo"]["variants"]["primary"]
    assert variant["file"] == f"sha256/{digest}"
    assert variant["format"] == "svg"
    assert updated["assets"]["uploaded-logo"]["kind"] == "logo"
    assert entry["variants"]["primary"]["file"] == f"sha256/{digest}"
    packaged = library.path().parent / "assets" / "sha256" / digest
    assert packaged.read_bytes() == data
    artifact_dir = library.workspace / "artifacts" / artifact
    assert any(p.is_file() and p.read_bytes() == data for p in artifact_dir.rglob("*"))
    assert source.read_bytes() == data
    second = mint(library, updated)
    assert second != first
    previous_version = second.read_bytes()
    # Reimport changed bytes through the same public operations; old artifact/version remain intact.
    changed = data.replace(b"#123456", b"#224466")
    source.write_bytes(changed)
    promote(library, source)
    changed_digest = hashlib.sha256(changed).hexdigest()
    newest = library.read()
    assert newest["assets"]["uploaded-logo"]["variants"]["primary"]["file"] == f"sha256/{changed_digest}"
    assert (packaged.parent / changed_digest).read_bytes() == changed
    assert mint(library, newest) != second
    assert second.read_bytes() == previous_version
    assert any(p.is_file() and p.read_bytes() == data for p in artifact_dir.rglob("*"))
    assert_no_private_paths(library)


def make_font(path):
    """Tiny real TTF authored from geometric glyphs, no system font dependency or download."""
    from fontTools.fontBuilder import FontBuilder
    from fontTools.pens.ttGlyphPen import TTGlyphPen

    builder = FontBuilder(1000, isTTF=True)
    names = [".notdef", "space"] + [f"uni{n:04X}" for n in range(33, 127)]
    builder.setupGlyphOrder(names)
    builder.setupCharacterMap({32: "space", **{n: f"uni{n:04X}" for n in range(33, 127)}})
    glyphs = {}
    for name in names:
        pen = TTGlyphPen(None)
        if name != "space":
            pen.moveTo((80, 0))
            pen.lineTo((520, 0))
            pen.lineTo((520, 700))
            pen.lineTo((80, 700))
            pen.closePath()
        glyphs[name] = pen.glyph()
    builder.setupGlyf(glyphs)
    builder.setupHorizontalMetrics({name: (600, 0) for name in names})
    builder.setupHorizontalHeader(ascent=800, descent=-200)
    builder.setupNameTable({"familyName": "Fixture Sans", "styleName": "Regular",
                            "uniqueFontIdentifier": "IndependentFixtureSans-Regular",
                            "fullName": "Fixture Sans Regular", "psName": "FixtureSans-Regular"})
    builder.setupOS2(sTypoAscender=800, sTypoDescender=-200, usWinAscent=800, usWinDescent=200, usWeightClass=400)
    builder.setupPost()
    builder.setupMaxp()
    # Stable OpenType timestamps, so bytes do not depend on the current wall clock.
    builder.font["head"].created = builder.font["head"].modified = 3406620153
    builder.font.recalcTimestamp = False
    builder.save(path)


def bind_font(library, language, tmp_path):
    path = tmp_path / "fixture.ttf"
    make_font(path)
    package_asset(library, language, "fixture-font", "font", path.read_bytes(),
                  variant="regular", fmt="ttf", weight=400, style="normal")
    language["assets"]["fixture-font"]["meta"] = {"font": {"family": "Fixture Sans"}}
    language["style"]["type"]["family"] = {
        "$type": "fontFamily", "$value": "Fixture Sans",
        "$extensions": {"kinbase-design": {"asset": "fixture-font"}},
    }
    library.write(language)
    return path


@pytest.mark.parametrize("property,value", [("font-weight", 700), ("font-style", "italic")])
@pytest.mark.parametrize("requester", ["role-defaults", "component", "slot", "override"])
def test_missing_font_face_is_a_missing_finding(library, language, vocabulary, tmp_path, property, value, requester):
    """Amendment 03: every used role and each treatment source identifies the requesting member."""
    bind_font(library, language, tmp_path)
    if property == "font-weight":
        language["style"]["type"]["bold"] = {"$type": "fontWeight", "$value": value}
        value = "{type.bold}"
    explicit = {"font-family": "{type.family}", "font-weight": "{type.weight}", "font-style": "normal"}
    if requester == "component":
        language["components"]["listing-card"]["properties"] = explicit
        paths = [("components", "listing-card", "properties")]
    elif requester == "slot":
        language["components"]["listing-card"]["slots"]["price"] = {"properties": explicit}
        paths = [("components", "listing-card", "slots", "price", "properties")]
    elif requester == "override":
        language["overrides"] = [{"scope": "listing-card.price", "reason": "font face fixture", "properties": explicit}]
        paths = [("overrides", 0, "properties")]
    else:
        used = {(slot["role"], slot["emphasis"]) for construct in vocabulary["constructs"].values()
                for slot in construct["slots"]}
        assert used
        paths = [("roles", role, emphasis) for role, emphasis in sorted(used)]
    library.write(language)
    library.validate()
    for path in paths:
        # A fresh copy per request isolates each unsupplied face from prior failing cases.
        document = copy.deepcopy(language)
        entry = document
        for key in path:
            entry = entry[key]
        entry[property] = value
        library.write(document)
        pointer = "/" + "/".join(str(key) for key in (*path, property))
        assert_finding(library.validate(accepted=False), document, "asset-font", pointer, value, "missing")
