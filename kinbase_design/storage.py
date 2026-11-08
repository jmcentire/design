"""Constrained paths and canonical, atomic JSON writes."""
import json
import os
from pathlib import Path
import re
import tempfile
from .config import MAX_JSON_BYTES

ID = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def identifier(value):
    if not isinstance(value, str) or not ID.fullmatch(value):
        raise ValueError(f"Invalid identifier: {value!r}")
    return value


def inside(root, *parts):
    root = Path(root).resolve()
    path = root.joinpath(*parts).resolve()
    if path != root and root not in path.parents:
        raise ValueError("Path escapes configured root")
    return path


def read_json(path, max_bytes=MAX_JSON_BYTES):
    if path.stat().st_size > max_bytes:
        raise ValueError(f"JSON exceeds size limit: {path.name}")
    return json.loads(path.read_text(encoding="utf-8"), parse_constant=lambda x: (_ for _ in ()).throw(ValueError(f"Invalid JSON number {x}")))


def write_json(path, value, max_bytes=MAX_JSON_BYTES):
    data = (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode()
    if len(data)>max_bytes:raise ValueError(f"JSON exceeds size limit: {path.name}")
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=path.parent, prefix=".write-")
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def language_path(library, language_id):
    return inside(library, "languages", identifier(language_id), "working.json")


def load_language(library, language_id):
    return read_json(language_path(library, language_id))


def save_language(library, language_id, document):
    """The single mutable language write path used by all authoring operations."""
    save_working(language_path(library, language_id), language_id, document)


def save_working(path, language_id, document):
    """Canonical working-copy writer for both private drafts and shared languages."""
    if document.get("id") != identifier(language_id):
        raise ValueError("Language id must match its directory")
    write_json(path, document)
