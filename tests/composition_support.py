"""Authored composition inputs and observations through public render/check APIs."""
import json

from tests.content_support import render_result, save_content
from tests.m1_support import token
from tests.support import FIXTURES, package_asset, pointer_value
from tests.test_composition_shipped import COMPOSITION_RULES, PARAGRAPH, assert_word_break_measurements


def language_for_content(library, document):
    """Complete the independent language with the newest public vocabulary ids.

    The vocabulary supplies semantic membership only; every presentation value
    below is authored by this suite. No shipped treatment supplies the oracle.
    """
    vocabulary = library.json("vocabulary")
    document["vocabulary"] = vocabulary["version"]
    for name, value in (("zero", 0), ("one", 1), ("eight", 8), ("sixteen", 16)):
        token(document, "space", name, "dimension", f"{value}px")
    token(document, "probe", "column", "dimension", "928px")
    token(document, "probe", "measure", "dimension", "640px")
    token(document, "color", "panel", "color", "#e8e8e8")
    document["roles"] = {
        role: {emphasis: {"color": "{color.ink}", "surface": "{color.paper}",
                         "font-family": "{type.family}", "font-size": "{size.body}",
                         "font-weight": "{type.weight}", "line-height": "{type.leading}"}
               for emphasis in vocabulary["emphasis"]}
        for role in vocabulary["roles"]}
    # Paint the interactive elements themselves, as required by separation's
    # antecedent. A painted noninteractive wrapper alone is not sufficient.
    for properties in document["roles"]["action"].values():
        properties.update({"background-color": "{color.panel}", "surface": "{color.panel}",
                           "border-style": "solid", "border-width": "{space.one}",
                           "border-color": "{color.ink}", "padding": "{space.eight}"})
    document["components"] = {}
    for identity, definition in vocabulary["constructs"].items():
        component = {"variant": "default", "properties": {
            "display": "flex", "flex-direction": "column", "gap": "{space.sixteen}",
            "padding": "{space.sixteen}", "max-width": "{probe.column}",
            "margin-inline": "auto"}, "slots": {}, "assets": {}}
        for slot in definition["slots"]:
            props = {"font-size": "{size.body}", "margin-block": "{space.zero}",
                     "max-width": "{probe.measure}"}
            if slot["kind"] == "action":
                props.update({"display": "flex", "flex-direction": "column", "gap": "{space.eight}"})
            component["slots"][slot["id"]] = {"properties": props}
            if slot["kind"] == "media":
                kind = slot.get("asset_kind", "image")
                asset_id = f"fixture-{kind}"
                package_asset(library, document, asset_id, kind, (FIXTURES / "mark.svg").read_bytes())
                component["assets"][slot["id"]] = f"{asset_id}:primary"
        document["components"][identity] = component
    library.write(document)
    library.validate(document["id"])
    return document


def content_fixture(path, paragraph=PARAGRAPH, actions=False):
    document = {"schema": "kinbase-content/1", "page": {"title": "Composition fixture"},
                "site": {"name": "Example Observatory", "nav": []},
                "blocks": [{"type": "hero", "title": "Leading heading", "body": "Short introduction"},
                           {"type": "section", "id": "reading", "title": "Second heading",
                            "content": [{"paragraph": paragraph}]}],
                "footer": {"text": "Synthetic footer"}}
    if actions:
        document["blocks"][0]["actions"] = [{"text": "One", "href": "#reading"},
                                            {"text": "Two", "href": "#reading"}]
    save_content(path, document)
    return document


def open_content(library, document, source, out, page, width=1280):
    library.write(document)
    render_result(library, source, out, document["id"])
    page.set_viewport_size({"width": width, "height": 900})
    page.goto((out / "index.html").as_uri())
    page.evaluate("document.fonts.ready")
    return json.loads((out / "hooks.json").read_text())


HOOK_SCOPE_JS = """e => {
  const hook=e.closest('[data-kd-slot],[data-kd-part],[data-kd-construct]');
  if(!hook) throw new Error('No semantic hook owns the fixture target');
  if(hook.hasAttribute('data-kd-slot')) return hook.dataset.kdSlot;
  if(hook.hasAttribute('data-kd-part')) {
    const owner=hook.closest('[data-kd-construct]');
    if(!owner) throw new Error('Part has no construct owner');
    return owner.dataset.kdConstruct+'~'+hook.dataset.kdPart;
  }
  return hook.dataset.kdConstruct;
}"""


def hook_scope(locator):
    # Individual content retains its semantic slot owner. Structural parts are
    # considered separately when locating a group that contains two targets.
    return locator.evaluate("""e => {
      const slot=e.closest('[data-kd-slot]');
      if(slot) return slot.dataset.kdSlot;
      return e.closest('[data-kd-construct]').dataset.kdConstruct;
    }""")


def common_hook_scope(targets):
    """Find the nearest hook containing both targets, including published parts."""
    assert targets.count() == 2, "The separation fixture requires exactly two targets"
    return targets.evaluate_all("""els => {
      let common=els[0].parentElement;
      while(common && !common.contains(els[1])) common=common.parentElement;
      if(!common) throw new Error('Targets do not share an ancestor');
      return (""" + HOOK_SCOPE_JS + """)(common);
    }""")


def scope_selector(contract, scope):
    """Validate discovered membership against the bundle's public hooks contract."""
    if "~" in scope:
        construct, part = scope.split("~", 1)
        return contract["constructs"][construct]["parts"][part]["selector"]
    construct, dot, slot = scope.partition(".")
    definition = contract["constructs"][construct]
    return definition["slots"][slot]["selector"] if dot else definition["selector"]


def scope_properties(document, scope):
    if "~" in scope:
        construct, part = scope.split("~", 1)
        return document["components"][construct].setdefault("parts", {}).setdefault(part, {})
    construct, dot, slot = scope.partition(".")
    component = document["components"][construct]
    return component["slots"][slot]["properties"] if dot else component["properties"]


def scope_pointer(scope):
    escape = lambda text: text.replace("~", "~0").replace("/", "~1")
    if "~" in scope:
        construct, part = scope.split("~", 1)
        return "/components/" + escape(construct) + "/parts/" + escape(part)
    construct, dot, slot = scope.partition(".")
    return "/components/" + escape(construct) + ("/slots/" + escape(slot) if dot else "")


def assert_only_rule(report, rule, document, scopes, widths, kind="violation"):
    if rule == "word-break":
        assert_word_break_measurements(report)
    problems = [f for f in report["findings"] if f["rule"] in COMPOSITION_RULES]
    assert problems, ("Seeded composition defect was not reported", rule, report)
    assert {f["rule"] for f in problems} == {rule}, problems
    if kind == "violation":
        assert report["accepted"] is False, report
    observed_widths = set()
    for finding in problems:
        assert finding["type"] == kind, finding
        if kind == "violation":
            assert not finding.get("exception"), finding
        assert finding["target"] in scopes, finding
        expected = scope_pointer(finding["target"])
        # The amendment identifies the offending construct/slot, without fixing
        # whether its pointer includes the particular property. Both must resolve
        # within that same construct/slot, never an unrelated token or element.
        assert finding["pointer"] == expected or finding["pointer"].startswith(expected + "/"), finding
        assert finding["file"] == f'languages/{document["id"]}/working.json', finding
        pointer_value(document, finding["pointer"])
        assert finding["measured"] is not None, finding
        assert finding["page"] in report["checked"]["pages"], finding
        assert finding["width"] in widths, finding
        occurrences = finding["occurrences"]
        assert occurrences, finding
        for occurrence in occurrences:
            assert occurrence["page"] in report["checked"]["pages"], occurrence
            assert occurrence["width"] in widths, occurrence
            observed_widths.add(occurrence["width"])
    assert observed_widths == set(widths), (observed_widths, widths, problems)
