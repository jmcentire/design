"""Immutable version minting; identity includes only presentation facts."""
import hashlib
import logging
import rfc8785
from ..storage import inside, load_language
from .validation import validate

MEMBERS = ('vocabulary', 'style', 'roles', 'layout', 'components', 'overrides', 'behaviors', 'assets')


def version_document(document):
    return {key: document.get(key, [] if key in {'overrides', 'behaviors'} else {}) for key in MEMBERS}


def digest(document):
    return hashlib.sha256(rfc8785.dumps(version_document(document))).hexdigest()


def mint(library, language_id):
    result = validate(library, language_id)
    if not result['accepted']:
        return result
    document = load_language(library, language_id)
    version = digest(document)
    path = inside(library, 'languages', language_id, 'versions', version + '.json')
    data = rfc8785.dumps(version_document(document))
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != data:
            raise ValueError('Immutable version file content mismatch')
    else:
        with path.open('xb') as stream:
            stream.write(data)
    logging.getLogger(__name__).info('mint language=%s hash=%s', language_id, version)
    return {'ref': language_id + '@' + version}
