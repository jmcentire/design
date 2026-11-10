"""View-only color scale labels from retained source names, never inferred hue."""
from collections import defaultdict
import re
from ..language.tokens import Tokens, normalize


def named_step(name):
    if not isinstance(name,str):return None
    name=name.strip()
    if re.search(r'(?:^|[./])(?:node_[^./]+|ingest\.v[0-9]+)(?:[./]|$)',name):return None
    match=re.fullmatch(r'(.+?)\s*[./_-]\s*([0-9]+)',name)
    if not match or not re.search(r'[A-Za-z]',match[1]):return None
    return match[1].strip(),int(match[2]),match[2]


def palette_groups(palette, style):
    """Keep every measured entry; ambiguous matches retain their measured order."""
    names={}
    try:tokens=Tokens(style)
    except ValueError:
        return [{'name':'Other colors','colors':[{'value':color['value'],'label':None,'step':None} for color in palette]}] if palette else []
    def walk(group,path=(),figma_name=None):
        extensions=group.get('$extensions',{})
        figma=extensions.get('figma',{}) if isinstance(extensions,dict) else {}
        if isinstance(figma,dict) and isinstance(figma.get('name'),str):figma_name=figma['name']
        if '$value' in group:
            candidates={value for value in (named_step('.'.join(path)),named_step(figma_name)) if value is not None}
            names['.'.join(path)]=candidates
            return
        for key,child in group.items():
            if not key.startswith('$') and isinstance(child,dict):walk(child,(*path,key),figma_name)
    walk(style)
    by_value=defaultdict(set);by_step=defaultdict(set)
    for path,candidates in names.items():
        try:kind,value=tokens.evaluate(path)
        except (KeyError,ValueError):continue
        if kind!='color':continue
        for family,step,label in candidates:
            identity=(family,step)
            by_value[value].add((family,step,label));by_step[identity].add(value)
    groups={};other=[]
    for color in palette:
        value=color['value']
        try:normalized=normalize('color',value)
        except ValueError:normalized=None
        candidates=by_value.get(normalized,set())
        identities={(family,step) for family,step,_ in candidates}
        if len(identities)==1:
            family,step=next(iter(identities))
            if len(by_step[(family,step)])==1:
                label=sorted(label for f,s,label in candidates)[0]
                groups.setdefault(family,[]).append({'value':value,'label':label,'step':step})
                continue
        other.append({'value':value,'label':None,'step':None})
    result=[{'name':name,'colors':sorted(colors,key=lambda color:color['step'])} for name,colors in groups.items()]
    if other:result.append({'name':'Other colors','colors':other})
    return result
