"""Private card extent on the vocabulary's media/content composition."""
from .quantize import px


def treatment(item,view,surface,token,origin):
    root=item['treatment']['properties']
    nodes=view.get('structure',view['nodes'])
    anchors=[n['selector'] for slot,n in item['nodes'].items() if slot!='media']
    wrappers=[n for n in nodes if n['tag'] in {'div','section','article'} and n['selector'].startswith(surface['selector']+' > ')
              and anchors and all(s.startswith(n['selector']+' > ') for s in anchors)]
    wrapper=max(wrappers,key=lambda n:len(n['selector'])) if wrappers else None
    inner=wrapper.get('styles',{}) if wrapper else {}
    style=surface.get('styles',{});box=surface.get('box');media=item['nodes'].get('media',{});image=media.get('box')
    border=px(style.get('border-top-width')) or 0
    full=bool(box and image and abs(image[0]-box[0]-border)<=2 and abs(image[2]-(box[2]-2*border))<=2)
    content={'display':'flex','flex-direction':'column','align-items':'stretch'}
    for axis,sides in [('inline',('left','right')),('block',('top','bottom'))]:
        inset=max(px(inner.get('padding-'+side)) or 0 for side in sides)
        bleed=full and (axis=='inline' or abs(image[1]-box[1]-border)<=2)
        if bleed:
            inset+=max(px(style.get('padding-'+side)) or 0 for side in sides)
            root['padding-'+axis]=token('dimension','0px',origin(view,surface,'full-bleed media'),spacing=True)
        content['padding-'+axis]=token('dimension',f'{inset:g}px',origin(view,wrapper or surface,'content inset'),spacing=True)
    item['treatment']['parts']={'content':content}
    if full:
        item['treatment']['slots']['media']['properties'].update({'width':token('dimension',f'{image[2]:g}px',origin(view,media,'measured full-bleed width')),'max-width':'100%'})
