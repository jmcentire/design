"""Pure preview assembly shared by disk builds and the workbench."""
import logging
from pathlib import Path
from ..assets import asset_path
from ..language import validate
from ..storage import load_language, inside
from ..vocabulary import load, samples
from .html import SampleRenderer
from .styles import stylesheet


class InvalidLanguage(ValueError):
    def __init__(self, report):
        self.report = report
        super().__init__('Language has unresolved validation findings')


def preview_files(library, language_id, compositions=None):
    document = load_language(library, language_id)
    result = validate(library, language_id, document)
    if not result['accepted']:
        raise InvalidLanguage(result)
    vocabulary = load(library, document['vocabulary'])
    sample_set = samples(library, document['vocabulary'])
    renderer = SampleRenderer(document, vocabulary, sample_set)
    files = ({name:renderer.reconstruction(page) for name,page in compositions.items()} if compositions is not None
             else {name:renderer.page(name) for name in vocabulary['context']['pages']})
    files['language.css'] = stylesheet(document, vocabulary).encode('utf-8')
    for asset, entry in document.get('assets', {}).items():
        for variant, detail in entry['variants'].items():
            files[f'assets/{asset}-{variant}.{detail["format"]}'] = asset_path(library, language_id, detail).read_bytes()
    return files


def build_preview(library, language_id, out):
    files = preview_files(library, language_id)
    root = Path(out).resolve()
    for name, data in files.items():
        path = inside(root, name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    logging.getLogger(__name__).info('build_preview language=%s files=%d', language_id, len(files))
    return files
