"""M3 B15: drive generate entirely through server-rendered forms with JS disabled.

The public workspace files corroborate effects, but no generate command performs
an operation for the UI. Falsifiers: dry interview, ineffective pin/remove,
uneditable history, JS-only actions, or a derived preview that cannot be saved.
"""

import re

import pytest
from PIL import Image
from playwright.sync_api import expect

from tests.browser_support import link_at
from tests.m2_support import assert_provenance, assert_valid_draft, read_json, scalar_leaves
from tests.m3_perceptual_support import assert_moodboard_variety
from tests.m3_support import BEACH, candidate_directory, candidate_library, log_bytes, log_records, settled
from tests.test_m2_workbench import activate, submit, visible
from tests.test_versions_assets import expected_hash

pytestmark = [pytest.mark.browser, pytest.mark.browser_timeout(600)]


def flags(document, name):
    return sum(value is True and pointer.rsplit("/", 1)[-1] == name
               for pointer, value in scalar_leaves(document))


def inspect_materialized_swatches(library, session_root, seen):
    """Amendment 11: language-backed interview/question samples are valid packages.

    Plain CSS color strips need not be languages. Inspect all materialized
    candidates without prescribing how many the visual interview must build.
    """
    for directory in (session_root / "candidates").glob("*"):
        if not directory.is_dir() or directory in seen:
            continue
        candidate_directory(library, session_root.name, {
            "hash": directory.name, "preview": str(directory.relative_to(library.workspace))})
        isolated, document = candidate_library(library, directory)
        isolated.validate(document["id"], accepted=True)
        seen.add(directory)


def visual_samples(page, minimum=2):
    """Require visible, loaded sample paint; plain choice text alone is insufficient."""
    samples = visible(page.locator("img,iframe,svg,[data-kd-construct]"))
    for sample in samples:
        box = sample.bounding_box()
        assert box and box["width"] > 0 and box["height"] > 0
        if sample.evaluate("e => e.tagName") == "IMG":
            assert sample.evaluate("e => e.complete && e.naturalWidth > 0 && e.naturalHeight > 0")
        if sample.evaluate("e => e.tagName") == "IFRAME":
            frame = sample.element_handle().content_frame()
            assert frame and (frame.locator("body").inner_text().strip() or
                              frame.locator("img").evaluate_all("els => els.some(e => e.complete && e.naturalWidth > 0)"))
    if len(samples) >= minimum:
        return
    # Inline CSS swatches/specimens are as valid as screenshot/iframe samples.
    # Exclude native controls and page navigation, whose default paint is not an
    # interview sample. Multiple distinct painted colors or typography must be
    # visible within the interview/mood content itself.
    samples = page.locator("main,form").evaluate_all("""roots => {
      const out = [], seen = new Set();
      for (const root of roots) for (const e of root.querySelectorAll('div,span,p,h2,h3,h4,figure')) {
        if (seen.has(e) || e.closest('nav,button,select')) continue;
        seen.add(e); const s = getComputedStyle(e), r = e.getBoundingClientRect();
        if (r.width <= 0 || r.height <= 0 || s.visibility === 'hidden' || s.display === 'none') continue;
        const color = s.backgroundColor;
        if (!['rgba(0, 0, 0, 0)','transparent'].includes(color)) out.push('color:' + color);
        if (e.textContent.trim() && e.children.length === 0)
          out.push('type:' + s.fontFamily + '/' + s.fontSize + '/' + s.fontWeight);
      }
      return [...new Set(out)];
    }""")
    assert len(samples) >= minimum + 1, "The visual interview/mood board contains only dry choice text"


def answer_interview(page):
    controls = visible(page.locator('select,input[type="range"],input[type="radio"]'))
    assert controls, "Visual interview has no usable choices"
    control = controls[0]
    form = control.locator("xpath=ancestor::form[1]")
    if control.evaluate("e => e.tagName") == "SELECT":
        alternatives = control.locator("option").evaluate_all(
            "els => els.filter(e => !e.disabled && e.value).map(e => e.value)")
        alternative = next(value for value in alternatives if value != control.input_value())
        control.select_option(alternative)
    elif control.get_attribute("type") == "range":
        before = control.input_value()
        control.focus()
        control.press("Home")
        if control.input_value() == before:
            control.press("End")
        assert control.input_value() != before
        alternative = control.input_value()
    else:
        choices = [item for item in controls if item.get_attribute("type") == "radio" and not item.is_checked()]
        assert choices
        control = choices[0]
        form = control.locator("xpath=ancestor::form[1]")
        control.check()
        alternative = control.input_value()
    submit(page, form)
    return alternative


def choose_visible(page, choice, comment, scope=None, require_comment=True):
    # Both a direct submit button and a native choice field + submit are valid.
    pattern = re.compile((r"\b" if scope is not None else r"^(?:(?:choose|pick|prefer|option)\s+)?") + choice + r"(?:\b|$)", re.I)
    owner = scope if scope is not None else page
    buttons = visible(owner.get_by_role("button", name=pattern))
    controls = buttons or visible(owner.get_by_role("radio", name=pattern))
    assert controls, ("Missing no-JS A/B choice", choice)
    control = controls[0]
    form = control.locator("xpath=ancestor::form[1]")
    assert form.count() == 1, "A/B choice must belong to a no-JS form"
    # The comment label's wording is not contract. Its form ownership ties the
    # labelled textbox to this choice instead of an unrelated field on the page.
    comments = visible(form.get_by_role("textbox", name=re.compile(r"\S")))
    if require_comment:
        assert comments, "A/B choice form must offer a labelled comment textbox"
    if comments:
        comments[0].fill(comment)
    if buttons:
        submit(page, form, control)
    else:
        control.check()
        submit(page, form)
    return bool(comments)


def revision_form(page, choice_id, choice):
    """Read rendered form ownership, without pinning a field name or endpoint."""
    for form in page.locator("form").all():
        values = form.locator('input[type="hidden"]').evaluate_all("els => els.map(e => e.value)")
        if choice_id not in values:
            continue
        pattern = re.compile(r"\b" + choice + r"\b", re.I)
        if visible(form.get_by_role("button", name=pattern)) or visible(form.get_by_role("radio", name=pattern)):
            return form
    return None


def name_draft(page):
    fields = visible(page.get_by_role("textbox", name=re.compile(r"language|draft.*name|name.*draft|^id$|^name$", re.I)))
    for field in fields:
        field.fill("generated-shore")


def test_no_js_generate_interview_moodboard_revise_derive_preview_and_save(server, library, tmp_path, page):
    before_sessions = set((library.workspace / "sessions").glob("*/session.json"))
    before_artifacts = set((library.workspace / "artifacts").iterdir()) if (library.workspace / "artifacts").exists() else set()
    before_drafts = set((library.workspace / "drafts").glob("*/working.json"))
    logo = tmp_path / "logo.png"
    with Image.new("RGB", (64, 32), "#135b75") as picture:
        picture.save(logo)
    page.goto(server + "/generate")
    briefs = visible(page.get_by_role("textbox", name=re.compile(r"brief|describe|vision", re.I)))
    if not briefs:
        briefs = visible(page.locator("textarea"))
    assert briefs
    briefs[0].fill(BEACH)
    form = briefs[0].locator("xpath=ancestor::form[1]")
    upload = form.locator('input[type="file"]')
    assert upload.count(), "Generate start must offer artifact upload"
    upload.first.set_input_files(logo)
    submit(page, form)
    sessions = set((library.workspace / "sessions").glob("*/session.json")) - before_sessions
    assert len(sessions) == 1
    session_file = sessions.pop()
    root = session_file.parent
    inspected = set()
    initial = read_json(session_file)
    assert initial["brief"] == BEACH
    imported = set((library.workspace / "artifacts").iterdir()) - before_artifacts
    assert any(file.read_bytes() == logo.read_bytes() for artifact in imported for file in artifact.rglob("*") if file.is_file())
    assert any(artifact.name in {str(value) for _, value in scalar_leaves(initial)} for artifact in imported)
    assert re.search(r"unknown|unconnected|not connected", page.locator("body").inner_text(), re.I)
    visual_samples(page)
    inspect_materialized_swatches(library, root, inspected)
    answer = answer_interview(page)
    after_interview = read_json(session_file)
    assert after_interview != initial
    answer_values = [value for _, value in scalar_leaves(after_interview)]
    try:
        retained_number = float(answer) in [value for value in answer_values if isinstance(value, (int, float))]
    except ValueError:
        retained_number = False
    assert answer in {str(value) for value in answer_values} or retained_number, "Interview answer was not retained"
    pins = visible(page.get_by_role("button", name=re.compile(r"\bpin\b", re.I)))
    if not pins:
        activate(page, r"mood.?board|continue|next")
        pins = visible(page.get_by_role("button", name=re.compile(r"\bpin\b", re.I)))
    visual_samples(page)
    inspect_materialized_swatches(library, root, inspected)
    assert pins, "Mood board needs a no-JS pin operation"
    assert_moodboard_variety(page)
    previous = read_json(session_file)
    submit(page, pins[0].locator("xpath=ancestor::form[1]"), pins[0])
    pinned = read_json(session_file)
    assert flags(pinned, "pinned") > flags(previous, "pinned")
    removals = visible(page.get_by_role("button", name=re.compile(r"remove", re.I)))
    assert removals
    submit(page, removals[-1].locator("xpath=ancestor::form[1]"), removals[-1])
    removed = read_json(session_file)
    assert flags(removed, "removed") > flags(pinned, "removed")
    # Playwright serializes role regexes into selectors delimited by '/'. Use
    # its Unicode escape so the accessible label still matches literal A/B.
    activate(page, r"compare|A\u002fB|round|continue|next")
    visual_samples(page)
    inspect_materialized_swatches(library, root, inspected)
    before_choice = log_bytes(root)
    choose_visible(page, "A", "Prefer the calmer sample")
    assert log_bytes(root).startswith(before_choice)
    history = log_records(root)
    assert len(history) == 1 and history[0]["choice"] == "A"
    first = history[0]
    assert first["comment"] == "Prefer the calmer sample"
    after_first = settled(library, root.name, root)  # Read-only corroboration of the UI submission.
    # Revision is reached through visible controls, never by constructing a route.
    inline = revision_form(page, first["id"], "B")
    if inline is None:
        if not visible(page.get_by_role("button", name=re.compile(r"revis|edit.*choice|change.*choice", re.I))) and not visible(
                page.get_by_role("link", name=re.compile(r"revis|edit.*choice|change.*choice", re.I))):
            activate(page, r"history|previous.*choice|earlier.*choice")
        inline = revision_form(page, first["id"], "B")
        if inline is None:
            activate(page, r"revis|edit.*choice|change.*choice")
            inline = revision_form(page, first["id"], "B")
        visual_samples(page)
        inspect_materialized_swatches(library, root, inspected)
    before_revision = log_bytes(root)
    revision_comment = choose_visible(page, "B", "The alternate works better", scope=inline, require_comment=False)
    assert log_bytes(root).startswith(before_revision)
    history = log_records(root)
    assert len(history) == 2
    assert history[1]["choice"] == "B" and history[1]["supersedes"] == first["id"]
    assert history[1]["pair"] == first["pair"]
    if revision_comment:
        assert history[1]["comment"] == "The alternate works better"
    after_revision = settled(library, root.name, root)
    for dimension in first["dimensions"]:
        assert after_revision["settled"][dimension]["value"] != after_first["settled"][dimension]["value"]
        assert after_revision["settled"][dimension]["choices"] == [history[1]["id"]]
    name_draft(page)
    activate(page, r"derive|stop|finish")
    created = set((library.workspace / "drafts").glob("*/working.json")) - before_drafts
    if not created:
        name_draft(page)
        activate(page, r"derive|create language|continue")
        created = set((library.workspace / "drafts").glob("*/working.json")) - before_drafts
    assert len(created) == 1
    working = created.pop()
    document = read_json(working)
    provenance = read_json(working.parent / "provenance.json")
    assert_valid_draft(library, document, working.parent)
    assert_provenance(document, provenance)
    assert any(record["kind"] == "chosen" and record["choice"] == history[1]["id"] for record in provenance.values())
    assert not any(record["kind"] == "chosen" and record["choice"] == first["id"] for record in provenance.values())
    review_url = page.url
    previews = visible(page.locator("iframe,[data-kd-construct]"))
    if not previews:
        activate(page, r"preview|view.*site")
        previews = visible(page.locator("iframe,[data-kd-construct]"))
    assert previews, "Derived language has no rendered site review"
    for preview in previews:
        box = preview.bounding_box()
        assert box and box["width"] > 0 and box["height"] > 0
        if preview.evaluate("e => e.tagName") == "IFRAME":
            frame = preview.element_handle().content_frame()
            assert frame and frame.locator("[data-kd-construct]").count() > 0
    page.goto(review_url)
    activate(page, r"save.*library|save.*language|save draft|^save$")
    saved = library.read(document["id"])
    assert saved == document
    shared = read_json(library.path(document["id"]).parent / "provenance" / (expected_hash(saved) + ".json"))
    assert_provenance(saved, shared, shared=True)
    page.goto(server + "/")
    expect(link_at(page, "/languages/" + saved["id"])).to_be_visible()
    assert saved["name"] in page.locator("body").inner_text()
