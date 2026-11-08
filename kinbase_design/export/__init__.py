"""Versioned exports shared by CLI, Apply and hand-off bundles."""
from pathlib import Path
import json
from ..assets import package_files, package_notices
from ..language import validate
from ..language.versions import digest, mint
from ..render import InvalidLanguage
from ..storage import inside, load_language
from ..vocabulary import load, hook_contract
from .adapters import ADAPTERS, metadata


def export_files(library, language_id, adapter_name):
    if adapter_name not in ADAPTERS:raise ValueError('Unknown export adapter: ' + adapter_name)
    document = load_language(library, language_id)
    result = validate(library, language_id, document)
    if not result['accepted']:raise InvalidLanguage(result)
    reference = language_id + '@' + digest(document)
    adapter = ADAPTERS[adapter_name]
    vocabulary = load(library,document['vocabulary'])
    files = adapter.files(document, vocabulary, reference)
    files['hooks.json'] = (json.dumps(hook_contract(vocabulary),ensure_ascii=False,indent=2)+'\n').encode()
    files.update(package_files(library, language_id, document))
    files['ATTRIBUTION.txt'] = (metadata(reference,adapter_name+'@'+adapter.version)['$description']+'\n\n'+'\n\n'.join(package_notices(library,language_id,document))+'\n').encode()
    return files


def export(library, language_id, adapter_name, out):
    files = export_files(library, language_id, adapter_name)
    root = Path(out).expanduser().resolve()
    # Export destinations may not overwrite source languages or vocabulary.
    library = Path(library).resolve()
    if root == library or root in library.parents or any(inside(library,sub)==root or inside(library,sub) in root.parents for sub in ('languages','vocabulary')):
        raise ValueError('Export output must not overwrite the language library')
    reference = mint(library, language_id)['ref']
    for name, data in sorted(files.items()):
        path = inside(root, name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    return {'language': reference, 'adapter': adapter_name+'@'+ADAPTERS[adapter_name].version,
            'out': str(root), 'files': sorted(files)}
