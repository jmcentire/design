"""Recover content and ancestry from immutable HTML, without executing markup."""
from html.parser import HTMLParser
from copy import deepcopy
import re

VOID={'area','base','br','col','embed','hr','img','input','link','meta','param','source','track','wbr'}
IGNORED={'script','style','noscript','template'}


class Snapshot(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True);self.stack=[];self.nodes=[]

    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs);parent=self.stack[-1] if self.stack else None
        counts=parent['_counts'] if parent else {};counts[tag]=counts.get(tag,0)+1
        selector='body' if tag=='body' else (parent['selector']+' > ' if parent else '')+tag+':nth-of-type('+str(counts[tag])+')'
        node={'tag':tag,'selector':selector,'parent':parent['selector'] if parent else None,'attributes':attrs,'_counts':{},'_text':[], '_direct':[]}
        if tag=='body' or parent and parent.get('_body'):node['_body']=True
        node['_ignored']=tag in IGNORED or bool(parent and parent.get('_ignored'))
        if node.get('_body') and not node['_ignored']:self.nodes.append(node)
        if tag not in VOID:self.stack.append(node)

    def handle_startendtag(self,tag,attrs):
        self.handle_starttag(tag,attrs)
        if tag not in VOID:self.handle_endtag(tag)

    def handle_endtag(self,tag):
        for index in range(len(self.stack)-1,-1,-1):
            if self.stack[index]['tag']==tag:del self.stack[index:];break

    def handle_data(self,data):
        if not self.stack or self.stack[-1]['_ignored']:return
        self.stack[-1]['_direct'].append(data)
        for node in self.stack:node['_text'].append(data)


def pattern(selector):return re.sub(r':nth-of-type\(\d+\)',':nth-of-type(*)',selector)


def content_nodes(view,html=None):
    """Keep measured samples exact; label inferred styles on unsampled content."""
    if not html:return view.get('nodes',[])
    parser=Snapshot();parser.feed(html)
    sampled={n['selector']:n for n in view['nodes']};patterns={}
    for node in view['nodes']:patterns.setdefault(pattern(node['selector']),[]).append(node)
    result=[];by_selector={}
    candidates={c['selector']:c for c in view.get('candidates',[]) if c.get('selector')}
    for raw in parser.nodes:
        selector=raw['selector'];parent=by_selector.get(raw['parent'])
        if 'hidden' in raw['attributes'] or re.search(r'display\s*:\s*none',raw['attributes'].get('style','')):continue
        classes=set(raw['attributes'].get('class','').split())
        if 'sr-only' in classes:continue
        if 'hidden' in classes and selector not in sampled and not any(key.startswith(selector+' > ') for key in sampled):continue
        if raw['parent']!='body' and raw['parent'] not in by_selector and raw['tag']!='body':continue
        node={k:v for k,v in raw.items() if not k.startswith('_')}
        node.update(text=' '.join(''.join(raw['_text']).split()),directText=' '.join(''.join(raw['_direct']).split()))
        if selector in sampled:node.update(deepcopy(sampled[selector]))
        else:
            matches=patterns.get(pattern(selector),[])
            def similarity(n):
                other=set(n.get('attributes',{}).get('class','').split())
                return len(classes&other)/len(classes|other) if classes|other else 1
            matching=max(matches,key=similarity,default=None)
            if matching and similarity(matching)<.6:matching=None
            witness=matching or parent
            if witness:
                node.update(styles=deepcopy(witness.get('styles',{})),normalized_colors=deepcopy(witness.get('normalized_colors',{})),backgrounds=deepcopy(witness.get('backgrounds',[])),style_inferred_from=witness.get('style_inferred_from',witness['selector']))
                if matching is None:
                    inherited={'color','font-family','font-size','font-weight','font-style','line-height','letter-spacing','text-align'}
                    node['styles']={k:v for k,v in node['styles'].items() if k in inherited}
                    node['normalized_colors']={k:v for k,v in node['normalized_colors'].items() if k=='color'}
            # Unsampled structure is not assigned its ancestor's dimensions.
            node['box']=None
        if node['tag']=='img':
            node['src']=node.get('src') or candidates.get(selector,{}).get('url') or node['attributes'].get('src')
        by_selector[selector]=node;result.append(node)
    return result
