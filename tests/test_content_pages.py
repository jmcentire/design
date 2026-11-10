"""Normative: design-examples amendments 01/02, CLI and bundle boundaries.

Falsifiers: language-dependent DOM, lost copy/links, executable text, invalid
image copied, escaped file read, unresolved findings, or overwritten user files.
Expectations are direct content rules and relations, never implementation output.
"""
import copy
import json
import shutil

from PIL import Image
import pytest

from tests.content_support import (content_library, write_content, save_content, render,
    content_findings, assert_portable, bundle_reference, tree_shape)


@pytest.mark.parametrize("collection", [False, True], ids=["guide", "cards"])
def test_content_is_invariant_semantic_and_portable(content_library, tmp_path, collection):
    source, content = write_content(tmp_path / "source", collection)
    outputs = [tmp_path / name for name in ("harbor", "lantern")]
    for language, out in zip(("harbor", "lantern"), outputs):
        render(content_library, source, out, language)
    assert (outputs[0] / "index.html").read_bytes() == (outputs[1] / "index.html").read_bytes()
    # Remove the original documents/assets and old output locations. References
    # that accidentally depend on either must now fail at the actual filesystem.
    shutil.rmtree(source.parent)
    for number, out in enumerate(outputs):
        moved = tmp_path / "relocated with spaces" / str(number)
        moved.parent.mkdir(exist_ok=True)
        shutil.move(out, moved)
        doc = assert_portable(moved)
        for landmark in ("header", "nav", "main", "footer"):
            assert doc.all(landmark), landmark
        assert [h.text() for h in doc.all("h1")] == [content["blocks"][0]["title"]]
        headings = [int(e.tag[1]) for e in doc.all() if e.tag in {"h1", "h2", "h3", "h4", "h5", "h6"}]
        assert all(b <= a + 1 for a, b in zip([0] + headings, headings))
        assert doc.all("ul") and doc.all("ol")
        for text in ("Bring a notebook", "Watch carefully", "First observe", "Then describe"):
            assert any(text in node.text() for node in doc.all("li"))
        assert any("A generated image caption" in f.text() and "Fixture artist" in f.text()
                   for f in doc.all("figcaption"))
        assert doc.all("figure")
        assert not doc.all("script"), "Hostile text became executable markup"
        assert content["blocks"][1]["content"][0]["paragraph"] in doc.text()
        for link in [*content["site"]["nav"], *content["footer"]["links"],
                     *content["blocks"][0]["actions"], *content["blocks"][-1]["actions"]]:
            assert any(link["text"] in a.text() and a.attrs.get("href") == link["href"] for a in doc.all("a"))
        content_images = [e for e in doc.all("img") if e.attrs.get("alt") == "Synthetic green rectangle"]
        assert content_images
        for img in content_images:
            path = bundle_reference(moved, moved / "index.html", img.attrs["src"])
            assert path.is_relative_to((moved / "content-assets").resolve())
            with Image.open(path) as decoded:
                decoded.load()
                assert decoded.size == (48, 32)
        assert doc.all("img", alt="Observatory mark")
        notices = (moved / "ATTRIBUTION.txt").read_text()
        assert all(notice in notices for notice in content["footer"]["notices"])
        # Both named shipped languages package Instrument Sans; public licence
        # notice is the source, not candidate-generated attribution output.
        assert "Copyright 2022 The Instrument Sans Project Authors" in notices
        assert "SIL Open Font License" in notices and "1.1" in notices


def test_no_hero_uses_page_title_and_words_cannot_choose_structure(content_library, tmp_path):
    source, content = write_content(tmp_path / "source")
    content["blocks"] = content["blocks"][1:]
    # Keep links resolvable after removing the hero.
    content["blocks"][-1]["actions"][0]["href"] = "#guide"
    save_content(source, content)
    first = render(content_library, source, tmp_path / "first")
    assert [n.text() for n in first.all("h1")] == [content["page"]["title"]]
    changed = copy.deepcopy(content)
    changed["blocks"][1]["items"][0].update(title="$600 4.9 property blog Paris",
        body="A price, rating, place and blog are only text")
    save_content(source, changed)
    second = render(content_library, source, tmp_path / "second")
    assert tree_shape(first.root) == tree_shape(second.root)
    assert changed["blocks"][1]["items"][0]["title"] in second.text()


@pytest.mark.parametrize("src", ["../outside.png", "/absolute.png", "https://example.invalid/a.png",
    "//example.invalid/a.png", "file:///outside.png", "data:image/png;base64,AA==", "img/escape.png"])
def test_media_path_escape_and_urls_are_refused(content_library, tmp_path, src):
    source, content = write_content(tmp_path / "source")
    outside = tmp_path / "outside.png"
    shutil.copyfile(source.parent / "img/sample.png", outside)
    (source.parent / "img/escape.png").symlink_to(outside)
    if src == "/absolute.png":
        src = str(outside)
    content["blocks"][0]["media"]["src"] = src
    save_content(source, content)
    report = content_library.json("render-page", "harbor", "--content", source, "--out", tmp_path / "bad", code=1)
    content_findings(report, source, content, "/blocks/0/media/src")
    assert outside.read_bytes() == (source.parent / "img/sample.png").read_bytes()


@pytest.mark.parametrize("name,data", [("missing.png", None), ("wrong.png", b"not a PNG"),
    ("wrong.gif", b"GIF89a"), ("unsafe.svg", b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>')])
def test_missing_unsupported_corrupt_and_unsafe_media_report_source(content_library, tmp_path, name, data):
    source, content = write_content(tmp_path / "source")
    if data is not None:
        (source.parent / "img" / name).write_bytes(data)
    content["blocks"][0]["media"]["src"] = "img/" + name
    save_content(source, content)
    report = content_library.json("render-page", "harbor", "--content", source, "--out", tmp_path / "bad", code=1)
    content_findings(report, source, content, "/blocks/0/media/src")


@pytest.mark.parametrize("pointer,value", [
    ("/schema", "kinbase-content/999"), ("/blocks/0/type", "unknown"),
    ("/blocks/0/title", 42), ("/blocks/0/media/alt", ""),
    ("/blocks/0/extra~1field~0", "unexpected"), ("/blocks", []),
    # Amendment 07 permits omission only, not explicit invalid section titles.
    ("/blocks/1/title", ""), ("/blocks/1/title", None), ("/blocks/1/title", 42),
    ("/blocks/1/title", []), ("/blocks/1/title", {}), ("/blocks/1/title", False)])
def test_invalid_content_has_precise_resolvable_findings(content_library, tmp_path, pointer, value):
    source, content = write_content(tmp_path / "source")
    keys = [k.replace("~1", "/").replace("~0", "~") for k in pointer[1:].split("/")]
    node = content
    for key in keys[:-1]:
        node = node[int(key)] if isinstance(node, list) else node[key]
    node[keys[-1]] = value
    save_content(source, content)
    report = content_library.json("render-page", "harbor", "--content", source, "--out", tmp_path / "bad", code=1)
    content_findings(report, source, content, pointer)


def test_decorative_media_positive_control_and_nonbundle_output_preservation(content_library, tmp_path):
    source, content = write_content(tmp_path / "source")
    content["blocks"][0]["media"].update(alt="", decorative=True)
    save_content(source, content)
    doc = render(content_library, source, tmp_path / "valid")
    assert doc.all("img", alt="")
    out = tmp_path / "user-work"
    out.mkdir()
    (out / "index.html").write_bytes(b"user-owned page")
    (out / "notes.txt").write_bytes(b"irreplaceable notes")
    before = {p.name: p.read_bytes() for p in out.iterdir()}
    content_library.cli("render-page", "harbor", "--content", source, "--out", out, code=2)
    assert {p.name: p.read_bytes() for p in out.iterdir()} == before


@pytest.mark.parametrize("suffix", ["jpg", "jpeg", "webp", "svg"])
def test_supported_image_formats_are_real_copied_resources(content_library, tmp_path, suffix):
    source, content = write_content(tmp_path / "source")
    original = source.parent / "img" / ("additional." + suffix)
    if suffix == "svg":
        original.write_bytes((source.parent / "img/logo.svg").read_bytes())
    else:
        Image.new("RGB", (48, 32), (45, 110, 90)).save(original, format="JPEG" if suffix in {"jpg", "jpeg"} else "WEBP")
    content["blocks"][0]["media"]["src"] = "img/" + original.name
    content["blocks"][0]["media"]["alt"] = "Additional format specimen"
    save_content(source, content)
    out = tmp_path / "page"
    doc = render(content_library, source, out)
    images = doc.all("img", alt="Additional format specimen")
    assert images
    for image in images:
        copied = bundle_reference(out, out / "index.html", image.attrs["src"])
        assert copied.is_relative_to((out / "content-assets").resolve())
        if suffix == "svg":
            # SVG decoding is observed by Chromium in the browser selection.
            import xml.etree.ElementTree as ET
            assert ET.fromstring(copied.read_bytes()).tag.endswith("svg")
        else:
            with Image.open(copied) as decoded:
                decoded.load()
                assert decoded.size == (48, 32)


def test_language_variant_does_not_change_vocabulary_owned_content_markup(content_library, tmp_path):
    source, _ = write_content(tmp_path / "source")
    baseline = tmp_path / "baseline"
    render(content_library, source, baseline)
    hooks = json.loads((baseline / "hooks.json").read_bytes())
    identity = hooks["content_pages"]["blocks"]["collection"]["item"]
    vocabulary = json.loads((content_library.library / "vocabulary" / hooks["vocabulary"] / "vocabulary.json").read_text())
    definition = vocabulary["constructs"][identity]
    document = content_library.read("harbor")
    slots = "".join("{{slot:" + slot["id"] + "}}" for slot in definition["slots"])
    tag = definition["root"]
    template = f'<{tag}><div data-kd-part="tester-wrapper">{slots}</div></{tag}>'
    document.setdefault("layout", {}).setdefault("variants", {}).setdefault(identity, {})["tester-wrapper"] = {"template": template}
    document["components"].setdefault(identity, {})["variant"] = "tester-wrapper"
    content_library.write(document)
    content_library.validate("harbor")
    changed = tmp_path / "changed"
    render(content_library, source, changed)
    assert (changed / "index.html").read_bytes() == (baseline / "index.html").read_bytes()


@pytest.mark.parametrize("field", ["schema", "page.title", "site.name", "blocks.0.title", "blocks.0.media.alt",
                                   "blocks.3.title", "blocks.2.items.0.title"])
def test_missing_required_content_is_rejected_with_resolvable_findings(content_library, tmp_path, field):
    from tests.support import pointer_value
    source, content = write_content(tmp_path / "source")
    node = content
    parts = field.split(".")
    for key in parts[:-1]:
        node = node[int(key)] if isinstance(node, list) else node[key]
    del node[parts[-1]]
    save_content(source, content)
    report = content_library.json("render-page", "harbor", "--content", source, "--out", tmp_path / "bad", code=1)
    assert report["findings"]
    for finding in report["findings"]:
        # Missing members have no value to point to. Only enforce the explicit
        # resolvability contract; no invented exact missing-key pointer rule.
        assert pointer_value(content, finding["pointer"]) == finding["observed"]
        assert finding["message"].strip()


def test_truncated_content_json_is_rejected_without_a_traceback(content_library, tmp_path):
    import random
    source, content = write_content(tmp_path / "source")
    payload = json.dumps(content)
    for cut in random.Random(20261108).sample(range(1, len(payload)), 8):
        source.write_text(payload[:cut])
        result = content_library.cli("render-page", "harbor", "--content", source, "--out", tmp_path / f"bad-{cut}", code=1)
        report = json.loads(result.stdout)
        assert report["findings"], (cut, report)
        assert "Traceback (most recent call last)" not in result.stderr


@pytest.mark.parametrize("with_hero", [True, False], ids=["hero-h1", "page-title-h1"])
def test_untitled_sections_preserve_content_without_adding_or_shifting_headings(content_library, tmp_path, with_hero):
    """Amendment 07: omission is valid; fabricated headings or shifted levels fail."""
    source, content = write_content(tmp_path / "source")
    if not with_hero:
        content["blocks"] = content["blocks"][1:]
        content["blocks"][-1]["actions"][0]["href"] = "#guide"
    save_content(source, content)
    expected_h1 = content["blocks"][0]["title"] if with_hero else content["page"]["title"]
    baseline = render(content_library, source, tmp_path / "titled")
    heading_tags = {"h1", "h2", "h3", "h4", "h5", "h6"}
    expected = [(node.tag, node.text()) for node in baseline.all() if node.tag in heading_tags]
    intro, passage = "An introduction without a heading", "An untitled passage between titled blocks"
    content["blocks"].insert(0, {"type": "section", "content": [{"paragraph": intro}]})
    content["blocks"].insert(-1, {"type": "section", "content": [{"paragraph": passage}]})
    save_content(source, content)
    out = tmp_path / "with-body-only-sections"
    doc = render(content_library, source, out)
    observed = [(node.tag, node.text()) for node in doc.all() if node.tag in heading_tags]
    assert observed == expected, "Body-only sections inserted a heading or changed existing heading levels/order"
    assert [node.text() for node in doc.all("h1")] == [expected_h1]
    levels = [int(tag[1]) for tag, _ in observed]
    assert all(level <= previous + 1 for previous, level in zip([0] + levels, levels))
    hooks = json.loads((out / "hooks.json").read_bytes())
    section = hooks["content_pages"]["blocks"]["section"]
    for text in (intro, passage):
        instances = [node for node in doc.all(**{"data-kd-construct": section}) if text in node.text()]
        assert len(instances) == 1, ("Untitled section body was lost or duplicated", text)
        assert not [node for node in instances[0].all() if node.tag in heading_tags]
    if with_hero:
        # This fixture contains every declared block kind; optional section title
        # must also agree with required-slot metadata in the exported hook contract.
        from tests.test_content_hooks_mapping import assert_hooks
        assert_hooks(hooks, doc)
