"""Pure preview assembly shared by disk builds and the workbench."""
import logging
import json
from copy import deepcopy
from pathlib import Path
from ..assets import package_files
from ..builder import current_builder, builder_label
from ..language import validate
from ..language.resolver import resolve
from ..storage import load_language, inside
from ..vocabulary import load, samples
from .html import SampleRenderer
from .styles import stylesheet


class InvalidLanguage(ValueError):
    def __init__(self, report):
        self.report = report
        super().__init__('Language has unresolved validation findings')


def preview_files(library, language_id, compositions=None, vocabulary_version=None, builder=None, document=None, vocabulary=None, sample_set=None, render_inputs=None):
    builder = current_builder() if builder is None else builder
    document = load_language(library, language_id) if document is None else deepcopy(document)
    if vocabulary is None:
        try:vocabulary=load(library,vocabulary_version or document.get('vocabulary'))
        except (OSError,ValueError,TypeError,AttributeError):
            raise InvalidLanguage(validate(library,language_id,document))
    result = validate(library, language_id, document, vocabulary=vocabulary)
    if not result['accepted']:
        raise InvalidLanguage(result)
    sample_set = samples(library, vocabulary_version or document['vocabulary']) if sample_set is None else sample_set
    renderer = SampleRenderer(document, vocabulary, sample_set)
    if compositions is not None:
        compositions=deepcopy(compositions)
        checked_contexts={}
        def context(component,treatment):
            key=(component,json.dumps(treatment,sort_keys=True))
            if key in checked_contexts:return checked_contexts[key]
            local=deepcopy(document);previous=local['components'].get(component,{})
            local['components']={component:{**{k:v for k,v in previous.items() if k in {'variant','assets','parts'}},**deepcopy(treatment)}}
            for slot,entry in local['components'][component].get('slots',{}).items():
                for field in ('role','emphasis'):
                    if field in previous.get('slots',{}).get(slot,{}):entry[field]=previous['slots'][slot][field]
            local['overrides']=[]
            checked=validate(library,language_id,local,vocabulary=vocabulary)
            if not checked['accepted']:raise InvalidLanguage(checked)
            checked_contexts[key]=local
            return local
        def contexts(items):
            for item in items:
                if item.get('group') is True:
                    contexts(item.get('children',[]));continue
                component=item['construct']
                if 'treatment' in item:item['resolved_context']=context(component,item['treatment'])
                for slot,fragments in item.get('fragments',{}).items():
                    for fragment in fragments:
                        props=fragment.get('properties',{})
                        local=context(component,{'slots':{slot:{'properties':props}}})
                        resolved=resolve(local,vocabulary,component+'.'+slot)['properties']
                        fragment['resolved_properties']={k:v for k,v in resolved.items() if k in props}
                contexts(item.get('children',[]))
        for page in compositions.values():contexts(page['instances'])
    files = ({name:renderer.reconstruction(page) for name,page in compositions.items()} if compositions is not None
             else {name:renderer.page(name) for name in vocabulary['context']['pages']})
    label = builder_label(builder)
    files = {name: ('<!-- ' + label + ' -->\n').encode() + data for name, data in files.items()}
    files['language.css'] = ('/* ' + label + ' */\n' + stylesheet(document, vocabulary)).encode('utf-8')
    files.update(package_files(library, language_id, document))
    if render_inputs is not None:
        from .identity import inputs
        render_inputs.update(inputs(document,vocabulary,sample_set,compositions,files,builder))
    return files


def build_preview(library, language_id, out, document=None, vocabulary=None, sample_set=None, render_inputs=None):
    files = preview_files(library, language_id, document=document,vocabulary=vocabulary,sample_set=sample_set,render_inputs=render_inputs)
    root = Path(out).resolve()
    for name, data in files.items():
        path = inside(root, name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    logging.getLogger(__name__).info('build_preview language=%s files=%d', language_id, len(files))
    return files
