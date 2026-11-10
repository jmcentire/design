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


def save_language(library, language_id, document, *, reason='', expected_version=None, restored_from=None):
    """The single mutable language write path used by all authoring operations."""
    import fcntl
    from datetime import datetime, timezone
    from .language.versions import archive, digest
    if document.get('id') != identifier(language_id):raise ValueError('Language id must match its directory')
    path=language_path(library,language_id);path.parent.mkdir(parents=True,exist_ok=True)
    with path.with_name('working.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        previous=read_json(path) if path.exists() else None
        before=digest(previous) if previous is not None else None
        if expected_version is not None and expected_version!=before:
            raise ValueError('Language changed since this edit began; reload the current language')
        after=digest(document)
        if previous is not None:archive(library,language_id,previous)
        archive(library,language_id,document)
        changed=before!=after
        history_path=path.with_name('revisions.json')
        history=read_json(history_path) if history_path.exists() else []
        entry=None
        if changed:
            entry={'sequence':len(history)+1,'before':before,'after':after,'reason':reason,
                   'created':datetime.now(timezone.utc).isoformat()}
            if restored_from is not None:entry['restored_from']=restored_from
            # Validate serialization/bounds before replacing the current file.
            encoded=json.dumps([*history,entry],ensure_ascii=False,indent=2,allow_nan=False)+'\n'
            if len(encoded.encode())>MAX_JSON_BYTES:raise ValueError('Language revision history exceeds JSON limit')
        save_working(path,language_id,document)
        if entry:write_json(history_path,[*history,entry])
    return {'language':language_id,'changed':changed,'previous':before,'version':after,
            'ref':language_id+'@'+after,'revision':entry['sequence'] if entry else None}


def save_working(path, language_id, document):
    """Canonical working-copy writer for both private drafts and shared languages."""
    if document.get("id") != identifier(language_id):
        raise ValueError("Language id must match its directory")
    write_json(path, document)
