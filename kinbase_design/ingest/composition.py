"""Main-flow evidence and construct-aware composition transfer."""
from collections import Counter
from copy import deepcopy
from statistics import median
import re
from ..findings import location
from ..language.tokens import Tokens
from .quantize import px,hex_color


def main_flow(sources):
    sources={**sources,'views':deepcopy(sources['views'])};notes=[];records=[]
    for view in sources['views']:
        excluded={item['selector']:item['reason'] for item in view.get('excluded',[])}
        positions={item['selector']:item.get('position',item['reason'].removeprefix('Outside document flow: ')) for item in view.get('excluded',[])}
        for node in view.get('structure',view['nodes']):
            position=node.get('styles',{}).get('position')
            if position:positions[node['selector']]=position
            if position in {'fixed','sticky','absolute'}:
                excluded[node['selector']]='Outside document flow: '+position
        def eligible(node):return not any(node['selector']==s or node['selector'].startswith(s+' > ') for s in excluded)
        for selector,position in positions.items():
            if not eligible({'selector':selector}):
                record={'selector':selector,'reason':'out-of-flow','position':position,'evidence':['color','role','treatment']}
                if record not in records:records.append(record)
        view['nodes']=[n for n in view['nodes'] if eligible(n)]
        if 'structure' in view:view['structure']=[n for n in view['structure'] if eligible(n)]
        view['excluded']=[{'selector':s,'reason':reason} for s,reason in excluded.items()]
        for selector,reason in excluded.items():
            notes.append({'rule':'ingest-off-flow','message':reason+'; excluded from color, role and treatment evidence',
                          'artifact':view['artifact'],'page':view['page'],'width':view['width'],'selector':selector})
    sources['excluded']=records
    return sources,notes


def correction(records,question,rule,selector,measured,chosen):
    """Keep the source alternative even when it is not a valid design choice."""
    if measured not in question['values']:question['values'].append(measured)
    records.append({'rule':rule,'pointer':question['pointer'],'selector':selector,
                    'measured':measured,'chosen':chosen})


def corrections_with_questions(document,records,questions):
    result=[]
    for record in records:
        chosen=location(document,record['pointer'])[1]
        if chosen==record['measured']:continue
        question=next(q for q in questions if any(t['pointer']==record['pointer'] for t in q.get('targets',[q]))
                      and any(c['value']==record['measured'] for c in q['candidates']))
        entry={**record,'chosen':chosen,'question':question['id']}
        if entry not in result:result.append(entry)
    return result


def pixels(value):
    if isinstance(value,str) and value.endswith('rem'):return float(value[:-3])*16
    return px(value)


def transfer(document,vocabulary,mappings,treatments,properties,token,space_token,origin,questions,notes,corrections,spacing_base,principal_groups=None):
    group='composition'
    while group in document['style']:group+='-derived'
    document['style'][group]={}
    def dimension(name,value,construct,reason=None,observed=None,rule=None,witnesses=()):
        document['style'][group][name]={'$type':'dimension','$value':f'{value:g}px'}
        if reason:
            choices=list(dict.fromkeys([f'{value:g}px',*[f'{v:g}px' for v in (observed or [])]]))
            questions.append({'pointer':'/style/'+group+'/'+name+'/$value','construct':construct,'state':'default',
                              'values':choices,'reason':reason,'source_values':observed or []})
            for selector,measured in witnesses:
                correction(corrections,questions[-1],rule,selector,measured,f'{value:g}px')
        return '{'+group+'.'+name+'}'
    def main(view):
        nodes=view.get('structure',view['nodes'])
        landmarks=[n for n in nodes if (n['tag']=='main' or n.get('attributes',{}).get('role')=='main') and n.get('box')]
        landmark=max(landmarks,key=lambda n:n['box'][2],default=None)
        if landmark is None:return None
        principal=(principal_groups or {}).get(view['page'])
        items=[i['selector'] for i in view['instances'] if i['construct']=='card']
        def contains(parent,child):return parent==child or child.startswith(parent+' > ')
        candidates=[]
        for node in nodes:
            if node.get('style_inferred_from') or not node.get('box') or node['tag'] not in {'body','main','div','section'}:continue
            if px(node.get('styles',{}).get('max-width')) is None:continue
            selector=node['selector']
            if not (contains(selector,landmark['selector']) or contains(landmark['selector'],selector)):continue
            if any(contains(item,selector) for item in items):continue
            x,_,size,_=node['box']
            if size<min(view['width']*.6,400) or abs(x+size/2-view['width']/2)>2:continue
            candidates.append(node)
        # A full-width main can contain a narrower measured column. Prefer the
        # container enclosing the principal repeated group over a hero's lede.
        return max(candidates,key=lambda n:(bool(principal and contains(n['selector'],principal)),n['box'][2]),default=landmark)
    if 'word-break' in vocabulary.get('composition_rules',[]):
        from .presentation import visible_text
        sizes=[px(n.get('styles',{}).get('font-size')) for v in mappings for n in v.get('structure',v['nodes']) if visible_text(n)]
        floor=min((s for s in sizes if s),default=None)
        if floor:
            for role,emphases in document['roles'].items():
                for emphasis,props in emphases.items():
                    size=pixels(Tokens(document['style']).reference(props['font-size'])[1])
                    if size is not None and size<floor:
                        construct=next(c for c,s in vocabulary['constructs'].items() if any(x['role']==role for x in s['slots']))
                        props['font-size']=dimension('role-floor-'+role+'-'+emphasis,floor,construct,
                            'An inferred role must not fall below the smallest measured source text',[size])
    containers={id(view):main(view) for view in mappings}
    for view in mappings:
        width=view['width'];nodes=view.get('structure',view['nodes']);by={n['selector']:n for n in nodes}
        weight=Counter()
        for n in nodes:
            if n['tag']=='p' and n.get('text','').strip() and (size:=px(n.get('styles',{}).get('font-size'))):weight[size]+=len(n['text'])
        body=max(weight,key=lambda size:(weight[size],size)) if weight else 16
        measured={}
        for n in nodes:
            if re.fullmatch('h[1-6]',n['tag']) and n.get('text','').strip() and (size:=px(n.get('styles',{}).get('font-size'))):
                measured.setdefault(int(n['tag'][1]),[]).append(size)
        floor_level=min(7,max(4,max(measured,default=0)+1))
        anchors={0:max([body*2,*[s for values in measured.values() for s in values]]),floor_level:body,7:body,
                 **{level:min(values) for level,values in measured.items()}}
        scale={};prior=anchors[0]
        for level in range(1,7):
            if level in anchors:value=anchors[level]
            else:
                a=max(n for n in anchors if n<level);b=min(n for n in anchors if n>level)
                value=anchors[a]+(anchors[b]-anchors[a])*(level-a)/(b-a)
            adjusted=max(body,min(value,prior));prior=adjusted
            witnesses=[(n['selector'],f'{px(n["styles"]["font-size"]):g}px') for n in nodes
                       if n['tag']=='h'+str(level) and n.get('text','').strip() and px(n.get('styles',{}).get('font-size')) not in {None,adjusted}]
            if level not in measured:witnesses=[(None,None)]
            reason=('Measured heading size adjusted to preserve heading order and the body-size floor' if adjusted!=value or level in measured and witnesses else
                    'Heading level absent from capture; interpolated between neighbouring levels and the body-size floor' if level not in measured else None)
            scale[level]=dimension(f'h{level}-{width}',adjusted,'hero' if level==1 else 'content-section',reason,measured.get(level,[]),'heading-scale',witnesses)
        for construct,spec in vocabulary['constructs'].items():
            for slot in spec['slots']:
                if not re.fullmatch('h[1-6]',slot['element']):continue
                level=int(slot['element'][1])
                treatments.setdefault((construct+'.'+slot['id'],width),{}).update({'font-size':scale[level]})
                # A content slot can render at a different semantic heading level
                # (for example cards with/without a collection heading). Keep all
                # measured levels in ordinary resolver-backed conditional scopes.
                for actual in range(1,7):
                    scope=construct+'.'+slot['id']+'.h'+str(actual)
                    if width!=min(v['width'] for v in mappings):scope+='@w'+str(width)
                    override=next((o for o in document['overrides'] if o['scope']==scope),None)
                    if override is None:
                        override={'scope':scope,'properties':{},'reason':'Measured or interpolated heading scale for the rendered semantic level'}
                        document['overrides'].append(override)
                    override['properties']['font-size']=scale[actual]
        container=containers[id(view)]
        if container:
            root=treatments.setdefault(('page-shell',width),{})
            following=min((other for other in mappings if other['page']==view['page'] and other['width']>width and containers[id(other)]),key=lambda other:other['width'],default=None)
            cap=max(container['box'][2],containers[id(following)]['box'][2]) if following else container['box'][2]
            margins=max(0,width-container['box'][2])
            inset=token('dimension',f'{margins:g}px',origin(view,container,'main column combined side margins'))
            root['width']='calc(100% - '+inset+')'
            cap_view=following if following and cap==containers[id(following)]['box'][2] else view
            root['max-width']=token('dimension',f'{cap:g}px',origin(cap_view,containers[id(cap_view)],'main column width cap'))
            root['margin-inline']='auto'
            x=container['box'][0];padding=px(container.get('styles',{}).get('padding-left')) or 0
            # Preserve the measurement here; the compliance pass adds a reviewed
            # question whenever a measured gutter needs to grow.
            root['padding-inline']=token('dimension',f'{padding:g}px',origin(view,container,'main column padding'),spacing=True)
            treatments.setdefault(('nav',width),{})['padding-inline']=token('dimension',f'{max(0,x+padding):g}px',origin(view,container,'navigation container inset'),spacing=True)
        prose=[n for n in nodes if n['tag']=='p' and len(n.get('text',''))>=60 and n.get('box') and n['box'][2]>0]
        prose_width=median(n['box'][2] for n in prose) if prose else body*36
        for construct,spec in vocabulary['constructs'].items():
            for slot in spec['slots']:
                if slot['kind']!='text' or slot['element']!='p':continue
                scope=construct+'.'+slot['id'];current=treatments.setdefault((scope,width),{})
                ref=current.get('font-size') or document['roles'][slot['role']][slot['emphasis']]['font-size']
                size=pixels(Tokens(document['style']).reference(ref)[1]) or body
                witnesses=[i['nodes'][slot['id']] for i in view['instances'] if i['construct']==construct and slot['id'] in i['nodes'] and i['nodes'][slot['id']].get('box')]
                if 'word-break' in vocabulary.get('composition_rules',[]):
                    # An inline caption's glyph width is not a prose measure.
                    witnesses=[n for n in witnesses if n['tag']=='p' and len(n.get('text',''))>=60]
                observed=median(n['box'][2] for n in witnesses) if witnesses else prose_width
                value=max(size*vocabulary.get('measure_minimum_em',0),min(observed,size*40))
                current['max-width']=dimension(scope.replace('.','-')+'-measure-'+str(width),value,construct,
                    'Measured prose width exceeds 40em; use the nearest compliant measure' if observed>size*40 else
                    'Use a reusable prose cap of at least 15em; narrower columns still constrain its actual width' if observed<value else None,[observed],
                    'measure',[(n['selector'],f'{n["box"][2]:g}px') for n in (witnesses or prose)
                               if n['box'][2]>size*40 or n['box'][2]<size*vocabulary.get('measure_minimum_em',0)])
        # The leading heading's nearest painted ancestor establishes its band.
        leading=next((n for n in nodes if n['tag']=='h1'),None)
        ancestor=by.get(leading.get('parent')) if leading else None
        while ancestor and ancestor['tag'] not in {'body','main','html'}:
            style=ancestor.get('styles',{});bg=hex_color(style.get('background-color'))
            if bg not in {None,'#00000000'} or (px(style.get('border-top-width')) or 0)>0:
                band={k:v for k,v in properties(view,ancestor,True).items() if k in {'background-color','border-color','border-width','border-style','border-radius','padding','padding-inline','padding-block'}}
                treatments.setdefault(('hero',width),{}).update(band)
                break
            ancestor=by.get(ancestor.get('parent'))
        instances={i['selector']:i for i in view['instances']}
        for item in view['instances']:
            construct=item['construct']
            action_construct=construct
            # A heading-led flow splits an action paragraph into its own prose
            # instance. Its controls still belong to the heading's construct.
            if item.get('flow') and item.get('action_items') and all(slot in item['action_items'] for slot in item['values']):
                parent=instances.get(item.get('parent'))
                if parent:action_construct=parent['construct']

            if 'actions' in vocabulary['constructs'][action_construct].get('parts',{}):
                controls=[by[a['selector']] for actions in item.get('action_items',{}).values() for a in actions if a['selector'] in by]
                if len(controls)>1:
                    parent=by.get(controls[0].get('parent'))
                    while parent and not all(n['selector'].startswith(parent['selector']+' > ') for n in controls):parent=by.get(parent.get('parent'))
                    if parent:
                        props={k:v for k,v in properties(view,parent).items() if k in {'padding','padding-inline','padding-block','gap','column-gap','row-gap'}}
                        gaps=[]
                        for a,b in zip(controls,controls[1:]):
                            if not a.get('box') or not b.get('box'):continue
                            ax,ay,aw,ah=a['box'];bx,by_pos,bw,bh=b['box']
                            gaps.append(max(bx-ax-aw,ax-bx-bw,by_pos-ay-ah,ay-by_pos-bh,0))
                        if gaps and not any(p in props for p in ('gap','column-gap','row-gap')):
                            props['gap']=space_token(median(gaps),origin(view,parent,'action-group separation'))
                        treatments.setdefault((action_construct+'~actions',width),{}).update(props)
            if item['construct']!='card':continue
            text=[n for slot,n in item['nodes'].items() if slot in {'title','body','eyebrow','meta','highlight'}]
            ancestors=[n for n in nodes if n['selector'].startswith(item['selector']+' > ') and text and all(t['selector'].startswith(n['selector']+' > ') for t in text)]
            padded=[n for n in ancestors if any((px(n.get('styles',{}).get(p)) or 0)>0 for p in ['padding-left','padding-right','padding-top','padding-bottom'])]
            if padded:
                witness=max(padded,key=lambda n:len(n['selector']))
                inner={k:v for k,v in properties(view,witness).items() if k in {'padding','padding-inline','padding-block','gap','row-gap','column-gap'}}
                treatments.setdefault(('card~content',width),{}).update(inner)
            gaps=[]
            boxes=sorted([n['box'] for n in text if n.get('box')],key=lambda b:b[1])
            for a,b in zip(boxes,boxes[1:]):
                gap=b[1]-a[1]-a[3]
                if gap>0:gaps.append(gap)
            inner=treatments.setdefault(('card~content',width),{})
            inner.update({'display':'flex','flex-direction':'column'})
            if gaps:inner['gap']=space_token(median(gaps),origin(view,text[0],'card text gap'))
        if 'word-break' in vocabulary.get('composition_rules',[]):
            selection=(None,[])
            if 'gutter' in vocabulary.get('composition_rules',[]):
                from .item_transfer import select
                selection=select(view,(principal_groups or {}).get(view['page']))
            from .composition_flow import transfer as transfer_flow
            transfer_flow(document,vocabulary,view,treatments,token,space_token,origin,questions,spacing_base,corrections,
                          primary_item=selection[1][0] if selection[1] else None)
            if 'gutter' in vocabulary.get('composition_rules',[]):
                from .item_transfer import transfer as transfer_items
                transfer_items(document,vocabulary,view,treatments,properties,token,space_token,origin,questions,corrections,selection)
