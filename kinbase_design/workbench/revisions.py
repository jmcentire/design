"""Exact scope/property controls over the canonical current-language revision API."""
from copy import deepcopy
import hashlib
import json
from ..findings import pointer
from ..language.revisions import revise, restore, history
from ..language.resolver import parse_scope
from ..language.tokens import normalize
from ..language.properties import SPACE_PROPERTIES
from ..language.versions import digest
from ..storage import load_language
from ..vocabulary import load
from .ingest import fields

PROPERTIES={'letter-spacing':'Letter spacing (px or rem)','line-height':'Line height (ratio, px or rem)',
            'padding':'Padding (px or rem)','padding-inline':'Side padding (px or rem)',
            'padding-block':'Top and bottom padding (px or rem)','gap':'Group spacing (px or rem)',
            'color':'Text color (#hex)','background-color':'Background color (#hex)'}


def scopes(document,vocabulary):
    result=[]
    for role,emphases in document['roles'].items():
        for emphasis in emphases:result.append(('role/'+role+'/'+emphasis,role.replace('-',' ').title()+' role · '+emphasis))
    for construct,spec in vocabulary['constructs'].items():
        label=construct.replace('-',' ').title();result.append((construct,label+' · whole group'))
        result.extend((construct+'.'+slot['id'],label+' · '+slot['id'].replace('-',' ')) for slot in spec['slots'])
        result.extend((construct+'~'+part,label+' · '+part.replace('-',' ')+' group') for part in spec.get('parts',{}))
    return result


def property_changes(document,vocabulary,scope,prop,value):
    if prop not in PROPERTIES:raise ValueError('Choose a supported language property')
    if scope not in dict(scopes(document,vocabulary)):raise ValueError('Choose a declared language scope')
    if not isinstance(value,str) or not value.strip():raise ValueError('Enter an exact property value')
    value=value.strip();kind='color' if prop in {'color','background-color'} else 'dimension'
    if prop=='line-height':
        try:value=float(value);kind='number'
        except ValueError:pass
    normalize(kind,value)  # Validate the same literal grammar used by tokens.
    candidate=deepcopy(document)
    if scope.startswith('role/'):
        _,role,emphasis=scope.split('/');target=candidate['roles'][role][emphasis]
    else:
        parsed=parse_scope(scope,vocabulary);target=candidate['components'].setdefault(parsed.construct,{})
        if parsed.part:target=target.setdefault('parts',{}).setdefault(parsed.part,{})
        else:
            if parsed.slot:target=target.setdefault('slots',{}).setdefault(parsed.slot,{})
            target=target.setdefault('properties',{})
    # A scope edit must not mutate a shared source token used by other scopes.
    name='edit-'+hashlib.sha256((scope+'/'+prop).encode()).hexdigest()[:16]
    group='space' if prop in SPACE_PROPERTIES else 'editing'
    if group=='space' and '$value' in candidate['style'].get(group,{}):
        raise ValueError('Spacing edits require the language space token group')
    while group in candidate['style'] and '$value' in candidate['style'][group]:group+='-derived'
    tokens=candidate['style'].setdefault(group,{})
    ref='{'+group+'.'+name+'}'
    serialized=json.dumps(document)
    while name in tokens and not (target.get(prop)==ref and serialized.count(json.dumps(ref))==1):
        name+='-derived';ref='{'+group+'.'+name+'}'
    tokens[name]={'$type':kind,'$value':value};target[prop]=ref
    return {pointer(root):candidate[root] for root in ('style','roles','components') if candidate[root]!=document[root]}


def handle(library,language_id,action,environ,html):
    from . import RequestError
    method=environ.get('REQUEST_METHOD','GET')
    if action=='history' and method=='GET':
        return 200,html('language-history.html',title='Language history',language=load_language(library,language_id),history=history(library,language_id)),'text/html; charset=utf-8',[]
    if method!='POST':raise RequestError('Unknown revision route',404)
    data={k:v[0] for k,v in fields(environ).items()}
    if action=='feedback-language':
        from ..language.feedback import feedback
        result=feedback(library,language_id,data.get('feedback',''),scope=data.get('scope') or None,expected_version=data.get('expected_version') or None)
        if result.get('accepted'):return 303,b'','text/html; charset=utf-8',[('Location','/languages/'+language_id)]
        document=load_language(library,language_id);vocabulary=load(library,document['vocabulary'])
        return (422,html('language-feedback.html',title='Design feedback',language=document,result=result,
                         feedback_text=data.get('feedback',''),feedback_scope=data.get('scope',''),
                         edit_scopes=scopes(document,vocabulary),current_version=digest(document)),
                'text/html; charset=utf-8',[])
    if action=='revise':
        document=load_language(library,language_id);vocabulary=load(library,document['vocabulary'])
        changes=property_changes(document,vocabulary,data.get('scope',''),data.get('property',''),data.get('value',''))
        result=revise(library,language_id,changes,reason=data.get('reason',''),expected_version=data.get('expected_version') or digest(document))
    elif action=='restore':
        result=restore(library,language_id,data.get('version',''),reason=data.get('reason',''),expected_version=data.get('expected_version') or None)
    else:raise RequestError('Unknown revision route',404)
    if not result.get('accepted'):raise RequestError('Language update rejected: '+'; '.join(f['message'] for f in result['findings']),422)
    return 303,b'','text/html; charset=utf-8',[('Location','/languages/'+language_id)]
