"""Normative amendment 08 / Q-0043-3da4cc0164b5: portable Design-to-Factory task.

CLI + real Git/worktree/files + recorder process at the explicitly approved
Factory seam. Never invokes a real Factory. Expected hashes come from authored
language data and actual export bytes; repository identity comes from real Git.
Falsifiers: dry-run invokes, wrong argv/task, stale or altered export submitted,
worktree pins another HEAD, hooks execute, or entrypoint failure masquerades as 0.
"""
import json

import pytest

from tests.factory_task_support import (prepare_handoff, recorder, task_cli, submission,
    assert_directive, assert_invocation, assert_refusal)
from tests.m4_support import git


@pytest.fixture
def factory_case(library, language, tmp_path):
    case = prepare_handoff(library, language, tmp_path)
    spy = recorder(tmp_path / "entrypoint")
    # Explicit flag and environment fallback both point only at our recorder.
    library.command_env["KINBASE_DESIGN_FACTORY"] = str(spy.path)
    return case, spy


@pytest.mark.parametrize("adapter,missing_slot,run", [("generic", False, "0"),
    ("dtcg-tailwind", True, "r" * 64)])
def test_dry_run_is_portable_deterministic_and_invokes_nothing(library, language, tmp_path, adapter, missing_slot, run, record_property):
    case = prepare_handoff(library, language, tmp_path, adapter=adapter, missing_slot=missing_slot)
    spy = recorder(tmp_path / "entrypoint")
    result = task_cli(case, run, factory=spy.path, dry=True)
    first = submission(case, result, run, invoked=False, exit_code=None)
    assert not spy.receipt.exists()
    text = assert_directive(case)
    record_property("directive_markdown_for_semantic_review", text)
    before = (case.bundle / "directive.md").read_bytes()
    # Entrypoint presence is not a dry-run precondition. Rewriting still produces
    # identical bytes/hash, with no implicit run or worktree creation.
    repeated = task_cli(case, run, factory=tmp_path / "absent entrypoint", dry=True)
    second = submission(case, repeated, run, invoked=False, exit_code=None)
    assert (case.bundle / "directive.md").read_bytes() == before
    assert second["directive_sha256"] == first["directive_sha256"]
    assert not spy.receipt.exists()


@pytest.mark.parametrize("mode", ["explicit", "environment", "flags"])
def test_submission_passes_literal_arguments_task_bytes_and_pinned_worktree(factory_case, tmp_path, mode):
    case, spy = factory_case
    run = "sample-run_1.0"
    extra = ("--runs", tmp_path / "runs dir $(echo literal)", "--budget", "12.5") if mode == "flags" else ()
    # Git checkout hooks must be ignored by the product operation. This hook has
    # only a harmless test-local file effect; no host hooks are touched.
    hooks = tmp_path / "repository-hooks"
    hooks.mkdir()
    sentinel = tmp_path / "hook-executed"
    import sys
    hook = hooks / "post-checkout"
    hook.write_text(f'#!{sys.executable}\nfrom pathlib import Path\nPath({str(sentinel)!r}).write_text("unexpected hook")\n')
    hook.chmod(0o755)
    git(case.repo, "config", "core.hooksPath", hooks)
    if mode == "environment":
        factory = None
    else:
        factory = spy.path
        fallback = recorder(tmp_path / "unused-environment-entrypoint")
        case.library.command_env["KINBASE_DESIGN_FACTORY"] = str(fallback.path)
    result = task_cli(case, run, factory=factory, extra=extra)
    record = submission(case, result, run, invoked=True, exit_code=0)
    assert record["stderr_tail"] == ""
    assert_directive(case)
    assert_invocation(case, spy, record, run, extra)
    assert not sentinel.exists(), "Git invoked a repository checkout hook"
    if mode != "environment":
        assert not fallback.receipt.exists(), "Explicit --factory did not override the environment"


def test_nonzero_factory_exit_is_recorded_and_worktree_is_retained(factory_case, tmp_path):
    case, unused = factory_case
    error = "diagnostic prefix " + "é" * 2300 + "\nENTRYPOINT FAILED\n"
    spy = recorder(tmp_path / "failing-entrypoint", exit_code=7, stderr=error)
    result = task_cli(case, "failed-run", factory=spy.path, code=1)
    record = submission(case, result, "failed-run", invoked=True, exit_code=7)
    assert record["stderr_tail"] and error.endswith(record["stderr_tail"])
    assert "ENTRYPOINT FAILED" in record["stderr_tail"]
    assert_invocation(case, spy, record, "failed-run")
    assert not unused.receipt.exists()


@pytest.mark.parametrize("failure", ["stale-language", "moved-branch", "deleted-branch", "altered-export-copy",
    "missing-export-copy", "extra-export-copy", "missing-entrypoint", "not-executable", "directory-entrypoint",
    "unset-entrypoint", "existing-worktree-directory", "existing-worktree-file"])
def test_refusals_do_not_invoke_factory(factory_case, tmp_path, failure):
    case, spy = factory_case
    # A valid dry-run reaches the same preconditions before one defect is seeded.
    submission(case, task_cli(case, "control", factory=spy.path, dry=True), "control", invoked=False, exit_code=None)
    factory = spy.path
    if failure == "stale-language":
        case.language["style"]["color"]["ink"]["$value"] = "#aabbcc"
        case.library.write(case.language)
    elif failure == "moved-branch":
        tree = git(case.repo, "rev-parse", case.commit + "^{tree}")
        later = git(case.repo, "commit-tree", tree, "-p", case.commit, "-m", "A later branch commit")
        git(case.repo, "update-ref", "refs/heads/" + case.branch, later, case.commit)
    elif failure == "deleted-branch":
        git(case.repo, "branch", "-D", case.branch)
    elif failure in {"altered-export-copy", "missing-export-copy", "extra-export-copy"}:
        path = case.bundle / "export" / "roles.css"
        if failure == "altered-export-copy":
            path.write_bytes(path.read_bytes() + b"\n:root{color:red}\n")
        elif failure == "missing-export-copy":
            path.unlink()
        else:
            (case.bundle / "export" / "extra.css").write_text(":root{color:red}")
        # Q-0043 clarification: corrupt the copy, isolating byte mismatch from a
        # moved-tip refusal. Both recorded commit and actual tip remain untouched.
        assert git(case.repo, "rev-parse", case.branch) == case.commit
        assert json.loads((case.bundle / "handoff.json").read_text())["local_branch"]["commit"] == case.commit
    elif failure == "missing-entrypoint":
        factory = tmp_path / "no-such-entrypoint"
    elif failure == "not-executable":
        spy.path.chmod(0o644)
    elif failure == "directory-entrypoint":
        factory = tmp_path / "entrypoint-is-a-directory"
        factory.mkdir()
    elif failure == "unset-entrypoint":
        factory = None
        case.library.command_env["KINBASE_DESIGN_FACTORY"] = ""
    elif failure == "existing-worktree-directory":
        case.worktree.mkdir()
        (case.worktree / "keep.txt").write_text("User work must survive")
    elif failure == "existing-worktree-file":
        case.worktree.write_text("User work must survive")
    result = task_cli(case, "refused-run", factory=factory, code=1)
    assert_refusal(case, spy, result)
    if failure == "existing-worktree-directory":
        assert (case.worktree / "keep.txt").read_text() == "User work must survive"
    elif failure == "existing-worktree-file":
        assert case.worktree.read_text() == "User work must survive"
    else:
        assert not case.worktree.exists(), "Refusal left a new worktree behind"


@pytest.mark.parametrize("run", ["", "Uppercase", ".leading", "space run", "../escape", "r" * 65, "r;echo-x", "r\nline"])
def test_bad_run_id_is_refused_before_invocation(factory_case, run):
    case, spy = factory_case
    result = task_cli(case, run, factory=spy.path, code=1)
    assert_refusal(case, spy, result)
    assert not case.worktree.exists()


def test_handoff_without_branch_cannot_be_submitted(library, language, tmp_path):
    case = prepare_handoff(library, language, tmp_path, branch=False)
    spy = recorder(tmp_path / "entrypoint")
    result = task_cli(case, "requires-branch", factory=spy.path, code=1)
    assert_refusal(case, spy, result)
    assert "requires a hand-off created with --branch" in result.stderr
    assert not case.worktree.exists()


def test_unknown_handoff_cannot_be_submitted(library, tmp_path):
    spy = recorder(tmp_path / "entrypoint")
    library.command_env["KINBASE_DESIGN_FACTORY"] = str(spy.path)
    result = library.cli("factory-task", "no-such-handoff", "--run", "unknown", "--factory", spy.path, code=1)
    assert result.stderr.strip() and len(result.stderr.strip().splitlines()) == 1
    assert not spy.receipt.exists()
