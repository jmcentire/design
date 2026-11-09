"""Amendment 09: measured source composition must survive in the saved language.

Real loopback HTTP capture -> draft -> save -> sample rendering/check. Authored
CSS constants, not draft summaries or fidelity contexts, supply expected values.
The public exclusion/correction records are pinned by clarification Q-0050.
"""
import pytest

from tests.content_browser_support import rgba
from tests.m2_support import capture, draft, dereference, dimension_px, token_values, color_distance
from tests.support import PAGES, pointer_value
from tests.test_composition_shipped import COMPOSITION_RULES, composition_report, assert_composition_passes
from tests.test_m2_capture import tree_hashes

pytestmark = [pytest.mark.browser, pytest.mark.browser_timeout(600)]
UTILITY = "#ff00ee"


def visible_rgb(value):
    """Return RGB for source-colour comparison; alpha zero contributes no colour.

    This is an evidence-origin check, not a contrast/compositing calculation.
    Any positive alpha retains its RGB even when it is less than one.
    """
    if isinstance(value, dict):
        if value.get("alpha", 1) == 0:
            return None
        assert value["colorSpace"] == "srgb"
        return "#" + "".join(f"{round(channel * 255):02x}" for channel in value["components"])
    value = value.lower()
    if value == "transparent":
        return None
    assert value.startswith("#") and len(value) in {4, 5, 7, 9}, value
    if len(value) in {4, 5}:
        value = "#" + "".join(channel * 2 for channel in value[1:])
    return None if len(value) == 9 and int(value[-2:], 16) == 0 else value[:7]


def configure_capture(library, ingest_config):
    ingest_config.update(widths=[375, 1280], capture_timeout_s=20)
    (library.project / "kinbase-design.toml").write_text(
        "[ingest]\n" + "\n".join(f"{key} = {value}" for key, value in ingest_config.items()) + "\n")


def css(locator, properties):
    assert locator.count(), "Missing rendered transfer target"
    return locator.first.evaluate(
        "(e, keys)=>Object.fromEntries(keys.map(k=>[k,getComputedStyle(e).getPropertyValue(k)]))", properties)


def source_page(fixture_site, *, position="fixed", sparse=False, correction=None):
    source = fixture_site.root / "composition" / "index.html"
    text = source.read_text()
    text = text.replace("position: fixed", "position: " + position)
    if sparse:
        text = text.replace("<h2>Recent observations</h2>", "<p>Recent observations</p>")
    if correction == "measure":
        # 720px at 16px type is 45em. Only the prose measure is outside the
        # contract: main remains 800px and all inset/target/type values comply.
        text = text.replace("max-width: 480px", "max-width: 720px")
    elif correction == "text-inset":
        # A background-only band removes the border-width ambiguity: four px
        # inset must become eight, the nearest compliant value.
        text = text.replace("border: 2px solid #2d4256; border-radius: 12px; padding: 24px",
                            "border: 0 solid #2d4256; border-radius: 12px; padding: 4px")
    source.write_text(text)
    return source, fixture_site.url + "/composition/index.html"


def derive(library, fixture_site, url, identity):
    artifact, root, captured = capture(library, [url])
    assert not captured["problems"], captured
    original = tree_hashes(root)
    fixture_site.available = False
    requests = len(fixture_site.requests)
    draft_root, document, summary = draft(library, [artifact], identity)
    assert isinstance(summary["excluded"], list)
    assert isinstance(summary["corrections"], list)
    assert len(fixture_site.requests) == requests, "draft revisited the source"
    assert tree_hashes(root) == original, "draft mutated capture evidence"
    return draft_root, document, summary, requests


def assert_correction_links(library, document, summary):
    questions = library.json("questions", document["id"], cwd=library.project)
    by_id = {question["id"]: question for question in questions}
    assert len(by_id) == len(questions)
    for correction in summary["corrections"]:
        assert {"rule", "pointer", "selector", "measured", "chosen", "question"} <= correction.keys()
        assert correction["rule"] in COMPOSITION_RULES, correction
        assert pointer_value(document, correction["pointer"]) == correction["chosen"], correction
        assert correction["question"] in by_id, correction
        candidates = by_id[correction["question"]]["candidates"]
        assert any(candidate["value"] == correction["measured"] for candidate in candidates), (
            "Correction question lost the measured alternative", correction, candidates)
        if correction["selector"] is None:
            assert correction["measured"] is None, correction
        else:
            assert isinstance(correction["selector"], str) and correction["selector"], correction
    return questions


def assert_utility_excluded(page, source, document, summary, position, tolerance):
    page.goto(source.as_uri())
    records = summary["excluded"]
    if position == "static":
        assert records == [], records
        assert any(color_distance(entry["value"], UTILITY) <= tolerance
                   for entry in summary["measured"]["palette"]), "In-flow positive control lost its measured color"
        return
    assert len(records) == 1, records
    entry = records[0]
    assert entry["reason"] == "out-of-flow" and entry["position"] == position
    assert set(entry["evidence"]) == {"color", "role", "treatment"}
    selected = page.locator(entry["selector"])
    assert selected.count() == 1 and selected.get_attribute("id") == "utility", entry
    assert css(selected, ["position"])["position"] == position
    for entry in summary["measured"]["palette"]:
        color = visible_rgb(entry["value"])
        assert color is None or color_distance(color, UTILITY) > tolerance, summary
    # Check actual draft tokens and role references as well as the reporting
    # palette. An honest exclusion record cannot excuse a contaminated language.
    colors = [visible_rgb(dereference(document["style"], value))
              for _, kind, value in token_values(document["style"]) if kind == "color"]
    assert colors and all(color is None or color_distance(color, UTILITY) > tolerance for color in colors), colors
    for role in document["roles"].values():
        for properties in role.values():
            for key in ("color", "surface", "background-color", "border-color"):
                if key in properties:
                    value = visible_rgb(dereference(document["style"], properties[key]))
                    assert value is None or color_distance(value, UTILITY) > tolerance, (key, value)


def assert_source_measurements(page, url, sparse):
    page.set_viewport_size({"width": 1280, "height": 1000})
    page.goto(url)
    assert page.locator("main").bounding_box()["width"] == 800
    assert page.locator("#prose").bounding_box()["width"] == 480
    assert css(page.locator("h1"), ["font-size"])["font-size"] == "32px"
    assert css(page.locator("h3"), ["font-size"])["font-size"] == "20px"
    assert page.locator("h2").count() == (0 if sparse else 1)
    if not sparse:
        assert css(page.locator("h2"), ["font-size"])["font-size"] == "24px"
    for selector, padding, gap in ((".item", "16px", "12px"), (".actions", "12px", "8px")):
        assert css(page.locator(selector), ["padding-left", "gap"]) == {"padding-left": padding, "gap": gap}


def assert_saved_transfer(library, document, tmp_path, page, sparse, tolerance):
    library.cli("save-draft", document["id"], cwd=library.project, timeout=90)
    assert library.read(document["id"]) == document
    preview = library.build(tmp_path / "saved-preview", document["id"])
    page.set_viewport_size({"width": 1280, "height": 1000})
    seen = set()
    for name in PAGES:
        page.goto((preview / name).as_uri())
        page.evaluate("document.fonts.ready")
        for heading in page.locator("h1,h2,h3").all():
            if not heading.is_visible():
                continue
            level = heading.evaluate("e=>Number(e.tagName.slice(1))")
            size = float(css(heading, ["font-size"])["font-size"].removesuffix("px"))
            if level == 2 and sparse:
                assert 20 < size < 32, (name, level, size, "Absent level must interpolate between measured neighbours")
            else:
                assert size == pytest.approx({1: 32, 2: 24, 3: 20}[level], abs=1), (name, level, size)
            seen.add(f"heading-{level}")
        # State examples are inset within demonstration frames; only ordinary
        # pages exercise transfer of the page's own container width.
        if name != "states.html":
            main = page.locator('[data-kd-construct="page-shell"]')
            for element in main.all():
                assert element.bounding_box()["width"] == pytest.approx(800, abs=1), name
                seen.add("column")
        paragraphs = page.locator("p")
        for paragraph in paragraphs.all():
            if paragraph.is_visible() and len(paragraph.inner_text().strip()) >= 60:
                assert paragraph.bounding_box()["width"] <= 481, (name, paragraph.inner_text())
                seen.add("prose")
        hero = page.locator('[data-kd-construct="hero"]')
        for element in hero.all():
            actual = css(element, ["background-color", "border-top-color", "border-top-width", "border-top-style",
                                   "border-top-left-radius", "padding-top", "padding-right", "padding-bottom", "padding-left"])
            for prop, color in (("background-color", "#e3edf5"), ("border-top-color", "#2d4256")):
                channels, alpha = rgba(actual[prop])
                assert alpha == 1
                hex_color = "#" + "".join(f"{round(channel):02x}" for channel in channels)
                assert color_distance(hex_color, color) <= tolerance, actual
            assert actual["border-top-width"] == "2px" and actual["border-top-style"] == "solid", actual
            assert actual["border-top-left-radius"] == "12px", actual
            assert all(actual["padding-" + side] == "24px" for side in ("top", "right", "bottom", "left")), actual
            seen.add("hero-surface")
            actions = element.locator("a[href]")
            if actions.count() >= 2:
                # Find the common rendered ancestor of the first two actual
                # targets. No part name or variant wrapper structure is pinned.
                values = element.evaluate("""e=>{
                  const [a,b]=e.querySelectorAll('a[href]'); let p=a.parentElement;
                  while(!p.contains(b)) p=p.parentElement;
                  const s=getComputedStyle(p); return {padding:s.paddingLeft,gap:s.gap};
                }""")
                assert values == {"padding": "12px", "gap": "8px"}, values
                seen.add("action-group")
        for card in page.locator('[data-kd-construct="card"]').all():
            values = css(card, ["padding-top", "padding-right", "padding-bottom", "padding-left", "gap"])
            assert values == {**{"padding-" + side: "16px" for side in ("top", "right", "bottom", "left")}, "gap": "12px"}, values
            seen.add("card-spacing")
        for link in page.locator('[data-kd-slot="nav.links"] a, a[data-kd-slot="nav.links"]').all():
            values = css(link, ["color", "background-color", "border-top-width", "text-decoration-line"])
            channels, alpha = rgba(values["color"])
            color = "#" + "".join(f"{round(channel):02x}" for channel in channels)
            assert alpha == 1 and color_distance(color, "#173e8f") <= tolerance, values
            assert rgba(values["background-color"])[1] == 0, values
            assert values["border-top-width"] == "0px" and "underline" in values["text-decoration-line"], values
            seen.add("navigation")
    assert {"heading-1", "heading-2", "column", "prose", "hero-surface", "action-group", "card-spacing", "navigation"} <= seen, seen
    report = composition_report(library, document["id"], tmp_path / "saved-check", widths=(375, 1280))
    assert_composition_passes(report)


@pytest.mark.parametrize("sparse", [False, True], ids=["measured-levels", "interpolated-level"])
def test_ingest_transfers_composition_to_saved_samples(library, fixture_site, ingest_config, tmp_path, page, sparse):
    configure_capture(library, ingest_config)
    source, url = source_page(fixture_site, sparse=sparse)
    assert_source_measurements(page, url, sparse)
    _, document, summary, requests = derive(library, fixture_site, url, "composed-source")
    assert_utility_excluded(page, source, document, summary, "fixed", ingest_config["color_delta_e"])
    assert_correction_links(library, document, summary)
    if sparse:
        interpolated = [c for c in summary["corrections"] if c["selector"] is None and c["rule"] == "heading-scale"]
        assert interpolated, "Absent heading level was not disclosed as interpolation"
        assert any(20 < dimension_px(dereference(document["style"], c["chosen"])) < 32 for c in interpolated), interpolated
    assert_saved_transfer(library, document, tmp_path, page, sparse, ingest_config["color_delta_e"])
    assert len(fixture_site.requests) == requests, "Saved-language operations fetched the source"


@pytest.mark.parametrize("position", ["sticky", "static"])
def test_exclusion_distinguishes_out_of_flow_from_visible_in_flow_evidence(library, fixture_site, ingest_config, page, position):
    configure_capture(library, ingest_config)
    source, url = source_page(fixture_site, position=position)
    _, document, summary, _ = derive(library, fixture_site, url, "position-source")
    assert_utility_excluded(page, source, document, summary, position, ingest_config["color_delta_e"])
    assert_correction_links(library, document, summary)


@pytest.mark.parametrize("rule,measured,chosen,selector", [
    ("measure", "720px", 640, "#prose"),
    ("text-inset", "4px", 8, "#leading"),
])
def test_ingest_discloses_nearest_compliant_replacement_and_keeps_measured_choice(
        library, fixture_site, ingest_config, tmp_path, page, rule, measured, chosen, selector):
    configure_capture(library, ingest_config)
    source, url = source_page(fixture_site, correction=rule)
    page.set_viewport_size({"width": 1280, "height": 1000})
    page.goto(url)
    property_name = "max-width" if rule == "measure" else "padding-left"
    assert css(page.locator(selector), [property_name])[property_name] == measured
    _, document, summary, requests = derive(library, fixture_site, url, "corrected-source")
    assert_correction_links(library, document, summary)
    candidates = [c for c in summary["corrections"] if c["rule"] == rule and c["measured"] == measured]
    assert candidates, ("Unsafe source treatment changed without explicit evidence/question", summary)
    page.goto(source.as_uri())
    for correction in candidates:
        assert correction["selector"] is not None
        selected = page.locator(correction["selector"])
        assert selected.count() and css(selected, [property_name])[property_name] == measured, correction
        assert dimension_px(dereference(document["style"], correction["chosen"])) == pytest.approx(chosen, abs=0.01), correction
    library.cli("save-draft", document["id"], cwd=library.project, timeout=90)
    report = composition_report(library, document["id"], tmp_path / "corrected-check", widths=(375, 1280))
    assert_composition_passes(report)
    assert len(fixture_site.requests) == requests
