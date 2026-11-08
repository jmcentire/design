"""Normative amendments 01/02/05: hook adoption and external section mapping.

Falsifiers: publish dead selectors, omit required slots, leak undeclared hooks,
choose generic rule over matching variant, coerce/evaluate source data, or silently
discard unmapped fields. Real CLI/files; values authored independently below.
"""
import json

import pytest

from tests.content_support import content_library, render, write_content, save_content
from tests.html_support import Element
from tests.support import pointer_value


def allowed_elements(spec):
    """Amendment 05 permits one tag or a nonempty list of allowed tags."""
    elements = spec["element"]
    if isinstance(elements, str):
        elements = [elements]
    assert isinstance(elements, list) and elements
    assert all(isinstance(tag, str) and tag for tag in elements)
    return elements


def assert_hooks(contract, doc):
    assert contract["schema"] == "kinbase-hooks/1"
    assert contract["attributes"] == {"construct": "data-kd-construct", "slot": "data-kd-slot", "part": "data-kd-part"}
    definitions = contract["constructs"]
    pages = contract["content_pages"]
    names = [pages["landmarks"][k] for k in ("header", "footer")]
    names += [pages["blocks"][k] for k in ("hero", "section", "cta")]
    names += list(pages["blocks"]["collection"].values())
    assert all(name in definitions for name in names)
    assert all(doc.all(**{"data-kd-construct": name}) for name in names)
    for identity, definition in definitions.items():
        assert definition["selector"] == f'[data-kd-construct="{identity}"]'
        for slot, spec in definition["slots"].items():
            assert spec["selector"] == f'[data-kd-slot="{identity}.{slot}"]'
            assert isinstance(spec["required"], bool)
            allowed_elements(spec)
        for part, spec in definition["parts"].items():
            assert spec["selector"] == f'[data-kd-part="{part}"]'

    def visit(node, ancestors=()):
        # Match the qualified construct among actual ancestors. Nested constructs
        # may contain slots owned by an outer construct; a sibling is never an
        # owner. Each frame holds this instance's observed required slots.
        if "data-kd-slot" in node.attrs:
            qualified = node.attrs["data-kd-slot"]
            owner_id, separator, slot = qualified.partition(".")
            assert separator and slot, ("Unqualified slot", qualified)
            owners = [frame for frame in ancestors if frame[0] == owner_id]
            assert owners, ("Slot has no matching ancestor construct", qualified)
            owner_id, seen = owners[-1]
            assert slot in definitions[owner_id]["slots"], qualified
            assert node.tag in allowed_elements(definitions[owner_id]["slots"][slot])
            seen.add(slot)
        identity = node.attrs.get("data-kd-construct")
        if identity:
            assert identity in definitions, identity
            ancestors = (*ancestors, (identity, set()))
        if "data-kd-part" in node.attrs:
            part = node.attrs["data-kd-part"]
            assert ancestors and part in definitions[ancestors[-1][0]]["parts"], part
        for child in node.children:
            if isinstance(child, Element):
                visit(child, ancestors)
        if identity:
            required = {key for key, spec in definitions[identity]["slots"].items() if spec["required"]}
            assert required <= ancestors[-1][1], (identity, ancestors[-1][1])
    visit(doc.root)


def test_hook_contract_round_trips_pages_and_exports(content_library, tmp_path):
    source, content = write_content(tmp_path / "source")
    # Exercise both captioned media and plain media in the same round trip.
    media = content["blocks"][2]["items"][0]["media"]
    del media["caption"], media["credit"]
    save_content(source, content)
    out = tmp_path / "page"
    doc = render(content_library, source, out)
    contract_bytes = content_library.cli("hooks").stdout.encode()
    contract = json.loads(contract_bytes)
    assert contract["vocabulary"] == "v2", "Content pages use the new content-capable vocabulary"
    assert json.loads((out / "hooks.json").read_bytes()) == contract
    assert_hooks(contract, doc)
    second = tmp_path / "second"
    render(content_library, source, second, "lantern")
    assert (out / "hooks.json").read_bytes() == (second / "hooks.json").read_bytes()
    # CLI serialization may have a final newline; JSON semantics establish CLI
    # agreement, and persisted bytes establish identical-vocabulary stability.
    pinned = content_library.json("hooks", "--vocabulary", contract["vocabulary"])
    assert pinned == contract
    for adapter in ("generic", "dtcg-tailwind"):
        target = tmp_path / adapter
        content_library.cli("export", "harbor", "--adapter", adapter, "--out", target)
        assert (target / "hooks.json").read_bytes() == (out / "hooks.json").read_bytes()


def mapping_document():
    return {"schema": "kinbase-section-map/1", "page": {"title": "Mapped notebook"},
        "site": {"name": "Mapped Observatory"}, "footer": {"notices": ["Synthetic mapping fixture"]},
        "sections": [
            {"match": {"type": "banner"}, "block": "cta", "fields": {"title": "/fallback"}},
            {"match": {"type": "banner", "variant": "lead"}, "block": "hero", "fields": {
                "title": "/heading", "body": "/description", "id": "/anchor",
                "actions/0/text": "/button/label", "actions/0/href": "/button/url"}},
            {"match": {"type": "prose"}, "block": "section", "fields": {
                "title": "/heading", "content": "/text", "id": "/anchor"}},
            {"match": {"type": "tiles"}, "block": "collection", "fields": {"title": "/heading"},
             "items": {"from": "/entries", "fields": {"title": "/name", "body": "/copy",
                 "media/src": "/picture/path", "media/alt": "/picture/description",
                 "action/text": "/link/text", "action/href": "/link/href",
                 "facts/0/label": "/fact/label", "facts/0/value": "/fact/value"}}}]}


def section_records():
    return [
        {"type": "banner", "variant": "lead", "fallback": "Wrong generic fallback", "heading": "Mapped hero",
         "description": '<b data-evaluated="yes">literal mapping text</b>', "anchor": "top",
         "button": {"label": "Read mapped prose", "url": "#prose"}, "subtitle": "Unmapped subtitle"},
        {"type": "prose", "heading": "Mapped prose", "text": "One copied paragraph", "anchor": "prose",
         "unused_count": 7, "unused_items": ["unused"], "version": 4, "theme": "ignored metadata"},
        {"type": "tiles", "heading": "Mapped collection", "entries": [
            {"name": "Mapped card", "copy": "Mapped card body", "picture": {"path": "img/sample.png", "description": "Mapped image"},
             "link": {"text": "Read mapped card", "href": "#prose"}, "fact": {"label": "Kind", "value": "Notebook"}}]},
        {"type": "prose", "text": "Mapped body-only passage", "anchor": "untitled"},
        {"type": "unknown", "heading": "Unmapped section"}]


@pytest.mark.parametrize("wrapped", [False, True])
def test_section_mapping_preserves_values_and_reports_every_unmapped_field(content_library, tmp_path, wrapped):
    original, _ = write_content(tmp_path / "source")
    source = section_records()
    sections = {"sections": source} if wrapped else source
    mapping = mapping_document()
    map_file, sections_file = original.parent / "mapping.json", original.parent / "sections.json"
    map_file.write_text(json.dumps(mapping))
    sections_file.write_text(json.dumps(sections))
    out = original.parent / "mapped.json"
    report = content_library.json("map-sections", "--mapping", map_file, "--sections", sections_file, "--out", out)
    assert report["blocks"] == 4 and out.is_file()
    content = json.loads(out.read_text())
    assert content["schema"] == "kinbase-content/1"
    assert [b["type"] for b in content["blocks"]] == ["hero", "section", "collection", "section"]
    hero, prose, collection, untitled = content["blocks"]
    assert hero["title"] == "Mapped hero"
    assert hero["body"] == source[0]["description"]
    assert hero["actions"] == [{"text": "Read mapped prose", "href": "#prose"}]
    assert prose["content"] == [{"paragraph": "One copied paragraph"}]
    # Amendment 07: a missing source title maps to a valid body-only section.
    assert "title" not in untitled
    assert untitled["content"] == [{"paragraph": "Mapped body-only passage"}]
    assert collection["items"][0]["facts"] == [{"label": "Kind", "value": "Notebook"}]
    assert collection["items"][0]["media"] == {"src": "img/sample.png", "alt": "Mapped image"}
    prefix = "/sections" if wrapped else ""
    expected = {prefix + p for p in ("/0/fallback", "/0/subtitle", "/1/unused_count", "/1/unused_items", "/4")}
    assert {item["pointer"] for item in report["unmapped"]} == expected
    assert not [f for f in report["findings"] if f["pointer"] in {prefix + "/3", prefix + "/3/heading"}
                and f["type"] in {"missing", "violation"}]
    for item in report["unmapped"]:
        pointer_value(sections, item["pointer"])
        assert item["reason"].strip()
    doc = render(content_library, out, tmp_path / "rendered")
    assert not doc.all(**{"data-evaluated": "yes"})
    for text in ("Mapped hero", "Mapped prose", "Mapped card", source[0]["description"], "One copied paragraph", "Mapped body-only passage"):
        assert text in doc.text()
    assert any(a.attrs.get("href") == "#prose" and "Read mapped card" in a.text() for a in doc.all("a"))


def test_unmapped_only_input_is_rejected(content_library, tmp_path):
    mapping = tmp_path / "mapping.json"
    sections = tmp_path / "sections.json"
    mapping.write_text(json.dumps(mapping_document()))
    sections.write_text(json.dumps([{"type": "no-rule", "text": "Do not lose me silently"}]))
    report = content_library.json("map-sections", "--mapping", mapping, "--sections", sections,
                                  "--out", tmp_path / "output.json", code=1)
    assert report["blocks"] == 0
    assert any(u["pointer"] == "/0" and u["reason"].strip() for u in report["unmapped"])


def test_mapping_does_not_coerce_nonstring_text(content_library, tmp_path):
    mapping = tmp_path / "mapping.json"
    sections = tmp_path / "sections.json"
    mapping.write_text(json.dumps(mapping_document()))
    data = [{"type": "prose", "heading": "Valid title", "text": 17}]
    sections.write_text(json.dumps(data))
    out = tmp_path / "content.json"
    report = content_library.json("map-sections", "--mapping", mapping, "--sections", sections, "--out", out, code=(0, 1))
    assert any(f["pointer"] == "/0/text" and f["observed"] == 17 and f["message"] for f in report["findings"])
    if out.exists():
        result = json.loads(out.read_text())
        for index, block in enumerate(result["blocks"]):
            entries = block.get("content", [])
            assert isinstance(entries, list), ("Mapped section content must be an array", index, entries)
            for entry in entries:
                assert isinstance(entry, dict), ("Mapped section content entry must be an object", index, entry)
                assert entry.get("paragraph") not in (17, "17"), (
                    "Invalid numeric text was copied or coerced into paragraph content", index, entry)
