"""Identity of the concrete inputs used for a render, without private paths."""
import hashlib
from pathlib import Path
import rfc8785
from ..language.versions import digest


def fingerprint():
    root=Path(__file__).resolve().parent.parent
    result=hashlib.sha256()
    for path in sorted(root.rglob('*')):
        if path.is_file() and path.suffix in {'.py','.css','.html'}:
            result.update(path.relative_to(root).as_posix().encode()+b'\0')
            result.update(hashlib.sha256(path.read_bytes()).digest())
    return result.hexdigest()


def inputs(document, vocabulary, samples, composition, files, builder):
    hashed=lambda value:hashlib.sha256(rfc8785.dumps(value)).hexdigest()
    return {'language':digest(document),'vocabulary':hashed(vocabulary),'samples':hashed(samples),
            'content':hashed(composition) if composition is not None else None,
            'assets':{name:hashlib.sha256(data).hexdigest() for name,data in sorted(files.items()) if name.startswith(('assets/','content-assets/'))},
            'renderer':{**builder,'code':fingerprint()}}
