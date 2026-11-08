"""Public-boundary drivers, with no production implementation imports or doubles."""

import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
from urllib.parse import urlsplit
from wsgiref.util import setup_testing_defaults

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).parent / "fixtures"
PAGES = ("index.html", "search.html", "listing.html", "form.html", "states.html")


class LibraryCase:
    def __init__(self, project, library, workspace):
        self.project, self.library, self.workspace = project, library, workspace

    def environment(self, extra=None):
        env = dict(os.environ)
        for key in ("KINBASE_DESIGN_LIBRARY", "KINBASE_DESIGN_WORKSPACE"):
            env.pop(key, None)
        env["PYTHONPATH"] = str(ROOT)
        env.update(extra or {})
        return env

    def cli(self, *args, code=0, configured=True, env=None, cwd=None, timeout=30):
        command = [sys.executable, "-m", "kinbase_design", *map(str, args)]
        if configured:
            command += ["--library", str(self.library), "--workspace", str(self.workspace)]
        result = subprocess.run(
            command, cwd=cwd or ROOT, env=self.environment(env),
            capture_output=True, text=True, timeout=timeout,
        )
        allowed_codes = {code} if isinstance(code, int) else set(code)
        assert result.returncode in allowed_codes, (
            f"{command!r}: expected exit {code}, got {result.returncode}\n"
            f"stdout={result.stdout}\nstderr={result.stderr}"
        )
        return result

    def json(self, *args, **kwargs):
        result = self.cli(*args, **kwargs)
        try:
            return json.loads(result.stdout)
        except ValueError as error:
            raise AssertionError(f"CLI did not return JSON: {result.stdout!r}") from error

    def path(self, language="tidal"):
        return self.library / "languages" / language / "working.json"

    def write(self, document):
        path = self.path(document["id"])
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8")

    def read(self, language="tidal"):
        return json.loads(self.path(language).read_text(encoding="utf-8"))

    def validate(self, language="tidal", accepted=True):
        report = self.json("validate", language, code=0 if accepted else 1)
        assert report["language"] == language
        assert report["accepted"] is accepted
        assert isinstance(report["findings"], list)
        # Amendment 03: for parseable input, every finding resolves to its observed value.
        # Malformed JSON has no JSON document; its pointer convention needs clarification.
        try:
            def invalid_constant(value):
                raise ValueError(value)
            json.loads(self.path(language).read_text(), parse_constant=invalid_constant)
        except ValueError:
            pass
        else:
            assert_report_pointers(self.library, report)
        if accepted:
            # These fixtures declare no exceptions. An accepted envelope cannot hide failures.
            assert not [f for f in report["findings"] if f["type"] in
                        {"violation", "missing", "needs-review"}], report
        return report

    def build(self, out, language="tidal"):
        self.cli("build-preview", language, "--out", out)
        for name in (*PAGES, "language.css"):
            assert (out / name).is_file(), f"Preview is missing {name}"
        return out


def pointer_value(document, pointer):
    value = document
    if not pointer:
        return value
    assert pointer.startswith("/"), pointer
    for segment in pointer[1:].split("/"):
        assert all(char != "~" or (i + 1 < len(segment) and segment[i + 1] in "01")
                   for i, char in enumerate(segment)), pointer
        key = segment.replace("~1", "/").replace("~0", "~")
        if isinstance(value, list):
            assert key.isascii() and key.isdigit() and str(int(key)) == key, pointer
            value = value[int(key)]
        else:
            value = value[key]
    return value


def assert_report_pointers(library, report):
    for finding in report["findings"]:
        relative = Path(finding["file"])
        assert not relative.is_absolute(), finding
        path = library / relative
        assert path.resolve().is_relative_to(library.resolve()), finding
        document = json.loads(path.read_text(encoding="utf-8"))
        assert pointer_value(document, finding["pointer"]) == finding["observed"], finding


def assert_finding(report, document, rule, pointer, observed, kind="violation"):
    kinds = {kind} if isinstance(kind, str) else kind
    matches = [f for f in report["findings"] if
               f["rule"] == rule and f["pointer"] == pointer and f["type"] in kinds]
    assert matches, (rule, pointer, kind, report)
    for finding in matches:
        assert finding["file"] == f"languages/{report['language']}/working.json"
        assert finding["observed"] == observed
        assert pointer_value(document, pointer) == observed
        assert isinstance(finding["expected"], str) and finding["expected"].strip()
        assert isinstance(finding["message"], str) and finding["message"].strip()


def package_asset(case, document, asset_id, kind, data, variant="primary", fmt="svg", **extra):
    """Hand-authored package input; promotion is exercised separately through the real CLI."""
    digest = hashlib.sha256(data).hexdigest()
    path = case.path(document["id"]).parent / "assets" / "sha256" / digest
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    document["assets"][asset_id] = {
        "kind": kind, "variants": {variant: {"file": f"sha256/{digest}", "format": fmt, **extra}}
    }
    return digest


def request(app, target, method="GET", body=b"", content_type=""):
    """Real WSGI request/response, no HTTP substitute claiming wire fidelity."""
    parts = urlsplit(target)
    environ = {}
    setup_testing_defaults(environ)
    environ.update({"REQUEST_METHOD": method, "PATH_INFO": parts.path,
                    "QUERY_STRING": parts.query, "wsgi.input": io.BytesIO(body),
                    "CONTENT_LENGTH": str(len(body)), "CONTENT_TYPE": content_type})
    response = {}

    def start_response(status, headers, exc_info=None):
        response["status"] = int(status.split()[0])
        response["headers"] = dict(headers)

    stream = app(environ, start_response)
    try:
        response["body"] = b"".join(stream)
    finally:
        if hasattr(stream, "close"):
            stream.close()
    return response


def multipart(fields, filename, data, media_type="image/svg+xml"):
    boundary = "kinbase-independent-fixture-boundary"
    chunks = []
    for key, value in fields.items():
        chunks.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"\r\n\r\n{value}\r\n'.encode())
    chunks.append(f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{filename}"\r\nContent-Type: {media_type}\r\n\r\n'.encode())
    chunks.extend([data, f"\r\n--{boundary}--\r\n".encode()])
    return b"".join(chunks), f"multipart/form-data; boundary={boundary}"
