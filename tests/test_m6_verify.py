"""Site verification and the Factory hand-off, through the public CLI.

A page is built only from what the hand-off publishes: the exported stylesheets and the
committed markup of each construct. The oracles are the shipped Harbor language's own
`resolve` output, the Vocabulary's contracts and hand-authored off-language values.
These tests were written alongside the implementation. They are not the independent
Tester's evidence, and no real Factory run stands behind them.

Falsifiers: accept a page whose values lie outside the language; miss a restyled slot;
accept a construct missing a required slot; hide an excepted finding; judge a pinned
version by the working copy; give the builder the tester's expected values; report an
unreachable page as compliant.
"""

import json
import shutil

import pytest

from tests.m4_support import git, inventory_document, site_repository
from tests.support import ROOT, pointer_value

REQUEST = "Build a page for our new checkout workflow using the Harbor design language."
TARGET = "design"
HEAD = ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1"><title>Checkout</title>'
        '<link rel="stylesheet" href="design/tokens.css"><link rel="stylesheet" href="design/roles.css">{extra}</head><body>')


@pytest.fixture
def harbor(library):
    source = ROOT / "library" / "languages" / "harbor"
    assert source.is_dir(), "prerequisite missing: shipped harbor language"
    shutil.copytree(source, library.path("harbor").parent)
    return library.read("harbor")


@pytest.fixture
def handoff(library, harbor, tmp_path):
    """A site repository with the hand-off branch checked out, as a Factory run would start."""
    repo = site_repository(tmp_path)
    (repo / "kinbase-design.inventory.json").write_text(json.dumps(inventory_document()))
    git(repo, "add", "kinbase-design.inventory.json")
    git(repo, "commit", "-m", "Declare the site's inventory")
    result = library.json("apply", "harbor", "--site", repo, "--adapter", "generic", "--target-dir", TARGET, "--branch",
                          "--request", REQUEST, "--verify-page", "http://localhost:3000/checkout", cwd=library.project, timeout=90)
    git(repo, "switch", result["branch"]["branch"])
    return repo, result


def markup(repo, construct, **text):
    html = (repo / TARGET / "kinbase-design" / "markup" / (construct + ".html")).read_text()
    return html.replace('src="assets/', 'src="design/assets/')


def write_page(repo, body, extra="", name="checkout.html"):
    file = repo / name
    file.write_text(HEAD.format(extra=extra) + body + "</body></html>")
    return file


def compliant(repo, inside="", extra="", name="checkout.html", edit=lambda html: html):
    shell = markup(repo, "page-shell").replace("</main>", markup(repo, "card") + markup(repo, "form") + inside + "</main>")
    return write_page(repo, edit(markup(repo, "nav") + shell + markup(repo, "footer")), extra, name)


def verify(library, reference, page, *extra, code=(0, 1)):
    return library.json("verify", reference, "--page", page, "--widths", "320,1280", *extra, cwd=library.project,
                        code=code, timeout=240)


def blocking(result, rule=None):
    return [f for f in result["findings"] if f["type"] in {"violation", "missing"} and not f.get("exception")
            and (rule is None or f["rule"] == rule)]


def test_handoff_gives_each_factory_role_its_own_input(library, harbor, handoff):
    repo, result = handoff
    bundle = library.workspace / "handoffs" / result["handoff"]
    task = (bundle / "TASK.md").read_text()
    reference = json.loads((bundle / "handoff.json").read_text())["language"]
    assert "> " + REQUEST in task  # the request reaches the roles verbatim
    assert f"kinbase-design verify {reference} --page http://localhost:3000/checkout" in task
    oracle = f"{TARGET}/kinbase-design/expected.json"
    assert f"--role coder --exclude {oracle}" in task and f"--role tester --include {TARGET}/kinbase-design" in task
    committed = set(git(repo, "ls-tree", "-r", "--name-only", "HEAD").splitlines())
    assert {oracle, f"{TARGET}/kinbase-design/CONTRACT.md", f"{TARGET}/kinbase-design/markup/form.html", f"{TARGET}/roles.css"} <= committed
    expected = json.loads((repo / oracle).read_text())
    assert expected["language"] == reference
    # The tester's oracle is the resolver's answer, state by state.
    for scope, state in (("listing-card.price", "default"), ("listing-card", "hover"), ("form.action", "default")):
        resolved = library.json("resolve", "harbor", scope, "--state", state)["properties"]
        assert expected["treatments"][scope][state] == {name: value["value"] for name, value in resolved.items()}
    assert expected["closed_set"]["colors"]["color.primary"] == pointer_value(harbor, "/style/color/primary/$value")
    contract = (repo / TARGET / "kinbase-design" / "CONTRACT.md").read_text()
    assert reference in contract and "| `form` | `<form>` | title, name, email, message, action |" in contract
    assert "expected" not in contract.lower().replace("expected.json", "")  # the builder's contract holds no oracle values


def test_a_handoff_without_a_branch_touches_nothing_in_the_site(library, harbor, tmp_path):
    repo = site_repository(tmp_path)
    (repo / "kinbase-design.inventory.json").write_text(json.dumps(inventory_document()))
    git(repo, "add", "-A")
    git(repo, "commit", "-m", "Inventory")
    result = library.json("apply", "harbor", "--site", repo, "--adapter", "generic", "--request", REQUEST, cwd=library.project, timeout=90)
    bundle = library.workspace / "handoffs" / result["handoff"]
    assert (bundle / "contract" / "expected.json").is_file() and (bundle / "contract" / "markup" / "card.html").is_file()
    task = (bundle / "TASK.md").read_text()
    assert "--page PAGE" in task and "Replace `PAGE`" in task
    assert git(repo, "status", "--porcelain") == "" and git(repo, "branch", "--list").strip() == "* main"


def test_verify_refuses_what_it_cannot_judge(library, harbor, tmp_path):
    page = tmp_path / "page.html"
    page.write_text("<!doctype html><title>x</title>")
    for arguments in (("harbor@abc", "--page", page), ("harbor@" + "0" * 64, "--page", page), ("harbor", "--page", tmp_path / "absent.html"),
                      ("harbor", "--page", "ftp://example.invalid/x"), ("harbor", "--page", "https://user:secret@example.invalid/")):
        assert "error" in library.json("verify", *arguments, cwd=library.project, code=2)


@pytest.mark.browser
@pytest.mark.browser_timeout(300)
def test_a_page_built_from_the_contract_complies(library, handoff):
    repo, _ = handoff
    result = verify(library, "harbor", compliant(repo), code=0)
    assert result["accepted"] and blocking(result) == []
    assert result["summary"]["text_elements"] == result["summary"]["hooked_text_elements"] > 0
    assert result["summary"]["constructs"] == {"nav": 1, "page-shell": 1, "card": 1, "form": 1, "footer": 1}
    assert result["checked"]["widths"] == [320, 1280]
    assert all(f["type"] != "coverage" or f["rule"] != "site-hooks" for f in result["findings"])


@pytest.mark.browser
@pytest.mark.browser_timeout(300)
def test_values_outside_the_language_are_named_with_their_nearest_token(library, harbor, handoff):
    repo, _ = handoff
    extra = ("<style>.promo{background:#ffe6f7;padding:13px;border-radius:5px}"
             ".promo p{color:#123456;font-family:Courier,monospace;font-size:17px;font-weight:500}</style>")
    page = compliant(repo, '<div class="promo"><p>Limited offer</p></div>', extra)
    result = verify(library, "harbor", page, code=1)
    assert not result["accepted"]
    found = {(f["rule"], f["measured"]["property"], f["measured"]["value"]) for f in blocking(result)}
    assert found == {("off-language-color", "background-color", "#ffe6f7"), ("off-language-color", "color", "#123456"),
                     ("off-language-space", "padding", "13px"), ("off-language-shape", "border-radius", "5px"),
                     ("off-language-type", "font-family", "courier"), ("off-language-type", "font-size", "17px"),
                     ("off-language-type", "font-weight", "500")}
    for finding in blocking(result):
        # Each finding points at the nearest value the language does hold.
        assert finding["source"] == "site" and finding["file"] == "languages/harbor/working.json"
        assert pointer_value(harbor, finding["pointer"]) == finding["observed"]
        assert "nearest is" in finding["message"] and finding["measured"]["element"]
    padding = next(f for f in blocking(result) if f["measured"]["property"] == "padding")
    assert padding["pointer"] == "/style/space/sm/$value" and padding["threshold"] == "16px"
    hooks = next(f for f in result["findings"] if f["rule"] == "site-hooks")
    assert hooks["type"] == "coverage" and hooks["observed"] == 1


@pytest.mark.browser
@pytest.mark.browser_timeout(300)
def test_a_restyled_slot_fails_against_the_resolved_treatment(library, harbor, handoff):
    repo, _ = handoff
    page = compliant(repo, edit=lambda html: html.replace('data-kd-slot="card.title"', 'data-kd-slot="card.title" style="color:#0b6e65"', 1))
    result = verify(library, "harbor", page, code=1)
    findings = blocking(result, "role-conformance")
    assert [f["target"] for f in findings] == ["card.title"]
    expected = library.json("resolve", "harbor", "card.title")["properties"]["color"]["value"]
    assert findings[0]["threshold"] == expected and findings[0]["measured"]["property"] == "color"
    # #0b6e65 is a language colour: only the slot's own treatment is broken.
    assert blocking(result) == findings


@pytest.mark.browser
@pytest.mark.browser_timeout(300)
def test_broken_construct_contracts_point_into_the_vocabulary(library, vocabulary, handoff):
    repo, _ = handoff
    def edit(html):
        html = html.replace('data-kd-slot="form.email"', 'data-kd-slot="form.cardnumber"', 1)
        html = html.replace('<footer data-kd-construct="footer"', '<div data-kd-construct="footer"', 1).replace("</footer>", "</div>", 1)
        return html.replace('data-kd-construct="card"', 'data-kd-construct="order-summary"', 1)
    result = verify(library, "harbor", compliant(repo, edit=edit), code=1)
    found = {(f["type"], f["rule"], f["target"]) for f in blocking(result) if f["rule"].startswith("site-")}
    assert {("violation", "site-slot", "form"), ("missing", "site-slot", "form.email"),
            ("violation", "site-semantics", "footer"), ("violation", "site-construct", "page")} <= found
    missing = next(f for f in blocking(result) if f["type"] == "missing")
    assert missing["file"] == "vocabulary/v1/vocabulary.json"
    assert pointer_value(vocabulary, missing["pointer"])["id"] == "email"


@pytest.mark.browser
@pytest.mark.browser_timeout(300)
def test_a_justified_exception_covers_a_finding_and_stays_reported(library, handoff):
    repo, _ = handoff
    page = compliant(repo, '<div style="padding:13px"><p>Note</p></div>')
    assert not verify(library, "harbor", page, code=1)["accepted"]
    inventory = inventory_document()
    inventory["exceptions"] = [{"scope": "13px", "rule": "off-language-space", "reason": "Third-party payment widget inset"},
                               {"scope": "5px", "rule": "off-language-space", "reason": ""}]
    (repo / "kinbase-design.inventory.json").write_text(json.dumps(inventory))
    result = verify(library, "harbor", page, "--inventory", repo / "kinbase-design.inventory.json", code=0)
    covered = [f for f in result["findings"] if f["rule"] == "off-language-space"]
    assert result["accepted"] and len(covered) == 1 and covered[0]["exception"] == "inventory:/exceptions/0"


@pytest.mark.browser
@pytest.mark.browser_timeout(300)
def test_a_pinned_version_judges_the_page_built_for_it(library, harbor, handoff):
    repo, result = handoff
    reference = json.loads((library.workspace / "handoffs" / result["handoff"] / "handoff.json").read_text())["language"]
    page = compliant(repo)
    harbor["style"]["color"]["primary"]["$value"] = "#7a1fa2"
    library.write(harbor)
    moved = verify(library, "harbor", page, code=1)
    assert any(f["rule"] == "role-conformance" for f in blocking(moved))
    pinned = verify(library, reference, page, code=0)
    assert pinned["accepted"] and pinned["language"] == reference


@pytest.mark.browser
@pytest.mark.browser_timeout(120)
def test_a_page_that_cannot_be_loaded_is_never_compliant(library, harbor):
    result = library.json("verify", "harbor", "--page", "http://127.0.0.1:9/checkout", "--widths", "320", cwd=library.project,
                          code=1, timeout=120)
    assert not result["accepted"] and [f["rule"] for f in blocking(result)] == ["render"]
