"""Normative public vocabulary + amendment 01: inspect the shipped data through CLI.

Falsifier: absent/defaultless state contracts or a reordered/retyped pinned slot,
which would otherwise make a data-driven renderer and its tests agree on wrong data.
Only nav/listing-card are pinned here; the other construct definitions may evolve.
"""


def test_vocabulary_pins_and_declared_defaults(vocabulary):
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
