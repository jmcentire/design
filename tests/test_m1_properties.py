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
