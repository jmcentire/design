"""Normative design-examples amendment 04: v2 presence cannot alter v1 behavior.

Oracle is the specified relation between identical v1 inputs with/without v2 in
an isolated library. No candidate baseline is recorded. Falsifier: validation,
resolution, preview or check accidentally uses the newest vocabulary globally.
"""
import shutil

import pytest

from tests.content_support import write_content
from tests.m1_support import run_check
from tests.support import LibraryCase, PAGES


@pytest.fixture
def v1_only(library, language, tmp_path):
    assert language["vocabulary"] == "v1"
    assert (library.library / "vocabulary" / "v2").is_dir(), "Amendment 04 requires v2"
    root = tmp_path / "v1-only-library"
    shutil.copytree(library.library / "vocabulary" / "v1", root / "vocabulary" / "v1")
    shutil.copytree(library.path(language["id"]).parent, root / "languages" / language["id"])
    workspace = tmp_path / "v1-only-workspace"
    workspace.mkdir()
    return LibraryCase(library.project, root, workspace)


def test_v1_validation_resolution_and_preview_do_not_depend_on_newer_vocabularies(library, language, v1_only, tmp_path):
    before = v1_only.validate(language["id"])
    after = library.validate(language["id"])
    assert before["findings"] == after["findings"]
    assert v1_only.json("resolve", language["id"], "listing-card.price") == library.json("resolve", language["id"], "listing-card.price")
    legacy = v1_only.build(tmp_path / "legacy-preview", language["id"])
    coexist = library.build(tmp_path / "coexisting-preview", language["id"])
    for filename in (*PAGES, "language.css"):
        assert (legacy / filename).read_bytes() == (coexist / filename).read_bytes(), filename


@pytest.mark.browser
@pytest.mark.browser_timeout(240)
def test_v1_rendered_checks_do_not_depend_on_newer_vocabularies(library, language, v1_only, tmp_path):
    reports = [run_check(case, tmp_path / name, language=language["id"], widths=(375,))
               for case, name in ((v1_only, "legacy-check"), (library, "coexisting-check"))]

    def semantic_findings(value):
        # Screenshot path varies with output directory; its actual artifact is
        # checked (PNG decode and dimensions) by run_check. Mask only that field.
        if isinstance(value, dict):
            return {k: semantic_findings(v) for k, v in value.items() if k != "screenshot"}
        if isinstance(value, list):
            return [semantic_findings(v) for v in value]
        return value

    assert reports[0]["accepted"] == reports[1]["accepted"]
    assert reports[0]["checked"] == reports[1]["checked"]
    assert semantic_findings(reports[0]["findings"]) == semantic_findings(reports[1]["findings"])


def test_content_render_rejects_vocabulary_without_content_hooks(library, language, tmp_path):
    library.validate(language["id"])
    source, _ = write_content(tmp_path / "source")
    report = library.json("render-page", language["id"], "--content", source, "--out", tmp_path / "page", code=1)
    assert any(f["pointer"] == "/vocabulary" and f["observed"] == "v1"
               and f["file"] == "languages/" + language["id"] + "/working.json"
               and f["message"].strip() for f in report["findings"])
