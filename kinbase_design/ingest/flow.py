"""Generic heading-led document flow, independent of subject matter or URL."""
from copy import deepcopy
import re
from .presentation import visible_text


def level(node):
    if re.fullmatch('h[1-6]',node['tag']):return int(node['tag'][1])
    if node.get('attributes',{}).get('role')=='heading':
        try:return int(node['attributes'].get('aria-level',2))
        except (TypeError,ValueError):return 2
    return None


def long_form(node,descendants):
    return node['tag']=='article' and sum(level(n) is not None for n in descendants)>=2


def split_flow(nodes,roots,owner):
    """Return explicit ownership for sibling heading runs and standalone media.

    Root ids stay real source selectors. Their private compositions may nest by
    heading level even when the original DOM uses flat sibling headings.
    """
    assigned={};parents={};by={n['selector']:n for n in nodes}
    original={n['selector']:owner(n) for n in nodes}
    for key,item in list(roots.items()):
        if item['construct'] in {'card','nav','footer','form','search-bar','gallery'}:continue
        owned=[n for n in nodes if original[n['selector']] is item]
        headings=[n for n in owned if level(n)]
        if not headings and not any(n['tag'] in {'pre','img','svg'} for n in owned):continue
        stack=[];active=key;paragraphs={}
        item['flow']=True
        for node in owned:
            depth=level(node)
            if depth:
                while stack and stack[-1][0]>=depth:stack.pop()
                parent=stack[-1][1] if stack else key
                active=node['selector'];stack.append((depth,active));parents[active]=parent
                root=deepcopy(node)
                root['styles']={};root['normalized_colors']={};root['box']=None
                roots[active]={'construct':'hero' if depth==1 else 'content-section','selector':active,
                               'values':{},'media':{},'nodes':{},'root_node':root,'flow':True}
            target=active
            # Prose blocks remain in source order with the media between them.
            # They use the existing body slot instead of an alternate renderer.
            if node['tag'] in {'p','li','blockquote','figcaption','pre'} and node['selector']!=key:
                target=node['selector'];paragraphs[target]=target;parents[target]=active
                root={'selector':target,'tag':'section','styles':{},'box':None}
                roots[target]={'construct':'content-section','selector':target,'values':{},'media':{},'nodes':{},'root_node':root,'flow':True}
            else:
                matches=[p for p in paragraphs if node['selector'].startswith(p+' > ')]
                if matches:target=max(matches,key=len)
            assigned[node['selector']]=target
    # Media without a media slot remains an ordered child construct.
    for node in nodes:
        if node['tag'] not in {'img','svg'} or not node.get('src'):continue
        key=assigned.get(node['selector']);item=roots.get(key) if key else original[node['selector']]
        if not item or not (item['construct']=='content-section' or item.get('flow')):continue
        key=node['selector'];parents[key]=item['selector'];assigned[key]=key
        root={'selector':key,'tag':'figure','styles':{},'box':node.get('box')}
        bounds=node.get('box');ancestor=by.get(node.get('parent'))
        while not bounds and ancestor:
            bounds=ancestor.get('box');ancestor=by.get(ancestor.get('parent'))
        if bounds and bounds[2]>0:
            # Unsampled inline thumbnails inherit a containing box, not page width.
            width=bounds[2] if node.get('box') else min(bounds[2],bounds[3])
            if width>0:root['styles']['max-width']=f'{width:g}px'
            if not node.get('box'):root['style_inferred_from']=node.get('style_inferred_from',node.get('parent',key))
        roots[key]={'construct':'gallery','selector':key,'values':{},'media':{},'nodes':{},'root_node':root,'flow':True}

    return assigned,parents


def block(node,by):
    current=node
    while current:
        if current['tag'] in {'p','li','blockquote','figcaption','pre','h1','h2','h3','h4','h5','h6'}:return current['selector']
        current=by.get(current.get('parent'))
    return node.get('parent') or node['selector']


def inline_role(node,by):
    """A link within prose/heading keeps that role and its original link target."""
    current=by.get(node.get('parent'))
    while current:
        if level(current):return 'title' if level(current)<=2 else 'subtitle'
        if current['tag'] in {'p','li','blockquote','figcaption','pre'} and (current.get('text') or visible_text(current)):return 'body'
        current=by.get(current.get('parent'))
    return None
