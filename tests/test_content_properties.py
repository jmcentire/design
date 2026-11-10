"""Normative amendment 02 D: closed layout grammar and content preservation.

Real validate/resolve CLI. Direct valid and boundary-invalid pairs catch both
reject-all and CSS pass-through validators; findings must identify authored input.
Browser geometry for these properties is in test_content_browser.py.
"""
import pytest

from tests.content_support import content_library
from tests.test_resolution import resolved


# Exact resolved values derive mechanically from the authored 8px space token.
VALUES = [
    ("grid-template-columns", "1fr 2fr", "1fr 2fr", "0fr"),
    ("grid-template-columns", "repeat(12, 1fr)", "repeat(12, 1fr)", "repeat(13, 1fr)"),
    ("grid-template-columns", "minmax({space.small}, 2fr)", "minmax(8px, 2fr)", "minmax({color.ink}, 1fr)"),
    ("grid-template-columns", "repeat(auto-fit, minmax({space.small}, 1fr))", "repeat(auto-fit, minmax(8px, 1fr))", "repeat(auto-fit, 1fr)"),
    ("grid-template-columns", "repeat(auto-fill, minmax({space.small}, 1fr))", "repeat(auto-fill, minmax(8px, 1fr))", "1fr " * 13),
    ("grid-column", "span 12", "span 12", "span 13"),
    ("grid-column", "1 / -1", "1 / -1", "2 / -1"),
    ("grid-row", "span 6", "span 6", "span 7"),
    ("align-self", "start", "start", "baseline"),
    ("justify-self", "stretch", "stretch", "space-between"),
    ("aspect-ratio", "32 / 1", "32 / 1", "33 / 1"),
    ("aspect-ratio", "1 / 32", "1 / 32", "1 / 0"),
    ("object-fit", "cover", "cover", "crop"),
    ("object-position", "left", "left", "20% 30%"),
    ("margin-inline", "{space.small}", "8px", "-100px"),
    ("margin-inline", "auto", "auto", "{color.ink}"),
    ("box-shadow", "none", "none", "0 0 10px red"),
    ("column-gap", "{space.small}", "8px", "{color.ink}"),
    ("row-gap", "{space.small}", "8px", "8px;display:none"),
]


@pytest.mark.parametrize("prop,valid,expected,invalid", VALUES)
def test_new_properties_resolve_with_provenance_and_reject_invalid_values(library, language, prop, valid, expected, invalid):
    properties = language["components"]["listing-card"]["properties"]
    properties[prop] = valid
    library.write(language)
    library.validate()
    actual = resolved(library, "listing-card")[prop]
    # CSS insignificant whitespace is not a serialization promise.
    assert "".join(str(actual["value"]).split()) == "".join(expected.split())
    assert actual["source"] == "component:listing-card"
    properties[prop] = invalid
    library.write(language)
    report = library.validate(accepted=False)
    pointer = "/components/listing-card/properties/" + prop
    assert any(f["pointer"] == pointer and f["observed"] == invalid for f in report["findings"])


def test_content_relative_widths_resolve_only_nonnegative_token_arithmetic(content_library):
    # P2 fluid-bleed contract extends the existing closed minus form to plus,
    # for width and max-width. The authored 8px token determines the CSS value.
    language = content_library.read("harbor")
    language["style"]["relative-test"] = {
        "inset": {"$type": "dimension", "$value": "8px"},
        "negative": {"$type": "dimension", "$value": "-8px"},
    }
    properties = language["components"]["card"]["properties"]
    for prop in ("width", "max-width"):
        for sign in ("-", "+"):
            properties[prop] = f"calc(100% {sign} {{relative-test.inset}})"
            content_library.write(language)
            content_library.validate("harbor")
            actual = content_library.json("resolve", "harbor", "card")["properties"][prop]
            assert "".join(str(actual["value"]).split()) == f"calc(100%{sign}8px)"
        for invalid in ("calc(100% + {relative-test.negative})", "calc(100% + 8px)"):
            properties[prop] = invalid
            content_library.write(language)
            report = content_library.validate("harbor", accepted=False)
            assert any(f["pointer"] == f"/components/card/properties/{prop}" and
                       f["observed"] == invalid for f in report["findings"])
        del properties[prop]


@pytest.mark.parametrize("where", ["construct", "slot", "part", "override"])
def test_content_cannot_be_hidden_at_any_scope(library, language, where):
    component = language["components"]["listing-card"]
    if where == "construct":
        properties, pointer = component["properties"], "/components/listing-card/properties/display"
    elif where == "slot":
        properties = component["slots"].setdefault("title", {}).setdefault("properties", {})
        pointer = "/components/listing-card/slots/title/properties/display"
    elif where == "part":
        # This validated variant's stack actually contains content slots, so the
        # prohibition is reached, not tested on an unused decorative wrapper.
        from tests.test_validation import VALID_VARIANT, set_variant
        set_variant(language, VALID_VARIANT)
        properties = component.setdefault("parts", {}).setdefault("stack", {})
        pointer = "/components/listing-card/parts/stack/display"
    else:
        language["overrides"] = [{"scope": "listing-card.title@md", "reason": "Visibility control", "properties": {}}]
        properties, pointer = language["overrides"][0]["properties"], "/overrides/0/properties/display"
    properties["display"] = "contents"
    library.write(language)
    library.validate()
    properties["display"] = "none"
    library.write(language)
    report = library.validate(accepted=False)
    assert any(f["rule"] == "content-hidden" and f["pointer"] == pointer and f["observed"] == "none" for f in report["findings"])


@pytest.mark.parametrize("prop,value", [("order", 1), ("position", "absolute"), ("visibility", "hidden"),
    ("content", "replacement"), ("transform", "scale(0)"), ("clip-path", "inset(100%)"),
    ("opacity", 0), ("text-indent", "-9999px")])
def test_content_reordering_and_replacement_properties_are_unknown(library, language, prop, value):
    library.validate()
    language["components"]["listing-card"]["properties"][prop] = value
    library.write(language)
    report = library.validate(accepted=False)
    assert any(f["pointer"] == "/components/listing-card/properties/" + prop
               and f["observed"] == value for f in report["findings"])


def test_shipped_languages_still_validate(content_library):
    for language in ("harbor", "lantern"):
        content_library.validate(language)
