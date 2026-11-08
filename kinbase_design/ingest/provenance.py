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


def complete(document,provenance,inputs):
    default={'kind':'inferred','method':'Vocabulary defaults and measured capture treatments','inputs':inputs}
    return {path:deepcopy(provenance.get(path,default)) for path,_ in values(document)}


def shared(provenance):
    result={}
    for path,entry in provenance.items():
        item={'kind':entry['kind']}
        if entry.get('artifact'):item['artifact']=entry['artifact']
        location=entry.get('location','')
        # Producers mark the location grammar. Unmarked paths/URLs remain private.
        if location.startswith('json:'):
            value=location[5:]
            if re.fullmatch(r'(?:/[a-zA-Z0-9_$~.-]+)*',value):item['location']=value
        elif location.startswith(('selector:','page:')):
            value=location.split(':',1)[1]
            if not any(s in value for s in ('://','\\','/')):item['location']=value
        if entry['kind']=='inferred':item['method']='Derived from captured measurements and Vocabulary defaults'
        if entry['kind']=='chosen':item['method']='Visual choice '+re.sub('[^a-zA-Z0-9_-]','',entry.get('choice',''))
        result[path]=item
    return result
