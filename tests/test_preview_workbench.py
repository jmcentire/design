"""Normative B1, B15/B16: byte identity, WSGI routes and lasting upload effects.

Falsifiers: embed language identity in HTML, serve a different preview, silently
omit a language/frame/page, render missing assets as healthy, or redirect an upload
without saving the bytes. Browser claims live in test_browser.py, not this parser.
"""

import copy
import hashlib
import shutil
import subprocess
from urllib.parse import parse_qs, urljoin, urlsplit

import pytest

from tests.html_support import Document
from tests.support import FIXTURES, PAGES, multipart, request


def second_language(library, language):
    second = copy.deepcopy(language)
    second["id"], second["name"] = "coral", "Coral Test Language"
    second["style"]["color"]["ink"]["$value"] = "#773311"
    library.write(second)
    shutil.copytree(library.path().parent / "assets", library.path("coral").parent / "assets")
    return second


def test_default_language_html_identity_and_css_difference(library, language, tmp_path):
    """B1 + amendment 02: identical binding ids/variants/formats, different token values."""
    second_language(library, language)
    a = library.build(tmp_path / "tidal-site")
    b = library.build(tmp_path / "coral-site", "coral")
    for name in PAGES:
        assert (a / name).read_bytes() == (b / name).read_bytes(), name
    assert (a / "language.css").read_bytes() != (b / "language.css").read_bytes()


def test_wsgi_serves_exact_static_preview_bytes(app, library, tmp_path):
    preview = library.build(tmp_path / "preview")
    for path in preview.rglob("*"):
        if path.is_file():
            result = request(app, "/preview/tidal/" + path.relative_to(preview).as_posix())
            assert result["status"] == 200
            assert result["body"] == path.read_bytes(), path


@pytest.mark.parametrize("target", ["/languages/absent", "/preview/absent/index.html", "/preview/tidal/absent.html"])
def test_unknown_language_or_preview_file_is_404(app, target):
    assert request(app, target)["status"] == 404


def test_grid_and_compare_expose_every_language(app, library, language):
    second = second_language(library, language)
    response = request(app, "/")
    assert response["status"] == 200
    grid = Document(response["body"])
    destinations = [urlsplit(urljoin("http://test/", a.attrs.get("href", ""))).path
                    for a in grid.all("a")]
    for item in (language, second):
        assert item["name"] in grid.text()
        assert f"/languages/{item['id']}" in destinations
    # Human-visible status is a mandated public message, not an internal prose pin.
    assert "unknown" in grid.text().lower()
    assert "kinbase" in grid.text().lower()
    compared = request(app, "/compare?a=tidal&b=coral&page=search.html&width=768")
    assert compared["status"] == 200
    frames = Document(compared["body"]).all("iframe")
    sources = [urlsplit(urljoin("http://test/compare", frame.attrs["src"])).path for frame in frames]
    assert sources.count("/preview/tidal/search.html") == 1
    assert sources.count("/preview/coral/search.html") == 1


def test_viewer_frames_selected_page_and_lists_all_page_links(app):
    response = request(app, "/languages/tidal?page=form.html&width=320")
    assert response["status"] == 200
    viewer = Document(response["body"])
    assert any(urlsplit(urljoin("http://test/languages/tidal", frame.attrs["src"])).path == "/preview/tidal/form.html"
               for frame in viewer.all("iframe"))
    linked_pages = set()
    for anchor in viewer.all("a"):
        target = urlsplit(urljoin("http://test/languages/tidal", anchor.attrs.get("href", "")))
        linked_pages.update(parse_qs(target.query).get("page", []))
        if target.path.startswith("/preview/tidal/"):
            linked_pages.add(target.path.rsplit("/", 1)[-1])
    assert set(PAGES) <= linked_pages


def test_assets_panel_shows_manifest_hashes_and_gaps(app, library, language):
    language["components"]["nav"]["assets"]["logo"] = "lost-logo:primary"
    library.write(language)
    result = request(app, "/languages/tidal")
    assert result["status"] == 200
    page = Document(result["body"])
    text = page.text()
    for asset_id, asset in language["assets"].items():
        assert asset_id in text
        for variant, details in asset["variants"].items():
            assert variant in text
            assert details["file"].split("/")[-1] in text
    assert "lost-logo" in text
    assert "missing" in text.lower()


def test_multipart_upload_promotes_bytes_before_redirect(app, library):
    data = (FIXTURES / "mark.svg").read_bytes()
    body, content_type = multipart({"asset_id": "web-upload", "kind": "logo", "variant": "primary"},
                                  "web-logo.svg", data)
    result = request(app, "/languages/tidal/assets", "POST", body, content_type)
    assert result["status"] in {302, 303}
    headers = {k.lower(): v for k, v in result["headers"].items()}
    assert urlsplit(headers["location"]).path == "/languages/tidal"
    digest = hashlib.sha256(data).hexdigest()
    working = library.read()
    assert working["assets"]["web-upload"]["variants"]["primary"]["file"] == f"sha256/{digest}"
    assert (library.path().parent / "assets" / "sha256" / digest).read_bytes() == data
    assert any(p.is_file() and p.read_bytes() == data for p in library.workspace.rglob("*"))
    viewer = request(app, headers["location"])
    assert viewer["status"] == 200
    assert "web-upload" in Document(viewer["body"]).text()


@pytest.mark.parametrize("configuration", ["flag", "env", "toml"])
def test_library_and_workspace_in_arbitrary_git_subfolder(library, language, tmp_path, configuration):
    """Observe validation and import persistence from another cwd, not just configuration echo."""
    subprocess.run(["git", "init", "-q", str(library.project)], check=True, capture_output=True)
    options = {"configured": configuration == "flag", "cwd": library.project}
    if configuration == "env":
        options["env"] = {"KINBASE_DESIGN_LIBRARY": str(library.library),
                          "KINBASE_DESIGN_WORKSPACE": str(library.workspace)}
    if configuration == "toml":
        # Both values are relative to this configuration file, per the public contract.
        (library.project / "kinbase-design.toml").write_text(
            'library = "design/shared-library"\nworkspace = "../private-workspace"\n')
    report = library.json("validate", "tidal", **options)
    assert report["accepted"] is True
    source = tmp_path / "configuration-logo.svg"
    source.write_bytes((FIXTURES / "mark.svg").read_bytes())
    artifact = library.json("import-artifact", "--file", source, **options)["artifact"]
    assert any(p.is_file() and p.read_bytes() == source.read_bytes()
               for p in (library.workspace / "artifacts" / artifact).rglob("*"))


def test_configuration_precedence_is_flag_then_env_then_toml(library, language):
    """A stale local configuration must not divert an explicitly targeted library write/read."""
    (library.project / "kinbase-design.toml").write_text('library = "does-not-exist"\n')
    report = library.json("validate", "tidal", cwd=library.project,
                          env={"KINBASE_DESIGN_LIBRARY": str(library.project / "also-absent")})
    assert report["accepted"] is True
    report = library.json("validate", "tidal", configured=False, cwd=library.project,
                          env={"KINBASE_DESIGN_LIBRARY": str(library.library),
                               "KINBASE_DESIGN_WORKSPACE": str(library.workspace)})
    assert report["accepted"] is True
