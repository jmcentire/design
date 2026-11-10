"""Current-language edits and explicit restoration; history never drives rendering."""
from copy import deepcopy
import re
from ..findings import location, pointer
from ..storage import inside, load_language, read_json, save_language
from .validation import validate
from .versions import MEMBERS, digest, version_document


def history(library, language_id):
    current=load_language(library,language_id)
    root=inside(library,'languages',language_id)
    path=root/'revisions.json'
    revisions=read_json(path) if path.exists() else []
    recorded={r['after'] for r in revisions}
    legacy=sorted(p.stem for p in (root/'versions').glob('*.json') if p.stem not in recorded)
    return {'language':language_id,'current':digest(current),'revisions':revisions,'legacy_versions':legacy}


def changed_document(document, changes):
    if not isinstance(changes,dict):raise ValueError('Changes must be an object of JSON pointers and values')
    candidate=deepcopy(document)
    for path,value in changes.items():
        if not isinstance(path,str) or not path.startswith('/') or re.search(r'~(?![01])',path):
            raise ValueError('Each change needs a valid JSON pointer')
        keys=[key.replace('~1','/').replace('~0','~') for key in path[1:].split('/')]
        if keys[0] not in MEMBERS:raise ValueError('Changes may only address versioned language presentation')
        parent_path=pointer(*keys[:-1]);found,parent=location(candidate,parent_path) if parent_path else ('',candidate)
        if found!=parent_path:raise ValueError('Change parent does not exist: '+parent_path)
        key=keys[-1]
        if isinstance(parent,dict):parent[key]=deepcopy(value)
        elif isinstance(parent,list) and key.isdecimal() and str(int(key))==key and int(key)<len(parent):parent[int(key)]=deepcopy(value)
        else:raise ValueError('Change target is not a dictionary member or existing array element: '+path)
    return candidate


def commit(library, language_id, document, candidate, reason, expected_version, restored_from=None, out=None, content=None):
    if not isinstance(reason,str) or len(reason)>4000:raise ValueError('Revision reason must be at most 4000 characters')
    if content is not None and out is None:raise ValueError('--content requires --out')
    before=digest(document)
    if expected_version is not None and expected_version!=before:
        raise ValueError('Language changed since this edit began; reload the current language')
    result=validate(library,language_id,candidate)
    if not result['accepted']:return {**result,'changed':False,'previous':before,'version':before}
    receipt=save_language(library,language_id,candidate,reason=reason,expected_version=before,restored_from=restored_from)
    if out is not None:
        try:
            if content is not None:
                from ..content import render_page
                rendered=render_page(library,language_id,content,out,document=candidate)
            else:
                from ..render import build_preview
                from ..vocabulary import load, samples
                vocabulary=load(library,candidate['vocabulary']);sample_set=samples(library,candidate['vocabulary'])
                identity={}
                files=build_preview(library,language_id,out,document=candidate,vocabulary=vocabulary,sample_set=sample_set,render_inputs=identity)
                rendered={'out':str(out),'version':receipt['version'],'files':sorted(files),'render_inputs':identity}
        except (ValueError,OSError,KeyError) as exc:
            rendered={'built':False,'error':str(exc)}
        receipt['rendered']=rendered
    return {**receipt,'accepted':True,'findings':result['findings']}


def revise(library, language_id, changes, reason='', expected_version=None, out=None, content=None):
    document=load_language(library,language_id)
    return commit(library,language_id,document,changed_document(document,changes),reason,expected_version,out=out,content=content)


def restore(library, language_id, version, reason='', expected_version=None, out=None, content=None):
    if not isinstance(version,str) or not re.fullmatch('[0-9a-f]{64}',version):raise ValueError('Expected an immutable language version hash')
    document=load_language(library,language_id)
    snapshot=read_json(inside(library,'languages',language_id,'versions',version+'.json'))
    if digest(snapshot)!=version:raise ValueError('Immutable version file content mismatch')
    candidate={**document,**deepcopy(version_document(snapshot))}
    return commit(library,language_id,document,candidate,reason,expected_version,restored_from=version,out=out,content=content)
