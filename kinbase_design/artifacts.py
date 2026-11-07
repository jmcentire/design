"""Immutable private originals. Only opaque ids leave this module."""
from datetime import datetime, timezone
import hashlib
import logging
from pathlib import Path
from .config import MAX_UPLOAD_BYTES
from .storage import identifier, inside, read_json, write_json

log = logging.getLogger(__name__)


def import_bytes(workspace, data, filename):
    if not data or len(data) > MAX_UPLOAD_BYTES:
        raise ValueError('Artifact is empty or exceeds upload limit')
    if not filename or Path(filename).name != filename or '/' in filename or '\\' in filename or filename in {'.', '..'}:
        raise ValueError('Upload filename must be a plain file name')
    digest = hashlib.sha256(data).hexdigest()
    artifact_id = 'artifact-' + digest
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
            'id': artifact_id, 'filename': filename, 'sha256': digest,
            'created': datetime.now(timezone.utc).isoformat(), 'size': len(data)})
    log.info('artifact_import artifact=%s bytes=%d', artifact_id, len(data))
    return artifact_id


def import_file(workspace, file):
    file = Path(file)
    with file.open('rb') as stream:
        data = stream.read(MAX_UPLOAD_BYTES + 1)
    return import_bytes(workspace, data, file.name)


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
