"""Author-controlled process seam for the explicitly authorized M4 adapter tests."""

import json
import os
import sys
from types import SimpleNamespace

import pytest

from tests.support import FIXTURES


def executable_seam(directory, explanations, *, initialized=True):
    directory.mkdir()
    source = (FIXTURES / "kinbase" / "seam.py").read_text()
    for name in ("kinbase", "kin"):
        executable = directory / name
        executable.write_text("#!" + sys.executable + "\n" + source)
        executable.chmod(0o755)
    responses = {"explain": explanations, "submit": {}, "questions": {},
                 "fsck": {"exit_code": 0 if initialized else 1,
                          "stdout": {"ok": initialized, "message": "ok" if initialized else "Repository not initialized"}}}
    (directory / "responses.json").write_text(json.dumps(responses))
    return directory


def calls(directory):
    file = directory / "calls.jsonl"
    return [json.loads(line) for line in file.read_text().splitlines()] if file.exists() else []


def configure(library, binary, repo, *, standard_keys=None, direction_keys=None):
    standards = standard_keys if standard_keys is not None else {"site": "fixture.standard"}
    directions = direction_keys if direction_keys is not None else {"site": "fixture.direction"}
    text = ('[kinbase]\nbinary = ' + json.dumps(str(binary)) + '\nrepo = ' + json.dumps(str(repo))
            + '\ndecision = "Independent fixture decision"\n')
    for table, keys in (("direction_keys", directions), ("standard_keys", standards)):
        text += '[kinbase.' + table + ']\n'
        text += ''.join(json.dumps(scope) + ' = ' + json.dumps(key) + '\n' for scope, key in keys.items())
    text += '[ingest]\nwidths = [320]\ncapture_timeout_s = 8\nmax_pages = 2\n'
    (library.project / "kinbase-design.toml").write_text(text)


def seam_environment(directory):
    # Put both stand-ins before any user's real executable. No feedback test may
    # accidentally invoke a real kin process, even if the adapter is defective.
    return {"PATH": str(directory) + os.pathsep + os.environ.get("PATH", "")}


def update_responses(directory, **sections):
    path = directory / "responses.json"
    responses = json.loads(path.read_text())
    responses.update(sections)
    path.write_text(json.dumps(responses))


def fact(statement, *, identity="fact-design-hue", scope="brand", standing="authoritative", state="current"):
    return {"state": state, "trusted": True, "unknowns": [],
            "current": {"fact_id": identity, "standing": standing, "scope": scope,
                        "status": "current", "atom_kind": "constraint", "statement": statement}}


def machine_fact(*, dimensions=None, values=None, **options):
    payload = {}
    if dimensions is not None:
        payload["dimensions"] = dimensions
    if values is not None:
        payload["values"] = values
    return fact(json.dumps({"kinbase-design": payload}), **options)


def assert_read_calls(directory, repo, keys, *, required_keys=None):
    """Pin the external command boundary, including exact user-configured values."""
    seen = set()
    logged = calls(directory)
    assert any(call["executable"] == "kinbase" and call["argv"][0] == "fsck" for call in logged)
    for call in logged:
        if call["executable"] != "kinbase":
            continue
        args = call["argv"]
        assert args[0] in {"fsck", "explain", "questions"}, call
        if args[0] == "questions":
            assert len(args) == 3 and args[1] == "ask"
            continue
        assert args.count("--repo") == 1 and args[args.index("--repo") + 1] == str(repo), call
        assert args.count("--json") == 1, call
        if args[0] == "fsck":
            assert len(args) == 4
        else:
            assert len(args) == 7 and args[1] in keys, call
            assert args.count("--decision") == 1 and args[args.index("--decision") + 1] == "Independent fixture decision", call
            seen.add(args[1])
    required = set(keys if required_keys is None else required_keys)
    assert required <= seen, ("Configured keys were not all explained", required, seen)


# The fixture is imported by the M4 tests, not installed as a product substitute.
@pytest.fixture
def kinbase_seam(library, tmp_path):
    repo = tmp_path / "authority-repository"
    repo.mkdir()
    unknown = {"state": "unknown", "trusted": True, "unknowns": [], "current": None}
    explanations = {"design/brand": unknown, "design/rhythm": unknown, "design/direction": unknown}
    directory = executable_seam(tmp_path / "available-kinbase", explanations)
    configure(library, directory / "kinbase", repo,
              standard_keys={"brand": "design/brand", "rhythm": "design/rhythm"},
              direction_keys={"brand": "design/direction"})
    library.command_env.update(seam_environment(directory))
    return SimpleNamespace(repo=repo, directory=directory, explanations=explanations,
                           standards={"design/brand", "design/rhythm"}, keys=set(explanations))


def set_facts(seam, **entries):
    seam.explanations.update(entries)
    update_responses(seam.directory, explain=seam.explanations)
