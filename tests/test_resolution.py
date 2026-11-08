"""Normative B3 and M0 Resolution: values and sources at the real CLI.

Oracles are authored token values and the stated precedence, not observed CSS.
Falsifiers include one-hop aliases, raw DTCG objects leaking out, merged root/slot
scopes, state leaking into default, reversed precedence, and stale override caches.
"""

import pytest

CSS_PROPERTIES = {
    "color", "background-color", "border-color", "font-family", "font-size",
    "letter-spacing", "border-width", "border-style", "border-radius", "width", "max-width",
    "font-weight", "line-height", "padding", "padding-block", "padding-inline",
    "margin-block", "gap", "display", "flex-direction", "flex-wrap", "align-items",
    "justify-content", "text-align", "text-transform", "font-style", "text-decoration-line",
    "overflow", "text-overflow", "white-space", "background-image",
}


def resolved(library, scope="listing-card.price", state="default", breakpoint=None):
    args = ["resolve", "tidal", scope, "--state", state]
    if breakpoint is not None:
        args += ["--breakpoint", breakpoint]
    result = library.json(*args)
    assert result["language"] == "tidal"
    assert result["scope"] == scope
    assert result["state"] == state
    assert result["breakpoint"] == breakpoint
    assert set(result["properties"]) <= CSS_PROPERTIES, result
    return result["properties"]


def test_surface_is_pairing_metadata_not_a_resolved_css_property(library, language):
    """Amendment 03: surface neither leaks as CSS nor silently becomes background-color."""
    before = resolved(library)
    assert before["color"] == {"value": "#123456", "source": "role:label.primary"}
    language["roles"]["label"]["primary"]["surface"] = "{color.component}"
    library.write(language)
    assert resolved(library) == before


@pytest.mark.parametrize("token_type,value,property,expected", [
    ("color", "#ABCDEF", "color", "#abcdef"),
    ("color", "#ABCDEF80", "color", "#abcdef80"),
    ("color", {"colorSpace": "srgb", "components": [1, 0, 0]}, "color", "#ff0000"),
    ("color", {"colorSpace": "srgb", "components": [0, 1, 0], "alpha": 0}, "color", "#00ff0000"),
    ("dimension", {"value": 16.0, "unit": "px"}, "font-size", "16px"),
    ("dimension", {"value": 1.5, "unit": "rem"}, "font-size", "1.5rem"),
    ("dimension", "16px", "font-size", "16px"),
    ("fontFamily", ["Fixture Sans", "sans-serif"], "font-family", '"Fixture Sans", sans-serif'),
    ("fontFamily", "serif", "font-family", "serif"),
    ("fontWeight", 1, "font-weight", 1),
    ("fontWeight", 1000, "font-weight", 1000),
    ("number", 1.25, "line-height", 1.25),
])
def test_normalizes_typed_values_through_alias_chain(library, language, token_type, value, property, expected):
    language["style"]["probe"] = {
        "$type": token_type, "leaf": {"$value": value},
        "alias": {"$value": "{probe.leaf}"}, "chain": {"$value": "{probe.alias}"},
    }
    language["roles"]["label"]["primary"][property] = "{probe.chain}"
    library.write(language)
    library.validate()
    assert resolved(library)[property] == {"value": expected, "source": "role:label.primary"}


def test_deleting_override_then_component_restores_inheritance(library, language):
    """B3 sequence: role -> component -> override -> component -> role, without cached residue."""
    steps = [
        ("#123456", "role:label.primary"),
        ("#654321", "component:listing-card.price"),
        ("#226644", "override:listing-card.price"),
        ("#654321", "component:listing-card.price"),
        ("#123456", "role:label.primary"),
    ]
    for step, (value, source) in enumerate(steps):
        if step == 1:
            language["components"]["listing-card"]["slots"]["price"] = {"properties": {"color": "{color.component}"}}
        elif step == 2:
            language["overrides"] = [{"scope": "listing-card.price", "reason": "special price", "properties": {"color": "{color.override}"}}]
        elif step == 3:
            language["overrides"] = []
        elif step == 4:
            del language["components"]["listing-card"]["slots"]["price"]["properties"]["color"]
        library.write(language)
        assert resolved(library)["color"] == {"value": value, "source": source}


def test_override_targets_exact_root_or_slot(library, language):
    language["components"]["listing-card"]["properties"]["color"] = "{color.component}"
    language["overrides"] = [{"scope": "listing-card", "reason": "root only", "properties": {"color": "{color.override}"}}]
    library.write(language)
    assert resolved(library, "listing-card")["color"] == {
        "value": "#226644", "source": "override:listing-card"}
    assert resolved(library)["color"] == {"value": "#123456", "source": "role:label.primary"}
    language["overrides"][0]["scope"] = "listing-card.price"
    library.write(language)
    assert resolved(library, "listing-card")["color"] == {
        "value": "#654321", "source": "component:listing-card"}
    assert resolved(library)["color"] == {"value": "#226644", "source": "override:listing-card.price"}


def interactive_scope(vocabulary):
    # State membership comes from amendment 01. Do not presume states for unpinned constructs.
    for construct, definition in vocabulary["constructs"].items():
        states = [state for state in definition["states"] if state != "default"]
        if states:
            return construct, states[0]
    pytest.fail("B9 interactive-state evidence needs a construct declaring a non-default state")


def specificity_overrides(scope, state):
    return [
        {"scope": scope + suffix, "reason": "precedence fixture", "properties": {"color": "{color." + token + "}"}}
        for suffix, token in [("", "override"), ("." + state, "hover"),
                              ("@md", "wide"), ("@lg", "widest"),
                              ("." + state + "@md", "combined")]
    ]


@pytest.mark.parametrize("order", [tuple(range(5)), tuple(reversed(range(5))), (2, 0, 4, 1, 3)])
def test_specificity_is_independent_of_override_array_order(library, language, vocabulary, order):
    """Derived table: plain < state < breakpoint < combined; larger bp wins within a tier."""
    scope, state = interactive_scope(vocabulary)
    overrides = specificity_overrides(scope, state)
    language["overrides"] = [overrides[i] for i in order]
    library.write(language)
    expected = {
        ("default", None): ("#226644", scope),
        (state, None): ("#662244", f"{scope}.{state}"),
        ("default", "md"): ("#442266", f"{scope}@md"),
        ("default", "lg"): ("#223366", f"{scope}@lg"),
        (state, "md"): ("#663322", f"{scope}.{state}@md"),
    }
    for (current_state, bp), (value, source) in expected.items():
        assert resolved(library, scope, current_state, bp)["color"] == {
            "value": value, "source": "override:" + source}
    # Removal exposes breakpoint-only before state-only at md, not whichever was appended last.
    language["overrides"] = [o for o in language["overrides"] if o["scope"] != f"{scope}.{state}@md"]
    library.write(language)
    assert resolved(library, scope, state, "md")["color"] == {
        "value": "#442266", "source": f"override:{scope}@md"}


def test_component_state_then_base_source(library, language, vocabulary):
    scope, state = interactive_scope(vocabulary)
    component = language["components"][scope]
    component["properties"] = {"color": "{color.component}", "display": "flex"}
    component["states"] = {state: {"color": "{color.hover}"}}
    library.write(language)
    assert resolved(library, scope, state)["color"] == {
        "value": "#662244", "source": f"component:{scope}.{state}"}
    assert resolved(library, scope)["color"] == {
        "value": "#654321", "source": f"component:{scope}"}
    assert resolved(library, scope)["display"] == {
        "value": "flex", "source": f"component:{scope}"}


@pytest.mark.parametrize("breakpoint", ["absent", "767", "768", "breakpoint.md"])
def test_invalid_breakpoint_argument_is_usage_error(library, language, breakpoint):
    """Amendment 02: only declared ids are accepted, never numeric viewport strings."""
    library.cli("resolve", "tidal", "listing-card.price", "--breakpoint", breakpoint, code=2)
