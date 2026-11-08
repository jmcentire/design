"""M4 B12: real Apply bundle, injected screenshot effects and strictly local Git.

Sources are independently authored red surfaces with persistent per-page markers;
the exported fixture paints green. Pixel areas prove injection happened without
using OCR as a legibility oracle. Git runs on disposable repositories only.
"""

from collections import Counter
import json
import os
import shutil

import pytest
from PIL import Image

from tests.m4_support import git, inventory_check, inventory_document, site_repository
from tests.support import FIXTURES
from tests.test_m4_export import export, export_headers
from tests.test_versions_assets import expected_hash

pytestmark = [pytest.mark.browser, pytest.mark.browser_timeout(420)]
TARGET = "design/kinbase-export"
PAGE_PAINT = {"first.html": ((173, 73, 98), (157, 36, 20)),
              "second.html": ((117, 83, 154), (141, 30, 60))}
AFTER = (34, 102, 68)  # Authored color.override = #226644.


def prepare_apply(library, language, tmp_path):
    language["components"]["card"]["properties"]["background-color"] = "{color.override}"
    library.write(language)
    repo = site_repository(tmp_path)
    shutil.copyfile(FIXTURES / "sites" / "apply" / "first.html", repo / "index.html")
    shutil.copyfile(FIXTURES / "sites" / "apply" / "second.html", repo / "second.html")
    inventory = inventory_document()
    report = inventory_check(library, repo, inventory, accepted=True)
    git(repo, "add", "kinbase-design.inventory.json", "index.html", "second.html")
    git(repo, "commit", "-m", "Declare the site's independently authored inventory")
    reference = "tidal@" + expected_hash(language)
    branch = "kinbase-design/tidal-" + expected_hash(language)[:8]
    return repo, report, reference, branch


def find_handoff(library, previous):
    tasks = set((library.workspace / "handoffs").glob("*/TASK.md")) - previous
    assert len(tasks) == 1, ("Expected one complete hand-off bundle", tasks)
    return tasks.pop().parent


def assert_bundle(bundle, repo, reference, branch, target, files, adapter, urls, inventory_report):
    task = (bundle / "TASK.md").read_text()
    adapter_ref = export_headers(files, reference, adapter)
    for required in (str(repo), reference, branch, target, adapter_ref):
        assert required is None or required in task, ("Factory task omitted a required hand-off value", required)
    # The export directory name is not pinned; discover it through a public
    # adapter filename, then compare every export byte with an independent call.
    marker = "roles.css" if adapter == "generic" else "theme.css"
    roots = [file.parent for file in bundle.rglob(marker)]
    assert len(roots) == 1
    for relative, data in files.items():
        assert (roots[0] / relative).read_bytes() == data, ("Bundle export differs from pure export", relative)
        assert relative in task, ("Task omitted a delivered file", relative)
    reports = []
    for file in bundle.rglob("*.json"):
        if file.is_relative_to(roots[0] / "assets"):
            continue
        value = json.loads(file.read_text())
        if isinstance(value, dict) and "accepted" in value and "findings" in value:
            reports.append(value)
    assert any(report["accepted"] == inventory_report["accepted"] and report["findings"] == inventory_report["findings"]
               for report in reports), "Bundle omitted the inventory findings"
    documentation = "\n".join(file.read_text() for file in bundle.rglob("*")
                              if file.is_file() and file.suffix in {".md", ".html", ".json"}
                              and "assets" not in file.relative_to(bundle).parts)
    assert "inject" in documentation.lower() and "preview" in documentation.lower(), "After screenshots must be labelled as an injected preview"
    screenshots = [file for file in bundle.rglob("*.png") if "assets" not in file.relative_to(bundle).parts]
    assert len(screenshots) >= 2 * len(urls)
    observed = set()
    for file in screenshots:
        with Image.open(file) as picture:
            assert picture.format == "PNG" and picture.width > 0 and picture.height > 0
            colors = Counter(picture.convert("RGB").getdata())
        for name, (marker_color, before_color) in PAGE_PAINT.items():
            if colors[marker_color] < 1000:
                continue
            if colors[before_color] >= 1000:
                observed.add((name, "before"))
            if colors[AFTER] >= 1000:
                observed.add((name, "after"))
    expected = {(url.rsplit("/", 1)[-1], stage) for url in urls for stage in ("before", "after")}
    assert expected <= observed, ("Missing original/injected page paint", expected, observed)


@pytest.mark.parametrize("adapter", ["generic", "dtcg-tailwind"])
@pytest.mark.parametrize("create_branch", [False, True], ids=["handoff-only", "local-branch"])
def test_apply_handoff_and_optional_branch_preserve_target_and_remote(
        library, language, tmp_path, fixture_site, page, adapter, create_branch):
    repo, inventory_report, reference, branch = prepare_apply(library, language, tmp_path)
    urls = [fixture_site.url + "/apply/" + name for name in PAGE_PAINT]
    for url in urls:
        page.goto(url)
        marker, before_color = PAGE_PAINT[url.rsplit("/", 1)[-1]]
        assert page.locator("aside").evaluate("e => getComputedStyle(e).backgroundColor") == "rgb(" + ", ".join(map(str, marker)) + ")"
        assert page.locator("article").evaluate("e => getComputedStyle(e).backgroundColor") == "rgb(" + ", ".join(map(str, before_color)) + ")"
    files = export(library, "tidal", adapter, tmp_path / "expected-export")
    main = git(repo, "rev-parse", "HEAD")
    baseline_files = {str(file.relative_to(repo)): file.read_bytes() for file in repo.rglob("*")
                      if file.is_file() and ".git" not in file.relative_to(repo).parts}
    remote = tmp_path / "local-only-remote.git"
    remote.mkdir()
    git(remote, "init", "--bare")
    git(repo, "remote", "add", "origin", remote)
    git(repo, "push", "origin", "main")  # Test setup only; product must not update it.
    remote_refs = git(remote, "for-each-ref", "--format=%(refname) %(objectname)")
    branches = set(git(repo, "for-each-ref", "refs/heads", "--format=%(refname)").splitlines())
    previous = set((library.workspace / "handoffs").glob("*/TASK.md"))
    args = ["apply", "tidal", "--site", repo, "--adapter", adapter, "--target-dir", TARGET]
    args += [arg for url in urls for arg in ("--page-url", url)]
    if create_branch:
        args += ["--branch"]
    result = library.cli(*args, cwd=library.project, timeout=90,
                         env={"GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull, "GIT_TERMINAL_PROMPT": "0"})
    bundle = find_handoff(library, previous)
    assert str(bundle) in result.stdout or str(bundle.relative_to(library.workspace)) in result.stdout
    assert_bundle(bundle, repo, reference, branch, TARGET, files, adapter, urls, inventory_report)
    assert git(repo, "rev-parse", "main") == main, "Apply merged into the original branch"
    assert git(remote, "for-each-ref", "--format=%(refname) %(objectname)") == remote_refs, "Apply touched remote refs"
    assert git(repo, "remote", "get-url", "origin") == str(remote)
    after_branches = set(git(repo, "for-each-ref", "refs/heads", "--format=%(refname)").splitlines())
    assert after_branches - branches == ({"refs/heads/" + branch} if create_branch else set())
    for relative, data in baseline_files.items():
        assert (repo / relative).read_bytes() == data, ("Apply changed a pre-existing site file", relative)
    if create_branch:
        git(repo, "merge-base", "--is-ancestor", main, branch)
        changed = git(repo, "diff", "--name-only", main, branch).splitlines()
        assert changed and all(path.startswith(TARGET + "/") for path in changed)
        for relative, data in files.items():
            assert git(repo, "show", f"{branch}:{TARGET}/{relative}", binary=True) == data
        assert git(repo, "status", "--porcelain") == "", "Export was not committed cleanly"
    else:
        assert git(repo, "rev-parse", "HEAD") == main
        assert git(repo, "status", "--porcelain") == "", "Hand-off-only apply changed the target worktree"
