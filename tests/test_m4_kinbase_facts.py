"""B17 / amendments 18 and 20: real adapter composition at the executable seam.

The stand-in's facts are input, not evidence of real Kinbase authority resolution.
Our oracles are known fixed values, observed public candidates/derived languages,
source provenance, scope/standing controls and exact recorded external argv.
"""

import colorsys
import json

from PIL import ImageColor

import pytest

from tests.m2_support import (assert_provenance, assert_shared_privacy, provenance_at,
                              read_json, token_values)
from tests.m3_render_support import hsl, paint_snapshot, primary
from tests.m3_support import candidate_directory, choose, generate, pair, start
from tests.m4_kinbase_support import (assert_read_calls, fact, kinbase_seam,
                                    machine_fact, set_facts)
from tests.support import pointer_value
from tests.test_m3_derive import check_draft, derive
from tests.test_versions_assets import expected_hash


def fixed_hue(seam, value=200):
    set_facts(seam, **{"design/brand": machine_fact(dimensions={"hue-family": value})})


def raw_settled(library, session):
    # The M3 choice-only helper correctly requires supporting choice ids. A fixed
    # Kinbase dimension precedes choices, so use the public settled shape directly.
    output = generate(library, "settled", session)
    assert output["session"] == session
    assert not set(output["settled"]) & set(output["unsettled"])
    return output


def test_authoritative_in_scope_dimensions_are_settled_from_start_and_never_offered(library, kinbase_seam):
    fixed_hue(kinbase_seam)
    set_facts(kinbase_seam, **{"design/rhythm": machine_fact(dimensions={"density": 10},
              identity="fact-design-density", scope="rhythm")})
    session, root, _ = start(library, "A calm reading room with red accents")
    initial = raw_settled(library, session)
    for dimension, value in (("hue-family", 200), ("density", 10)):
        assert initial["settled"][dimension]["value"] == value
        assert dimension not in initial["unsettled"]
    offered = 0
    for _ in range(8):
        current = pair(library, session, root)
        if current.get("done"):
            break
        offered += 1
        assert not {"hue-family", "density"} & set(current["dimensions"])
        for side in ("a", "b"):
            assert current[side]["values"]["hue-family"] == 200
            assert current[side]["values"]["density"] == 10
        choose(library, session, root, current, "B", comment="Keep comparing only unconstrained dimensions")
    assert offered and pair(library, session, root)["done"] is True
    final = raw_settled(library, session)
    assert final["settled"]["hue-family"]["value"] == 200 and final["settled"]["density"]["value"] == 10
    assert_read_calls(kinbase_seam.directory, kinbase_seam.repo, kinbase_seam.keys, required_keys=kinbase_seam.standards)


@pytest.mark.parametrize("case", ["prevalent", "wrong-scope", "conflict", "unknown", "free-text", "unrelated-json"])
def test_only_machine_applicable_authoritative_in_scope_current_facts_fix_dimensions(library, kinbase_seam, case):
    current = machine_fact(dimensions={"hue-family": 200})
    if case == "prevalent":
        current["current"]["standing"] = "prevalent"
    elif case == "wrong-scope":
        current["current"]["scope"] = "another-brand"
    elif case in {"conflict", "unknown"}:
        current["state"] = case
    elif case == "free-text":
        current["current"]["statement"] = "Keep the title calm; favor a hue of 200 degrees."
    else:
        current["current"]["statement"] = json.dumps({"hue-family": 200})
    set_facts(kinbase_seam, **{"design/brand": current})
    session, _, _ = start(library)
    state = raw_settled(library, session)
    assert "hue-family" in state["unsettled"] and "hue-family" not in state["settled"]
    assert_read_calls(kinbase_seam.directory, kinbase_seam.repo, kinbase_seam.keys, required_keys=kinbase_seam.standards)


def alias_value_pointer(document, alias):
    """Follow a public DTCG alias to its leaf; no generated token names assumed."""
    seen = set()
    while isinstance(alias, str) and alias.startswith("{") and alias.endswith("}"):
        name = alias[1:-1]
        assert name not in seen
        seen.add(name)
        pointer = "/style/" + "/".join(part.replace("~", "~0").replace("/", "~1") for part in name.split(".")) + "/$value"
        alias = pointer_value(document, pointer)
    assert seen, "Fixture role must resolve through a public token alias"
    return pointer


def assert_hue_source(document, provenance):
    expected = {"kind": "source", "artifact": "kinbase:fact-design-hue",
                "location": "/kinbase-design/dimensions/hue-family"}
    # Primary and attention hues both derive from the fixed base hue per
    # amendment 11. Check their actual token leaves, including alias chains.
    pointers = set()
    for role in ("action", "label"):
        for emphasis in ("primary", "attention"):
            entry = document["roles"].get(role, {}).get(emphasis)
            if entry and "color" in entry:
                pointer = alias_value_pointer(document, entry["color"])
                rgb = ImageColor.getrgb(pointer_value(document, pointer))[:3]
                if max(rgb) - min(rgb) > 8:  # White/grey contrast text has no base hue.
                    pointers.add(pointer)
    for name, kind, value in token_values(document["style"]):
        if kind != "color" or not isinstance(value, str) or value.startswith("{"):
            continue
        rgb = ImageColor.getrgb(value)[:3]
        hue, _, saturation = colorsys.rgb_to_hls(*(channel / 255 for channel in rgb))
        if saturation > 0.05 and abs(hue * 360 - 200) <= 1:
            pointers.add("/style/" + "/".join(part.replace("~", "~0").replace("/", "~1") for part in name.split(".")) + "/$value")
    assert pointers
    for pointer in pointers:
        assert all(provenance_at(provenance, pointer).get(key) == value for key, value in expected.items()), (pointer, provenance_at(provenance, pointer))


def save_and_shared(library, root, document):
    library.cli("save-draft", document["id"], cwd=library.project, timeout=90)
    assert library.read(document["id"]) == document
    shared = read_json(library.path(document["id"]).parent / "provenance" / (expected_hash(document) + ".json"))
    assert_provenance(document, shared, shared=True)
    assert_shared_privacy(library)
    return shared


@pytest.mark.browser
@pytest.mark.browser_timeout(600)
def test_fixed_hue_renders_and_survives_derive_checks_and_shared_provenance(library, kinbase_seam, tmp_path, page):
    fixed_hue(kinbase_seam)
    session, _, _ = start(library, "A calm reading room with red accents")
    root, document, provenance = derive(library, session, "authority-hue")
    assert_hue_source(document, provenance)
    case = check_draft(library, root, document, tmp_path / "checks")
    preview = case.build(tmp_path / "preview", document["id"])
    page.goto((preview / "index.html").as_uri())
    hue, saturation, _ = hsl(primary(paint_snapshot(page))["css"]["color"])
    assert saturation > 0.05 and hue == pytest.approx(200, abs=1)
    shared = save_and_shared(library, root, document)
    assert_hue_source(document, shared)
    assert_read_calls(kinbase_seam.directory, kinbase_seam.repo, kinbase_seam.keys, required_keys=kinbase_seam.standards)


@pytest.mark.browser
@pytest.mark.browser_timeout(600)
def test_fixed_pointer_value_is_exact_and_keeps_escaped_source_location(library, kinbase_seam, tmp_path):
    # Find an existing color leaf in the public candidate, avoiding an assumption
    # about the generator's token names or requiring it to create missing parents.
    session, session_root, _ = start(library)
    current = pair(library, session, session_root)
    document = read_json(candidate_directory(library, session, current["a"]) / "working.json")
    pointer = alias_value_pointer(document, document["roles"]["label"]["primary"]["color"])
    set_facts(kinbase_seam, **{"design/brand": machine_fact(dimensions={"shape": 12}, values={pointer: "#0b6e65"}, identity="fact-brand-value")})
    fixed_session, _, _ = start(library)
    assert raw_settled(library, fixed_session)["settled"]["shape"]["value"] == 12
    root, document, provenance = derive(library, fixed_session, "authority-pointer")
    expected = {"kind": "source", "artifact": "kinbase:fact-brand-value",
                "location": "/kinbase-design/values/" + pointer.replace("~", "~0").replace("/", "~1")}
    assert pointer_value(document, pointer) == "#0b6e65"
    assert all(provenance_at(provenance, pointer).get(key) == value for key, value in expected.items())
    check_draft(library, root, document, tmp_path / "pointer-checks")
    shared = save_and_shared(library, root, document)
    assert pointer_value(library.read(document["id"]), pointer) == "#0b6e65"
    assert all(provenance_at(shared, pointer).get(key) == value for key, value in expected.items())
    assert_read_calls(kinbase_seam.directory, kinbase_seam.repo, kinbase_seam.keys, required_keys=kinbase_seam.standards)


@pytest.mark.browser
@pytest.mark.browser_timeout(420)
@pytest.mark.parametrize("standing", ["prevalent", "manual"])
def test_suggestions_and_manual_standards_never_write_kinbase_source_provenance(library, kinbase_seam, standing):
    value = (machine_fact(dimensions={"hue-family": 200}, standing="prevalent") if standing == "prevalent"
             else fact("Use a calm visual rhythm; prefer a hue of 200 degrees."))
    set_facts(kinbase_seam, **{"design/brand": value})
    session, _, _ = start(library)
    root, document, provenance = derive(library, session, "advisory-" + standing)
    assert "hue-family" in raw_settled(library, session)["unsettled"]
    assert not [p for p in provenance.values() if p.get("artifact", "").startswith("kinbase:")]
    shared = save_and_shared(library, root, document)
    assert not [p for p in shared.values() if p.get("artifact", "").startswith("kinbase:")]
