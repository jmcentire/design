"""Amendment 10 / Q-0065: real word line boxes and label/value geometry.

All layout comes from validated language properties and public content. Read-only
browser measurements prove the seeded condition before the real check command.
The same text/pairs must pass when given sufficient room/closer own labels.
"""
import pytest

from tests.composition_support import (language_for_content, content_fixture, open_content,
                                       hook_scope, scope_selector, scope_properties, assert_only_rule)
from tests.content_support import save_content
from tests.m1_support import token
from tests.test_composition_shipped import composition_report, assert_composition_passes

pytestmark = [pytest.mark.browser, pytest.mark.browser_timeout(600)]
CHECK_WIDTHS = (375, 1280)
WORD = "Observations123456"
FACTS = [{"label": "A", "value": "1"}, {"label": "B", "value": "2"}, {"label": "C", "value": "3"}]


def word_layout(paragraph):
    """Each ASCII letter/digit gets its actual Range rect; wrappers cannot add lines."""
    return paragraph.evaluate("""e => {
      const tops=new Set(); let glyphs=0, totalWidth=0;
      const walker=document.createTreeWalker(e,NodeFilter.SHOW_TEXT);
      while(walker.nextNode()) {
        const node=walker.currentNode;
        for(let i=0;i<node.textContent.length;i++) {
          if(!/[a-zA-Z0-9]/.test(node.textContent[i])) continue;
          const range=document.createRange(); range.setStart(node,i); range.setEnd(node,i+1);
          const rects=[...range.getClientRects()].filter(r=>r.width>0 && r.height>0);
          if(rects.length) glyphs++;
          for(const r of rects) {tops.add(Math.round(r.top*1000)/1000);totalWidth+=r.width;}
        }
      }
      return {text:e.textContent.trim(),lines:tops.size,glyphs,totalWidth,
              width:e.getBoundingClientRect().width};
    }""")


def word_fixture(library, language, source, out, page, word):
    document = language_for_content(library, language)
    content = content_fixture(source, paragraph="Short section text")
    content["blocks"][0]["body"] = word
    save_content(source, content)
    contract = open_content(library, document, source, out, page)
    paragraph = page.get_by_text(word, exact=True)
    scope = hook_scope(paragraph)
    assert paragraph.evaluate("(e,s)=>e.localName==='p' && e.matches(s)", scope_selector(contract, scope)), scope
    props = scope_properties(document, scope)
    props.update({"width": token(document, "probe", "wordroom", "dimension", "240px"),
                  "max-width": "{probe.wordroom}"})
    return document, paragraph, scope


def test_avoidable_word_split_is_a_violation_and_same_text_with_room_passes(library, language, tmp_path, page):
    source = tmp_path / "content.json"
    document, paragraph, scope = word_fixture(library, language, source, tmp_path / "discover", page, WORD)
    narrow = token(document, "probe", "wordnarrow", "dimension", "64px")
    for label, broken in (("broken", True), ("room", False)):
        # The word fits at the smallest checked viewport. Narrowing its slot at
        # lg is avoidable, so the long-word exception cannot excuse the split.
        document["overrides"] = ([{"scope": scope + "@lg", "reason": "Independent avoidable word split",
                                    "properties": {"width": narrow, "max-width": narrow}}] if broken else [])
        open_content(library, document, source, tmp_path / label, page, width=375)
        for width in CHECK_WIDTHS:
            page.set_viewport_size({"width": width, "height": 900})
            observed = word_layout(paragraph)
            assert observed["text"] == WORD and observed["glyphs"] == len(WORD), observed
            if broken and width == 1280:
                assert observed["width"] == 64 and observed["lines"] > 1, observed
            else:
                assert observed["width"] == 240 and observed["lines"] == 1, observed
        report = composition_report(library, document["id"], tmp_path / (label + "-check"), source, widths=CHECK_WIDTHS)
        if broken:
            assert_only_rule(report, "word-break", document, {scope}, (1280,))
        else:
            assert_composition_passes(report)


def test_unavoidable_oversized_word_remains_visible_needs_review(library, language, tmp_path, page):
    source = tmp_path / "content.json"
    word = "W" * 300
    document, paragraph, scope = word_fixture(library, language, source, tmp_path / "discover", page, word)
    open_content(library, document, source, tmp_path / "oversized", page, width=375)
    for width in CHECK_WIDTHS:
        page.set_viewport_size({"width": width, "height": 900})
        observed = word_layout(paragraph)
        assert observed["text"] == word and observed["glyphs"] == len(word), observed
        assert observed["lines"] > 1 and observed["totalWidth"] > max(CHECK_WIDTHS), observed
    report = composition_report(library, document["id"], tmp_path / "oversized-check", source, widths=CHECK_WIDTHS)
    assert_only_rule(report, "word-break", document, {scope}, CHECK_WIDTHS, kind="needs-review")
    assert report["needs_review"] >= 1, report


def pair_gaps(facts, direction):
    boxes = facts.locator("dt,dd").evaluate_all("""els=>els.map(e=>{
      const r=e.getBoundingClientRect();return {tag:e.localName,text:e.textContent.trim(),
        left:r.left,right:r.right,top:r.top,bottom:r.bottom,width:r.width,height:r.height};
    })""")
    assert [box["tag"] for box in boxes] == ["dt", "dd"] * len(FACTS), boxes
    assert [box["text"] for box in boxes] == [text for fact in FACTS for text in (fact["label"], fact["value"])], boxes
    assert all(box["width"] > 0 and box["height"] > 0 for box in boxes), boxes
    start, end = ("top", "bottom") if direction == "column" else ("left", "right")
    gaps = []
    for index in range(0, len(boxes) - 2, 2):
        own, value, following = boxes[index:index + 3]
        # Row probes must actually share a line. Stacked definitions may have
        # an indented value; horizontal overlap is not a proximity requirement.
        if direction == "row":
            assert min(own["bottom"], value["bottom"], following["bottom"]) > max(
                own["top"], value["top"], following["top"]), boxes
        gaps.append((value[start] - own[end], following[start] - value[end]))
    assert len(gaps) == len(FACTS) - 1
    return gaps


@pytest.mark.parametrize("direction", ["column", "row"], ids=["stacked", "side-by-side"])
def test_value_is_closer_to_its_own_label_than_the_following_label(library, language, tmp_path, page, direction):
    document = language_for_content(library, language)
    source = tmp_path / "content.json"
    content = content_fixture(source, paragraph="Short section text")
    content["blocks"].append({"type": "collection", "title": "Facts",
                              "items": [{"title": "Pair probe", "facts": FACTS}]})
    save_content(source, content)
    contract = open_content(library, document, source, tmp_path / "discover", page)
    facts = page.locator("dl")
    assert facts.count() == 1
    facts_scope = hook_scope(facts)
    assert facts.evaluate("(e,s)=>e.matches(s)", scope_selector(contract, facts_scope)), facts_scope
    pairs = facts.locator('[data-kd-part="pair"]')
    assert pairs.count() == len(FACTS)
    owner = pairs.first.evaluate("e=>e.closest('[data-kd-construct]').dataset.kdConstruct")
    assert facts_scope.partition(".")[0] == owner
    pair_scope = owner + "~pair"
    assert scope_selector(contract, pair_scope) == '[data-kd-part="pair"]'
    published = library.json("hooks", "--vocabulary", document["vocabulary"])
    assert published["constructs"][owner]["parts"]["pair"] == contract["constructs"][owner]["parts"]["pair"]
    for pair in pairs.all():
        assert pair.locator("dt").count() == pair.locator("dd").count() == 1
    base = {"display": "flex", "flex-direction": direction, "align-items": "start",
            "justify-content": "start", "padding": "{space.zero}", "margin-block": "{space.zero}"}
    scope_properties(document, facts_scope).update({**base, "gap": "{space.sixteen}"})
    properties = scope_properties(document, pair_scope)
    properties.update(base)
    for label, inner in (("wrong-neighbour", 24), ("own-label", 8)):
        properties["gap"] = token(document, "space", "pairgap", "dimension", f"{inner}px")
        open_content(library, document, source, tmp_path / label, page, width=375)
        for width in CHECK_WIDTHS:
            page.set_viewport_size({"width": width, "height": 900})
            for own_gap, next_gap in pair_gaps(facts, direction):
                assert own_gap >= 0 and next_gap >= 0, (own_gap, next_gap)
                if inner == 24:
                    assert own_gap > next_gap, (own_gap, next_gap)
                else:
                    assert own_gap < next_gap, (own_gap, next_gap)
        report = composition_report(library, document["id"], tmp_path / (label + "-check"), source, widths=CHECK_WIDTHS)
        if inner == 24:
            assert_only_rule(report, "label-proximity", document, {facts_scope, pair_scope, owner}, CHECK_WIDTHS)
        else:
            assert_composition_passes(report)
