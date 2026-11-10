"""M2 B15: complete no-JS ingest through real visible forms and links.

Only /ingest and the existing language viewer/grid routes are pinned. Intermediate
routes come from rendered links/forms. The CLI is used by server fixtures, never
to execute an ingest step. Persisted public artifacts establish each effect.
"""

import json
import re

import pytest
from playwright.sync_api import expect

from tests.browser_support import link_at
from tests.m2_support import assert_provenance, draft, read_json
from tests.support import FIXTURES
from tests.test_language_revision import presentation_hashes
from tests.test_versions_assets import expected_hash

pytestmark = [pytest.mark.browser, pytest.mark.browser_timeout(420)]


def visible(locator):
    return [locator.nth(i) for i in range(locator.count()) if locator.nth(i).is_visible()]


def submit(page, form, button=None):
    assert form.get_attribute("method").lower() == "post"
    if button is None:
        button = form.locator('button[type="submit"],button:not([type]),input[type="submit"]').first
    with page.expect_navigation(wait_until="load", timeout=90000) as navigation:
        button.click(no_wait_after=True)
    response = navigation.value
    assert response is not None and response.ok
    # M2 explicitly promises POST/redirect/GET; a redirect alone is not evidence
    # of completion (the caller separately checks persisted state).
    assert response.request.method == "GET" and response.request.redirected_from is not None


def activate(page, label):
    """Find a user-visible operation; no private route, class or template coupling."""
    pattern = re.compile(label, re.I)
    buttons = visible(page.get_by_role("button", name=pattern))
    if buttons:
        button = buttons[0]
        form = button.locator("xpath=ancestor::form[1]")
        assert form.count(), "A no-JS operation needs a form"
        submit(page, form, button)
        return
    links = visible(page.get_by_role("link", name=pattern))
    assert links, ("Missing visible ingest operation", label)
    with page.expect_navigation(wait_until="load", timeout=90000):
        links[0].click(no_wait_after=True)


def assert_live_images(page, minimum):
    images = visible(page.locator("img"))
    assert len(images) >= minimum
    assert all(image.evaluate("e => e.complete && e.naturalWidth > 0 && e.naturalHeight > 0") for image in images)
    for image in images:
        box = image.bounding_box()
        assert box and box["width"] > 0 and box["height"] > 0


def choice_controls(page):
    def post_controls(locator):
        result = []
        for control in visible(locator):
            form = control.locator("xpath=ancestor::form[1]")
            if form.count() and (form.get_attribute("method") or "get").lower() == "post":
                result.append(control)
        return result

    radios = post_controls(page.locator('input[type="radio"]'))
    selects = [select for select in post_controls(page.locator("select"))
               if 2 <= len([value for value in select.locator("option").evaluate_all("els => els.map(e => e.value)") if value]) <= 4]
    buttons = post_controls(page.get_by_role("button", name=re.compile(r"choose|select|pick|use.*candidate", re.I)))
    return radios, selects, buttons


def test_palette_groups_named_shades_without_changing_language_or_render(
        server, library, ingest_config, tmp_path, page):
    # Display-only contract: explicit names establish scales; numeric shade
    # order is not lexicographic. Ambiguous/opaque names must not invent a scale.
    source = read_json(FIXTURES / "ingest-tokens.json")
    source["color"].update({
        "blue": {"900": {"$value": "#123456"}, "50": {"$value": "#eaf3ff"},
                 "100": {"$value": "{color.ink}"}, "200": {"$value": "#33669980"}},
        "node_9_9": {"$value": "#eeeeee", "$extensions": {"figma": {"name": "Neutral / 50"}}},
        "node_8_8": {"$value": "#777777", "$extensions": {"figma": {"name": "Neutral / 900"}}},
        "green-100": {"$value": "#27885d"}, "teal-200": {"$value": "#27885d"},
        "node_4_5": {"$value": "#b65c82", "$extensions": {"figma": {"name": "Rectangle 1"}}},
    })
    original = tmp_path / "palette-tokens.json"
    original.write_text(json.dumps(source))
    artifact = library.json("import-artifact", "--file", original, "--kind", "dtcg")["artifact"]
    root, document, summary = draft(library, [artifact], "palette-scales")
    before = (root / "working.json").read_bytes()
    identity = expected_hash(document)
    library.cli("save-draft", document["id"], cwd=library.project)
    first = presentation_hashes(library.build(tmp_path / "before-palette-view", document["id"]))
    named = {"blue": ["#eaf3ff", "#102a43", "#33669980", "#123456"],
             "Neutral": ["#eeeeee", "#777777"]}
    named_values = {value for colors in named.values() for value in colors}
    measured = [entry["value"] for entry in summary["measured"]["palette"]]
    other = [value for value in measured if value not in named_values]
    family_order = sorted(named, key=lambda family: min(measured.index(value) for value in named[family]))
    assert "#27885d" in other and "#b65c82" in other
    palette_markup = {}
    for width in (375, 1280):
        page.set_viewport_size({"width": width, "height": 900})
        page.goto(server + "/ingest")
        page.get_by_role("link", name=document["name"], exact=True).click()
        positions = []
        for family in family_order:
            positions.append(page.get_by_role("heading", name=re.compile(family, re.I)).evaluate(
                "e => [...document.querySelectorAll('h1,h2,h3,h4,h5,h6')].indexOf(e)"))
        assert positions == sorted(positions)
        for family, values in {**named, "Other colors": other}.items():
            heading = page.get_by_role("heading", name=re.compile(re.escape(family), re.I))
            expect(heading).to_be_visible()
            section = heading.locator("xpath=ancestor::section[1]")
            text = section.inner_text()
            if family in named:
                assert all(re.search(r"\b" + step + r"\b", text) for step in
                           (["50", "100", "200", "900"] if family == "blue" else ["50", "900"]))
            assert [text.index(value) for value in values] == sorted(text.index(value) for value in values)
            for value in values:
                assert section.get_by_text(value, exact=True).count() == 1
                assert section.evaluate("""(section,value) => {
                  const probe=document.createElement('span'); probe.style.backgroundColor=value;
                  document.body.append(probe); const expected=getComputedStyle(probe).backgroundColor; probe.remove();
                  return [...section.querySelectorAll('*')].some(e=>getComputedStyle(e).backgroundColor===expected &&
                    e.getBoundingClientRect().width>0 && e.getBoundingClientRect().height>0);
                }""", value), (family, value)
            palette_markup.setdefault(family, section.inner_html())
            assert section.inner_html() == palette_markup[family]
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        page.screenshot(path=str(tmp_path / f"palette-{width}.png"), full_page=True)
    assert (root / "working.json").read_bytes() == before
    assert library.read(document["id"]) == document and expected_hash(library.read(document["id"])) == identity
    assert presentation_hashes(library.build(tmp_path / "after-palette-view", document["id"])) == first


def test_workbench_ingest_capture_draft_fidelity_choice_and_save_without_js(
        server, library, fixture_site, page):
    before_drafts = set((library.workspace / "drafts").glob("*/working.json"))
    before_captures = set((library.workspace / "artifacts").glob("*/capture.json"))
    page.goto(server + "/ingest")
    url_fields = visible(page.get_by_role("textbox", name=re.compile(r"url|website", re.I)))
    if not url_fields:
        url_fields = visible(page.locator('input[type="url"],textarea'))
    assert url_fields, "The ingest view needs a URL entry field"
    url = fixture_site.url + "/editorial/index.html"
    url_fields[0].fill(url)
    form = url_fields[0].locator("xpath=ancestor::form[1]")
    submit(page, form)
    created = set((library.workspace / "artifacts").glob("*/capture.json")) - before_captures
    assert len(created) == 1
    capture_path = created.pop()
    capture = read_json(capture_path)
    assert capture["pages"] and capture["pages"][0]["url"] == url and not capture["problems"]
    widths = {int(w) for entry in capture["pages"] for w in entry["widths"]}
    assert {320, 768, 800, 1280} <= widths
    assert_live_images(page, len(widths))
    body = page.locator("body").inner_text()
    assert all(str(width) in body for width in widths)
    fixture_site.available = False
    request_count = len(fixture_site.requests)
    # Fill a language/name field if the capture-review form requests one. An
    # autogenerated draft id is equally valid and is read from the public output.
    for field in visible(page.get_by_role("textbox", name=re.compile(r"language|draft.*name|name.*draft|^id$|^name$", re.I))):
        field.fill("journey-cedar")
    created_drafts = set((library.workspace / "drafts").glob("*/working.json")) - before_drafts
    if not created_drafts:
        activate(page, r"draft|create language|continue|next")
        created_drafts = set((library.workspace / "drafts").glob("*/working.json")) - before_drafts
    assert len(created_drafts) == 1
    working = created_drafts.pop()
    draft_root = working.parent
    document = read_json(working)
    summary = read_json(draft_root / "summary.json")
    assert summary["mapping"] == "heuristic" and summary["questions"] > 0
    draft_view = page.url
    body = page.locator("body").inner_text().lower()
    assert "heuristic" in body and "unknown" in body
    assert "fixture sans" in body
    assert re.search(r"palette|colou?r", body) and re.search(r"spacing|space", body)
    assert re.search(r"asset|logo|font", body)
    # Found assets must be an offered action, not an automatic promotion.
    assert visible(page.get_by_role("button", name=re.compile(r"promot|approve|use asset", re.I))) or visible(
        page.get_by_role("link", name=re.compile(r"promot|approve|assets", re.I)))
    page.goto(server + "/ingest")
    assert document["name"] in page.locator("body").inner_text() or document["id"] in page.locator("body").inner_text()
    page.goto(draft_view)
    activate(page, r"fidelity|reconstruct|compare.*source")
    report = read_json(draft_root / "fidelity" / "report.json")
    assert {(p["page"], p["width"]) for p in report["pairs"]} == {
        (entry["name"], int(width)) for entry in capture["pages"] for width in entry["widths"]}
    assert_live_images(page, 2)
    body = page.locator("body").inner_text().lower()
    assert re.search(r"delta|δe|Δe|colour|color|palette", body)
    assert re.search(r"spacing|space", body) and re.search(r"font|type", body)
    # Questions may be inline with fidelity or linked as the next view.
    radios, selects, choices = choice_controls(page)
    if not radios and not selects and not choices:
        page.goto(draft_view)
        activate(page, r"question|choice|continue|next")
        radios, selects, choices = choice_controls(page)
    old_provenance = read_json(draft_root / "provenance.json")
    previews = visible(page.locator("img,iframe,[data-kd-construct]"))
    assert len(previews) >= 2, "Visual choices need rendered previews"
    for preview in previews:
        box = preview.bounding_box()
        assert box and box["width"] > 0 and box["height"] > 0
    if radios:
        choice_form = radios[-1].locator("xpath=ancestor::form[1]")
        group = radios[-1].get_attribute("name")
        count = choice_form.locator('input[type="radio"]').evaluate_all(
            "(els, name) => els.filter(e => e.name === name).length", group)
        assert 2 <= count <= 4
        radios[-1].check()
        submit(page, choice_form)
    elif selects:
        select = selects[-1]
        values = select.locator("option").evaluate_all("els => els.map(e => e.value).filter(Boolean)")
        select.select_option(values[-1])
        submit(page, select.locator("xpath=ancestor::form[1]"))
    else:
        assert choices, "The question has no no-JS choice action"
        button = choices[-1]
        submit(page, button.locator("xpath=ancestor::form[1]"), button)
    provenance = read_json(draft_root / "provenance.json")
    document = read_json(working)
    assert_provenance(document, provenance)
    assert provenance != old_provenance and any(record["kind"] == "chosen" for record in provenance.values())
    page.goto(draft_view)
    activate(page, r"save.*library|save.*language|save draft|^save$")
    saved = library.read(document["id"])
    assert saved == document
    shared = read_json(library.path(document["id"]).parent / "provenance" / (expected_hash(saved) + ".json"))
    assert_provenance(saved, shared, shared=True)
    page.goto(server + "/")
    expect(link_at(page, "/languages/" + saved["id"])).to_be_visible()
    assert saved["name"] in page.locator("body").inner_text()
    assert len(fixture_site.requests) == request_count, "Workbench reread the live source after capture"
