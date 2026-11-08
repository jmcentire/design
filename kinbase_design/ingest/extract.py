"""Pure draft derivation from captured data and unchanged source token trees."""
from collections import Counter
from copy import deepcopy
import json
import re
from ..config import INGEST_COLOR_DELTA_E, INGEST_DEFAULT_SPACE, INGEST_TYPE_TOLERANCE_PX, INGEST_SPACE_TOLERANCE_PX
from ..findings import pointer
from ..language.properties import KEYWORDS, SPACE_PROPERTIES
from ..language.tokens import Tokens, normalize
from ..vocabulary import slot_map
from .mapping import map_view
from .provenance import values, source, complete
from .quantize import measurements, hex_color, delta_e, px, scale, spacing_base


def derive(language_id,vocabulary,sources,suggestions=()):
    facts=measurements(sources['views'],sources['colors']);provenance={};notes=[];questions=[]
    for key,entries in sources.get('source_facts',{}).items():
        if not facts[key] and entries:facts[key]=list(dict.fromkeys(entries)) if key=='font_families' else scale(entries)
    facts['spacing_base']=spacing_base(facts['spacing'])
    facts['type_scale_ratios']=[round(b/a,4) for a,b in zip(facts['type_scale'],facts['type_scale'][1:]) if a]
    document={'id':language_id,'name':language_id.replace('-',' ').title(),'vocabulary':vocabulary['version'],
              'style':{},'roles':{},'layout':{'variants':{}},'components':{},'overrides':[],'behaviors':[],'assets':{}}
    for imported in sources['tokens']:
        def merge(target,incoming,path=()):
            for key,value in incoming.items():
                if key not in target:
                    target[key]=deepcopy(value)
                    for suffix,_ in values(value):provenance[pointer('style',*path,key)+suffix]=source(imported['artifact'],'json:'+pointer(*path,key)+suffix)
                elif isinstance(value,dict) and isinstance(target[key],dict) and '$value' not in value:
                    merge(target[key],value,(*path,key))
                elif target[key]!=value:
                    notes.append({'rule':'ingest-source-conflict','message':'Conflicting source token retained in its original artifact', 'artifact':imported['artifact'],'location':pointer(*path,key)})
                    if key=='$value':
                        questions.append({'pointer':pointer('style',*path,key),'construct':'content-section','state':'default',
                                          'values':[deepcopy(target[key]),deepcopy(value)]})
        merge(document['style'],imported['tree'])
    group='ingest'
    while group in document['style']:group+='-derived'
    serial=0
    cache={}
    try:
        imported_tokens=Tokens(document['style'])
        for name in imported_tokens.nodes:
            try:
                kind,normal=imported_tokens.evaluate(name)
                cache.setdefault((kind,json.dumps(normal),False),'{'+name+'}')
                if name.startswith('space.'):cache.setdefault((kind,json.dumps(normal),True),'{'+name+'}')
            except (ValueError,KeyError):pass
    except ValueError:pass
    def token(kind,value,origin=None,spacing=False):
        nonlocal serial
        try:
            normal=normalize(kind,value)
            key=(kind,json.dumps(normal),spacing)
            if key in cache:return cache[key]
        except ValueError:
            notes.append({'rule':'ingest-value','message':f'Unsupported captured {kind}: {value!r}'})
            return None
        serial+=1;root='space' if spacing else group
        if root in document['style'] and '$value' in document['style'][root]:
            notes.append({'rule':'ingest-source-conflict','message':'Source space token conflicts with the required spacing group'})
            return None
        name='v'+str(serial);document['style'].setdefault(root,{})[name]={'$type':kind,'$value':value}
        if origin:
            for suffix,_ in values(value):provenance[pointer('style',root,name,'$value')+suffix]=deepcopy(origin)
        cache[key]='{'+root+'.'+name+'}'
        return cache[key]
    def color_token(raw,origin=None):
        value=hex_color(raw)
        if value is None:return None
        nearby=[g['value'] for g in facts['palette'] if len(g['value'])==len(value) and (len(value)!=9 or value[-2:]==g['value'][-2:]) and delta_e(g['value'],value)<=INGEST_COLOR_DELTA_E]
        chosen=nearby[0] if nearby else value
        if origin and chosen!=value:origin={'kind':'inferred','method':'CIEDE2000 palette quantization','inputs':[origin]}
        return token('color',chosen,origin)
    def space_token(number,where):
        base=facts['spacing_base'];nearest=round(number/base)*base
        if abs(number-nearest)<=INGEST_SPACE_TOLERANCE_PX:
            if nearest!=number:where={'kind':'inferred','method':'Spacing base quantization','inputs':[where]}
            number=nearest
        else:notes.append({'rule':'ingest-spacing','message':f'{number:g}px lies outside the inferred spacing rhythm and is retained exactly'})
        return token('dimension',f'{number:g}px',where,True)
    mappings=[]
    for view in sorted(sources['views'],key=lambda v:v['width']):
        mappings.append({**view,**map_view(view,vocabulary,suggestions)})
    body=next((n for v in mappings for n in v['nodes'] if n['tag']=='body'),None)
    body_style=body.get('styles',{}) if body else {}
    foreground=body_style.get('color') or (facts['palette'][0]['value'] if facts['palette'] else '#222222')
    surface=body_style.get('background-color') or '#ffffff'
    if hex_color(surface) in {None,'#00000000'}:surface='#ffffff'
    base_size=px(body_style.get('font-size')) or (facts['type_scale'][0] if facts['type_scale'] else 16)
    family=body_style.get('font-family') or (facts['font_families'][0] if facts['font_families'] else 'system-ui')
    family=[f.strip().strip('\"\'') for f in family.split(',')]
    base={'color':color_token(foreground),'surface':color_token(surface),'font-family':token('fontFamily',family),
          'font-size':token('dimension',f'{base_size:g}px'),'font-weight':token('fontWeight',400),'line-height':token('number',1.5)}
    base={k:v for k,v in base.items() if v is not None}
    def origin(view,node,prop):return source(view['artifact'],'selector:'+node['selector']+'; '+prop+'; '+view['page']+'@'+str(view['width']))
    def properties(view,node,root=False):
        style=node.get('styles',{});result={}
        for prop,raw in style.items():
            ref=None;where=origin(view,node,prop)
            if prop in KEYWORDS and raw in KEYWORDS[prop]:
                if prop in {'overflow','white-space','text-overflow'} and raw in {'hidden','clip','nowrap','ellipsis'}:
                    notes.append({'rule':'ingest-behavior','message':f'{node["selector"]}: {prop}={raw} needs an intentional behavior review'})
                result[prop]=raw;continue
            if prop in {'color','background-color','border-color','border-top-color'}:
                ref=color_token(raw,where);prop='border-color' if prop=='border-top-color' else prop
            elif prop=='font-family':ref=token('fontFamily',[f.strip().strip('\"\'') for f in raw.split(',')],where)
            elif prop=='font-weight':
                try:ref=token('fontWeight',float(raw),where)
                except ValueError:pass
            elif prop=='line-height' and px(raw) is not None and px(style.get('font-size')):
                ref=token('number',px(raw)/px(style['font-size']),where)
            elif prop in {'font-size','letter-spacing','border-top-width','border-top-left-radius','max-width'} and px(raw) is not None:
                prop={'border-top-width':'border-width','border-top-left-radius':'border-radius'}.get(prop,prop)
                number=px(raw)
                if prop=='font-size':
                    number=next((v for v in facts['type_scale'] if abs(v-number)<=INGEST_TYPE_TOLERANCE_PX),number)
                if number!=px(raw):where={'kind':'inferred','method':'Type scale quantization','inputs':[where]}
                ref=token('dimension',f'{number:g}px',where)
            elif prop in SPACE_PROPERTIES and px(raw) is not None:ref=space_token(px(raw),where)
            if ref:result[prop]=ref
        for prop,sides in [('padding-block',('padding-top','padding-bottom')),('padding-inline',('padding-left','padding-right')),('margin-block',('margin-top','margin-bottom'))]:
            a,b=[px(style.get(side)) for side in sides]
            if a is not None and a==b:result[prop]=space_token(a,origin(view,node,sides[0]))
            elif a!=b and a is not None and b is not None:notes.append({'rule':'ingest-spacing','message':f'{node["selector"]}: asymmetric {prop} cannot be expressed by the closed property set'})
        if style.get('background-image','none')!='none':notes.append({'rule':'ingest-background','message':f'{node["selector"]}: background image/gradient retained in capture for visual review'})
        for prop,ordinary in [('position',{'static','relative'}),('box-shadow',{'none'}),('grid-template-columns',{'none'})]:
            if prop in style and style[prop] not in ordinary:
                notes.append({'rule':'ingest-layout','message':f'{node["selector"]}: {prop}={style[prop]} is outside the closed property set; compare the captured layout'})
        return {k:v for k,v in result.items() if v is not None}
    role_nodes={}
    for view in mappings:
        for item in view['instances']:
            slots=slot_map(vocabulary['constructs'][item['construct']])
            for name,node in item['nodes'].items():role_nodes.setdefault(slots[name]['role'],(view,node))
    for role in vocabulary['roles']:
        treatment=deepcopy(base)
        if role in role_nodes:
            view,node=role_nodes[role]
            treatment.update({k:v for k,v in properties(view,node).items() if k in {'color','font-family','font-size','font-weight','font-style','line-height','letter-spacing'}})
        document['roles'][role]={emphasis:deepcopy(treatment) for emphasis in vocabulary['emphasis']}
    document['components']['page-shell']={'properties':{'background-color':base['surface']}}
    treatments={}
    for view in mappings:
        for item in view['instances']:
            scope=item['construct']
            if item.get('root_node'):treatments.setdefault((scope,view['width']),properties(view,item['root_node'],True))
            for slot,node in item['nodes'].items():treatments.setdefault((scope+'.'+slot,view['width']),properties(view,node))
        if view['unmapped']:notes.append({'rule':'ingest-mapping','message':f'{view["page"]}@{view["width"]}: {len(view["unmapped"])} elements have no matching Vocabulary slot','locations':view['unmapped']})
    for scope in sorted({scope for scope,width in treatments}):
        prior={}
        for (target,width),treatment in sorted(treatments.items(),key=lambda item:item[0][1]):
            if target!=scope:continue
            construct,_,slot=scope.partition('.')
            component=document['components'].setdefault(construct,{})
            if not prior:
                owner=component.setdefault('slots',{}).setdefault(slot,{}) if slot else component
                owner.setdefault('properties',{}).update(treatment)
            elif treatment!=prior:
                bp='w'+str(width)
                document['style'].setdefault('breakpoint',{}).setdefault(bp,{'$type':'dimension','$value':f'{width}px'})
                document['overrides'].append({'scope':scope+'@'+bp,'properties':treatment,'reason':'Measured responsive treatment in immutable capture'})
            prior=treatment
    for width in facts['breakpoints']:
        document['style'].setdefault('breakpoint',{}).setdefault('w'+format(width,'g').replace('.','-'),{'$type':'dimension','$value':f'{width:g}px'})
    def ask(ref,construct,choices):
        if not ref:return
        questions.append({'pointer':pointer('style',*ref[1:-1].split('.'),'$value'),'construct':construct,'state':'default','values':choices})
    if not facts['font_families']:ask(base.get('font-family'),'content-section',[['system-ui'],['Georgia'],['Arial']])
    if not facts['type_scale']:ask(base.get('font-size'),'content-section',['16px','18px','20px'])
    if not facts['palette']:ask(base.get('surface'),'page-shell',['#ffffff','#fbf6ee','#edf4f5'])
    if not any(v>0 for v in facts['spacing']):
        space=token('dimension',f'{INGEST_DEFAULT_SPACE}px',spacing=True)
        document['components'].setdefault('content-section',{}).setdefault('properties',{})['padding']=space
        ask(space,'content-section',['8px','16px','24px'])
    if any(item['construct']=='listing-card' and item.get('root_node',{}).get('styles',{}).get('display')=='flex'
           and item['root_node']['styles'].get('flex-direction')=='row' for view in mappings for item in view['instances']):
        slots=list(slot_map(vocabulary['constructs']['listing-card']))
        template='<article>{{slot:media}}<div data-kd-part="content">'+''.join('{{slot:'+slot+'}}' for slot in slots if slot!='media')+'</div></article>'
        document['layout']['variants']['listing-card']={'captured-side':{'template':template}}
        card=document['components'].setdefault('listing-card',{});card['variant']='captured-side'
        card.setdefault('parts',{})['content']={'display':'flex','flex-direction':'column'}
    for index,q in enumerate(questions,1):
        q['id']='question-'+str(index)
        q['candidates']=[{'id':'candidate-'+str(n),'value':v} for n,v in enumerate(q.pop('values'),1)]
    return {'document':document,'provenance':complete(document,provenance,[a.get('artifact') for a in sources['tokens']]+list(dict.fromkeys(v['artifact'] for v in sources['views']))),
            'facts':facts,'mappings':mappings,'questions':questions,'notes':notes,'mapping':'heuristic'}
