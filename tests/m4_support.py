"""Public M4 drivers; real temporary Git repositories, no Git/CLI doubles."""

import json
import os
from pathlib import Path
import subprocess

from tests.support import pointer_value


def git(repo, *args, binary=False):
    environment = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    environment.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull, GIT_TERMINAL_PROMPT="0")
    result = subprocess.run(
        ["git", "-C", str(repo), "-c", "user.name=Independent Fixture", "-c", "user.email=fixture@example.invalid",
         "-c", "commit.gpgSign=false", "-c", f"core.hooksPath={repo / 'disabled-hooks'}", *map(str, args)],
        env=environment, capture_output=True, text=not binary, timeout=20)
    assert result.returncode == 0, (args, result.stdout, result.stderr)
    return result.stdout if binary else result.stdout.strip()


def site_repository(parent):
    repo = parent / "independent-target"
    repo.mkdir()
    git(repo, "init", "--initial-branch=main")
    # The product's real --branch commit must work without a host-global Git
    # identity, signing key or hooks. All configuration remains test-local.
    for key, value in (("user.name", "Independent Fixture"), ("user.email", "fixture@example.invalid"),
                       ("commit.gpgSign", "false"), ("core.hooksPath", str(repo / "disabled-hooks"))):
        git(repo, "config", key, value)
    (repo / "README.md").write_text("An independently authored generic site fixture.\n")
    git(repo, "add", "README.md")
    git(repo, "commit", "-m", "Initial fixture")
    assert git(repo, "remote") == ""
    return repo


def inventory_document(construct="card", slots=("title", "body"), states=("default",), assets=()):
    return {"site": "independent-site", "pages": [{"id": "overview", "path": "index.html",
             "constructs": [{"construct": construct, "states": list(states), "slots": list(slots)}],
             "assets": list(assets), "contract_version": "v1"}], "exceptions": []}


def inventory_check(library, repo, document, accepted):
    inventory = repo / "kinbase-design.inventory.json"
    inventory.write_text(json.dumps(document, indent=2))
    report = library.json("inventory-check", "tidal", "--inventory", inventory, code=0 if accepted else 1)
    assert report["language"] == "tidal" and report["accepted"] is accepted
    assert isinstance(report["findings"], list)
    assert_mixed_report_pointers(library, repo, report)
    return report


def assert_mixed_report_pointers(library, repo, report):
    """Amendment 22: inventory and language findings have distinct file roots."""
    roots = {"inventory": repo.resolve(), "language": library.library.resolve()}
    for finding in report["findings"]:
        assert finding.get("source") in roots, ("Missing/unknown finding source", finding)
        root = roots[finding["source"]]
        relative = Path(finding["file"])
        assert not relative.is_absolute()
        file = (root / relative).resolve()
        assert file.is_relative_to(root), ("Finding escaped its declared source root", finding)
        value = json.loads(file.read_text())
        assert pointer_value(value, finding["pointer"]) == finding["observed"]


def only_missing(report):
    missing = [finding for finding in report["findings"] if finding["type"] == "missing"]
    assert len(missing) == 1, report
    assert missing[0]["source"] == "inventory", report
    assert not [finding for finding in report["findings"] if finding["type"] == "violation"], report
    return missing[0]
