"""Addendum 11b: long prose fails only below both 15em and 2/3 of its column."""
import math

import pytest

from tests.composition_support import (language_for_content, content_fixture, open_content,
                                       hook_scope, common_hook_scope, scope_selector, scope_properties, assert_only_rule)
from tests.content_support import save_content
from tests.m1_support import token
from tests.test_composition_shipped import composition_report, assert_composition_passes

pytestmark = [pytest.mark.browser, pytest.mark.browser_timeout(420)]
WIDTHS = (375, 768, 1280)


def assert_lower_measure_evidence(report, observations):
    """Require the public measurement fields to agree with independent geometry."""
    findings = [finding for finding in report["findings"]
                if finding["rule"] == "measure" and finding["type"] == "violation"]
    assert findings, report
    for finding in findings:
        measured = finding["measured"]
        assert isinstance(measured, dict), finding
        assert {"width", "font_size", "em", "characters", "column_width", "column", "column_kind"} <= measured.keys(), finding
        for key in ("width", "font_size", "em", "characters", "column_width"):
            assert type(measured[key]) in {int, float} and math.isfinite(measured[key]) and measured[key] > 0, finding
        assert measured["column"] and measured["column_kind"], finding
        expected = observations[finding["width"]]
        for key, value in expected.items():
            assert measured[key] == pytest.approx(value, abs=0.05), (finding, expected)
        assert measured["em"] == pytest.approx(measured["width"] / measured["font_size"], abs=0.01), finding
        assert measured["characters"] >= 60, finding
        assert measured["width"] < 15 * measured["font_size"], finding
        assert measured["width"] < 2 * measured["column_width"] / 3, finding


def containing_column(paragraph):
    """Observe the clarified column independently of the check report.

    The paragraph itself is not its own ancestor. A grid item or row-flex item
    needs a visible peer beside it on the same row. Stacks are not columns.
    """
    return paragraph.evaluate("""e=>{
      const items=parent=>[...parent.children].flatMap(node=>
        getComputedStyle(node).display==='contents'?items(node):[node]);
      const visible=node=>{
        const r=node.getBoundingClientRect(), s=getComputedStyle(node);
        return r.width>0 && r.height>0 && !['hidden','collapse'].includes(s.visibility)
          && Number(s.opacity)>0 && !['absolute','fixed'].includes(s.position);
      };
      for(let node=e.parentElement;node;node=node.parentElement) {
        let parent=node.parentElement;
        while(parent && getComputedStyle(parent).display==='contents') parent=parent.parentElement;
        if(!parent) continue;
        const layout=getComputedStyle(parent), style=getComputedStyle(node);
        const grid=['grid','inline-grid'].includes(layout.display);
        const row=['flex','inline-flex'].includes(layout.display)
          && ['row','row-reverse'].includes(layout.flexDirection);
        if(!(grid || row) || style.display==='contents' || !visible(node)) continue;
        const box=node.getBoundingClientRect();
        const beside=items(parent).some(peer=>{
          if(peer===node || !visible(peer)) return false;
          const p=peer.getBoundingClientRect();
          return Math.min(box.bottom,p.bottom)>Math.max(box.top,p.top)
            && (p.left>=box.right-0.05 || box.left>=p.right-0.05);
        });
        if(beside) return {kind:grid?'grid':'flex',width:box.width};
      }
      const main=e.closest('main,[role="main"]') || document.querySelector('main,[role="main"]');
      if(!main) throw new Error('Paragraph has no main landmark');
      const s=getComputedStyle(main);
      const inset=['paddingLeft','paddingRight','borderLeftWidth','borderRightWidth']
        .reduce((sum,key)=>sum+parseFloat(s[key]),0);
      return {kind:'main',width:main.getBoundingClientRect().width-inset};
    }""")


@pytest.mark.parametrize("characters", [59, 60])
@pytest.mark.parametrize("font_size", [16, 18])
@pytest.mark.parametrize("bad_width", [375, 1280])
def test_measure_lower_bound_requires_both_small_type_measure_and_column_fraction(
        library, language, tmp_path, page, characters, font_size, bad_width):
    document = language_for_content(library, language)
    document["style"]["size"]["body"]["$value"] = {"value": font_size, "unit": "px"}
    source = tmp_path / "content.json"
    text = ("A small note " * 6)[:characters - 1] + "."
    assert len(text) == characters
    content = content_fixture(source, paragraph="Short section text")
    content["blocks"][0]["body"] = text
    save_content(source, content)
    contract = open_content(library, document, source, tmp_path / "discover", page)
    paragraph = page.get_by_text(text, exact=True)
    scope = hook_scope(paragraph)
    assert paragraph.evaluate("(e,s)=>e.localName==='p' && e.matches(s)", scope_selector(contract, scope)), scope
    limit = 15 * font_size
    room = token(document, "probe", "minimummeasure", "dimension", f"{limit}px")
    narrow = token(document, "probe", "belowminimum", "dimension", "64px")
    for label, squeezed in (("squeezed", True), ("room", False)):
        base = narrow if squeezed and bad_width == 375 else room
        scope_properties(document, scope).update({"width": base, "max-width": base})
        breakpoint, override = ("md", room) if bad_width == 375 else ("lg", narrow)
        document["overrides"] = ([{
            "scope": scope + "@" + breakpoint, "reason": "Independent lower measure boundary",
            "properties": {"width": override, "max-width": override}}] if squeezed else [])
        open_content(library, document, source, tmp_path / label, page)
        main = page.locator(contract["content_pages"]["landmarks"]["main"])
        assert main.count() == 1
        observations = {}
        for width in WIDTHS:
            page.set_viewport_size({"width": width, "height": 900})
            observed = paragraph.evaluate("""e=>({width:e.getBoundingClientRect().width,
              font:parseFloat(getComputedStyle(e).fontSize),text:e.textContent.trim()})""")
            expected_width = 64 if squeezed and width == bad_width else limit
            assert observed == {"width": expected_width, "font": font_size, "text": text}, observed
            column = containing_column(paragraph)
            assert column["kind"] == "main", column
            assert column["width"] > limit, ("Fixture column must exceed the type-based threshold", column)
            if squeezed and width == bad_width:
                assert observed["width"] < column["width"] / 3
            observations[width] = {"width": observed["width"], "font_size": font_size,
                                   "characters": characters, "column_width": column["width"]}
        report = composition_report(library, document["id"], tmp_path / (label + "-check"), source, widths=WIDTHS)
        if squeezed and characters == 60:
            assert_only_rule(report, "measure", document, {scope}, (bad_width,))
            assert_lower_measure_evidence(report, observations)
        else:
            assert_composition_passes(report)


def test_long_paragraph_spans_main_when_main_is_narrower_than_fifteen_em(
        library, language, tmp_path, page):
    document = language_for_content(library, language)
    document["style"]["size"]["body"]["$value"] = {"value": 24, "unit": "px"}
    # Remove authored component insets so the paragraph and containing main
    # column have the same available width. No viewport or DOM CSS is injected.
    for component in document["components"].values():
        component["properties"].update({"padding": "{space.zero}", "margin-inline": "{space.zero}"})
    source = tmp_path / "content.json"
    text = "A small note " * 6
    content = content_fixture(source, paragraph="Short section text")
    content["blocks"][0]["body"] = text.strip()
    save_content(source, content)
    contract = open_content(library, document, source, tmp_path / "discover", page, width=320)
    paragraph = page.get_by_text(text.strip(), exact=True)
    scope = hook_scope(paragraph)
    assert paragraph.evaluate("(e,s)=>e.localName==='p' && e.matches(s)", scope_selector(contract, scope))
    main = page.locator(contract["content_pages"]["landmarks"]["main"])
    assert main.count() == 1
    props = scope_properties(document, scope)
    for label in ("squeezed", "spanning"):
        if label == "squeezed":
            props.update({"width": token(document, "probe", "toosmall", "dimension", "80px"),
                          "max-width": "{probe.toosmall}"})
        else:
            props.pop("width", None)
            props.pop("max-width", None)
        open_content(library, document, source, tmp_path / label, page, width=320)
        column = containing_column(paragraph)
        assert column["kind"] == "main", column
        column_width = column["width"]
        assert 120 < column_width < 15 * 24, column_width
        assert paragraph.evaluate("e=>getComputedStyle(e).fontSize") == "24px"
        assert paragraph.bounding_box()["width"] == pytest.approx(
            80 if label == "squeezed" else column_width, abs=0.05)
        report = composition_report(library, document["id"], tmp_path / (label + "-check"), source, widths=(320,))
        if label == "squeezed":
            assert_only_rule(report, "measure", document, {scope}, (320,))
            assert_lower_measure_evidence(report, {320: {"width": 80, "font_size": 24,
                "characters": len(text.strip()), "column_width": column_width}})
        else:
            assert_composition_passes(report)


def test_padded_panel_below_fifteen_em_but_above_two_thirds_passes_at_320(
        library, language, tmp_path, page):
    document = language_for_content(library, language)
    source = tmp_path / "content.json"
    text = "A small note keeps a clear record of the day and gives each later visit a point of comparison."
    content = content_fixture(source, paragraph="Short section text")
    content["blocks"][0]["body"] = text
    save_content(source, content)
    contract = open_content(library, document, source, tmp_path / "discover", page, width=320)
    paragraph = page.get_by_text(text, exact=True)
    scope = hook_scope(paragraph)
    owner = scope.partition(".")[0]
    assert paragraph.evaluate("(e,s)=>e.localName==='p' && e.matches(s)", scope_selector(contract, scope))
    scope_properties(document, owner).update({
        "display": "block", "width": token(document, "probe", "panel", "dimension", "256px"),
        "max-width": "{probe.panel}", "padding": "{space.sixteen}",
        "border-width": "{space.zero}", "background-color": "{color.panel}"})
    transparent = token(document, "color", "transparent", "color", "#00000000")
    for part in contract["constructs"][owner]["parts"]:
        scope_properties(document, owner + "~" + part).update({
            "display": "block", "padding": "{space.zero}", "margin-inline": "{space.zero}",
            "background-color": transparent, "border-width": "{space.zero}"})
    for slot in document["components"][owner]["slots"].values():
        slot["properties"].update({"padding": "{space.zero}", "background-color": transparent,
                                   "border-width": "{space.zero}"})
    scope_properties(document, scope).update({
        "width": token(document, "probe", "panelprose", "dimension", "224px"),
        "max-width": "{probe.panelprose}"})
    open_content(library, document, source, tmp_path / "panel", page, width=320)
    panel = page.locator(scope_selector(contract, owner))
    assert panel.bounding_box()["width"] == 256
    assert panel.evaluate("e=>getComputedStyle(e).paddingLeft") == "16px"
    assert paragraph.bounding_box()["width"] == 224
    assert paragraph.evaluate("e=>getComputedStyle(e).fontSize") == "16px"
    column = containing_column(paragraph)
    assert column["kind"] == "main" and column["width"] >= 256, column
    assert 2 * column["width"] / 3 < 224 < 15 * 16, column
    report = composition_report(library, document["id"], tmp_path / "panel-check", source, widths=(320,))
    assert_composition_passes(report)


@pytest.mark.parametrize("layout", ["grid", "flex"])
def test_grid_or_flex_column_fraction_distinguishes_ordinary_and_excessive_padding(
        library, language, tmp_path, page, layout):
    document = language_for_content(library, language)
    source = tmp_path / "content.json"
    content = content_fixture(source, paragraph="Short section text")
    text = "A small note keeps a clear record of the day and gives each later visit a point of comparison."
    assert len(text) >= 60
    content["blocks"].append({"type": "collection", "title": "Notes", "items": [
        {"title": "One", "body": text}, {"title": "Two", "body": text}]})
    save_content(source, content)
    contract = open_content(library, document, source, tmp_path / "discover", page)
    owner = contract["content_pages"]["blocks"]["collection"]["item"]
    items = page.locator(scope_selector(contract, owner))
    assert items.count() == 2
    group_scope = common_hook_scope(items)
    scope_selector(contract, group_scope)
    group = scope_properties(document, group_scope)
    group.update({"display": layout, "gap": "{space.sixteen}", "align-items": "start"})
    if layout == "flex":
        group.update({"flex-direction": "row", "flex-wrap": "nowrap"})
    props = scope_properties(document, owner)
    props.update({"display": "block", "border-width": "{space.zero}", "margin-inline": "{space.zero}"})
    # Make the card's border box the relevant column, without an intervening
    # flex/grid part that could legitimately become a nearer ancestor column.
    for part in contract["constructs"][owner]["parts"]:
        scope_properties(document, owner + "~" + part).update({"display": "block", "padding": "{space.zero}"})
    for slot in document["components"][owner]["slots"].values():
        slot["properties"].update({"display": "block", "padding": "{space.zero}", "margin-block": "{space.zero}"})
    paragraphs = page.get_by_text(text, exact=True)
    assert paragraphs.count() == 2
    scopes = {hook_scope(paragraph) for paragraph in paragraphs.all()}
    # Both 240px items and their gap fit at these viewports. Keeping them on
    # the same row is part of the fixture, not a side effect of overflow.
    checked_widths = (768, 1280)
    for label, width, padding in (("narrow-exempt", 200, 0), ("stacked-not-column", 200, 0),
                                  ("ordinary-padding", 240, 24), ("two-thirds", 240, 40),
                                  ("padding-squeeze", 240, 41), ("full-measure", 240, 0)):
        stacked = label == "stacked-not-column"
        column_ref = token(document, "probe", "itemcolumn", "dimension", f"{width}px")
        props.update({"width": column_ref, "max-width": column_ref,
                      "padding": token(document, "space", "iteminset", "dimension", f"{padding}px")})
        if layout == "grid":
            group["grid-template-columns"] = column_ref if stacked else f"repeat(2, {column_ref})"
        else:
            group["flex-direction"] = "column" if stacked else "row"
        open_content(library, document, source, tmp_path / label, page)
        observations = {}
        for viewport in checked_widths:
            page.set_viewport_size({"width": viewport, "height": 900})
            main = page.locator(contract["content_pages"]["landmarks"]["main"])
            assert main.bounding_box()["width"] > 240
            a, b = [item.bounding_box() for item in items.all()]
            if stacked:
                assert a["x"] == pytest.approx(b["x"], abs=0.05), (a, b)
                assert b["y"] - a["y"] - a["height"] == pytest.approx(16, abs=0.05), (a, b)
            else:
                assert a["y"] == pytest.approx(b["y"], abs=0.05), (a, b)
                assert b["x"] - a["x"] - a["width"] == pytest.approx(16, abs=0.05), (a, b)
                assert 0 <= a["x"] < b["x"] and b["x"] + b["width"] <= viewport, (a, b)
            for paragraph in paragraphs.all():
                assert paragraph.evaluate("e=>e.localName==='p' && getComputedStyle(e).fontSize==='16px'")
                column = containing_column(paragraph)
                if stacked:
                    assert column["kind"] == "main" and column["width"] > 240, column
                else:
                    assert column == {"kind": layout, "width": width}, column
                assert paragraph.bounding_box()["width"] == pytest.approx(width - 2 * padding, abs=0.05)
                observations[viewport] = {"width": width - 2 * padding, "font_size": 16,
                                           "characters": len(text), "column_width": column["width"]}
                fails = (width - 2 * padding < 240 and width - 2 * padding < 2 * column["width"] / 3)
                assert fails is (label in {"padding-squeeze", "stacked-not-column"}), (label, column)
        report = composition_report(library, document["id"], tmp_path / (label + "-check"), source, widths=checked_widths)
        if label in {"padding-squeeze", "stacked-not-column"}:
            assert_only_rule(report, "measure", document, scopes, checked_widths)
            assert_lower_measure_evidence(report, observations)
        else:
            assert_composition_passes(report)
