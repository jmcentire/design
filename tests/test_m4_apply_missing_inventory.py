"""Apply without inventory: an advisory bundle or actionable failure, never a traceback.

No URLs are supplied, so this boundary requires real Git/CLI/files but no browser.
Both documented adapters use the same independently authored valid language.
"""

import json
import re

import pytest

from tests.m4_support import git, site_repository
from tests.test_m4_apply import TARGET, find_handoff
from tests.test_m4_export import export, export_headers
from tests.test_versions_assets import expected_hash


def absent_inventory_message(value):
    text = value.lower()
    return "inventory" in text and bool(re.search(r"absent|missing|not found|not present|not provided|does not exist|doesn.t exist|(?:cannot|could not) (?:find|locate)|no inventory|without.*inventory|required", text))


@pytest.mark.parametrize("adapter", ["generic", "dtcg-tailwind"])
def test_apply_without_inventory_is_advisory_or_actionable(library, language, tmp_path, adapter):
    library.validate(accepted=True)
    repo = site_repository(tmp_path)
    inventory = repo / "kinbase-design.inventory.json"
    assert not inventory.exists()
    head = git(repo, "rev-parse", "HEAD")
    previous = set((library.workspace / "handoffs").glob("*/TASK.md"))
    result = library.cli("apply", "tidal", "--site", repo, "--adapter", adapter, "--target-dir", TARGET,
                         cwd=library.project, timeout=45, code=(0, 1, 2))
    output = result.stdout + "\n" + result.stderr
    assert "Traceback (most recent call last)" not in output, output
    if result.returncode == 0:
        bundle = find_handoff(library, previous)
        assert str(bundle) in result.stdout or str(bundle.relative_to(library.workspace)) in result.stdout
        files = export(library, "tidal", adapter, tmp_path / "expected-export")
        reference = "tidal@" + expected_hash(language)
        adapter_reference = export_headers(files, reference, adapter)
        task = (bundle / "TASK.md").read_text()
        assert reference in task and adapter_reference in task and str(repo) in task
        marker = "roles.css" if adapter == "generic" else "theme.css"
        roots = [file.parent for file in bundle.rglob(marker)]
        assert len(roots) == 1
        assert all((roots[0] / name).read_bytes() == data for name, data in files.items())
        reports = []
        for file in bundle.rglob("*.json"):
            if "assets" in file.relative_to(bundle).parts:
                continue
            value = json.loads(file.read_text())
            if isinstance(value, dict) and "findings" in value:
                reports.append(value)
        assert any(report.get("accepted") is True and any(
            finding.get("source") == "inventory" and finding["type"] == "coverage" and absent_inventory_message(finding.get("message", ""))
            for finding in report["findings"]) for report in reports), (
                "Successful Apply silently omitted the absent-inventory advisory", reports)
    else:
        # An OS exception naming the file is not actionable on its own. A clear
        # stop must identify the missing inventory and how the user can supply it.
        assert absent_inventory_message(output), output
        assert "kinbase-design.inventory.json" in output, output
        assert re.search(r"\b(?:creat\w*|add\w*|provid\w*|writ\w*|plac\w*|suppl\w*|defin\w*|prepar\w*|copy|put|save|generat\w*|required|expected)\b", output, re.I), output
    assert not inventory.exists(), "Apply invented an inventory instead of reporting its absence"
    assert git(repo, "rev-parse", "HEAD") == head
    assert git(repo, "status", "--porcelain") == ""
    assert git(repo, "remote") == ""
