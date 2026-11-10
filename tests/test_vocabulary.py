"""Normative public vocabulary + amendment 01: inspect the shipped data through CLI.

Falsifier: absent/defaultless state contracts or a reordered/retyped pinned slot,
which would otherwise make a data-driven renderer and its tests agree on wrong data.
Nav/listing-card and amendment 13's generic card are pinned here.
"""


def test_v1_vocabulary_pins_and_declared_defaults(vocabulary):
    assert vocabulary["version"] == "v1"
    assert set(vocabulary["roles"]) == {"title", "subtitle", "body", "subtext", "label", "caption", "media", "action", "control"}
    assert set(vocabulary["emphasis"]) == {"neutral", "primary", "attention", "muted"}
    assert set(vocabulary["states"]) == {"default", "hover", "focus-visible", "active", "disabled", "selected", "expanded", "loading", "empty", "error"}
    constructs = vocabulary["constructs"]
    assert {"listing-card", "nav"} <= constructs.keys()
    for definition in constructs.values():
        assert "default" in definition["states"]
        assert set(definition["states"]) <= set(vocabulary["states"])
        assert isinstance(definition["contract"], dict)
        for slot in definition["slots"]:
            assert slot["role"] in vocabulary["roles"]
            assert slot["emphasis"] in vocabulary["emphasis"]
            assert slot["id"] not in vocabulary["states"]
    card = constructs["listing-card"]
    assert card["root"] == "article"
    assert [s["id"] for s in card["slots"]] == ["media", "title", "location", "rating", "price", "action"]
    by_id = {s["id"]: s for s in card["slots"]}
    for name, role, required in [("media", "media", True), ("title", "title", True),
                                 ("location", "subtext", False), ("rating", "caption", False),
                                 ("price", "label", True), ("action", "action", False)]:
        assert by_id[name]["role"] == role
        assert by_id[name]["required"] is required
    assert by_id["price"]["emphasis"] == "primary"
    nav = constructs["nav"]
    assert nav["root"] == "nav"
    assert [s["id"] for s in nav["slots"]] == ["logo", "links"]
    assert all(s["required"] for s in nav["slots"])
    assert nav["slots"][0]["kind"] == "media"
    assert nav["slots"][0]["asset_kind"] == "logo"
    assert nav["slots"][1]["role"] == "action"


def test_generic_card_contract(vocabulary):
    """Amendment 13 adds a domain-neutral repeated-group vocabulary contract."""
    card = vocabulary["constructs"]["card"]
    assert card["root"] == "article"
    slots = card["slots"]
    assert [slot["id"] for slot in slots] == ["media", "eyebrow", "title", "body", "meta", "highlight", "action"]
    assert {slot["id"] for slot in slots if slot["required"]} == {"title"}
    by_id = {slot["id"]: slot for slot in slots}
    for name, role in {"eyebrow": "caption", "title": "title", "meta": "subtext", "highlight": "label"}.items():
        assert by_id[name]["role"] == role
    assert by_id["media"]["kind"] == "media" and by_id["media"]["asset_kind"] == "image"
    assert by_id["highlight"]["emphasis"] == "primary"


def test_vocabulary_and_hooks_default_to_newest_explicit_version(library):
    """Amendment 04: stale defaults and ignored version options must fail."""
    import re
    versions = [path.name for path in (library.library / "vocabulary").iterdir()
                if path.is_dir() and re.fullmatch(r"v[0-9]+", path.name)]
    assert {"v1", "v2"} <= set(versions), "Amendment 04 requires both public versions"
    newest = max(versions, key=lambda name: int(name[1:]))
    for command, version_field in (("vocabulary", "version"), ("hooks", "vocabulary")):
        default = library.json(command)
        explicit = library.json(command, "--vocabulary", newest)
        assert default == explicit
        assert default[version_field] == newest
        assert library.json(command, "--vocabulary", "v1")[version_field] == "v1"
        library.cli(command, "--vocabulary", "not-a-version", code=2)
