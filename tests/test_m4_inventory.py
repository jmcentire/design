"""M4 B11 / amendment 16: effective defaults, distinct states and bound assets.

Oracle: known complete role defaults, equal/distinct authored colors, and an
unbound versus bound real font. Presence of a component/state/asset declaration
alone is not evidence of treatment. All commands and Git repositories are real.
"""

import pytest

from tests.m4_support import inventory_check, inventory_document, only_missing, site_repository
from tests.support import package_asset
from tests.test_versions_assets import bind_font, make_font


@pytest.fixture
def site(tmp_path):
    return site_repository(tmp_path)


def state_fixture(language, vocabulary):
    construct, state = next((name, state) for name, contract in vocabulary["constructs"].items()
                            for state in contract["states"] if state != "default")
    component = language["components"][construct]
    component["properties"]["color"] = "{color.ink}"
    # Distinct aliases resolve to exactly the same authored color, so the state
    # is declared but still untreated according to amendment 16.
    component["states"] = {state: {"color": "{color.chain}"}}
    return construct, state, inventory_document(construct, slots=(), states=("default", state))


def test_role_defaults_treat_construct_and_slots_without_component_declarations(library, language, site):
    del language["components"]["card"]
    library.write(language)
    library.validate(accepted=True)
    report = inventory_check(library, site, inventory_document(), accepted=True)
    assert not [finding for finding in report["findings"] if finding["type"] in {"missing", "violation"}], report


@pytest.mark.parametrize("gap", ["construct", "slot"])
def test_unknown_required_construct_or_slot_is_one_missing_gap(library, language, site, gap):
    inventory = (inventory_document("fixture-unrepresented-group", slots=(), states=()) if gap == "construct"
                 else inventory_document(slots=("fixture-unrepresented-slot",)))
    only_missing(inventory_check(library, site, inventory, accepted=False))
    # Resolve the sole requested gap with a vocabulary-backed requirement; no
    # language changes are necessary because its role defaults already suffice.
    report = inventory_check(library, site, inventory_document(), accepted=True)
    assert not [finding for finding in report["findings"] if finding["type"] in {"missing", "violation"}], report


def test_nondefault_state_requires_resolved_difference_not_a_declaration(library, language, vocabulary, site):
    construct, state, inventory = state_fixture(language, vocabulary)
    library.write(language)
    library.validate(accepted=True)
    default = library.json("resolve", "tidal", construct)["properties"]
    altered = library.json("resolve", "tidal", construct, "--state", state)["properties"]
    assert {p: v["value"] for p, v in default.items()} == {p: v["value"] for p, v in altered.items()}
    only_missing(inventory_check(library, site, inventory, accepted=False))
    language["components"][construct]["states"][state]["color"] = "{color.override}"
    library.write(language)
    assert library.json("resolve", "tidal", construct, "--state", state)["properties"]["color"]["value"] == "#226644"
    report = inventory_check(library, site, inventory, accepted=True)
    assert not [finding for finding in report["findings"] if finding["type"] in {"missing", "violation"}], report


def test_justified_exception_reports_and_covers_its_missing_state(library, language, vocabulary, site):
    construct, state, inventory = state_fixture(language, vocabulary)
    library.write(language)
    missing = only_missing(inventory_check(library, site, inventory, accepted=False))
    # Rule identifiers are not pinned for inventory findings. The caller uses
    # the reported rule to address this independently seeded gap through the
    # public exception contract, rather than guessing a private rule spelling.
    inventory["exceptions"] = [{"scope": f"overview/{construct}.{state}", "rule": missing["rule"],
                                 "reason": "This page intentionally uses the same treatment in this state."}]
    covered = only_missing(inventory_check(library, site, inventory, accepted=True))
    assert covered.get("exception"), "A covered finding must remain reported with its exception"
    for key in ("source", "rule", "file", "pointer", "observed"):
        assert covered[key] == missing[key]
    inventory["exceptions"][0]["reason"] = ""
    report = inventory_check(library, site, inventory, accepted=False)
    assert any(finding["type"] in {"missing", "violation"} and not finding.get("exception") for finding in report["findings"])


def test_required_font_kind_needs_binding_not_only_a_packaged_original(library, language, site, tmp_path):
    font = tmp_path / "unbound.ttf"
    make_font(font)
    package_asset(library, language, "fixture-font", "font", font.read_bytes(), variant="regular", fmt="ttf", weight=400, style="normal")
    language["assets"]["fixture-font"]["meta"] = {"font": {"family": "Fixture Sans"}}
    library.write(language)
    library.validate(accepted=True)
    inventory = inventory_document(assets=("font",))
    only_missing(inventory_check(library, site, inventory, accepted=False))
    bind_font(library, language, tmp_path)
    report = inventory_check(library, site, inventory, accepted=True)
    assert not [finding for finding in report["findings"] if finding["type"] in {"missing", "violation"}], report


def test_confirmed_language_violation_fails_inventory_acceptance(library, language, site):
    language["components"]["card"]["properties"]["padding"] = "9px"
    library.write(language)
    report = inventory_check(library, site, inventory_document(), accepted=False)
    assert any(finding["source"] == "language" and finding["type"] == "violation" and finding["rule"] == "R2" for finding in report["findings"]), report


def test_coverage_alone_does_not_fail_inventory_acceptance(library, language, vocabulary, site):
    slots = "".join("{{slot:" + slot["id"] + "}}" for slot in vocabulary["constructs"]["card"]["slots"])
    language["layout"]["variants"]["card"] = {"no-parts": {"template": "<article>" + slots + "</article>"}}
    language["components"]["card"]["variant"] = "no-parts"
    language["components"]["card"]["parts"] = {"unused-part": {"padding": "{space.small}"}}
    library.write(language)
    control = library.validate(accepted=True)
    assert any(finding["type"] == "coverage" for finding in control["findings"])
    report = inventory_check(library, site, inventory_document(), accepted=True)
    assert any(finding["source"] == "language" and finding["type"] == "coverage" for finding in report["findings"]), report
    assert not [finding for finding in report["findings"] if finding["type"] in {"missing", "violation"}], report


def test_inventory_requires_only_requested_variant_of_a_bound_asset(library, language, site):
    """Amendment 19: a named variant is an inventory need, not an intrinsic one.

    The asset is bound through its primary variant. The request asks whether that
    bound asset *has* on-dark; it does not require rewriting the primary binding.
    A different, unbound logo with on-dark cannot satisfy the request.
    """
    logo = language["assets"]["fixture-logo"]
    assert "on-dark" not in logo["variants"]
    bindings = [value for component in language["components"].values()
                for value in component["assets"].values()]
    assert "fixture-logo:primary" in bindings
    library.validate(accepted=True)
    bare = inventory_document(assets=("logo",))
    assert not [f for f in inventory_check(library, site, bare, accepted=True)["findings"]
                if f["type"] in {"missing", "violation"}]
    requested = inventory_document(assets=("logo:on-dark",))
    missing = only_missing(inventory_check(library, site, requested, accepted=False))
    assert missing["pointer"] == "/pages/0/assets/0" and missing["observed"] == "logo:on-dark"
    dark = b'<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24"><circle cx="12" cy="12" r="10" fill="white"/></svg>'
    package_asset(library, language, "offered-logo", "logo", dark, variant="on-dark")
    library.write(language)
    library.validate(accepted=True)
    still_missing = only_missing(inventory_check(library, site, requested, accepted=False))
    assert still_missing["pointer"] == missing["pointer"] and still_missing["observed"] == missing["observed"]
    # Reuse the test-owned packaged bytes under the bound asset's manifest.
    logo["variants"]["on-dark"] = dict(language["assets"]["offered-logo"]["variants"]["on-dark"])
    library.write(language)
    library.validate(accepted=True)
    report = inventory_check(library, site, requested, accepted=True)
    assert not [f for f in report["findings"] if f["type"] in {"missing", "violation"}]
    assert bindings == [value for component in library.read()["components"].values()
                        for value in component["assets"].values()]


def test_inventory_reports_exactly_unsupplied_kind_variant_requests(library, language, site):
    # A primary logo and image already exist and are bound by the fixture. A
    # variant on another kind cannot satisfy an identically named logo variant.
    image = language["assets"]["fixture-image"]
    image["variants"]["on-dark"] = dict(image["variants"]["primary"])
    library.write(language)
    library.validate(accepted=True)
    requests = ("logo", "image", "image:on-dark", "logo:on-dark", "image:on-light")
    inventory = inventory_document(assets=requests)
    report = inventory_check(library, site, inventory, accepted=False)
    missing = [f for f in report["findings"] if f["type"] == "missing"]
    assert len(missing) == 2, report
    assert {(f["pointer"], f["observed"]) for f in missing} == {
        ("/pages/0/assets/3", "logo:on-dark"), ("/pages/0/assets/4", "image:on-light")}
    assert not [f for f in report["findings"] if f["type"] == "violation"], report
    # Removing only the two unsupplied requirements closes every missing gap.
    inventory["pages"][0]["assets"] = list(requests[:3])
    report = inventory_check(library, site, inventory, accepted=True)
    assert not [f for f in report["findings"] if f["type"] in {"missing", "violation"}]


def test_asset_exceptions_respect_variant_kind_and_page_and_retain_findings(library, language, site):
    inventory = inventory_document(assets=("logo:on-dark", "logo:on-light", "image:on-dark"))
    other_page = inventory_document(assets=("logo:on-dark",))["pages"][0]
    other_page.update(id="details", path="details.html")
    inventory["pages"].append(other_page)
    before = inventory_check(library, site, inventory, accepted=False)
    missing = {f["pointer"]: f for f in before["findings"] if f["type"] == "missing"}
    expected = {"/pages/0/assets/0", "/pages/0/assets/1", "/pages/0/assets/2", "/pages/1/assets/0"}
    assert set(missing) == expected and sum(f["type"] == "missing" for f in before["findings"]) == 4
    inventory["exceptions"] = [{"scope": "overview/asset/logo:on-dark", "rule": "missing",
                                 "reason": "This page presents its logo only on the light surface."}]

    def reported_exceptions(accepted):
        report = inventory_check(library, site, inventory, accepted=accepted)
        findings = [f for f in report["findings"] if f["type"] == "missing"]
        assert len(findings) == 4 and {f["pointer"] for f in findings} == expected
        for finding in findings:
            original = missing[finding["pointer"]]
            for key in ("source", "file", "pointer", "rule", "observed"):
                assert finding[key] == original[key], "An exception changed or removed its underlying finding"
            if finding.get("exception"):
                # Amendment 21 pins an inventory JSON pointer, not a scope string
                # or free-text justification, as the reported exception identity.
                pointer = finding["exception"]
                assert pointer.startswith("/exceptions/") and pointer.count("/") == 2
                assert inventory["exceptions"][int(pointer.rsplit("/", 1)[1])]["reason"]
        return {f["pointer"]: f.get("exception") for f in findings}

    exceptions = reported_exceptions(False)
    assert exceptions["/pages/0/assets/0"] == "/exceptions/0"
    assert all(not exceptions[pointer] for pointer in expected - {"/pages/0/assets/0"})
    # Widening to a bare kind covers both logo variants on this page, but neither
    # another kind nor the same request on a different page.
    inventory["exceptions"][0]["scope"] = "overview/asset/logo"
    exceptions = reported_exceptions(False)
    assert exceptions["/pages/0/assets/0"] == exceptions["/pages/0/assets/1"] == "/exceptions/0"
    assert not exceptions["/pages/0/assets/2"] and not exceptions["/pages/1/assets/0"]
    inventory["exceptions"] += [
        {"scope": "overview/asset/image:on-dark", "rule": "missing", "reason": "Only the light image presentation is used here."},
        {"scope": "details/asset/logo:on-dark", "rule": "missing", "reason": "The details page also uses a light surface."}]
    assert reported_exceptions(True) == {
        "/pages/0/assets/0": "/exceptions/0", "/pages/0/assets/1": "/exceptions/0",
        "/pages/0/assets/2": "/exceptions/1", "/pages/1/assets/0": "/exceptions/2"}


def test_bare_asset_kind_exception_covers_bare_and_variant_requests_only_with_reason(library, language, site):
    assert not any(asset["kind"] == "font" for asset in language["assets"].values())
    inventory = inventory_document(assets=("font", "font:regular"))
    inventory["exceptions"] = [{"scope": "overview/asset/font:regular", "rule": "missing",
                                 "reason": "The site intentionally uses the platform font."}]
    report = inventory_check(library, site, inventory, accepted=False)
    missing = [f for f in report["findings"] if f["type"] == "missing"]
    assert len(missing) == 2
    exceptions = {f["observed"]: f.get("exception") for f in missing}
    assert not exceptions["font"] and exceptions["font:regular"] == "/exceptions/0"
    inventory["exceptions"][0]["scope"] = "overview/asset/font"
    report = inventory_check(library, site, inventory, accepted=True)
    missing = [f for f in report["findings"] if f["type"] == "missing"]
    assert len(missing) == 2 and {f["observed"] for f in missing} == {"font", "font:regular"}
    assert all(f["exception"] == "/exceptions/0" for f in missing)
    inventory["exceptions"][0]["reason"] = ""
    report = inventory_check(library, site, inventory, accepted=False)
    assert any(f["type"] in {"missing", "violation"} and not f.get("exception") for f in report["findings"])
