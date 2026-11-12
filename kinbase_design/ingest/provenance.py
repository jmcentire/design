"""Complete value provenance and deliberate redaction at the library boundary."""
from copy import deepcopy
import re
from ..findings import pointer


def values(document,path=''):
    yield path,document
    if isinstance(document,dict):
        for key,value in document.items():yield from values(value,path+pointer(key))
    elif isinstance(document,list):
        for index,value in enumerate(document):yield from values(value,path+pointer(index))


def source(artifact,location):
    return {'kind':'source','artifact':artifact,'location':location}


def record_at(provenance,path):
    """Resolve the nearest RFC 6901 ancestor, including the root record."""
    while True:
        if path in provenance:return provenance[path]
        if not path:return None
        path=path.rsplit('/',1)[0]


def design_values(document):
    """Yield required design leaves; token metadata and reasons need no record."""
    def leaves(value,path,skip_reason=False):
        if isinstance(value,dict):
            for key,child in value.items():
                if key in {'$type','$description','$extensions'} or skip_reason and key=='reason':continue
                yield from leaves(child,path+pointer(key),skip_reason)
        elif isinstance(value,list):
            for index,child in enumerate(value):yield from leaves(child,path+pointer(index),skip_reason)
        else:yield path,value
    def tokens(value,path):
        if not isinstance(value,dict):return
        if '$value' in value:
            yield from leaves(value['$value'],path+'/$value')
        else:
            for key,child in value.items():
                if not key.startswith('$'):yield from tokens(child,path+pointer(key))
    yield from tokens(document.get('style',{}),'/style')
    for group in ('roles','layout','components','overrides','behaviors','assets'):
        if group in document:yield from leaves(document[group],pointer(group),group in {'overrides','behaviors'})


def complete(document,provenance,inputs):
    if not isinstance(provenance,dict):raise ValueError('Provenance must be a direct JSON-pointer map')
    for path,entry in provenance.items():
        if not isinstance(path,str) or path and not path.startswith('/') or re.search(r'~(?![01])',path):
            raise ValueError('Provenance keys must be RFC 6901 pointers')
        if not isinstance(entry,dict) or entry.get('kind') not in {'source','inferred','chosen'}:
            raise ValueError('Provenance records must be source, inferred or chosen')
    default={'kind':'inferred','method':'Vocabulary defaults and measured capture treatments','inputs':inputs}
    existing={path for path,_ in values(document)}
    result={path:deepcopy(entry) for path,entry in provenance.items() if path in existing}
    for path,_ in design_values(document):
        if record_at(result,path) is None:result[path]=deepcopy(default)
    return result


def shared(provenance):
    result={}
    for path,entry in provenance.items():
        item={'kind':entry['kind']}
        if entry.get('artifact'):item['artifact']=entry['artifact']
        if re.fullmatch(r'kinbase:[a-zA-Z0-9_.:-]+',entry.get('source','')):item['source']=entry['source']
        location=entry.get('location','')
        # Producers mark the location grammar. Unmarked paths/URLs remain private.
        if str(entry.get('artifact','')).startswith('kinbase:') and location.startswith('/kinbase-design/') and not any(x in location for x in ('://','\\')):
            item['location']=location
            # Composite values may depend on more than one fixed dimension.
            if entry.get('inputs'):
                item['inputs']=list(shared({str(i):r for i,r in enumerate(entry['inputs'])}).values())
        elif location.startswith('json:'):
            value=location[5:]
            if re.fullmatch(r'(?:/[a-zA-Z0-9_$~.-]+)*',value):item['location']=value
        elif location.startswith(('selector:','page:')):
            value=location.split(':',1)[1]
            if not any(s in value for s in ('://','\\','/')):item['location']=value
        # A meaning mapping keeps its token path and standing; reviewers' names stay private.
        if entry.get('standing') in {'certified','chosen','candidate'} and re.fullmatch(r'[a-zA-Z0-9_-]+(?:\.[a-zA-Z0-9_-]+)*',str(entry.get('mapping',''))):
            item.update(mapping=entry['mapping'],standing=entry['standing'])
        if entry['kind']=='source':item.setdefault('location','')  # The artifact root, when a private location is redacted.
        if entry['kind']=='inferred':item['method']='Derived from design evidence and Vocabulary defaults'
        if entry['kind']=='chosen':
            choices=entry.get('choices') or [entry.get('choice','')]
            item['method']=('Meaning mapping reviewed locally, ' if 'mapping' in item else 'Visual choice ')+', '.join(re.sub('[^a-zA-Z0-9_-]','',choice.removeprefix('meaning/')) for choice in choices)
        result[path]=item
    return result


def inspect_sources(workspace,provenance):
    from ..storage import inside,identifier
    def artifacts(entry):
        found=[]
        if isinstance(entry,dict):
            if entry.get('artifact') and not entry['artifact'].startswith('kinbase:'):found.append(entry['artifact'])
            for value in entry.get('inputs',[]):found.extend(artifacts(value))
        elif isinstance(entry,str) and entry.startswith('artifact-'):found.append(entry)
        return found
    entries=[]
    for path,entry in provenance.items():
        refs=artifacts(entry)
        present=all(inside(workspace,'artifacts',identifier(ref),'metadata.json').is_file() for ref in refs)
        entries.append({'pointer':path,**entry,'status':'source removed' if refs and not present else 'source available' if refs else entry['kind']})
    return entries


def protected(provenance,path):
    """A write cannot replace a source value at, above, or below its target."""
    return any(entry.get('kind')=='source' and (key==path or key.startswith(path+'/') or path.startswith(key+'/'))
               for key,entry in provenance.items())
