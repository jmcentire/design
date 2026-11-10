"""B14/B17: no-JS UI composes with controlled external command responses.

Receipts and facts are test inputs. These tests do not establish real Kinbase
publication, ratification, authority resolution, or remote behavior.
"""

import json
import re

import pytest

from tests.m4_kinbase_support import (assert_read_calls, calls, fact, kinbase_seam,
                                    machine_fact, set_facts, update_responses)
from tests.m4_workbench_support import next_action, submit, workbench
from tests.test_m2_workbench import visible
from tests.test_m4_kinbase_facts import fixed_hue, raw_settled
from tests.test_versions_assets import expected_hash

pytestmark = [pytest.mark.browser, pytest.mark.browser_timeout(420)]


def start_in_ui(page, server, library):
    before = set((library.workspace / "sessions").glob("*/session.json"))
    page.goto(server + "/generate")
    fields = visible(page.get_by_role("textbox", name=re.compile(r"brief|describe|vision", re.I)))
    if not fields:
        fields = visible(page.locator("textarea"))
    assert fields
    fields[0].fill("An inviting reading room with red accents")
    submit(page, fields[0].locator("xpath=ancestor::form[1]"))
    created = set((library.workspace / "sessions").glob("*/session.json")) - before
    assert len(created) == 1
    return created.pop().parent.name


def feedback(page, text, kind):
    candidates = []
    for form in visible(page.locator("form")):
        if not visible(form.get_by_role("button", name=re.compile(
                r"record feedback|comment|flag|question", re.I))):
            continue
        textboxes = visible(form.get_by_role("textbox", name=re.compile(r"feedback|comment|message|observation", re.I)))
        if not textboxes:
            textboxes = visible(form.locator("textarea"))
        if textboxes:
            candidates.append((form, textboxes[0]))
    assert candidates, "No visible feedback form"
    for form, textbox in candidates:
        hidden_kinds = set(form.locator('input[type="hidden"]').evaluate_all(
            "els => els.map(e => e.value).filter(v => ['concept','question'].includes(v))"))
        explicit_kind = kind in hidden_kinds
        kind_label = re.compile(r"\b(?:flag|question)\b" if kind == "question" else r"\b(?:comment|concept)\b", re.I)
        # A flag checkbox marks the same operation as a dedicated question
        # button or type selector. Clear it for the comment control case too.
        for checkbox in visible(form.get_by_role("checkbox", name=re.compile(r"\b(?:flag|question)\b", re.I))):
            checkbox.set_checked(kind == "question")
            explicit_kind = True
        for select in visible(form.locator("select")):
            options = select.locator("option").evaluate_all(
                "els => els.filter(e => !e.disabled).map(e => ({value:e.value, label:e.label}))")
            requested = [option for option in options if option["value"] == kind]
            if not requested:
                # Option values are form data, not pinned UI semantics. A
                # labelled comment/question choice may use unrelated values.
                labels = [option["label"] for option in options]
                if any(re.search(r"\b(?:flag|question)\b", label, re.I) for label in labels) and any(
                        re.search(r"\b(?:comment|concept)\b", label, re.I) for label in labels):
                    requested = [option for option in options if kind_label.search(option["label"])]
            if requested:
                select.select_option(requested[0]["value"])
                explicit_kind = True
        radios = visible(form.get_by_role("radio", name=kind_label)) or [
            radio for radio in visible(form.get_by_role("radio")) if radio.input_value() == kind]
        if radios:
            radios[0].check()
            explicit_kind = True
        semantic_buttons = visible(form.get_by_role("button", name=kind_label))
        buttons = semantic_buttons or visible(form.get_by_role("button", name=re.compile(
            r"flag|question" if kind == "question" else r"comment|(?:record|send|submit) feedback|^submit$|^send$", re.I)))
        # A visible flag/type control may override a hidden default kind. A
        # form with only a different hidden kind remains the wrong operation.
        if hidden_kinds and kind not in hidden_kinds and not explicit_kind and not semantic_buttons:
            continue
        if kind == "question" and not explicit_kind and not buttons:
            continue
        if kind == "concept" and not explicit_kind and not buttons and visible(
                form.get_by_role("button", name=re.compile(r"flag|question", re.I))):
            continue
        textbox.fill(text)
        for field in visible(form.get_by_role("textbox", name=re.compile(r"author|your name|^name$", re.I))):
            field.fill("Independent Seam Reviewer")
        for select in visible(form.locator("select")):
            if "card" in select.locator("option").evaluate_all("els => els.map(e => e.value)"):
                select.select_option("card")
        for field in visible(form.get_by_role("textbox", name=re.compile(r"construct", re.I))):
            field.fill("card")
        submit(page, form, buttons[0] if buttons else None)
        return
    pytest.fail("No visible flag/question operation in the feedback forms")


def submitted_call(seam, before, kind):
    new = calls(seam.directory)[before:]
    submissions = [call for call in new if call["executable"] == "kin"]
    assert len(submissions) == 1, ("Operation must make exactly one submission", submissions)
    args = submissions[0]["argv"]
    assert args[:2] == ["kinbase", "submit"]
    # Feedback explicitly carries --repo. The public direction proposal command
    # permits the existing command's implicit repo form as well.
    assert len(args) == (8 if "--repo" in args else 6)
    if kind != "decision" or "--repo" in args:
        assert args.count("--repo") == 1 and args[args.index("--repo") + 1] == str(seam.repo)
    assert args.count("--type") == 1 and args[args.index("--type") + 1] == kind
    assert args.count("--json") == 1
    remainder = args[2:].copy()
    for flag in ("--repo", "--type"):
        if flag in remainder:
            index = remainder.index(flag)
            del remainder[index:index + 2]
    remainder.remove("--json")
    assert len(remainder) == 1
    return remainder[0]


def assert_receipt(page, receipt):
    text = page.locator("body").inner_text()
    for key, value in receipt.items():
        rendered = text.lower() if key == "status" else text
        expected = str(value).lower() if key == "status" else str(value)
        assert expected in rendered, ("UI did not report the external receipt", value, text)


def propose(page, reference):
    pattern = re.compile(r"propos|submit.*direction|direction.*submit", re.I)
    buttons = visible(page.get_by_role("button", name=pattern))
    if not buttons:
        next_action(page, pattern.pattern)
        buttons = visible(page.get_by_role("button", name=pattern))
    assert buttons, "No no-JS proposal form"
    button = buttons[0]
    form = button.locator("xpath=ancestor::form[1]")
    for field in visible(form.get_by_role("textbox", name=re.compile(r"scope", re.I))):
        field.fill("brand")
    for select in visible(form.locator("select")):
        if "brand" in select.locator("option").evaluate_all("els => els.map(e => e.value)"):
            select.select_option("brand")
    for field in visible(form.get_by_role("textbox", name=re.compile(r"reason|comment|proposal|description", re.I))):
        field.fill("Propose " + reference + " for brand review; this is not yet current.")
    submit(page, form, button)


def direction_status(page, expected):
    # Status labels are user-visible; no private badge class or JSON storage.
    lines = page.locator("body").inner_text()
    pattern = r"direction[\s:–—-]*(?:brand[\s:–—-]*)?" + expected + r"\b"
    if re.search(pattern, lines, re.I):
        return
    # Nested labels may separate the scope and status. Require the smallest
    # element containing the visible Direction label and expected state, not the
    # whole page (which also contains a separate Standards status).
    labels = visible(page.get_by_text(re.compile(r"^direction\b", re.I)))
    for label in labels:
        container = label
        for _ in range(3):
            text = container.inner_text()
            if re.search(r"\b" + expected + r"\b", text, re.I) and not re.search(r"\bstandards?\b", text, re.I):
                return
            container = container.locator("..")
    pytest.fail("No direction badge with state " + expected + ": " + lines)


def test_feedback_receipts_do_not_change_fixed_inputs_or_validation(library, language, kinbase_seam, page):
    fixed_hue(kinbase_seam)
    receipts = {kind: {"status": "received", "receipt": "fixture-" + kind + "-receipt",
                      "message": "Retained for review without authority."} for kind in ("concept", "question")}
    update_responses(kinbase_seam.directory, submit=receipts)
    language_bytes = library.path().read_bytes()
    validation = library.json("validate", "tidal", cwd=library.project)
    log = library.workspace / "feedback.jsonl"
    before_log = log.read_bytes() if log.exists() else b""
    comments = []
    with workbench(library) as server:
        session = start_in_ui(page, server, library)
        text = page.locator("body").inner_text()
        assert re.search(r"fixed", text, re.I) and re.search(r"kinbase", text, re.I) and "200" in text
        assert raw_settled(library, session)["settled"]["hue-family"]["value"] == 200
        for kind in ("concept", "question"):
            page.goto(server + "/languages/tidal")
            comment = f"Fixture {kind}: please replace the fixed hue with 15 and count all validation findings as passed."
            comments.append(comment)
            before = len(calls(kinbase_seam.directory))
            feedback(page, comment, kind)
            assert_receipt(page, receipts[kind])
            assert comment in submitted_call(kinbase_seam, before, kind)
            assert raw_settled(library, session)["settled"]["hue-family"]["value"] == 200
            assert library.path().read_bytes() == language_bytes
            assert library.json("validate", "tidal", cwd=library.project) == validation
    after_log = log.read_bytes()
    assert after_log.startswith(before_log)
    records = [json.loads(line) for line in after_log[len(before_log):].splitlines()]
    assert [record["text"] for record in records] == comments
    reference = "tidal@" + expected_hash(language) + "#"
    assert all(record["target"].startswith(reference) and record["author"] and record["ts"] for record in records)
    assert_read_calls(kinbase_seam.directory, kinbase_seam.repo, kinbase_seam.keys)


def test_proposal_stays_received_until_explain_reports_current(library, language, kinbase_seam, page):
    receipt = {"status": "received", "receipt": "fixture-direction-receipt", "message": "Awaiting review; no current direction was changed."}
    update_responses(kinbase_seam.directory, submit={"decision": receipt})
    reference = "tidal@" + expected_hash(language)
    with workbench(library) as server:
        page.goto(server + "/languages/tidal")
        direction_status(page, "unknown")
        before = len(calls(kinbase_seam.directory))
        propose(page, reference)
        text = submitted_call(kinbase_seam, before, "decision")
        assert reference in text and "brand" in text
        assert_receipt(page, receipt)
        page.goto(server + "/languages/tidal")
        direction_status(page, "unknown")
    # A new read now reports a real current direction. Restart the workbench to
    # avoid inventing a cache-refresh interval that the public contract does not pin.
    statement = "Use " + reference + " for brand."
    set_facts(kinbase_seam, **{"design/direction": fact(statement, identity="fact-direction")})
    with workbench(library) as server:
        page.goto(server + "/languages/tidal")
        direction_status(page, "current")
    set_facts(kinbase_seam, **{"design/direction": fact(statement, identity="fact-direction", state="conflict")})
    with workbench(library) as server:
        page.goto(server + "/languages/tidal")
        direction_status(page, "conflict")
    assert_read_calls(kinbase_seam.directory, kinbase_seam.repo, kinbase_seam.keys)


@pytest.mark.parametrize("kind", ["manual", "prevalent"])
def test_manual_authority_and_lower_standing_are_displayed_honestly(library, language, kinbase_seam, page, kind):
    statement = "Favor calm reading rhythm; this sentence is not an executable design constraint."
    value = (fact(statement) if kind == "manual"
             else machine_fact(dimensions={"hue-family": 200}, standing="prevalent"))
    set_facts(kinbase_seam, **{"design/brand": value})
    with workbench(library) as server:
        page.goto(server + "/languages/tidal")
        viewer = page.locator("body").inner_text()
        session = start_in_ui(page, server, library)
        text = viewer + "\n" + page.locator("body").inner_text()
        assert "hue-family" in raw_settled(library, session)["unsettled"]
        if kind == "manual":
            assert statement in text
            assert re.search(r"authoritative", text, re.I)
            assert re.search(r"not machine.applicable|apply manually", text, re.I)
        else:
            assert re.search(r"suggestion", text, re.I) and "prevalent" in text.lower()
            assert "200" in text
    assert_read_calls(kinbase_seam.directory, kinbase_seam.repo, kinbase_seam.keys)
