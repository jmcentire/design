"""Source-free real-site regression: concurrent resource loading and cancellation.

Falsifiers: interception busy loops on pending responses, partial captures marked
successful, serial stalls up to the bound, or an orphaned capture worker after TERM.
"""

import json
import time
from urllib.parse import urlsplit

import pytest

from tests.m2_support import captured_artifact
from tests.process_support import ExitEvents, capture_job, job_processes

pytestmark = [pytest.mark.browser, pytest.mark.browser_timeout(60)]


def test_concurrent_subresources_complete_with_headroom(library, fixture_site, ingest_config, tmp_path):
    config = library.project / "kinbase-design.toml"
    config.write_text(config.read_text().replace("capture_timeout_s = 8", "capture_timeout_s = 40"))
    url = fixture_site.url + "/fanout/index.html"
    started = time.monotonic()
    with capture_job(library, url, tmp_path) as job:
        assert fixture_site.resource_started.wait(timeout=10), "Capture never requested the fan-out resources"
        job.known.update(job_processes(job.process.pid))
        job.process.wait(timeout=max(0.001, 32 - (time.monotonic() - started)))
        elapsed = time.monotonic() - started
        assert job.process.returncode == 0, job.stderr.read_text()
        assert elapsed < 30, f"Capture used {elapsed:.2f}s of its 40s bound"
        _, _, captured = captured_artifact(library, [url], json.loads(job.stdout.read_text()))
        assert not captured["problems"], captured
        assert len(captured["pages"]) == 1
        assert set(captured["pages"][0]["widths"]) == {str(width) for width in ingest_config["widths"]}
    expected = {f"/fanout/image-{i}.svg" for i in range(36)} | {
        f"/fanout/{kind}-{i}.{extension}" for i in range(6)
        for kind, extension in (("style", "css"), ("font", "ttf"))}
    requested = {urlsplit(request["path"]).path for request in fixture_site.requests}
    assert expected <= requested, ("Subresources were not loaded", expected - requested)
    assert fixture_site.peak_inflight >= 2, "Fixture did not exercise overlapping requests"


def test_terminating_capture_leaves_no_capture_workers(library, fixture_site, ingest_config, tmp_path):
    fixture_site.hold_resources = True
    url = fixture_site.url + "/fanout/index.html"
    with capture_job(library, url, tmp_path) as job:
        assert fixture_site.resource_started.wait(timeout=10), "Capture did not reach the in-flight boundary"
        assert job.process.poll() is None, "Capture exited before cancellation could be exercised"
        processes = job_processes(job.process.pid)
        job.known.update(processes)
        children = set(processes) - {job.process.pid}
        assert children, "No capture/browser subprocess reached the regression seam"
        exits = ExitEvents(children)
        try:
            # Signal the public CLI only. Killing its whole group here would hide
            # the bug; group cleanup happens only after this observation succeeds/fails.
            job.process.terminate()
            job.process.wait(timeout=5)
            assert exits.wait(timeout=5), ("Capture descendants survived TERM", sorted(exits.pending))
            assert not job_processes(job.process.pid, job.known), "Capture left a running descendant"
        finally:
            exits.close()
            fixture_site.release_resources.set()
