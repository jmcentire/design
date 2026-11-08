"""Normative amendment 04: rendered conditions remain expressible through validated language data.

Falsifiers: reject all new properties, accept a color as a gradient, or fail to
report the actual missing background binding. Real validation CLI, no CSS injection.
"""

import pytest

from tests.m1_support import slot_properties, token
from tests.support import assert_finding


def test_render_condition_properties_are_valid_language_input(library, language):
    gradient = token(language, "background", "fade", "gradient", [
        {"color": "{color.ink}", "position": 0}, {"color": "#ffffff", "position": 1}])
    properties = slot_properties(language)
    properties.update({"overflow": "hidden", "text-overflow": "ellipsis", "white-space": "nowrap",
                       "background-image": gradient})
    library.write(language)
    library.validate()
    properties["background-image"] = "asset:fixture-image:primary"
    library.write(language)
    library.validate()


@pytest.mark.parametrize("value,kind", [("{color.ink}", "violation"),
                                        ("{background.absent}", "violation"),
                                        ("asset:absent:primary", "missing"),
                                        ("asset:fixture-image:absent", "missing")])
def test_background_reference_failure_is_precise(library, language, value, kind):
    library.validate()
    slot_properties(language)["background-image"] = value
    library.write(language)
    assert_finding(library.validate(accepted=False), language, "R1",
                   "/components/listing-card/slots/title/properties/background-image", value, kind)


def test_unknown_check_language_is_usage_error(library):
    library.cli("check", "no-such-language", code=2)


def test_lantern_declares_the_briefs_space_scale_and_breakpoints(lantern):
    """Public language data is a delivered artifact; values are fixed by the design brief."""
    def dereference(value, seen=()):
        if isinstance(value, str) and value.startswith("{") and value.endswith("}"):
            path = value[1:-1]
            assert path not in seen, "Cyclic dimension alias"
            node = lantern["style"]
            for key in path.split("."):
                node = node[key]
            return dereference(node["$value"], (*seen, path))
        return value

    def pixels(value):
        value = dereference(value)
        if isinstance(value, dict):
            assert value["unit"] == "px"
            return value["value"]
        assert value.endswith("px")
        return float(value[:-2])

    def leaves(node):
        if "$value" in node:
            yield pixels(node["$value"])
        else:
            for key, value in node.items():
                if not key.startswith("$") and isinstance(value, dict):
                    yield from leaves(value)

    assert {4, 8, 12, 16, 24, 32, 48} <= set(leaves(lantern["style"]["space"]))
    assert pixels(lantern["style"]["breakpoint"]["md"]["$value"]) == 768
    assert pixels(lantern["style"]["breakpoint"]["lg"]["$value"]) == 1200
