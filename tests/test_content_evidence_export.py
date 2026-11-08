"""Normative design-examples amendment 03: real snapshot -> real JSONL export.

The declared API seam supplies source conditions only, not expected exporter
output. No call-log assertions or network/protocol claims. Falsifiers: overlong
source metadata, oversized UTF-8 statements, naive timestamps, extra publisher
fields, reject-all export, append-on-reexport. Omission-reason wording requires
semantic review; recorded command output exposes it without a prose regex.
"""
import copy
from datetime import datetime
import json
import re

import pytest


class SyntheticFigma:
    def __init__(self, *, version="42", node_id="1:2", comment_id="c1",
                 modified="2026-11-01T10:00:00Z", comment="A synthetic observation"):
        self.file = {"version": version, "lastModified": modified,
            "document": {"id": "0:1", "children": [{"id": node_id, "name": "Fixture title",
                "fills": [{"type": "SOLID", "color": {"r": 0, "g": 0.5, "b": 1}}],
                "style": {"fontFamily": "Example Sans", "fontSize": 32}}]}}
        self.comments = {"comments": [{"id": comment_id, "message": comment, "user": {"id": "u1"}}]}

    def get(self, path, **query):
        return copy.deepcopy(self.comments if path.endswith("/comments") else self.file)


def seed(library, file_key="synthetic-file", **source):
    from kinbase_design.figma import snapshot
    return snapshot(library.workspace, file_key, api=SyntheticFigma(**source), comments=True)["artifact"]


def records(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()] if path.exists() else []


def publisher_record(record):
    """Independent, mechanical translation of amendment 03 publisher limits."""
    assert set(record) == {"schema", "id", "source", "statement", "author_kind", "updated_at", "evidence_refs"}
    assert record["schema"] == "design-evidence/1"
    assert re.fullmatch(r"[0-9a-f]{64}", record["id"])
    assert record["author_kind"] == "agent"
    source = record["source"]
    required = {"kind", "file_key", "version", "digest", "evidence_kind"}
    assert required <= set(source) <= required | {"node_id", "comment_id", "time_basis"}
    assert source["kind"] == "figma"
    for name in ("file_key", "digest", "evidence_kind"):
        assert isinstance(source[name], str) and 1 <= len(source[name]) <= 256
    for name in ("version", "node_id", "comment_id"):
        if source.get(name) is not None:
            assert isinstance(source[name], str) and 1 <= len(source[name]) <= 256
    if "time_basis" in source:
        assert source["time_basis"] in {"source-modified", "observed", "capture-fallback"}
    assert isinstance(record["statement"], str) and record["statement"].strip()
    refs = record["evidence_refs"]
    assert isinstance(refs, list) and 1 <= len(refs) <= 16
    assert all(isinstance(ref, str) and 1 <= len(ref) <= 2048 for ref in refs)
    timestamp = datetime.fromisoformat(record["updated_at"].replace("Z", "+00:00"))
    assert timestamp.tzinfo is not None and timestamp.utcoffset() is not None
    text = ("Machine design evidence (not approved direction), source "
            + json.dumps(source, sort_keys=True, ensure_ascii=False) + ": " + record["statement"])
    assert len(re.sub(r"\s+", " ", text).strip().encode("utf-8")) <= 16384


def test_conforming_export_is_useful_and_idempotent(library, tmp_path):
    artifact = seed(library)
    out = tmp_path / "evidence.jsonl"
    library.cli("evidence-export", "--artifact", artifact, "--out", out)
    exported = records(out)
    assert exported, "Reject-all exporter is not a conforming implementation"
    assert any(r["source"].get("node_id") == "1:2" for r in exported)
    assert any(r["source"].get("comment_id") == "c1" and "synthetic observation" in r["statement"] for r in exported)
    for record in exported:
        publisher_record(record)
    original = out.read_bytes()
    library.cli("evidence-export", "--artifact", artifact, "--out", out)
    assert out.read_bytes() == original


@pytest.mark.parametrize("source", [
    {"file_key": "f" * 256}, {"file_key": "f" * 257},
    {"version": "v" * 256}, {"version": "v" * 257},
    {"node_id": "n" * 257}, {"comment_id": "c" * 257},
    {"modified": "2026-11-01T10:00:00"},
    {"comment": "Observation " + "é界" * 6000},
], ids=["file-limit", "file-over", "version-limit", "version-over", "node-over", "comment-id-over", "naive-time", "utf8-size"])
def test_export_never_writes_out_of_contract_records(library, tmp_path, source, record_property):
    # Positive control in every isolated case: data reaches the real snapshot and
    # exporter before the one hazardous input is changed.
    control = seed(library)
    good = tmp_path / "positive.jsonl"
    library.cli("evidence-export", "--artifact", control, "--out", good)
    assert records(good)
    for record in records(good):
        publisher_record(record)
    artifact = seed(library, **source)
    out = tmp_path / "bounded.jsonl"
    result = library.cli("evidence-export", "--artifact", artifact, "--out", out, code=(0, 1, 2))
    record_property("export_stdout", result.stdout)
    record_property("export_stderr", result.stderr)
    exported = records(out)
    for record in exported:
        publisher_record(record)
    # Exactly-at-limit metadata is conforming and must still be exported.
    if source in ({"file_key": "f" * 256}, {"version": "v" * 256}):
        assert result.returncode == 0 and exported
        name, value = next(iter(source.items()))
        assert any(r["source"][name] == value for r in exported)
    if not exported:
        assert result.returncode != 0 or result.stdout.strip() or result.stderr.strip()
