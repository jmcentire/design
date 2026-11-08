"""B15 Apply: user-visible forms carry the entire hand-off journey without JS."""

import re

import pytest

from tests.m4_support import git
from tests.m4_workbench_support import choose_value, next_action, submit, workbench
from tests.test_m2_workbench import visible
from tests.test_m4_apply import PAGE_PAINT, TARGET, assert_bundle, find_handoff, prepare_apply
from tests.test_m4_export import export

pytestmark = [pytest.mark.browser, pytest.mark.browser_timeout(420)]


def test_workbench_apply_creates_reviewable_handoff_without_javascript(library, language, fixture_site, tmp_path, page):
    repo, inventory_report, reference, branch = prepare_apply(library, language, tmp_path)
    original = git(repo, "rev-parse", "HEAD")
    files = export(library, "tidal", "generic", tmp_path / "independent-export")
    previous = set((library.workspace / "handoffs").glob("*/TASK.md"))
    urls = [fixture_site.url + "/apply/" + next(iter(PAGE_PAINT))]
    with workbench(library) as server:
        page.goto(server + "/apply")
        choose_value(page, "tidal", r"language")
        choose_value(page, "generic", r"adapter")
        repos = visible(page.get_by_role("textbox", name=re.compile(r"repo|site.*path|target.*repo", re.I)))
        assert repos, "Apply needs a visible target-repository field"
        repos[0].fill(str(repo))
        form = repos[0].locator("xpath=ancestor::form[1]")
        target_fields = visible(form.get_by_role("textbox", name=re.compile(r"target.*dir|output.*dir", re.I)))
        for field in target_fields:
            field.fill(TARGET)
        url_fields = visible(form.get_by_role("textbox", name=re.compile(r"url", re.I)))
        assert url_fields, "The hand-off journey must accept optional preview URLs"
        url_fields[0].fill(urls[0])
        # Branch creation is optional. Exercise the default hand-off-only path;
        # both branch modes are separately checked at the public CLI boundary.
        for checkbox in visible(form.get_by_role("checkbox", name=re.compile(r"branch", re.I))):
            checkbox.uncheck()
        submit(page, form)
        seen = []
        # Finite workflow transitions, not readiness polling or retry-to-green.
        for step in range(6):
            seen.append(page.locator("body").inner_text())
            created = set((library.workspace / "handoffs").glob("*/TASK.md")) - previous
            if created:
                break
            next_action(page, r"inventory|check|review|export|hand.?off|create.*bundle|apply|continue|next")
        bundle = find_handoff(library, previous)
        text = "\n".join(seen)
        assert re.search(r"inventory|findings|accepted|missing|coverage", text, re.I), "Apply never presented inventory findings"
        assert_bundle(bundle, repo, reference, branch, TARGET if target_fields else None,
                      files, "generic", urls, inventory_report)
    assert git(repo, "rev-parse", "HEAD") == original
    assert git(repo, "status", "--porcelain") == ""
    assert git(repo, "remote") == ""
