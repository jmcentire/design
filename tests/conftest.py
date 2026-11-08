"""Independent M0 fixtures. Oracle: M0 public contract + amendment 01, normative."""

import json
import math
from contextlib import nullcontext
import queue
import shutil
import socket
import subprocess
import sys
import threading

import pytest

from tests.browser_deadline import browser_deadline
from tests.support import FIXTURES, ROOT, LibraryCase, package_asset


def pytest_configure(config):
    config.addinivalue_line("markers", "browser: requires real Chromium and optionally loopback HTTP")
    config.addinivalue_line("markers", "browser_timeout(seconds): finite host phase budget for multi-render checks")


def browser_phase_guard(item, phase):
    if item.get_closest_marker("browser"):
        budget = item.get_closest_marker("browser_timeout")
        seconds = budget.args[0] if budget else 60
        if not isinstance(seconds, (int, float)) or not math.isfinite(seconds) or seconds <= 0:
            raise pytest.UsageError("browser_timeout must be a positive finite number")
        return browser_deadline(f"{item.nodeid} ({phase})", seconds=seconds)
    return nullcontext()


@pytest.hookimpl(hookwrapper=True, tryfirst=True)
def pytest_runtest_setup(item):
    with browser_phase_guard(item, "setup"):
        yield


@pytest.hookimpl(hookwrapper=True, tryfirst=True)
def pytest_runtest_call(item):
    with browser_phase_guard(item, "call"):
        yield


@pytest.hookimpl(hookwrapper=True, tryfirst=True)
def pytest_runtest_teardown(item, nextitem):
    with browser_phase_guard(item, "teardown"):
        yield


@pytest.fixture
def library(tmp_path):
    project = tmp_path / "unrelated-project"
    root = project / "design" / "shared-library"
    root.mkdir(parents=True)
    # Only public library data is consumed. Never copy candidate languages or expected values.
    vocabulary = ROOT / "library" / "vocabulary"
    assert vocabulary.is_dir(), "Candidate prerequisite missing: library/vocabulary"
    shutil.copytree(vocabulary, root / "vocabulary")
    case = LibraryCase(project, root, tmp_path / "private-workspace")
    case.workspace.mkdir()
    return case


@pytest.fixture
def vocabulary(library):
    return library.json("vocabulary")


@pytest.fixture
def language(library, vocabulary):
    document = json.loads((FIXTURES / "language.json").read_text())
    # Complete the hand-authored fixture using only vocabulary-declared ids/defaults.
    # Values remain independent constants from this test suite, never candidate output.
    for role in vocabulary["roles"]:
        document["roles"][role] = {
            emphasis: {"color": "{color.chain}", "surface": "{color.paper}",
                       "font-family": "{type.family}", "font-size": "{size.body}",
                       "font-weight": "{type.weight}", "line-height": "{type.leading}"}
            for emphasis in vocabulary["emphasis"]
        }
    for construct, contract in vocabulary["constructs"].items():
        component = {"variant": "default", "properties": {}, "slots": {}, "assets": {}}
        for slot in contract["slots"]:
            if slot["kind"] == "media":
                kind = slot.get("asset_kind", "image")
                asset_id = f"fixture-{kind}"
                package_asset(library, document, asset_id, kind, (FIXTURES / "mark.svg").read_bytes())
                component["assets"][slot["id"]] = f"{asset_id}:primary"
        document["components"][construct] = component
    library.write(document)
    return document


@pytest.fixture
def app(library, language):
    # Delayed import keeps collection possible before the candidate exists.
    from kinbase_design.workbench import create_app
    return create_app(library.library, library.workspace)


@pytest.fixture
def lantern(library):
    # M1 explicitly designates this shipped language as the test subject. Expected
    # design values come exclusively from the ratified brief, never from these files.
    source = ROOT / "library" / "languages" / "lantern"
    assert source.is_dir(), "M1 prerequisite missing: shipped lantern language"
    shutil.copytree(source, library.path("lantern").parent)
    return library.read("lantern")


@pytest.fixture
def browser_context():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, timeout=15000)
        context = browser.new_context(java_script_enabled=False, viewport={"width": 1280, "height": 900})
        try:
            yield context
        finally:
            context.close()
            browser.close()


@pytest.fixture
def page(browser_context):
    page = browser_context.new_page()
    page.set_default_timeout(5000)
    page.set_default_navigation_timeout(5000)
    yield page
    page.close()


@pytest.fixture
def server(library, language):
    from tests.test_preview_workbench import second_language
    second_language(library, language)
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
    command = [sys.executable, "-u", "-m", "kinbase_design", "serve", "--host", "127.0.0.1",
               "--port", str(port), "--library", str(library.library), "--workspace", str(library.workspace)]
    process = subprocess.Popen(command, cwd=ROOT, env=library.environment(),
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    lines = queue.Queue()
    output = []
    ready = f"listening http://127.0.0.1:{port}/"

    def read_ready():
        signalled = False
        for line in process.stdout:
            output.append(line)
            if line.strip() == ready and not signalled:
                lines.put(True)
                signalled = True
        if not signalled:
            lines.put(False)

    reader = threading.Thread(target=read_ready, daemon=True)
    reader.start()
    try:
        # Wait on the contract's readiness signal. No sleep, HTTP polling, or retry-to-green.
        try:
            listening = lines.get(timeout=15)
        except queue.Empty:
            pytest.fail("No serve readiness signal within 15s: " + "".join(output))
        assert listening, "serve exited before readiness: " + "".join(output)
        yield f"http://127.0.0.1:{port}"
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
        reader.join(timeout=5)
        process.stdout.close()
