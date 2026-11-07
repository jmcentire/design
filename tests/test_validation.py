"""Normative: B1/B2, public composition rules. Real CLI, one-defect inputs.

Falsifiers: accept-all validators; wrong rule/pointer/value; references checked only
for existence; template checkers that lose meaning while accepting valid wrappers.
"""

import copy
import json
import random

import pytest

from tests.support import FIXTURES, assert_finding


def test_valid_language_is_accepted(library, language):
    """Positive control prevents an always-reject validator passing the negative cases."""
    library.validate()


@pytest.mark.parametrize("value,rule", [
    ("{color.absent}", "R1"), ("{size.body}", "R1"), ("#aabbcc", "R2"),
])
def test_color_reference_failure_identifies_exact_input(library, language, value, rule):
    library.validate()
    language["roles"]["label"]["primary"]["color"] = value
    library.write(language)
    report = library.validate(accepted=False)
    assert_finding(report, language, rule, "/roles/label/primary/color", value)


@pytest.mark.parametrize("path,value", [
    (("color", "ink"), "blue-ish"),
    (("size", "body"), {"value": 16, "unit": "bananas"}),
    (("type", "weight"), 0), (("type", "weight"), 1001),
    (("type", "leading"), "not-a-number"),
])
def test_token_type_is_parsed(library, language, path, value):
    library.validate()
    group, token = path
    language["style"][group][token]["$value"] = value
    library.write(language)
    assert_finding(library.validate(accepted=False), language, "R2",
                   f"/style/{group}/{token}/$value", value)


@pytest.mark.parametrize("property,value,rule", [
    ("padding", "{size.body}", "R4"),
    ("gap", "{size.large}", "R4"),
    ("display", "potato", "R2"),
    ("unrecognized-property", "{color.ink}", "schema"),
    ("bad/name~", "{color.ink}", "schema"),
])
def test_property_rules_report_the_broken_field(library, language, property, value, rule):
    library.validate()
    language["components"]["listing-card"]["properties"][property] = value
    library.write(language)
    escaped = property.replace("~", "~0").replace("/", "~1")
    assert_finding(library.validate(accepted=False), language, rule,
                   f"/components/listing-card/properties/{escaped}", value)


@pytest.mark.parametrize("absent", ["color", "surface", "emphasis", "role"])
def test_required_pairing_cannot_be_omitted(library, language, absent):
    """R3/amendment 03: implicit use reports the declaration or its nearest existing ancestor."""
    library.validate()
    if absent == "role":
        del language["roles"]["label"]
        pointer, observed = "/roles", language["roles"]
    elif absent == "emphasis":
        del language["roles"]["label"]["primary"]
        pointer, observed = "/roles/label", language["roles"]["label"]
    else:
        del language["roles"]["label"]["primary"][absent]
        pointer, observed = "/roles/label/primary", language["roles"]["label"]["primary"]
    library.write(language)
    report = library.validate(accepted=False)
    assert_finding(report, language, "R3", pointer, observed, {"missing", "violation"})


@pytest.mark.parametrize("scope,reason,rule", [
    ("listing-card.price@absent", "test", "R4"),
    ("listing-card..price", "test", "override-scope"),
    ("listing-card.price", "", "override-reason"),
    ("listing-card.price", None, "override-reason"),
])
def test_invalid_override_is_explained(library, language, scope, reason, rule):
    library.validate()
    language["overrides"] = [{"scope": scope, "reason": reason, "properties": {"color": "{color.override}"}}]
    if reason is None:
        del language["overrides"][0]["reason"]
    library.write(language)
    field = "reason" if rule == "override-reason" else "scope"
    pointer = "/overrides/0" if reason is None else f"/overrides/0/{field}"
    observed = language["overrides"][0] if reason is None else reason if field == "reason" else scope
    assert_finding(library.validate(accepted=False), language, rule, pointer, observed)


def test_duplicate_scope_is_rejected(library, language):
    """An ambiguous second exact scope must not silently become last-write-wins."""
    override = {"scope": "listing-card.price", "reason": "test", "properties": {"color": "{color.override}"}}
    language["overrides"] = [override]
    library.write(language)
    library.validate()
    language["overrides"].append(copy.deepcopy(override))
    library.write(language)
    report = library.validate(accepted=False)
    assert any(f["rule"] == "override-scope" and f["type"] == "violation"
               for f in report["findings"]), report


SLOTS = "{{slot:media}}{{slot:title}}{{slot:location}}{{slot:rating}}{{slot:price}}{{slot:action}}"
VALID_VARIANT = '<article><div data-kd-part="stack">' + SLOTS + '</div></article>'


def set_variant(language, template):
    language["layout"]["variants"]["listing-card"] = {"stacked": {"template": template}}
    language["components"]["listing-card"]["variant"] = "stacked"


@pytest.mark.parametrize("template", [
    VALID_VARIANT.replace("{{slot:price}}", ""),
    VALID_VARIANT.replace("{{slot:price}}", "{{slot:price}}{{slot:price}}"),
    VALID_VARIANT.replace("{{slot:location}}", "{{slot:location}}{{slot:location}}"),
    VALID_VARIANT.replace("{{slot:title}}", "{{slot:not-a-slot}}"),
    VALID_VARIANT.replace("{{slot:media}}{{slot:title}}", "{{slot:title}}{{slot:media}}"),
    VALID_VARIANT.replace("</article>", "new text</article>"),
    VALID_VARIANT.replace("</article>", "<button>Book</button></article>"),
    VALID_VARIANT.replace("</article>", "<h1>Heading</h1></article>"),
    VALID_VARIANT.replace("</article>", "<nav></nav></article>"),
    VALID_VARIANT.replace("article", "section"),
    VALID_VARIANT.replace('data-kd-part="stack"', 'class="uncontracted"'),
])
def test_semantic_contract_breaking_variant_is_rejected(library, language, template):
    set_variant(language, VALID_VARIANT)
    library.write(language)
    library.validate()
    set_variant(language, template)
    library.write(language)
    assert_finding(library.validate(accepted=False), language, "R5",
                   "/layout/variants/listing-card/stacked/template", template)


@pytest.mark.parametrize("binding", ["absent:primary", "fixture-logo:absent"])
def test_missing_asset_or_variant_is_not_accepted(library, language, binding):
    library.validate()
    language["components"]["nav"]["assets"]["logo"] = binding
    library.write(language)
    assert_finding(library.validate(accepted=False), language, "R1",
                   "/components/nav/assets/logo", binding, "missing")


@pytest.mark.parametrize("malformed", json.loads((FIXTURES / "malformed-json.json").read_text()))
def test_malformed_json_is_a_schema_report(library, language, malformed):
    """User-edited malformed JSON produces a finding, not a traceback or success."""
    library.validate()
    library.path().write_text(malformed)
    report = library.validate(accepted=False)
    assert any(f["rule"] == "schema" and f["type"] == "violation" and
               f["file"] == "languages/tidal/working.json" for f in report["findings"]), report


def test_truncated_document_fuzz_reports_schema_instead_of_crashing(library, language):
    """T13 bounded grammar fuzz. Seed 20261107; every proper JSON-object prefix is incomplete."""
    library.validate()
    payload = json.dumps(language)
    for cut in random.Random(20261107).sample(range(1, len(payload)), 12):
        # Each run is a new process over an independently truncated original document.
        library.path().write_text(payload[:cut])
        report = library.validate(accepted=False)
        assert any(f["rule"] == "schema" and f["type"] == "violation"
                   for f in report["findings"]), (cut, report)


def test_missing_required_identity_is_schema_failure(library, language):
    library.validate()
    del language["id"]
    library.path().write_text(json.dumps(language))
    report = library.validate(accepted=False)
    assert_finding(report, language, "schema", "", language, {"missing", "violation"})


def test_unknown_language_is_usage_error(library):
    library.cli("validate", "no-such-language", code=2)
