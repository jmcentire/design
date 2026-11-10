"""Private card extent on the vocabulary's media/content composition."""
from .quantize import px


def insets(item,view,surface):
    """Locate the text inset independently of whether its wrapper was sampled."""
    nodes=view.get('structure',view['nodes'])
    text=[n for slot,n in item['nodes'].items() if slot not in {'media','action','secondary-action'}]
    anchors=[n['selector'] for n in text]
    wrappers=[n for n in nodes if n['tag'] in {'div','section','article'} and n['selector'].startswith(surface['selector']+' > ')
              and anchors and all(s==n['selector'] or s.startswith(n['selector']+' > ') for s in anchors)]
    wrapper=max(wrappers,key=lambda n:len(n['selector']),default=None)
    style=surface.get('styles',{});box=surface.get('box');image=item['nodes'].get('media',{}).get('box')
    horizontal=bool(image and any(n.get('box') and min(n['box'][1]+n['box'][3],image[1]+image[3])>max(n['box'][1],image[1])
                                 and (n['box'][0]>=image[0]+image[2]-1 or n['box'][0]+n['box'][2]<=image[0]+1) for n in text))
    border=px(style.get('border-top-width')) or 0
    full=bool(box and image and abs(image[0]-box[0]-border)<=2 and abs(image[2]-(box[2]-2*border))<=2)
    result={}
    for axis,sides in [('inline',('left','right')),('block',('top','bottom'))]:
        outer=max(px(style.get('padding-'+side)) or 0 for side in sides)
        inner=sum(max(px(n.get('styles',{}).get('padding-'+side)) or 0 for side in sides) for n in wrappers)
        # Geometry survives unsampled wrapper styles. Use block text edges,
        # rather than the width of a short or right-aligned metadata label.
        boxes=[n['box'] for n in text if n.get('box') and n['tag'] in {'p','h1','h2','h3','h4','h5','h6','dl','dt'}]
        if axis=='inline' and box and boxes and not horizontal:
            inner=max(0,min(b[0] for b in boxes)-box[0]-border-outer)
        result[axis]=(outer,inner)
    return result,wrapper,full


def treatment(item,view,surface,token,origin,properties):
    root=item['treatment']['properties']
    nodes=view.get('structure',view['nodes'])
    measured,wrapper,full=insets(item,view,surface)
    media=item['nodes'].get('media',{});image=media.get('box')
    content={'display':'flex','flex-direction':'column','align-items':'stretch'}
    for axis,(outer,inset) in measured.items():
        root['padding-'+axis]=token('dimension',f'{outer:g}px',origin(view,surface,'item inset'),spacing=True)
        content['padding-'+axis]=token('dimension',f'{inset:g}px',origin(view,wrapper or surface,'content inset'),spacing=True)
    def within(node,parent):return node['selector']==parent or node['selector'].startswith(parent+' > ')
    owned=[n for n in nodes if within(n,surface['selector'])]
    def enclosing(children):
        return max((n for n in owned if children and all(c['selector'].startswith(n['selector']+' > ') for c in children)),key=lambda n:len(n['selector']),default=None)
    zero=token('dimension','0px',origin(view,surface,'single content inset'),spacing=True)
    def group(node):
        result={'padding':zero,'padding-inline':zero,'padding-block':zero,'background-color':token('color','#00000000'),'border-style':'none','border-width':token('dimension','0px'),'box-shadow':'none'}
        if node:result.update({k:v for k,v in properties(view,node).items() if k in set(result)|{'border-color','border-radius','gap','row-gap','column-gap'}})
        return result
    dl=next((n for n in owned if n['tag']=='dl'),None)
    fields=[n for n in owned if dl and within(n,dl['selector']) and n['tag'] in {'dt','dd'}][:2]
    pair=enclosing(fields)
    content.update({k:v for k,v in group(wrapper).items() if not k.startswith('padding')})
    item['treatment']['parts']={'content':content}
    if dl and 'meta' in item['treatment']['slots']:
        item['treatment']['parts']['pair']=group(pair if pair!=dl else None)
        item['treatment']['slots']['meta']['properties'].update(group(dl))
    if full:
        item['treatment']['slots']['media']['properties'].update(bleed_properties(item,view,surface,token,origin,measured))


def bleed_properties(item,view,surface,token,origin,measured):
    """Let measured media escape the inset without changing the item's surface."""
    media=item['nodes']['media'];image=media['box'];box=surface['box']
    extension=token('dimension',f'{2*measured["inline"][0]:g}px',origin(view,media,'full-bleed width beyond content inset'))
    result={'width':'calc(100% + '+extension+')','max-width':'calc(100% + '+extension+')',
            'margin-inline':token('dimension',f'{-measured["inline"][0]:g}px',origin(view,media,'full-bleed inline extent'),spacing=True)}
    border=px(surface.get('styles',{}).get('border-top-width')) or 0
    if abs(image[1]-box[1]-border)<=2:
        result['margin-block-start']=token('dimension',f'{-measured["block"][0]:g}px',origin(view,media,'full-bleed block extent'),spacing=True)
    return result
