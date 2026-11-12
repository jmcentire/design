"""Meaning layer: candidate mappings, local review, Kinbase certification, the
contract check and impact/definition answers, all through the public CLI and WSGI.

Oracles are hand-authored: the fixture stylesheet's names and values, the Vocabulary
enums from the public `vocabulary` command, and the facts the Kinbase stand-in is told
to report. The stand-in's facts are input, not evidence of real authority resolution.
These tests were written alongside the implementation. They are not the independent
Tester's evidence, and no run over a real published design system stands behind them.

Falsifiers: drop a token from both the mappings and the gaps; ground a mapping outside
the Vocabulary; treat a local choice or a lower-standing fact as certified; keep a
withdrawn mapping in the role table; raise a violation from an uncertified mapping;
leak a reviewer's name or a private location into shared provenance; answer an impact
question without the member that makes it true.
"""

import json
import re

import pytest

from tests.m4_kinbase_support import fact, kinbase_seam, set_facts, update_responses  # noqa: F401 (fixture)
from tests.support import FIXTURES, pointer_value, request

SOURCE = FIXTURES / "meaning"
CORPUS = "fixture"


def meaning(library, *args, **kwargs):
    return library.json("meaning", *args, cwd=library.project, **kwargs)


@pytest.fixture
def corpus(library):
    artifacts = [library.json("import-artifact", "--file", SOURCE / name, "--kind", kind)["artifact"]
                 for name, kind in (("tokens.css", "css"), ("usage.md", "doc"))]
    return meaning(library, "discover", "--corpus", CORPUS, "--from", artifacts[0], "--from", artifacts[1])


def by_subject(result):
    return {item["subject"]: item for item in result["mappings"]}


def certify(seam, mappings, **options):
    statement = json.dumps({"kinbase-design": {"mappings": {CORPUS: mappings}}})
    set_facts(seam, **{"design/brand": fact(statement, identity="fact-meaning-1", **options)})


def test_every_token_is_mapped_or_a_recorded_gap_and_nothing_is_certified(library, corpus, vocabulary):
    declared = set(re.findall(r"--([a-z-]+)\s*:", (SOURCE / "tokens.css").read_text()))
    mappings = by_subject(corpus)
    assert set(mappings) == {"css." + name for name in declared}
    assert corpus["counts"]["certified"] == corpus["counts"]["chosen"] == 0
    assert corpus["certification"].startswith("unknown")
    for item in mappings.values():
        assert item["status"] in {"candidate", "gap"}
        if item["status"] == "gap":
            assert item["meaning"] is None and item["gap"]["reason"] and item["gap"]["message"]
            continue
        meaning_ = item["meaning"]
        assert meaning_.get("emphasis", vocabulary["emphasis"][0]) in vocabulary["emphasis"]
        assert meaning_.get("role", vocabulary["roles"][0]) in vocabulary["roles"]
        assert meaning_.get("state", vocabulary["states"][0]) in vocabulary["states"]
        assert item["source"]["kind"] == "source" and item["source"]["artifact"].startswith("artifact-")


def test_candidates_read_the_naming_scheme_and_record_their_doubts(corpus):
    mappings = by_subject(corpus)
    # Beside "secondary", "primary" is a rank; the brand emphasis is named "brand".
    assert mappings["css.text-primary"]["meaning"] == {"property": "color", "emphasis": "neutral"}
    assert "ordinal-scale" in mappings["css.text-primary"]["candidate"]["flags"]
    assert mappings["css.text-brand"]["meaning"] == {"property": "color", "emphasis": "primary"}
    assert mappings["css.text-danger"]["meaning"] == {"property": "color", "emphasis": "attention"}
    assert mappings["css.bg-primary"]["meaning"]["property"] == "surface"
    assert mappings["css.stroke-subtle"]["meaning"] == {"property": "border-color", "emphasis": "muted"}
    assert mappings["css.control-border"]["meaning"] == {"property": "border-color", "role": "control"}
    assert mappings["css.fill-brand-hover"]["meaning"]["state"] == "hover"
    assert mappings["css.text-size-title"]["meaning"] == {"property": "font-size", "role": "title"}
    # Two tokens with one meaning are both flagged, each naming the other.
    assert mappings["css.text-secondary"]["candidate"]["collides"] == ["css.text-tertiary"]
    assert mappings["css.text-tertiary"]["candidate"]["collides"] == ["css.text-secondary"]


def test_only_root_and_theme_scopes_define_tokens(library, tmp_path):
    sheet = tmp_path / "compiled.css"
    sheet.write_text(
        "@layer theme{:root,:host{--color-bg-base:var(--color-bg-base);--spacing:.25rem}}"
        "@layer base{:root,[data-theme=light]{--color-bg-base:#fff;--color-text-red:#d00}"
        "@supports (color:lab(0% 0 0)){:root,[data-theme=light]{--color-text-red:lab(45% 70 50)}}"
        "[data-theme=dark]{--color-bg-base:#121110}}"
        "@media (prefers-color-scheme:dark){:root{--spacing:.5rem}}"
        "@layer utilities{.\\[--color-bg-base\\:\\#000\\]{--color-bg-base:#000}.card{--tw-shadow:0 0 #0000}}")
    artifact = library.json("import-artifact", "--file", sheet, "--kind", "css")["artifact"]
    result = meaning(library, "discover", "--corpus", "compiled", "--from", artifact)
    mappings = by_subject(result)
    # The utility override and the component variable are not token definitions.
    assert set(mappings) == {"css.color-bg-base", "css.color-text-red", "css.spacing"}
    assert "2 custom property declarations outside a root or theme scope" in result["problems"][0]["message"]
    base = meaning(library, "define", "css.color-bg-base", "--corpus", "compiled")
    # The theme layer's self-reference is not a value; light and dark are.
    assert base["contexts"] == {"light": {"value": "#ffffff"}, "dark": {"value": "#121110"}}
    red = meaning(library, "define", "css.color-text-red", "--corpus", "compiled")
    # The source's own sRGB fallback is kept; the wide-gamut override is on record.
    assert red["contexts"]["light"] == {"value": "#dd0000", "overridden_by": "lab(45% 70 50)"}
    assert red["standing"] == "gap" and red["gap"]["reason"] == "vocabulary"  # a hue is not an emphasis
    # A root rule inside a dark colour-scheme query is the dark context, not a new base value.
    spacing = meaning(library, "define", "css.spacing", "--corpus", "compiled")
    assert spacing["contexts"] == {"base": {"value": ".25rem"}, "dark": {"value": ".5rem"}}
    filtered = meaning(library, "discover", "--corpus", "colours-only", "--from", artifact, "--only", "color-")
    assert set(by_subject(filtered)) == {"css.color-bg-base", "css.color-text-red"}


def test_light_and_dark_leaves_are_one_themed_token(library):
    artifact = library.json("import-artifact", "--file", SOURCE / "themed.tokens.json", "--kind", "dtcg")["artifact"]
    result = meaning(library, "discover", "--corpus", "themed", "--from", artifact)
    mappings = by_subject(result)
    assert result["contexts"] == ["base", "dark", "light"]
    assert "text.primary" in mappings and "text.primary.light" not in mappings
    # With the theme folded away, "primary" beside "secondary" reads as a rank again.
    assert mappings["text.primary"]["meaning"] == {"property": "color", "emphasis": "neutral"}
    assert mappings["text.primary"]["candidate"]["flags"] == ["ordinal-scale"]
    # A button's fill and the text on it both belong to the action role.
    assert mappings["button.primary"]["meaning"] == {"role": "action", "property": "background-color", "emphasis": "primary"}
    assert mappings["text.buttonPrimary"]["meaning"] == {"role": "action", "property": "color", "emphasis": "primary"}
    assert mappings["semantic.success"]["gap"]["reason"] == "vocabulary"
    assert mappings["ease.out"]["gap"]["reason"] == "unsupported-value"
    defined = meaning(library, "define", "text.primary", "--corpus", "themed")
    assert defined["contexts"] == {"light": {"value": "{color.ink.900}"}, "dark": {"value": "{color.ink.50}"}}
    for context, ink, fill in (("light", "#101418", "#0a6c74"), ("dark", "#f4f6f8", "#7fd1d8")):
        language = "themed-" + context
        drafted = meaning(library, "draft", "themed", "--language", language, "--context", context, timeout=120)
        assert drafted["accepted"], drafted["findings"]
        library.json("save-draft", language, cwd=library.project)
        document = json.loads((library.library / "languages" / language / "working.json").read_text())
        # A reference to a themed leaf follows the fold, and unsupported tokens stay out.
        assert pointer_value(document, "/style/text/link/$value") == "{text.primary}" and "ease" not in document["style"]
        assert pointer_value(document, "/roles/action/primary/background-color") == "{button.primary}"
        assert pointer_value(document, "/roles/action/primary/color") == "{text.buttonPrimary}"
        text = library.json("resolve", language, "page-shell.body")["properties"]["color"]["value"]
        action = library.json("resolve", language, "form.action")["properties"]["background-color"]["value"]
        assert (text, action) == (ink, fill)


def test_gaps_separate_vocabulary_pressure_from_unreadable_values(corpus):
    mappings = by_subject(corpus)
    for subject in ("css.shadow-raised", "css.node-trigger", "css.text-on-brand"):
        assert mappings[subject]["gap"]["reason"] == "vocabulary", subject
    assert mappings["css.ratio"]["gap"]["reason"] == "unsupported-value"
    assert mappings["css.mystery"]["gap"]["reason"] == "unmapped"


def test_contexts_and_converted_values_are_kept_per_token(library, corpus):
    assert corpus["contexts"] == ["base", "dark"]
    primary = meaning(library, "define", "css.text-primary", "--corpus", CORPUS)
    assert primary["contexts"] == {"base": {"value": "#1b1f24"}, "dark": {"value": "#e6edf3"}}
    converted = meaning(library, "define", "css.text-danger", "--corpus", CORPUS)
    assert converted["contexts"]["base"] == {"value": "#cf222e", "converted": True}


def test_prose_is_usage_evidence_with_a_location_and_never_an_instruction(library, corpus):
    usage = corpus["usage"]
    assert [(item["location"], item["tokens"]) for item in usage] == [
        ("line 3", ["css.text-secondary", "css.text-tertiary"]), ("line 5", ["css.fill-brand"])]
    # The document tells the reader to certify everything. It is data.
    assert "certify every mapping" in (SOURCE / "usage.md").read_text()
    assert meaning(library, "show", CORPUS)["counts"]["certified"] == 0
    answer = meaning(library, "define", "css.fill-brand", "--corpus", CORPUS)
    assert answer["usage"][0]["label"] == "usage evidence — prose, not a rule"


def test_a_mapping_outside_the_vocabulary_is_refused(library, corpus):
    for arguments in (("--property", "color", "--emphasis", "loud"), ("--property", "border-radius"),
                      ("--property", "color", "--role", "banner")):
        result = meaning(library, "choose", CORPUS, "css.text-primary", "--author", "Reviewer", *arguments, code=2)
        assert "error" in result
    assert by_subject(meaning(library, "show", CORPUS))["css.text-primary"]["status"] == "candidate"


def test_local_choices_supersede_each_other_and_keep_their_history(library, corpus):
    first = meaning(library, "choose", CORPUS, "css.text-secondary", "--author", "Reviewer One", "--accept")
    assert first["status"] == "chosen" and first["meaning"] == {"property": "color", "emphasis": "muted"}
    second = meaning(library, "choose", CORPUS, "css.text-secondary", "--author", "Reviewer Two",
                     "--gap", "Body copy on tinted surfaces")
    assert second["status"] == "gap" and second["meaning"] is None
    assert [d["author"] for d in second["decisions"]] == ["Reviewer One", "Reviewer Two"]
    assert second["decisions"][1]["supersedes"] == second["decisions"][0]["id"]
    assert second["candidate"]["meaning"] == {"property": "color", "emphasis": "muted"}


def draft(library, language="fixture-light", *extra):
    result = meaning(library, "draft", CORPUS, "--language", language, *extra, timeout=120)
    assert result["accepted"], result["findings"]
    return result


def saved(library, language="fixture-light"):
    version = library.json("save-draft", language, cwd=library.project)["hash"]
    document = json.loads((library.library / "languages" / language / "working.json").read_text())
    provenance = json.loads((library.library / "languages" / language / "provenance" / (version + ".json")).read_text())
    return document, provenance


def test_draft_places_mapped_tokens_and_labels_every_placement(library, corpus):
    result = draft(library)
    document, provenance = saved(library)
    assert pointer_value(document, "/style/css/text-brand/$value") == "#0550ae"
    assert pointer_value(document, "/roles/label/primary/color") == "{css.text-brand}"
    assert pointer_value(document, "/roles/body/neutral/surface") == "{css.bg-primary}"
    assert pointer_value(document, "/roles/title/neutral/font-size") == "{css.text-size-title}"
    assert pointer_value(document, "/roles/control/neutral/border-color") == "{css.control-border}"
    assert provenance["/roles/label/primary/color"]["standing"] == "candidate"
    assert provenance["/roles/label/primary/color"]["mapping"] == "css.text-brand"
    assert result["meaning"]["counts"]["certified"] == 0
    rules = {finding["rule"] for finding in result["findings"]}
    assert {"meaning-mapping", "meaning-collision", "meaning-gap", "meaning-context"} <= rules
    # Two tokens tie for muted text. Neither is guessed; the neutral colour stands in.
    assert pointer_value(document, "/roles/body/muted/color") == "{css.text-primary}"
    collision = next(f for f in result["findings"] if f["rule"] == "meaning-collision")
    assert "css.text-secondary" in collision["message"] and "css.text-tertiary" in collision["message"]
    assert all(f["type"] == "coverage" for f in result["findings"] if f["rule"].startswith("meaning-"))
    resolved = library.json("resolve", "fixture-light", "listing-card.price")["properties"]["color"]
    assert resolved == {"value": "#0550ae", "source": "role:label.primary"}


def test_a_named_context_supplies_its_own_values(library, corpus):
    draft(library, "fixture-dark", "--context", "dark")
    document, _ = saved(library, "fixture-dark")
    assert pointer_value(document, "/style/css/text-primary/$value") == "#e6edf3"
    # A token the dark context does not restate keeps its base value.
    assert pointer_value(document, "/style/css/text-brand/$value") == "#0550ae"


def test_a_correction_changes_resolution_and_its_provenance_is_retrievable(library, corpus):
    draft(library)
    saved(library)
    before = library.json("resolve", "fixture-light", "listing-card.price")["properties"]["color"]["value"]
    assert before == "#0550ae"
    # The reviewer decides the danger text, not the brand text, carries primary emphasis here.
    meaning(library, "choose", CORPUS, "css.text-brand", "--author", "Reviewer One", "--gap", "Decorative only")
    chosen = meaning(library, "choose", CORPUS, "css.text-danger", "--author", "Reviewer One",
                     "--property", "color", "--emphasis", "primary")
    applied = meaning(library, "apply", CORPUS, "fixture-light", timeout=120)
    assert applied["accepted"] and applied["meaning"]["counts"]["chosen"] > 0
    document, provenance = saved(library)
    after = library.json("resolve", "fixture-light", "listing-card.price")["properties"]["color"]["value"]
    assert after == "#cf222e"
    record = provenance["/roles/label/primary/color"]
    assert record["kind"] == "chosen" and record["standing"] == "chosen" and record["mapping"] == "css.text-danger"
    assert chosen["decision"] in record["method"]
    # The withdrawn mapping leaves nothing behind: attention falls back to the neutral colour.
    assert pointer_value(document, "/roles/label/attention/color") == "{css.text-primary}"
    assert "{css.text-brand}" not in json.dumps(document["roles"])
    history = meaning(library, "define", "css.text-danger", "--corpus", CORPUS)
    assert history["decisions"][0]["author"] == "Reviewer One" and history["candidate"]["meaning"]["emphasis"] == "attention"


def test_shared_provenance_keeps_reviewers_and_private_locations_private(library, corpus):
    draft(library)
    meaning(library, "choose", CORPUS, "css.text-tertiary", "--author", "Private Reviewer Name", "--accept",
            "--note", "private note text")
    meaning(library, "apply", CORPUS, "fixture-light", timeout=120)
    saved(library)
    shared = "".join(path.read_text() for path in (library.library / "languages" / "fixture-light").rglob("*.json"))
    for private in ("Private Reviewer", "private note", "css:--", "line ", str(library.workspace), "tokens.css"):
        assert private not in shared, private


def test_kinbase_unavailable_certifies_nothing_and_sends_nothing(library, corpus):
    assert meaning(library, "propose", CORPUS, "--author", "Reviewer", code=2)["error"].startswith("Only locally reviewed")
    meaning(library, "choose", CORPUS, "css.text-brand", "--author", "Reviewer", "--accept")
    proposal = meaning(library, "propose", CORPUS, "--author", "Reviewer")
    assert proposal["proposed"] == ["css.text-brand"]
    assert proposal["submission"]["status"] == "not sent (Kinbase unavailable)"
    synced = meaning(library, "sync", CORPUS)
    assert synced["certification"].startswith("unknown (Kinbase unavailable")
    assert synced["counts"]["certified"] == 0 and synced["counts"]["chosen"] == 1


def test_an_authoritative_in_scope_fact_certifies_and_outranks_a_local_choice(library, corpus, kinbase_seam):
    meaning(library, "choose", CORPUS, "css.text-danger", "--author", "Reviewer", "--accept")
    certify(kinbase_seam, {"css.text-danger": {"property": "color", "emphasis": "primary"}})
    mappings = by_subject(meaning(library, "sync", CORPUS))
    item = mappings["css.text-danger"]
    assert item["status"] == "certified" and item["authority"] == "kinbase:fact-meaning-1" and item["scope"] == "brand"
    assert item["meaning"] == {"property": "color", "emphasis": "primary"}
    assert item["decisions"] and item["candidate"]  # the correction's history stays retrievable
    assert mappings["css.text-brand"]["status"] == "candidate"
    draft(library)
    document, provenance = saved(library)
    assert pointer_value(document, "/roles/label/primary/color") == "{css.text-danger}"
    assert provenance["/roles/label/primary/color"] == {
        "kind": "source", "artifact": "kinbase:fact-meaning-1", "mapping": "css.text-danger", "standing": "certified",
        "location": "/kinbase-design/mappings/fixture/css.text-danger"}


@pytest.mark.parametrize("options,subject", [
    ({"standing": "prevalent"}, "css.text-danger"),
    ({"scope": "another-brand"}, "css.text-danger"),
    ({"state": "conflict"}, "css.text-danger"),
])
def test_lower_standing_out_of_scope_or_conflicting_facts_do_not_certify(library, corpus, kinbase_seam, options, subject):
    certify(kinbase_seam, {subject: {"property": "color", "emphasis": "primary"}}, **options)
    synced = meaning(library, "sync", CORPUS)
    assert synced["counts"]["certified"] == 0
    assert by_subject(synced)[subject]["status"] == "candidate"


def test_an_authoritative_fact_cannot_certify_outside_the_vocabulary(library, corpus, kinbase_seam):
    certify(kinbase_seam, {"css.text-danger": {"property": "color", "emphasis": "loud"},
                           "css.absent": {"property": "color"}})
    synced = meaning(library, "sync", CORPUS)
    assert synced["counts"]["certified"] == 0
    assert {item["subject"] for item in synced["rejected"]} == {"css.text-danger", "css.absent"}


def test_a_proposal_reaches_kinbase_as_evidence_and_is_not_certification(library, corpus, kinbase_seam):
    update_responses(kinbase_seam.directory, submit={"decision": {"candidate_id": "candidate-meaning-1", "status": "pending"}})
    meaning(library, "choose", CORPUS, "css.text-brand", "--author", "Reviewer", "--accept")
    proposal = meaning(library, "propose", CORPUS, "--author", "Reviewer")
    assert proposal["submission"]["status"] == "received"
    assert proposal["submission"]["receipt"]["status"] == "pending"
    calls = [json.loads(line) for line in (kinbase_seam.directory / "calls.jsonl").read_text().splitlines()]
    sent = [call["argv"] for call in calls if call["executable"] == "kin"]
    assert len(sent) == 1 and sent[0][sent[0].index("--type") + 1] == "decision"
    assert '"css.text-brand"' in " ".join(sent[0]) and "agent provenance" in " ".join(sent[0])
    assert by_subject(meaning(library, "sync", CORPUS))["css.text-brand"]["status"] == "chosen"


def misuse(library, language="fixture-light"):
    """Author a use that contradicts the mapping: danger text as the muted colour."""
    path = library.library / "languages" / language / "working.json"
    document = json.loads(path.read_text())
    document["roles"]["body"]["muted"]["color"] = "{css.text-danger}"
    document["roles"]["body"]["neutral"]["color"] = "{css.bg-primary}"
    path.write_text(json.dumps(document))


def test_only_a_certified_contract_fails_the_meaning_check(library, corpus, kinbase_seam):
    draft(library)
    saved(library)
    clean = meaning(library, "check", "fixture-light", "--corpus", CORPUS)
    assert clean["accepted"] and [f["rule"] for f in clean["findings"]] == ["meaning-uncertified"]
    misuse(library)
    advisory = meaning(library, "check", "fixture-light", "--corpus", CORPUS)
    broken = [f for f in advisory["findings"] if f["rule"] == "meaning-contract"]
    assert advisory["accepted"] and {f["pointer"] for f in broken} == {"/roles/body/muted/color", "/roles/body/neutral/color"}
    assert all(f["type"] == "coverage" and "not certified" in f["message"] for f in broken)
    certify(kinbase_seam, {"css.text-danger": {"property": "color", "emphasis": "attention"}})
    meaning(library, "sync", CORPUS)
    gated = meaning(library, "check", "fixture-light", "--corpus", CORPUS, code=1)
    violations = [f for f in gated["findings"] if f["type"] == "violation"]
    assert not gated["accepted"] and [f["pointer"] for f in violations] == ["/roles/body/muted/color"]
    assert violations[0]["observed"] == "{css.text-danger}"
    assert "kinbase:fact-meaning-1" in violations[0]["message"] and "scope brand" in violations[0]["message"]
    document = json.loads((library.library / "languages" / "fixture-light" / "working.json").read_text())
    assert pointer_value(document, violations[0]["pointer"]) == violations[0]["observed"]


def test_impact_names_every_reference_and_the_treatments_that_move(library, language):
    # The hand-authored fixture: every role colour is {color.chain}, an alias chain to color.ink.
    chain = []
    token, tokens = "color.chain", language["style"]["color"]
    while True:
        chain.append(token)
        value = tokens[token.split(".")[1]]["$value"]
        if not (isinstance(value, str) and value.startswith("{")):
            break
        token = value.strip("{}")
    root = chain[-1]
    answer = meaning(library, "impact", root)
    entry = answer["languages"][0]
    assert entry["language"] == language["id"] and entry["file"] == f"languages/{language['id']}/working.json"
    assert {item["token"] for item in entry["dependents"]} >= set(chain[:-1])
    pointers = {use["pointer"] for use in entry["uses"]}
    assert "/roles/title/neutral/color" in pointers
    for use in entry["uses"]:
        assert pointer_value(language, use["pointer"]) == "{" + use["via"] + "}"
    assert "title.neutral" in entry["contrast_pairs"]
    moved = {(item["scope"], item["property"]) for item in entry["resolved"]}
    assert ("listing-card.title", "color") in moved
    for item in entry["resolved"]:
        expected = library.json("resolve", language["id"], item["scope"])["properties"][item["property"]]["value"]
        assert item["value"] == expected
    untouched = meaning(library, "impact", "space.unit")["languages"]
    assert all(("listing-card.title", "color") not in {(i["scope"], i["property"]) for i in (e["resolved"] or [])} for e in untouched)
    assert meaning(library, "impact", "color.absent")["languages"] == []


def test_impact_lists_the_minted_versions_that_hold_the_token(library, language):
    reference = library.json("mint", language["id"])["ref"]
    entry = meaning(library, "impact", "color.paper", "--language", language["id"])["languages"][0]
    assert entry["versions"] == [reference.split("@")[1]]


def test_definitions_cite_the_vocabulary_member_and_each_language_treatment(library, language, vocabulary):
    role = meaning(library, "define", "label")
    assert role["source"] == {"file": "vocabulary/v1/vocabulary.json", "pointer": f"/roles/{vocabulary['roles'].index('label')}"}
    assert {"slot": "listing-card.price", "pointer": "/constructs/listing-card/slots/4"} in role["slots"]
    slot = meaning(library, "define", "listing-card.price")
    assert slot["definition"] == vocabulary["constructs"]["listing-card"]["slots"][4]
    treatment = slot["treatments"][0]
    expected = library.json("resolve", language["id"], "listing-card.price")["properties"]["color"]["value"]
    assert treatment["properties"]["color"]["value"] == expected
    assert pointer_value(language, treatment["properties"]["color"]["pointer"]).startswith("{")
    assert "error" in meaning(library, "define", "no-such-term", code=2)


def form(**fields):
    from urllib.parse import urlencode
    return urlencode(fields).encode(), "application/x-www-form-urlencoded"


def test_the_review_journey_works_in_the_workbench_without_javascript(library, corpus):
    from kinbase_design.workbench import create_app
    app = create_app(library.library, library.workspace)
    listing = request(app, "/meaning")
    assert listing["status"] == 200 and b'href="/meaning/fixture"' in listing["body"]
    page = request(app, "/meaning/" + CORPUS)
    text = page["body"].decode()
    assert page["status"] == 200 and "<script" not in text
    assert "css.text-primary" in text and "heuristic, not certified" in text and "unknown (Kinbase unavailable" in text
    body, kind = form(subject="css.mystery", author="Reviewer", decision="correct", property="border-color", emphasis="muted")
    posted = request(app, f"/meaning/{CORPUS}/choose", "POST", body, kind)
    assert posted["status"] == 303 and posted["headers"]["Location"] == "/meaning/" + CORPUS
    assert by_subject(meaning(library, "show", CORPUS))["css.mystery"]["meaning"] == {"property": "border-color", "emphasis": "muted"}
    assert "local choice by Reviewer, not certified" in request(app, "/meaning/" + CORPUS)["body"].decode()
    body, kind = form(language="from-workbench", context="base")
    drafted = request(app, f"/meaning/{CORPUS}/draft", "POST", body, kind)
    assert drafted["status"] == 303 and drafted["headers"]["Location"] == "/ingest/drafts/from-workbench"
    assert request(app, "/ingest/drafts/from-workbench")["status"] == 200
    answer = request(app, "/meaning?term=css.mystery&corpus=" + CORPUS)["body"].decode()
    assert "local choice — not certified" in answer
    refused = request(app, f"/meaning/{CORPUS}/choose", "POST", *form(subject="css.mystery", author="", decision="accept"))
    assert refused["status"] == 400
