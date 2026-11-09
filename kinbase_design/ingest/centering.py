"""Distinguish source column centring from a reusable block's internal inset."""
from collections import defaultdict
from .quantize import px


def inline_margins(style):
    """Computed logical shorthands may serialize as either one or two values."""
    values=style.get('margin-inline','').split()
    left=style.get('margin-left',style.get('margin-inline-start'))
    right=style.get('margin-right',style.get('margin-inline-end'))
    if len(values) in {1,2}:
        left=left if left is not None else values[0]
        right=right if right is not None else values[-1]
    return left,right


def content_edges(node):
    x,_,width,_=node['box'];style=node.get('styles',{})
    left=sum(px(style.get(p)) or 0 for p in ('padding-left','border-left-width'))
    right=sum(px(style.get(p)) or 0 for p in ('padding-right','border-right-width'))
    return x+left,x+width-right


def viewport_centres(views):
    observed=defaultdict(list);centres=set()
    for view in views:
        nodes=view.get('structure',view['nodes']);by={n['selector']:n for n in nodes}
        for node in nodes:
            if node.get('style_inferred_from'):continue
            style=node.get('styles',{});key=(view['page'],node['selector'])
            left,right=inline_margins(style)
            if left==right=='auto':
                centres.add(key);continue
            left,right=px(left),px(right)
            if left is None or right is None or min(left,right)<0 or abs(left-right)>1 or not node.get('box'):continue
            x,_,width,_=node['box'];viewport=view['width']
            parent=by.get(node.get('parent'))
            edges=content_edges(parent) if parent and parent.get('box') else (0,viewport) if node.get('tag')=='body' else None
            # Equal margins consuming the parent's remaining content width are
            # alignment, even when cross-origin rules hide the authored 'auto'.
            if edges and max(left,right)>0 and abs(x-edges[0]-left)<=1 and abs(edges[1]-x-width-right)<=1:
                centres.add(key)
            # A captured cap can establish viewport alignment even when the
            # parent was not sampled.
            cap=px(style.get('max-width'))
            extras=sum(px(style.get(p)) or 0 for p in ('padding-left','padding-right','border-left-width','border-right-width'))
            if cap is not None and min(abs(width-cap),abs(width-cap-extras))<=1 and min(left,right)>0 and abs(x-left)<=1 and abs(viewport-x-width-right)<=1:
                centres.add(key)
            observed[key].append((viewport,(left+right)/2,width,abs(x-left)<=1 and abs(viewport-x-width-right)<=1))
    for key,records in observed.items():
        # The parent may be unsampled. A fixed-width block whose equal margins
        # change with viewport width also supplies direct centring evidence.
        for i,(viewport,margin,width,aligned) in enumerate(records):
            if any(other_view!=viewport and abs(other_margin-margin)>1 and (abs(other_width-width)<=1 or aligned and other_aligned)
                   for other_view,other_margin,other_width,other_aligned in records[i+1:]):
                centres.add(key);break
    return centres


def portable(view,node,properties,centres,notes):
    result=dict(properties)
    selector=node.get('style_inferred_from',node['selector'])
    explicit_auto=inline_margins(node.get('styles',{}))==('auto','auto')
    if ('margin-inline' in result or explicit_auto) and (view['page'],selector) in centres:
        result['margin-inline']='auto'
        note={'rule':'ingest-centering','message':'Source column centring is retained as auto alignment, not a fixed inset inside the portable column',
              'artifact':view['artifact'],'page':view['page'],'width':view['width'],'selector':selector}
        if note not in notes:notes.append(note)
    return result
