"""Immutable private originals. Only opaque ids leave this module."""
from datetime import datetime, timezone
import hashlib
import logging
from pathlib import Path
from ..config import MAX_UPLOAD_BYTES
from ..storage import identifier, inside, read_json, write_json

log = logging.getLogger(__name__)


KINDS = {"image", "mock", "wireframe", "figma-export", "dtcg", "asset", "brief", "css", "doc"}


def import_bytes(workspace, data, filename, kind=None):
    if kind is not None and kind not in KINDS:
        raise ValueError("Unknown artifact kind")
    if not data or len(data) > MAX_UPLOAD_BYTES:
        raise ValueError('Artifact is empty or exceeds upload limit')
    if not filename or Path(filename).name != filename or '/' in filename or '\\' in filename or filename in {'.', '..'}:
        raise ValueError('Upload filename must be a plain file name')
    if kind == 'figma-export':
        from .bundle import import_export_zip
        return import_export_zip(workspace,data,filename)
    digest = hashlib.sha256(data).hexdigest()
    artifact_id = 'artifact-' + (hashlib.sha256(kind.encode() + b'\0' + data).hexdigest() if kind else digest)
    folder = inside(workspace, 'artifacts', artifact_id)
    folder.mkdir(parents=True, exist_ok=True)
    original = inside(workspace, 'artifacts', artifact_id, 'original')
    if original.exists():
        if original.read_bytes() != data:
            raise ValueError('Immutable artifact content mismatch')
    else:
        with original.open('xb') as stream:
            stream.write(data)
        write_json(inside(workspace, 'artifacts', artifact_id, 'metadata.json'), {
            'id': artifact_id, 'filename': filename, 'sha256': digest, 'kind': kind or 'asset',
            'created': datetime.now(timezone.utc).isoformat(), 'size': len(data)})
    log.info('artifact_import artifact=%s bytes=%d', artifact_id, len(data))
    return artifact_id


def import_file(workspace, file, kind=None):
    file = Path(file)
    if file.is_dir():
        from .bundle import import_directory
        return import_directory(workspace, file, kind or "figma-export")
    with file.open('rb') as stream:
        data = stream.read(MAX_UPLOAD_BYTES + 1)
    return import_bytes(workspace, data, file.name, kind)


def read_artifact(workspace, artifact_id):
    identifier(artifact_id)
    metadata = read_json(inside(workspace, 'artifacts', artifact_id, 'metadata.json'))
    path = inside(workspace, 'artifacts', artifact_id, 'original')
    if path.stat().st_size > MAX_UPLOAD_BYTES:
        raise ValueError('Artifact exceeds upload limit')
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != metadata['sha256']:
        raise ValueError('Immutable artifact content mismatch')
    return data, metadata
