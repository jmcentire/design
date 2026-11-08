"""Read versioned, presentation-free content contracts from an explicit library."""
import re
from .storage import identifier, inside, read_json


def selected_version(library, version=None):
    root = inside(library, "vocabulary")
    versions = [p.name for p in root.iterdir() if p.is_dir() and (p/"vocabulary.json").is_file()]
    if version is None:
        if not versions:raise ValueError('Library has no vocabularies')
        version = max(versions, key=lambda name:tuple((1,int(part)) if part.isdigit() else (0,part) for part in re.split(r'(\d+)',name)))
    if identifier(version) not in versions:raise ValueError('Unknown vocabulary: ' + version)
    return version


def load(library, version=None):
    return read_json(inside(library, "vocabulary", selected_version(library,version), "vocabulary.json"))


def samples(library, version=None):
    return read_json(inside(library, "vocabulary", selected_version(library,version), "samples.json"))


def slot_map(contract):
    """Index the public ordered slots without creating a second contract."""
    return {slot['id']: slot for slot in contract['slots']}


def hook_contract(vocabulary):
    constructs = {}
    for name, contract in vocabulary['constructs'].items():
        root = f'[data-kd-construct="{name}"]'
        slots = {}
        for slot in contract['slots']:
            element = slot.get('content-element', 'span' if slot['kind']=='media' and slot['element']!='a' else 'label' if slot['element'] in {'input','textarea'} else slot['element'])
            slots[slot['id']] = {'element':slot.get('content-elements',element),
                'selector':f'[data-kd-slot="{name}.{slot["id"]}"]',
                'required':slot.get('content-required',slot['required'])}
        constructs[name] = {'selector':root,'slots':slots,
                            'parts':{part:{'selector':f'[data-kd-part="{part}"]'} for part in contract.get('parts',{})}}
    return {'schema':'kinbase-hooks/1','vocabulary':vocabulary['version'],
            'attributes':{'construct':'data-kd-construct','slot':'data-kd-slot','part':'data-kd-part'},
            'constructs':constructs,'content_pages':vocabulary.get('content_pages',{})}
