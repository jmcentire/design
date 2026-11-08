"""M2 B5: authored source values, real HTTP/Chromium capture and offline reconstruction.

Falsifiers: hard-coded palette/type/spacing, omit a media-query width, invent a
font match, refetch the live site during drafting, lose captures, or hide divergence.
"""

import hashlib
import json
import socket

import pytest
from PIL import Image

from tests.m2_support import (capture, color_distance, confined, dereference, dimension_px,
                              draft, png, read_json, token_values)

pytestmark = [pytest.mark.browser, pytest.mark.browser_timeout(420)]

PALETTE = ("#102a43", "#f3f0e8", "#b34224", "#ffffff")
SIZES = (16, 20, 25, 31.25)


def family_names(value):
    return [family.strip().strip('"\'') for family in value.split(",")]


def opaque_color(value):
    if isinstance(value, dict):
        assert value["colorSpace"] == "srgb" and value.get("alpha", 1) == 1
        return "#" + "".join(f"{round(channel * 255):02x}" for channel in value["components"])
    value = value.lower()
    if len(value) == 9:
        assert value[-2:] == "ff"
        value = value[:7]
    return value


def tree_hashes(root):
    return {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in root.rglob("*") if path.is_file()}


def test_authored_site_is_captured_measured_and_reconstructed_offline(
        library, fixture_site, ingest_config, tmp_path):
    urls = [fixture_site.url + "/editorial/" + name for name in ("index.html", "detail.html")]
    artifact, artifact_root, captured = capture(library, urls)
    assert not captured["problems"], captured
    for item in captured["pages"]:
        assert {320, 800, 960} <= {int(width) for width in item["widths"]}
    assert any("800px" in query for query in captured["media_queries"])
    assert any(font["family"].strip('"\'') == "Fixture Sans" and str(font["weight"]) == "400"
               and font["style"] == "normal" and font["src"] for font in captured["fonts"])
    logos = [asset for asset in captured["assets"] if asset["kind"] == "logo"]
    assert logos, "The authored nav logo was not offered"
    original_logo = (fixture_site.root / "editorial" / "logo.svg").read_bytes()
    assert any(confined(artifact_root, logo["file"]).read_bytes() == original_logo for logo in logos)
    immutable = tree_hashes(artifact_root)
    fixture_site.available = False
    request_count = len(fixture_site.requests)
    root, document, summary = draft(library, [artifact], "cedar")
    facts = summary["measured"]
    assert facts["palette"]
    for color in PALETTE:
        assert min(color_distance(color, entry["value"]) for entry in facts["palette"]) <= ingest_config["color_delta_e"]
    for entry in facts["palette"]:
        assert entry["sources"]
        measured = max(color_distance(source, entry["value"]) for source in entry["sources"])
        assert entry["max_delta_e"] == pytest.approx(measured, abs=0.02)
        assert measured <= ingest_config["color_delta_e"]
        assert opaque_color(dereference(document["style"], "{" + entry["token"] + "}")) == entry["value"].lower()
    assert any("Fixture Sans" in family_names(family) for family in facts["font_families"])
    assert facts["type_scale"]["base_px"] == pytest.approx(16, abs=ingest_config["type_size_px"])
    assert facts["type_scale"]["ratio"] == pytest.approx(1.25, abs=ingest_config["type_ratio"])
    for size in SIZES:
        assert min(abs(size - actual) for actual in facts["type_scale"]["sizes_px"]) <= ingest_config["type_size_px"]
    assert facts["spacing"]["base_px"] == pytest.approx(8, abs=ingest_config["spacing_px"])
    for step in (8, 16, 24, 32):
        assert min(abs(step - value) for value in facts["spacing"]["steps_px"]) <= ingest_config["spacing_px"]
    for radius in (8, 16):
        assert min(abs(radius - value) for value in facts["radii_px"]) <= ingest_config["radius_px"]
    assert 800 in facts["breakpoints_px"]
    dimensions = [dimension_px(dereference(document["style"], value))
                  for _, kind, value in token_values(document["style"]) if kind == "dimension"]
    for size in SIZES:
        assert min(abs(size - actual) for actual in dimensions) <= ingest_config["type_size_px"]
    space = [dimension_px(dereference(document["style"], value))
             for _, kind, value in token_values(document["style"]["space"]) if kind == "dimension"]
    assert min(abs(8 - actual) for actual in space) <= ingest_config["spacing_px"]
    # Found originals are offered; an extraction must not silently approve them.
    original_digests = {hashlib.sha256((fixture_site.root / "editorial" / filename).read_bytes()).hexdigest()
                        for filename in ("logo.svg", "fixture.ttf")}
    assert not [variant for asset in document.get("assets", {}).values() for variant in asset["variants"].values()
                if variant.get("file", "").split("/")[-1] in original_digests]
    library.cli("fidelity", "cedar", cwd=library.project, timeout=90)
    fidelity_root = root / "fidelity"
    report = read_json(fidelity_root / "report.json")
    expected = {(item["name"], int(width)): artifact_root / files["screenshot"]
                for item in captured["pages"] for width, files in item["widths"].items()}
    assert {(pair["page"], pair["width"]) for pair in report["pairs"]} == set(expected)
    assert len(report["pairs"]) == len(expected)
    for pair in report["pairs"]:
        for key in ("capture", "reconstruction"):
            path = fidelity_root / pair[key]
            assert path.resolve().is_relative_to(library.workspace.resolve())
            png(path)
        with Image.open(fidelity_root / pair["capture"]) as reported, Image.open(expected[pair["page"], pair["width"]]) as original:
            assert reported.size == original.size
            assert reported.convert("RGBA").tobytes() == original.convert("RGBA").tobytes()
    measured = report["facts"]
    assert family_names(measured["font_family"]["captured"])[0] == "Fixture Sans"
    assert family_names(measured["font_family"]["draft"])[0] == "Fixture Sans"
    assert measured["font_family"]["match"] is True
    for key in ("captured_ratio", "draft_ratio"):
        assert measured["type_scale"][key] == pytest.approx(1.25, abs=ingest_config["type_ratio"])
    for key in ("captured_px", "draft_px"):
        assert measured["spacing_base"][key] == pytest.approx(8, abs=ingest_config["spacing_px"])
    assert measured["palette"]
    for color in PALETTE:
        assert any(color_distance(color, entry["captured"]) <= ingest_config["color_delta_e"]
                   for entry in measured["palette"])
    for entry in measured["palette"]:
        assert entry["delta_e"] == pytest.approx(color_distance(entry["captured"], entry["draft"]), abs=0.02)
    # The rotated radial layout cannot be expressed by the closed M0/M1 property
    # set. The ingest must expose a coverage gap or a visual question.
    questions = library.json("questions", "cedar", cwd=library.project)
    assert questions or any(f["type"] == "coverage" for f in summary["findings"] + report["findings"])
    assert tree_hashes(artifact_root) == immutable
    assert len(fixture_site.requests) == request_count, "Later ingest steps revisited the live URL"


def test_instruction_like_page_text_cannot_direct_mapping(library, fixture_site, ingest_config):
    summaries = []
    styles = []
    mappings = []
    for name in ("ordinary", "instruction"):
        artifact, root, captured = capture(library, [fixture_site.url + f"/editorial/{name}.html"])
        _, document, summary = draft(library, [artifact], name)
        measured = summary["measured"]
        # Token names may incorporate source identity; compare measured values
        # and resolved token contents rather than naming decisions.
        measured["palette"] = [{key: value for key, value in entry.items() if key != "token"}
                               for entry in measured["palette"]]
        summaries.append(measured)
        styles.append(sorted((kind, json.dumps(dereference(document["style"], value), sort_keys=True))
                             for _, kind, value in token_values(document["style"])))
        mappings.append({construct: {slot: (entry.get("role"), entry.get("emphasis"))
                                     for slot, entry in component.get("slots", {}).items()}
                         for construct, component in document["components"].items()})
        assert set(document["components"]) <= set(library.json("vocabulary")["constructs"])
        if name == "instruction":
            assert any("Ignore previous instructions" in (root / entry["dom"]).read_text()
                       for page in captured["pages"] for entry in page["widths"].values())
    assert summaries[0] == summaries[1]
    assert styles[0] == styles[1]
    assert mappings[0] == mappings[1]


def test_capture_never_sends_credentials_or_cookies(library, fixture_site, ingest_config):
    fixture_site.cookies = True
    capture(library, [fixture_site.url + "/editorial/index.html"])
    assert any("site.css" in request["path"] for request in fixture_site.requests)
    assert all(request["authorization"] is None and request["cookie"] is None
               for request in fixture_site.requests), fixture_site.requests


@pytest.mark.parametrize("endpoint", ["/unavailable", "/protected"])
def test_unavailable_source_reports_failure_without_empty_draft(library, fixture_site, ingest_config, endpoint):
    result = library.cli("capture", "--url", fixture_site.url + endpoint,
                         cwd=library.project, code=(0, 1, 2), timeout=30)
    if result.returncode == 0:
        output = json.loads(result.stdout)
        assert output["problems"] and all(p["message"] for p in output["problems"])
    else:
        assert (result.stdout + result.stderr).strip()
    assert not (library.workspace / "drafts" / "unavailable" / "working.json").exists()
    assert all(request["authorization"] is None for request in fixture_site.requests)


def test_missing_chromium_is_reported_as_environment_failure(library, fixture_site, ingest_config, tmp_path):
    empty_installation = tmp_path / "empty-playwright-installation"
    empty_installation.mkdir()
    result = library.cli("capture", "--url", fixture_site.url + "/editorial/index.html",
                         env={"PLAYWRIGHT_BROWSERS_PATH": str(empty_installation)},
                         cwd=library.project, code=(1, 2), timeout=30)
    diagnostic = (result.stdout + result.stderr).lower()
    assert "chromium" in diagnostic or "browser" in diagnostic
    assert not list((library.workspace / "drafts").glob("*/working.json"))


def assert_capture_refused(result):
    """M2 allows retained capture problems; neither success nor an empty diagnostic is refusal."""
    if result.returncode == 0:
        output = json.loads(result.stdout)
        assert not output["pages"] and output["problems"], output
        diagnostic = " ".join(problem["message"] for problem in output["problems"])
    else:
        diagnostic = result.stdout + result.stderr
    assert diagnostic.strip() and "traceback" not in diagnostic.lower(), diagnostic
    return diagnostic.lower()


@pytest.mark.parametrize("url", ["data:text/html,<h1>Unapproved source</h1>", "javascript:void(0)",
                                 "chrome://version", "ftp://127.0.0.1/source.html", "file"])
def test_non_http_targets_are_refused(library, ingest_config, tmp_path, url):
    if url == "file":
        local = tmp_path / "unapproved-source.html"
        local.write_text("<h1>Unapproved source</h1>")
        url = local.as_uri()
    result = library.cli("capture", "--url", url, cwd=library.project, code=(0, 1, 2), timeout=30)
    diagnostic = assert_capture_refused(result)
    assert any(word in diagnostic for word in ("url", "scheme", "protocol", "http")), diagnostic


def test_embedded_credentials_are_refused_before_contacting_source(library, fixture_site, ingest_config):
    url = fixture_site.url.replace("://", "://fixture-user:fixture-password@") + "/editorial/index.html"
    result = library.cli("capture", "--url", url, cwd=library.project, code=(0, 1, 2), timeout=30)
    diagnostic = assert_capture_refused(result)
    assert any(word in diagnostic for word in ("credential", "auth", "userinfo", "user info")), diagnostic
    assert not fixture_site.requests, "A credential-bearing target was contacted"


def test_localhost_is_an_unauthenticated_capture_target(library, fixture_site, ingest_config):
    url = fixture_site.url.replace("127.0.0.1", "localhost") + "/editorial/index.html"
    _, _, captured = capture(library, [url])
    assert not captured["problems"], captured
    assert captured["pages"] and captured["pages"][0]["widths"]
    assert fixture_site.requests


def test_refused_network_connection_has_a_clear_bounded_failure(library, ingest_config):
    # Bound but not listening: a real unavailable TCP service with no port-reuse race.
    with socket.socket() as unavailable:
        unavailable.bind(("127.0.0.1", 0))
        port = unavailable.getsockname()[1]
        result = library.cli("capture", "--url", f"http://127.0.0.1:{port}/",
                             cwd=library.project, code=(0, 1, 2), timeout=30)
    diagnostic = assert_capture_refused(result)
    assert any(word in diagnostic for word in ("connect", "network", "refused", "unreachable", "failed")), diagnostic
    assert not list((library.workspace / "drafts").glob("*/working.json"))
