"""Portable group layout inferred from source geometry, independent of source names."""
from statistics import median
import math
from ..language.tokens import Tokens
from .quantize import px
from .presentation import visible_text


def transfer(document,vocabulary,view,treatments,token,space_token,origin,questions,spacing_base,corrections,primary_item=None):
    nodes=view.get('structure',view['nodes']);width=view['width'];by={n['selector']:n for n in nodes}
    def props(scope):return treatments.setdefault((scope,width),{})
    def dimension(name,value,construct,old=None,reason=None,spacing=False):
        group='space' if spacing else 'flow';name='flow-'+name+'-'+str(width)
        document['style'].setdefault(group,{})[name]={'$type':'dimension','$value':f'{value:g}px'}
        if reason:
            questions.append({'pointer':'/style/'+group+'/'+name+'/$value','construct':construct,'state':'default',
                              'values':list(dict.fromkeys([f'{value:g}px',old])) if old is not None else [f'{value:g}px'], 'reason':reason})
        return '{'+group+'.'+name+'}'
    def number(ref):
        if ref is None:return None
        value=Tokens(document['style']).reference(ref)[1]
        return float(value[:-3])*16 if value.endswith('rem') else px(value)
    def heading_rhythm(construct,item):
        level={'hero':1,'content-section':2,'card':3}[construct]
        title=(item or {}).get('nodes',{}).get('title',{})
        candidates=[n for n in nodes if n['tag']=='h'+str(level)]
        if title.get('tag') not in {'h1','h2','h3','h4','h5','h6'}:
            title=next(iter(candidates),{})
        binding='heading-binding' in vocabulary.get('composition_rules',[])
        if binding and not title:
            title=min((n for n in nodes if n['tag'] in {'h1','h2','h3','h4','h5','h6'}),key=lambda n:abs(int(n['tag'][1])-level),default={})
        before=px(title.get('styles',{}).get('margin-top'));after=px(title.get('styles',{}).get('margin-bottom'))
        measured_before=before
        if binding:before=before or 0;after=after if after is not None else spacing_base
        if before is None or after is None or min(before,after)<0:return
        # Put the shared spacing in the group once; retain the heading's larger
        # leading margin as a start-only offset, rather than doubling p margins.
        group=construct+'~content' if 'content' in vocabulary['constructs'][construct].get('parts',{}) else construct
        gap=max(after,px((item or {}).get('root_node',{}).get('styles',{}).get('gap')) or 0)
        witness=title or (item or {}).get('root_node') or body or {'selector':'body'}
        props(group)['gap']=space_token(gap,origin(view,witness,'margin-bottom'))
        if binding and 'heading' in vocabulary['constructs'][construct].get('parts',{}):
            props(construct+'~heading').update({'display':'flex','flex-direction':'column','gap':space_token(max(4,gap),origin(view,witness,'heading group separation'))})
        zero=space_token(0,origin(view,witness,'normalized group margins'))
        for slot in vocabulary['constructs'][construct]['slots']:
            if slot['kind']=='media':continue
            current=props(construct+'.'+slot['id']);current['margin-block']=zero
            current['margin-block-start']=zero;current['margin-block-end']=zero
        start=max(0,before-max(4,gap))
        # A section's heading wrapper and following body can have different
        # row gaps. Account for the effective axes, not only the gap shorthand.
        after_gap=number(props(group).get('row-gap',props(group).get('gap'))) or 0
        before_group=construct+'~heading' if 'heading' in vocabulary['constructs'][construct].get('parts',{}) else group
        before_gap=number(props(before_group).get('row-gap',props(before_group).get('gap'))) or 0
        required=max(0,after_gap-before_gap)
        if binding and before_gap+start<=after_gap:
            from .composition import correction
            chosen=(math.floor(required/spacing_base)+1)*spacing_base
            ref=dimension('binding-'+construct,chosen,construct,f'{before:g}px','Heading must be closer to following content than preceding content',spacing=True)
            questions[-1]['values'].append(f'{chosen+spacing_base:g}px')
            correction(corrections,questions[-1],'heading-binding',title.get('selector'),f'{measured_before:g}px' if measured_before is not None else None,f'{chosen:g}px')
            props(construct+'.title')['margin-block-start']=ref
        else:props(construct+'.title')['margin-block-start']=space_token(start,origin(view,witness,'margin-top'))
    text=[n for n in nodes if visible_text(n) and px(n.get('styles',{}).get('font-size'))]
    floor=min((px(n['styles']['font-size']) for n in text),default=16)
    body=next((n for n in nodes if n['tag']=='body'),{})
    body_size=px(body.get('styles',{}).get('font-size')) or 16
    body_align=body.get('styles',{}).get('text-align','start')
    for construct,spec in vocabulary['constructs'].items():
        for slot in spec['slots']:
            if slot['kind']=='media':continue
            scope=construct+'.'+slot['id'];current=treatments.get((scope,width),{})
            ref=current.get('font-size') or document['roles'][slot['role']][slot['emphasis']].get('font-size')
            size=number(ref)
            if size is not None and size<floor:
                props(scope)['font-size']=dimension(construct+'-'+slot['id']+'-floor',floor,construct,f'{size:g}px',
                    'Reusable text cannot be smaller than the smallest measured source text; infer that measured floor')
    for construct in ('hero','content-section','card'):
        items=[i for i in view['instances'] if i['construct']==construct]
        expected='h1' if construct=='hero' else 'h2'
        if construct!='card':items=[i for i in items if i.get('nodes',{}).get('title',{}).get('tag')==expected]
        item=max(items,key=lambda i:(i.get('box') or i.get('root_node',{}).get('box') or [0,0,0,0])[2],default=None)
        if construct=='card' and primary_item:item=primary_item
        if item is None and construct=='hero':
            leading=next((n for n in nodes if n['tag']=='h1'),None)
            ancestor=by.get(leading.get('parent')) if leading else None
            while ancestor and ancestor['tag'] not in {'body','main'}:
                paragraphs=[n for n in nodes if n['tag']=='p' and n['selector'].startswith(ancestor['selector']+' > ')]
                if paragraphs:
                    item={'root_node':ancestor,'nodes':{'title':leading,'body':paragraphs[0]}};break
                ancestor=by.get(ancestor.get('parent'))
        root=item.get('root_node',{}) if item else {};style=root.get('styles',{})
        title=item.get('nodes',{}).get('title',{}) if item else {}
        alignment=style.get('text-align') or title.get('styles',{}).get('text-align') or body_align
        props(construct)['text-align']=alignment
        spec=vocabulary['constructs'][construct]
        for slot in spec['slots']:
            if slot['kind']=='media':continue
            current=props(construct+'.'+slot['id']);current['text-align']=alignment
            if slot['kind']=='text':current.update({'display':'block','align-self':'stretch','justify-self':'stretch'})
            if not item and slot['id']=='body':current['font-size']=dimension(construct+'-body',max(body_size,floor),construct)
        if construct in ('hero','content-section'):
            root_props=props(construct)
            if root_props.get('display') not in {'grid','inline-grid','flex','inline-flex'}:root_props.update({'display':'grid','grid-template-columns':'1fr'})
            root_props.update({'justify-content':'start','align-items':'start'})
            # Margins need not be symmetric to establish a group's rhythm.
            # Measure adjacent text/control boxes without importing stretched rows.
            boxes=sorted([n['box'] for n in (item or {}).get('nodes',{}).values() if n.get('box') and n['tag'] not in {'img','svg'}],key=lambda b:b[1])
            gaps=[b[1]-a[1]-a[3] for a,b in zip(boxes,boxes[1:])
                  if b[1]>a[1]+a[3] and min(a[0]+a[2],b[0]+b[2])>max(a[0],b[0])]
            rhythm=px(style.get('row-gap',style.get('gap'))) or (median(gaps) if gaps else None)
            if rhythm is not None:
                root_props['gap']=space_token(rhythm,origin(view,root,'group block gap'))
                if 'content' in spec.get('parts',{}):props(construct+'~content')['gap']=root_props['gap']
            if 'actions' in spec.get('parts',{}):
                props(construct+'~actions').update({'justify-content':'center' if alignment=='center' else 'end' if alignment in {'right','end'} else 'start'})
            if 'content' in spec.get('parts',{}):
                content=props(construct+'~content');content.update({'align-self':'start','justify-content':'start','align-items':'stretch'})
                if alignment=='center':
                    content['margin-inline']='auto'
                    boxes=[n['box'] for n in (item or {}).get('nodes',{}).values() if n.get('box') and n['tag'] in {'h1','p'}]
                    if boxes:content['max-width']=dimension(construct+'-group-width',max(b[2] for b in boxes),construct)
                else:content['margin-inline']=dimension(construct+'-group-margin',0,construct,spacing=True)
        if construct!='card':
            heading_rhythm(construct,item)
            continue
        # Content rows are sized by their text, even when adjacent media is taller.
        inner=props('card~content');inner.update({'display':'flex','flex-direction':'column','justify-content':'start','align-items':'stretch','align-self':'start'})
        media=(item or {}).get('nodes',{}).get('media');image_box=media.get('box') if media else None
        text_boxes=[n['box'] for s,n in (item or {}).get('nodes',{}).items() if s in {'title','body','meta'} and n.get('box')]
        text_box=max(text_boxes,key=lambda b:b[2],default=None)
        horizontal=bool(image_box and text_box and min(image_box[1]+image_box[3],text_box[1]+text_box[3])>max(image_box[1],text_box[1])
                        and (image_box[0]+image_box[2]<=text_box[0]+1 or text_box[0]+text_box[2]<=image_box[0]+1))
        root_props=props('card');root_props.update({'display':'grid','grid-template-columns':'1fr','align-items':'start','justify-content':'start'})
        media_props=props('card.media');media_props.pop('width',None);media_props.update({'display':'block','align-self':'start','justify-self':'start'})
        if image_box and image_box[2]>0 and image_box[3]>0:
            media_width=dimension('card-media-width',image_box[2],'card');media_props['max-width']=media_width
            bounds=root.get('box')
            if bounds and not horizontal:
                left=bounds[0]+(px(style.get('padding-left')) or 0)+(px(style.get('border-left-width',style.get('border-top-width'))) or 0)
                right=bounds[0]+bounds[2]-(px(style.get('padding-right')) or 0)-(px(style.get('border-right-width',style.get('border-top-width'))) or 0)
                if abs(image_box[0]-left)<=2 and abs(image_box[0]+image_box[2]-right)<=2:
                    media_props.update({'max-width':'100%','justify-self':'stretch'})
            a,b=min(((a,b) for a in range(1,33) for b in range(1,33)),key=lambda pair:(abs(pair[0]/pair[1]-image_box[2]/image_box[3]),sum(pair)))
            media_props.update({'aspect-ratio':f'{a} / {b}','object-fit':media.get('styles',{}).get('object-fit') if media.get('styles',{}).get('object-fit') in {'contain','cover','scale-down'} else 'cover'})
            if horizontal:root_props['grid-template-columns']=media_width+' minmax('+dimension('zero',0,'card')+', 1fr)'
        else:
            # A source that omits media at this width gives no portrait evidence.
            box=(item or {}).get('box') or root.get('box')
            media_props.update({'aspect-ratio':'3 / 2','object-fit':'cover','max-width':dimension('card-media-width',box[2] if box else width,'card')})
            questions.append({'pointer':'/components/card/slots/media/properties/aspect-ratio','construct':'card','state':'default',
                              'values':['3 / 2','16 / 9'],'reason':f'No card media measured at {width}px; infer a bounded landscape image in a full-width stacked card'})
        # Explicit reset avoids source inline widths and positional grid placement
        # squeezing text after the fixed semantic template introduces wrappers.
        for slot in spec['slots']:
            current=props('card.'+slot['id'])
            for key in ('grid-column','grid-row'):current[key]='auto'
        # Source spacing comes from the actual inner wrapper, not stretched boxes.
        if item:
            text_nodes=[n for s,n in item['nodes'].items() if s in {'title','body','eyebrow','meta','highlight'}]
            parents=[n for n in nodes if text_nodes and n['selector'].startswith(item['selector']+' > ') and all(t['selector'].startswith(n['selector']+' > ') for t in text_nodes)]
            padded=[n for n in parents if (px(n.get('styles',{}).get('padding-left')) or 0)>0]
            if padded:
                witness=max(padded,key=lambda n:len(n['selector']))
                for axis,side in [('padding-inline','padding-left'),('padding-block','padding-top')]:
                    value=px(witness.get('styles',{}).get(side))
                    if value is not None:inner[axis]=space_token(value,origin(view,witness,side))
        heading_rhythm(construct,item)
        if not any(i['construct']=='listing-card' for i in view['instances']):
            props('listing-card').update(root_props)
            props('listing-card~content').update(inner)
            props('listing-card.media').update(media_props)
            for slot in vocabulary['constructs']['listing-card']['slots']:
                if slot['kind']=='text':props('listing-card.'+slot['id']).update({'text-align':alignment,'display':'block'})
                mapped={'location':'eyebrow','price':'meta','rating':'highlight'}.get(slot['id'],slot['id'])
                for prop in ('margin-block','margin-block-start','margin-block-end'):
                    if prop in props('card.'+mapped):props('listing-card.'+slot['id'])[prop]=props('card.'+mapped)[prop]
    # Fact values form a compact stacked pair, separated from the next pair.
    pair_part=next((s.get('fact-part') for s in vocabulary['constructs']['card']['slots'] if s['id']=='meta'),None)
    if pair_part:
        within=[];between=[]
        for dl in (n for n in nodes if n['tag']=='dl'):
            pairs=[n for n in nodes if n['tag'] in {'dt','dd'} and n.get('box') and n['selector'].startswith(dl['selector']+' > ')]
            for i,n in enumerate(pairs):
                if n['tag']!='dd' or i==0:continue
                previous=next((x for x in reversed(pairs[:i]) if x['tag']=='dt'),None)
                following=next((x for x in pairs[i+1:] if x['tag']=='dt'),None)
                def gap(a,b):
                    x,y,w,h=a['box'];xx,yy,ww,hh=b['box']
                    return max(xx-x-w,x-xx-ww,yy-y-h,y-yy-hh,0)
                if previous:within.append(gap(previous,n))
                if following:between.append(gap(n,following))
        own=median(within) if within else 0
        next_gap=median(between) if between else math.ceil(max(8,own+spacing_base)/spacing_base)*spacing_base
        if next_gap<=own:next_gap=math.ceil((own+spacing_base)/spacing_base)*spacing_base
        props('card.meta').update({'display':'grid','gap':dimension('fact-between',next_gap,'card',
            f'{median(between):g}px' if between else None,'Keep each value closer to its label than to the next pair' if between and median(between)<=own else None,spacing=True)})
        props('card~'+pair_part).update({'display':'grid','grid-template-columns':'1fr','gap':dimension('fact-within',own,'card',spacing=True)})
