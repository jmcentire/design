"""Real M4 workbench launcher and visible-form drivers; no route implementation imports."""

from contextlib import contextmanager
import queue
import re
import socket
import subprocess
import sys
import threading

from tests.test_m2_workbench import visible


@contextmanager
def workbench(library, env=None):
    """Launch from the test project so its public TOML config is in effect."""
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
    command = [sys.executable, "-u", "-m", "kinbase_design", "serve", "--host", "127.0.0.1",
               "--port", str(port), "--library", str(library.library), "--workspace", str(library.workspace)]
    process = subprocess.Popen(command, cwd=library.project, env=library.environment(env),
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    ready = f"listening http://127.0.0.1:{port}/"
    signal, output = queue.Queue(), []

    def read_output():
        signalled = False
        for line in process.stdout:
            output.append(line)
            if line.strip() == ready and not signalled:
                signal.put(True)
                signalled = True
        if not signalled:
            signal.put(False)

    reader = threading.Thread(target=read_output, daemon=True)
    reader.start()
    try:
        try:
            listening = signal.get(timeout=15)
        except queue.Empty:
            raise AssertionError("No workbench readiness within 15s: " + "".join(output))
        assert listening, "Workbench exited before readiness: " + "".join(output)
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


def submit(page, form, button=None):
    """Accept direct rendered responses or redirects; both work without JS."""
    assert (form.get_attribute("method") or "get").lower() == "post"
    if button is None:
        button = form.locator('button[type="submit"],button:not([type]),input[type="submit"]').first
    with page.expect_navigation(wait_until="load", timeout=90000) as navigation:
        button.click(no_wait_after=True)
    assert navigation.value is not None and navigation.value.ok


def choose_value(page, value, label):
    """Use an offered select/radio value; text input fallback uses its visible label."""
    for control in visible(page.locator("select")):
        values = control.locator("option").evaluate_all("els => els.map(e => e.value)")
        if value in values:
            control.select_option(value)
            return control
    for control in visible(page.get_by_role("radio")):
        if control.input_value() == value:
            control.check()
            return control
    fields = visible(page.get_by_role("textbox", name=re.compile(label, re.I)))
    assert fields, ("No visible choice control", label, value)
    fields[0].fill(value)
    return fields[0]


def next_action(page, pattern):
    buttons = visible(page.get_by_role("button", name=re.compile(pattern, re.I)))
    if buttons:
        button = buttons[0]
        submit(page, button.locator("xpath=ancestor::form[1]"), button)
        return
    links = visible(page.get_by_role("link", name=re.compile(pattern, re.I)))
    assert links, ("No visible next operation", pattern, page.locator("body").inner_text())
    with page.expect_navigation(wait_until="load", timeout=90000) as navigation:
        links[0].click(no_wait_after=True)
    assert navigation.value is not None and navigation.value.ok
