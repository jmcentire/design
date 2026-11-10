"""Synthetic content and public-boundary readers for design-examples amendments 01/02.

No implementation imports, mocks, or captured candidate baselines. All copy and
images are generated here; no Wander or third-party material enters fixtures.
"""
import json
from pathlib import Path
import re
import shutil
from urllib.parse import unquote, urlsplit

from PIL import Image
import pytest

from tests.html_support import Document, Element
from tests.support import ROOT, pointer_value


@pytest.fixture
def content_library(library):
    for name in ("harbor", "lantern"):
        assert (ROOT / "library" / "languages" / name).is_dir(), f"Missing shipped test subject: {name}"
    for source in (ROOT / "library" / "languages").iterdir():
        if (source / "working.json").is_file():
            shutil.copytree(source, library.path(source.name).parent)
    license_file = ROOT / "library" / "FONT-LICENSE.txt"
    if license_file.is_file():
        shutil.copyfile(license_file, library.library / license_file.name)
    return library


def write_content(directory, collection=True):
    directory.mkdir(parents=True, exist_ok=True)
    images = directory / "img"
    images.mkdir(exist_ok=True)
    Image.new("RGB", (48, 32), (45, 110, 90)).save(images / "sample.png")
    (images / "logo.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 32"><rect width="48" height="32" fill="#246"/></svg>')
    media = {"src": "img/sample.png", "alt": "Synthetic green rectangle",
             "caption": "A generated image caption", "credit": "Fixture artist"}
    document = {
        "schema": "kinbase-content/1",
        "page": {"title": "Field notebook", "lang": "en", "description": "A synthetic guide"},
        "site": {"name": "Test Observatory", "logo": {"src": "img/logo.svg", "alt": "Observatory mark"},
                 "nav": [{"text": "Read the guide", "href": "#guide"}]},
        "blocks": [
            {"type": "hero", "id": "welcome", "eyebrow": "An independent example",
             "title": "A day of small discoveries", "body": ["Start here. ",
                 {"text": "Read on", "href": "#guide", "strong": True},
                 {"text": "Take your time", "em": True}], "media": dict(media),
             "actions": [{"text": "Continue", "href": "#guide"}]},
            {"type": "section", "id": "guide", "title": "The practical guide", "content": [
                {"paragraph": 'Literal <script>danger()</script> & "quoted" text'},
                {"list": {"ordered": False, "items": ["Bring a notebook", "Watch carefully"]}},
                {"list": {"ordered": True, "items": ["First observe", "Then describe"]}},
                {"media": dict(media)},
                {"quote": {"text": "Details reward attention", "cite": "An invented author"}}]},
            {"type": "cta", "id": "finish", "title": "Keep exploring", "body": "Return another day",
             "actions": [{"text": "Back to start", "href": "#welcome"}]}],
        "footer": {"text": "End of the notebook", "links": [{"text": "Guide index", "href": "#guide"}],
                   "notices": ["Synthetic fixture: permission granted for testing.", "Second independent notice."]}}
    if collection:
        document["blocks"].insert(2, {"type": "collection", "id": "entries", "title": "Selected entries",
            "intro": "A few examples", "items": [
                {"title": f"Notebook entry {i}", "eyebrow": "Field note", "body": f"Observation number {i}",
                 "media": dict(media), "facts": [{"label": "Category", "value": "Sample"}],
                 "action": {"text": f"Open entry {i}", "href": "#guide"}} for i in range(1, 4)]})
    path = directory / "content.json"
    save_content(path, document)
    return path, document


def save_content(path, document):
    path.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")


def render_result(library, content, out, language="harbor"):
    result = library.json("render-page", language, "--content", content, "--out", out)
    assert Path(result["out"]).resolve() == out.resolve()
    assert result["language"] == language
    assert isinstance(result["version"], str) and result["version"]
    assert isinstance(result["findings"], list)
    assert result["validated"] is True
    assert result["rendered_check"] in {"accepted", "rejected", "unchecked"}
    assert result["accepted"] is (result["rendered_check"] == "accepted")
    assert (out / "index.html").is_file()
    assert (out / "hooks.json").is_file()
    assert (out / "ATTRIBUTION.txt").is_file()
    return result


def render(library, content, out, language="harbor"):
    render_result(library, content, out, language)
    return Document((out / "index.html").read_bytes())


def content_findings(report, content, document, pointer):
    matches = [f for f in report["findings"] if f["pointer"] == pointer]
    assert matches, (pointer, report)
    for finding in matches:
        file = Path(finding["file"])
        # The amendment names the content file without fixing absolute vs relative.
        assert any(p.resolve() == content.resolve() for p in
                   (file, content.parent / file, ROOT / file)), finding
        assert pointer_value(document, finding["pointer"]) == finding["observed"]
        assert finding["message"].strip() and finding["expected"].strip()


def bundle_reference(bundle, referring, url):
    parts = urlsplit(url)
    assert not parts.scheme and not parts.netloc, ("Remote/absolute resource", url)
    path = Path(unquote(parts.path))
    assert not path.is_absolute(), url
    target = (referring.parent / path).resolve() if parts.path else referring.resolve()
    assert target.is_relative_to(bundle.resolve()), url
    assert target.is_file(), (url, target)
    return target


def assert_portable(bundle):
    """Read actual shipped HTML/CSS references after relocation.

    CSS URL/import spellings cover ordinary serializer output; browser request
    observation is the complementary check for computed CSS and loading.
    """
    html = bundle / "index.html"
    doc = Document(html.read_bytes())
    assert not doc.all("base"), "A base URL defeats bundle-relative portability"
    for node in doc.all():
        for attr in ("src", "poster"):
            if attr in node.attrs:
                bundle_reference(bundle, html, node.attrs[attr])
        if node.tag == "link" and "href" in node.attrs:
            bundle_reference(bundle, html, node.attrs["href"])
        if node.tag == "a" and "href" in node.attrs:
            href = node.attrs["href"]
            parts = urlsplit(href)
            if not parts.scheme and not parts.netloc:
                target = bundle_reference(bundle, html, href)
                if parts.fragment:
                    assert Document(target.read_bytes()).all(id=unquote(parts.fragment)), href
    css_files = list(bundle.rglob("*.css"))
    assert css_files, "Missing language stylesheet"
    for path in css_files:
        css = re.sub(r"/\*.*?\*/", "", path.read_text(), flags=re.S)
        urls = re.findall(r"url\(\s*([^)]*?)\s*\)", css, re.I)
        imports = re.findall(r"@import\s+(['\"])(.*?)\1", css, re.I)
        for url in [u.strip().strip('\"\'') for u in urls] + [u for _, u in imports]:
            bundle_reference(bundle, path, url)
    return doc


def tree_shape(node):
    """Metamorphic domain-word test: text values vary; tags/hook structure must not."""
    return (node.tag, tuple(sorted((k, v) for k, v in node.attrs.items()
                                  if k.startswith("data-kd-") or k in {"href", "src"})),
            tuple(tree_shape(c) for c in node.children if isinstance(c, Element)))
