"""Amendment 08: real Apply/Git inputs and a recorder at the Factory process seam.

The recorder is not Factory and never launches agents. It records the invocation
and reads task/repository state at the edge; tests assert the product's actual
composition effects, not any simulated Factory business outcome.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from types import SimpleNamespace

from tests.m4_support import git, inventory_check, inventory_document, site_repository
from tests.test_m4_apply import find_handoff
from tests.test_m4_export import export_headers
from tests.test_versions_assets import expected_hash

TARGET = "design/theme bundle"
ENV_CANARY = "SYNTHETIC_PRIVATE_ENV_VALUE_NOT_FOR_DIRECTIVES"
SOURCE_CANARY = "SYNTHETIC_PRIVATE_CAPTURE_NOT_FOR_DIRECTIVES"


def recorder(directory, *, exit_code=0, stderr=""):
    directory.mkdir(parents=True)
    receipt = directory / "received.json"
    executable = directory / "factory recorder $(echo literal).py"
    # Literal repr values are embedded in a Python file, never interpolated into
    # shell text. The executable's metacharacters exercise literal path handling.
    executable.write_text(f'''#!{sys.executable}
import json
from pathlib import Path
import subprocess
import sys

receipt = Path({str(receipt)!r})
args = sys.argv
repository = Path(args[args.index("--repo") + 1])
def git(*arguments):
    return subprocess.run(["git", "-C", str(repository), *arguments], check=True,
        capture_output=True, text=True, timeout=10).stdout.strip()
payload = {{"argv": args, "task_hex": Path(args[2]).read_bytes().hex(),
           "head": git("rev-parse", "HEAD"), "branch": git("symbolic-ref", "--short", "HEAD"),
           "root": git("rev-parse", "--show-toplevel"),
           "linked_worktree": (repository / ".git").is_file()}}
with receipt.open("x") as output:
    json.dump(payload, output)
sys.stderr.write({stderr!r})
raise SystemExit({exit_code!r})
''')
    executable.chmod(0o755)
    return SimpleNamespace(path=executable, receipt=receipt)


def prepare_handoff(library, language, tmp_path, *, branch=True, adapter="generic", missing_slot=False):
    # Never allow an ambient real Factory entrypoint to become a test dependency.
    library.command_env.update({"KINBASE_DESIGN_FACTORY": "", "FACTORY_TEST_PRIVATE_CANARY": ENV_CANARY,
                               "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull,
                               "GIT_TERMINAL_PROMPT": "0"})
    repo = site_repository(tmp_path)
    inventory = inventory_document(slots=("title", "body", "unrepresented-slot") if missing_slot else ("title", "body"))
    review = inventory_check(library, repo, inventory, accepted=not missing_slot)
    git(repo, "add", "kinbase-design.inventory.json")
    git(repo, "commit", "-m", "Declare the synthetic site's inventory")
    original_head = git(repo, "rev-parse", "HEAD")
    previous = set((library.workspace / "handoffs").glob("*/TASK.md"))
    args = ["apply", language["id"], "--site", repo, "--adapter", adapter, "--target-dir", TARGET]
    if branch:
        args.append("--branch")
    library.cli(*args, cwd=library.project, timeout=45)
    bundle = find_handoff(library, previous)
    record = json.loads((bundle / "handoff.json").read_text())
    reference = language["id"] + "@" + expected_hash(language)
    expected_branch = "kinbase-design/" + language["id"] + "-" + expected_hash(language)[:8]
    assert record["branch"] == expected_branch
    if branch:
        assert record["local_branch"]["branch"] == expected_branch
        commit = record["local_branch"]["commit"]
        assert re.fullmatch(r"[0-9a-f]{40}", commit)
        assert git(repo, "rev-parse", expected_branch) == commit
    else:
        assert record["local_branch"] is None
        commit = None
    files = {p.relative_to(bundle / "export").as_posix(): p.read_bytes()
             for p in (bundle / "export").rglob("*") if p.is_file()}
    assert files and "hooks.json" in files
    adapter_reference = export_headers(files, reference, adapter)
    (library.workspace / "private-source.txt").write_text(SOURCE_CANARY)
    return SimpleNamespace(library=library, language=language, repo=repo, bundle=bundle,
        handoff=bundle.name, branch=expected_branch, commit=commit, reference=reference,
        adapter=adapter_reference, files=files, review=review, site_name=inventory["site"], original_head=original_head,
        worktree=bundle / "factory-repo")


def task_cli(case, run, *, factory=None, dry=False, extra=(), code=0):
    args = ["factory-task", case.handoff, "--run", run]
    if factory is not None:
        args += ["--factory", factory]
    if dry:
        args.append("--dry-run")
    return case.library.cli(*args, *extra, code=code, timeout=45)


def directive_document(path):
    text = path.read_text(encoding="utf-8")
    assert text.splitlines()[0] == "<!-- kinbase-design-directive/1 -->"
    lines, blocks, prose = text.splitlines(), [], []
    i = 0
    while i < len(lines):
        opener = re.fullmatch(r"(`{3,}|~{3,})[ \t]*json kinbase-design-directive[ \t]*", lines[i])
        if not opener:
            prose.append(lines[i])
            i += 1
            continue
        fence = opener[1]
        i += 1
        start = i
        while i < len(lines) and not re.fullmatch(re.escape(fence[0]) + "{" + str(len(fence)) + r",}[ \t]*", lines[i]):
            i += 1
        assert i < len(lines), "Unclosed directive JSON fence"
        blocks.append(json.loads("\n".join(lines[start:i])))
        i += 1
    assert len(blocks) == 1 and isinstance(blocks[0], dict)
    return text, blocks[0], "\n".join(prose)


def assert_directive(case):
    text, payload, prose = directive_document(case.bundle / "directive.md")
    assert {"schema", "handoff", "language", "adapter", "vocabulary", "target_dir",
            "branch", "commit", "hooks", "files", "findings", "constraints", "acceptance"} <= payload.keys()
    assert payload["schema"] == "kinbase-design-directive/1"
    assert payload["handoff"] == case.handoff
    assert payload["language"] == case.reference
    assert payload["adapter"] == case.adapter
    assert payload["vocabulary"] == case.language["vocabulary"]
    assert payload["target_dir"] == TARGET
    assert payload["branch"] == case.branch and payload["commit"] == case.commit
    assert payload["hooks"] == TARGET + "/hooks.json"
    expected_files = [{"path": TARGET + "/" + name, "sha256": hashlib.sha256(data).hexdigest()}
                      for name, data in sorted(case.files.items())]
    assert payload["files"] == expected_files
    assert payload["findings"]["accepted"] is case.review["accepted"]
    assert type(payload["findings"]["count"]) is int
    assert payload["findings"]["count"] == len(case.review["findings"])
    for key in ("constraints", "acceptance"):
        assert isinstance(payload[key], list) and payload[key]
        assert all(isinstance(value, str) and value.strip() for value in payload[key])
    headings = re.findall(r"^# (.+)$", prose, re.M)
    assert any(any(name.casefold() in h.casefold() for name in (case.language["id"], case.language["name"]))
               and any(target.casefold() in h.casefold() for target in (TARGET, case.repo.name, case.site_name))
               for h in headings), headings
    for finding in case.review["findings"]:
        # Mandated finding identifiers/locations are output data. We do not use
        # prose phrase matching to claim the directive's policies are followed.
        assert finding["rule"] in prose and finding["file"] in prose, finding
        if finding["pointer"]:
            assert finding["pointer"] in prose, finding
    for value in (str(case.library.workspace), str(case.library.workspace.resolve()),
                  str(case.library.library), str(case.library.library.resolve()), ENV_CANARY, SOURCE_CANARY):
        assert value not in text, ("Private input leaked into portable directive", value)
    for item in payload["files"]:
        path = Path(item["path"])
        assert not path.is_absolute() and ".." not in path.parts
        assert git(case.repo, "show", f'{case.commit}:{item["path"]}', binary=True) == case.files[path.relative_to(TARGET).as_posix()]
    return text


def submission(case, result, run, *, invoked, exit_code):
    record = json.loads(result.stdout)
    assert record == json.loads((case.bundle / "factory-submission.json").read_text())
    assert {"schema", "handoff", "run", "directive", "directive_sha256", "repository",
            "commit", "invoked", "exit", "stderr_tail"} <= record.keys()
    assert record["schema"] == "kinbase-design-factory-submission/1"
    assert record["handoff"] == case.handoff and record["run"] == run
    assert record["commit"] == case.commit
    assert record["invoked"] is invoked and record["exit"] == exit_code
    assert type(record["exit"]) is int if invoked else record["exit"] is None
    assert isinstance(record["stderr_tail"], str) and len(record["stderr_tail"]) <= 2000
    path = Path(record["directive"])
    assert path.is_absolute() and path.resolve() == (case.bundle / "directive.md").resolve()
    assert record["directive_sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    if invoked:
        worktree = Path(record["repository"])
        assert worktree.is_absolute() and worktree.resolve() == case.worktree.resolve()
        assert (worktree / ".git").is_file(), "Submission repository is not a linked worktree"
        assert git(worktree, "rev-parse", "HEAD") == case.commit
        assert git(worktree, "symbolic-ref", "--short", "HEAD") == case.branch
        assert Path(git(worktree, "rev-parse", "--show-toplevel")).resolve() == worktree.resolve()
        assert str(worktree.resolve()) in git(case.repo, "worktree", "list", "--porcelain")
        for name, data in case.files.items():
            assert (worktree / TARGET / name).read_bytes() == data, name
    else:
        assert record["repository"] is None and record["stderr_tail"] == ""
        assert not case.worktree.exists(), "Dry-run created a worktree"
    assert git(case.repo, "rev-parse", "HEAD") == case.original_head
    assert git(case.repo, "status", "--porcelain") == ""
    return record


def assert_invocation(case, spy, record, run, extra=()):
    received = json.loads(spy.receipt.read_text())
    assert received["argv"] == [str(spy.path), run, record["directive"], "--repo", record["repository"], *map(str, extra)]
    assert bytes.fromhex(received["task_hex"]) == (case.bundle / "directive.md").read_bytes()
    assert received["head"] == case.commit and received["branch"] == case.branch
    assert received["linked_worktree"] is True
    assert Path(received["root"]).resolve() == case.worktree.resolve()


def assert_refusal(case, spy, result):
    assert result.returncode == 1
    assert len(result.stderr.strip().splitlines()) == 1 and result.stderr.strip(), result.stderr
    assert not spy.receipt.exists(), "Factory entrypoint was invoked despite a refused precondition"
