"""Pure draft derivation from captured data and unchanged source token trees."""
from collections import Counter
from copy import deepcopy
from decimal import Decimal
import json
import math
import re
from ..config import INGEST_DEFAULT_SPACE, INGEST_FULL_RADIUS_PX, IngestConfig, CHECK_TEXT_CONTRAST, CHECK_TARGET_SIZE
from ..checks.math import effective_background, color, contrast
from ..language.resolver import resolve
from .presentation import literal_node
from ..findings import pointer
from ..language.properties import KEYWORDS, SPACE_PROPERTIES, CONTROL_TEXT_PROPERTIES, property_value
from ..language.tokens import Tokens, normalize
from ..vocabulary import slot_map
from .mapping import map_view, semantic_role
from .provenance import values, source, complete
from .quantize import measurements, hex_color, delta_e, px, scale, spacing_base, full_radius
from .question_quality import role_sizes, size_choices, deduplicate


def derive(language_id,vocabulary,sources,suggestions=(),settings=None):
    settings=settings or IngestConfig()
    facts=measurements(sources['views'],sources['colors'],settings);provenance={};notes=[];questions=[]
    for key,entries in sources.get('source_facts',{}).items():
        tolerance=settings.radius_px if key=='radii' else settings.spacing_px if key=='spacing' else settings.type_size_px
        if not facts[key] and entries:facts[key]=list(dict.fromkeys(entries)) if key=='font_families' else scale(entries,tolerance)
    facts['spacing']=[v for v in facts['spacing'] if v>=0]
    if not sources['views']:facts['spacing_base']=spacing_base(facts['spacing'],settings.spacing_px)
    facts['type_scale_ratios']=[round(b/a,4) for a,b in zip(facts['type_scale'],facts['type_scale'][1:]) if a]
    document={'id':language_id,'name':language_id.replace('-',' ').title(),'vocabulary':vocabulary['version'],
              'style':{},'roles':{},'layout':{'variants':{}},'components':{},'overrides':[],'behaviors':[],'assets':{}}
    for imported in sources['tokens']:
        def merge(target,incoming,path=()):
            for key,value in incoming.items():
                if key not in target:
                    target[key]=deepcopy(value)
                    for suffix,_ in values(value):provenance[pointer('style',*path,key)+suffix]=source(imported['artifact'],
                        ('member:'+imported['location']+'#' if imported.get('location') else 'json:')+pointer(*path,key)+suffix)
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
        nearby=[g['value'] for g in facts['palette'] if len(g['value'])==len(value) and (len(value)!=9 or value[-2:]==g['value'][-2:]) and delta_e(g['value'],value)<=settings.color_delta_e]
        chosen=nearby[0] if nearby else value
        if origin and chosen!=value:origin={'kind':'inferred','method':'CIEDE2000 palette quantization','inputs':[origin]}
        return token('color',chosen,origin)
    def space_token(number,where):
        if number<0:
            notes.append({'rule':'ingest-spacing','message':f'Negative offset {number:g}px retained in the capture; it is not a spacing step'})
            return None
        base=facts['spacing_base'];nearest=round(number/base)*base
        if abs(number-nearest)<=settings.spacing_px:
            if nearest!=number:where={'kind':'inferred','method':'Spacing base quantization','inputs':[where]}
            number=nearest
        else:notes.append({'rule':'ingest-spacing','message':f'{number:g}px lies outside the inferred spacing rhythm and is retained exactly'})
        return token('dimension',f'{number:g}px',where,True)
    mappings=[]
    # Preserve each sampled palette cluster even when its element has no slot
    # mapping; the reusable palette must cover the source's accent colors too.
    for entry in facts['palette']:color_token(entry['value'])
    for size in facts['type_scale']:token('dimension',f'{size:g}px')
    for view in sorted(sources['views'],key=lambda v:v['width']):
        mappings.append({**view,**map_view(view,vocabulary,suggestions)})
    body=next((n for v in mappings for n in v['nodes'] if n['tag']=='body'),None)
    body_style={**body.get('styles',{}),**body.get('normalized_colors',{})} if body else {}
    foreground=body_style.get('color') or (facts['palette'][0]['value'] if facts['palette'] else '#222222')
    surface=body_style.get('background-color') or '#ffffff'
    if hex_color(surface) in {None,'#00000000'}:surface='#ffffff'
    base_size=px(body_style.get('font-size')) or (facts['type_scale'][0] if facts['type_scale'] else 16)
    facts['type_base_px']=base_size
    family=body_style.get('font-family') or (facts['font_families'][0] if facts['font_families'] else 'system-ui')
    family=[f.strip().strip('\"\'') for f in family.split(',')]
    base={'color':color_token(foreground) or color_token('#222222'),'surface':color_token(surface) or color_token('#ffffff'),'font-family':token('fontFamily',family),
          'font-size':token('dimension',f'{base_size:g}px'),'font-weight':token('fontWeight',400),'line-height':token('number',1.5)}
    base={k:v for k,v in base.items() if v is not None}
    base_tokens=Tokens(document['style']);base_bg=color(base_tokens.reference(base['surface'])[1])
    base_fg=base_tokens.reference(base['color'])[1]
    if contrast(color(base_fg),base_bg)<CHECK_TEXT_CONTRAST:
        chosen=max(('#000000','#ffffff'),key=lambda value:contrast(color(value),base_bg))
        document['style'].setdefault(group,{})['page-foreground']={'$type':'color','$value':chosen}
        base['color']='{'+group+'.page-foreground}'
        questions.append({'pointer':pointer('style',group,'page-foreground','$value'),'construct':'page-shell','state':'default',
                          'values':[chosen,base_fg],'reason':'The captured page pair is unreadable or its surface is unresolved; a legible foreground is inferred'})
    def origin(view,node,prop):
        evidence=source(view['artifact'],'selector:'+node.get('style_inferred_from',node['selector'])+'; '+prop+'; '+view['page']+'@'+str(view['width']))
        return {'kind':'inferred','method':'Style from matching repeated DOM structure or inherited text','inputs':[evidence]} if node.get('style_inferred_from') else evidence
    def properties(view,node,root=False):
        style={**node.get('styles',{}),**node.get('normalized_colors',{})};result={}
        for prop,raw in style.items():
            ref=None;where=origin(view,node,prop)
            if prop in KEYWORDS and raw in KEYWORDS[prop]:
                if prop in {'overflow','white-space','text-overflow'} and raw in {'hidden','clip','nowrap','ellipsis'}:
                    notes.append({'rule':'ingest-behavior','message':f'{node["selector"]}: {prop}={raw} needs an intentional behavior review'})
                result[prop]=raw;continue
            if prop=='grid-template-columns' and raw!='none':
                tracks = raw.split()
                if 1<=len(tracks)<=12 and all(px(t) is not None and px(t)>0 for t in tracks):
                    smallest = min(px(t) for t in tracks)
                    ratios=[px(t)/smallest for t in tracks]
                    if all(abs(r-round(r))<.03 and 1<=round(r)<=12 for r in ratios):
                        result[prop] = ' '.join(f'{round(r)}fr' for r in ratios)
                        continue
                notes.append({'rule':'ingest-layout','message':f'{node["selector"]}: {prop} cannot be represented as bounded proportional tracks'})
            elif prop=='aspect-ratio':
                if raw=='auto':result[prop]='auto'
                elif (match:=re.fullmatch(r'([\d.]+)\s*/\s*([\d.]+)',raw)):
                    try:
                        ratio = float(match[1])/float(match[2])
                        if all(float(x).is_integer() and 1<=float(x)<=32 for x in match.groups()):result[prop]=f'{int(float(match[1]))} / {int(float(match[2]))}'
                    except (ValueError,ZeroDivisionError):pass
            elif prop=='box-shadow' and raw!='none':
                color_match=re.search(r'rgba?\([^)]*\)|#[0-9a-fA-F]{6,8}',raw)
                lengths=re.findall(r'-?[\d.]+px',raw)
                if color_match and len(lengths)==4 and not re.search(r'\binset\b',raw) and ',' not in raw[:color_match.start()]+raw[color_match.end():]:
                    color=hex_color(color_match[0])
                    if color:result[prop]=token('shadow',dict(zip(('offsetX','offsetY','blur','spread'),lengths))|{'color':color},where)
                else:notes.append({'rule':'ingest-shadow','message':f'{node["selector"]}: multiple/inset or unsupported shadow retained for review'})
            if prop in {'color','background-color','border-color','border-top-color'}:
                ref=color_token(raw,where);prop='border-color' if prop=='border-top-color' else prop
            elif prop=='font-family':ref=token('fontFamily',[f.strip().strip('\"\'') for f in raw.split(',')],where)
            elif prop=='font-weight':
                try:
                    weight=float(raw)
                    ref=token('fontWeight',int(weight) if weight.is_integer() else weight,where)
                except ValueError:pass
            elif prop=='line-height' and px(raw) is not None and px(style.get('font-size')):
                ref=token('number',px(raw)/px(style['font-size']),where)
            elif (prop in {'font-size','letter-spacing','border-top-width','border-top-left-radius','max-width'}
                  or prop=='width' and node['tag'] in {'img','svg'}) and px(raw) is not None:
                prop={'border-top-width':'border-width','border-top-left-radius':'border-radius'}.get(prop,prop)
                number=px(raw)
                if prop=='border-radius' and full_radius(number,node.get('box') or ()):
                    document['style'].setdefault(group,{})['full-radius']={'$type':'dimension','$value':f'{INGEST_FULL_RADIUS_PX}px'}
                    result[prop]='{'+group+'.full-radius}'
                    provenance[pointer('style',group,'full-radius')]={'kind':'inferred','method':'Full/pill radius normalized from computed radius and element box','inputs':[where]}
                    continue
                if prop=='font-size':
                    number=next((v for v in facts['type_scale'] if abs(v-number)<=settings.type_size_px),number)
                if number!=px(raw):where={'kind':'inferred','method':'Type scale quantization','inputs':[where]}
                ref=token('dimension',f'{number:g}px',where)
            elif prop in SPACE_PROPERTIES and px(raw) is not None:ref=space_token(px(raw),where)
            if ref:result[prop]=ref
        for prop,sides in [('padding-block',('padding-top','padding-bottom')),('padding-inline',('padding-left','padding-right')),('margin-block',('margin-top','margin-bottom'))]:
            a,b=[px(style.get(side)) for side in sides]
            if a is not None and a==b:result[prop]=space_token(a,origin(view,node,sides[0]))
            elif a!=b and a is not None and b is not None:notes.append({'rule':'ingest-spacing','message':f'{node["selector"]}: asymmetric {prop} cannot be expressed by the closed property set'})
        if style.get('background-image','none')!='none':notes.append({'rule':'ingest-background','message':f'{node["selector"]}: background image/gradient retained in capture for visual review'})
        for prop,ordinary in [('position',{'static','relative'})]:
            if prop in style and style[prop] not in ordinary:
                notes.append({'rule':'ingest-layout','message':f'{node["selector"]}: {prop}={style[prop]} is outside the closed property set; compare the captured layout'})
        if root and hex_color(style.get('background-color')) in {None,'#00000000'}:
            painted=effective_background(node.get('backgrounds',[]))
            if painted:
                result['background-color']=color_token('#'+''.join(f'{round(c*255):02x}' for c in painted[:3]),origin(view,node,'backgrounds'))
        return {k:v for k,v in result.items() if v is not None}
    def paint_pair(view,node,props):
        painted=effective_background(node.get('backgrounds',[])) if node.get('backgrounds') else None
        raw=hex_color(node.get('normalized_colors',{}).get('color',node.get('styles',{}).get('color','')))
        if painted and raw:
            bg='#'+''.join(f'{round(c*255):02x}' for c in painted[:3])
            props['background-color']=token('color',bg,origin(view,node,'effective background'))
            props['color']=token('color',raw,origin(view,node,'color'))
        return props

    def media_treatment(node):
        box=node.get('box');result={}
        if box and box[2]>0 and box[3]>0:
            ratio=box[2]/box[3]
            w,h=min(((w,h) for w in range(1,33) for h in range(1,33)),key=lambda pair:(abs(pair[0]/pair[1]-ratio),sum(pair)))
            result['aspect-ratio']=f'{w} / {h}'
        else:
            result['aspect-ratio']='3 / 2'
            notes.append({'rule':'ingest-media','message':node['selector']+': media box unmeasured; neutral 3:2 proportion inferred'})
        fit=node.get('styles',{}).get('object-fit')
        result['object-fit']=fit if fit in {'cover','contain','scale-down'} else 'cover'
        return result

    role_nodes={};role_surfaces={};sizes_by_role=role_sizes(sources['views'])
    # A paragraph can stand in for a title in a captured card's reconstruction,
    # but reusable title roles should use the source's actual heading scale.
    for view in mappings:
        for node in view['nodes']:
            role=semantic_role(node)
            if role in {'title','subtitle'} and not literal_node(node) and node.get('text','').strip():
                role_nodes.setdefault(role,(view,node))
    for view in mappings:
        for item in view['instances']:
            slots=slot_map(vocabulary['constructs'][item['construct']])
            for name,node in item['nodes'].items():
                if literal_node(node):continue
                role=slots[name]['role']
                if role not in {'title','subtitle'} or semantic_role(node) in {'title','subtitle'}:
                    role_nodes.setdefault(role,(view,node))
                layers=list(node.get('backgrounds',[]))
                if not layers:
                    by_selector={n['selector']:n for n in view['nodes']};parent=node
                    while parent:
                        style=parent.get('styles',{})
                        layers.append({'color':style.get('background-color','transparent'),'image':style.get('background-image','none')})
                        parent=by_selector.get(parent.get('parent'))
                layers=[{**layer,'color':hex_color(layer.get('color')) or layer.get('color')} for layer in layers]
                # A transparent ancestry only tells us the browser canvas default;
                # it does not establish the author's intended role pairing.
                opaque=any((c:=hex_color(layer.get('color'))) and len(c)==7 for layer in layers)
                rgba=effective_background(layers) if opaque else None
                if rgba:
                    value='#'+''.join(f'{round(c*255):02x}' for c in rgba[:3])
                    role_surfaces.setdefault(role,{}).setdefault(value,origin(view,node,'effective background'))
    for role in vocabulary['roles']:
        treatment=deepcopy(base)
        if role in role_nodes:
            view,node=role_nodes[role]
            treatment.update({k:v for k,v in properties(view,node).items() if k in {'color','font-family','font-size','font-weight','font-style','line-height','letter-spacing'}})
        treatment['color']=base['color']
        document['roles'][role]={emphasis:deepcopy(treatment) for emphasis in vocabulary['emphasis']}
        construct=next(c for c,spec in vocabulary['constructs'].items() if any(s['role']==role for s in spec['slots']))
        observed_sizes=sizes_by_role.get(role,[])
        if (role not in role_nodes or len(set(observed_sizes))>1) and role!='media' and sources['views']:
            name='size-'+role
            default_size,choices=size_choices(observed_sizes,base_size)
            document['style'].setdefault(group,{})[name]={'$type':'dimension','$value':f'{default_size:g}px'}
            for emphasis in vocabulary['emphasis']:document['roles'][role][emphasis]['font-size']='{'+group+'.'+name+'}'
            questions.append({'pointer':pointer('style',group,name,'$value'),'construct':construct,'state':'default',
                              'values':[f'{size:g}px' for size in choices],
                              'role':role,'property':'font-size','source_values':sorted(set(observed_sizes)),
                              'reason':'Choose among captured role sizes' if observed_sizes else 'No captured text establishes this role’s type size'})
        observed=role_surfaces.get(role,{})
        reusable_fg=color(Tokens(document['style']).reference(base['color'])[1])
        compatible=[value for value in observed if contrast(reusable_fg,color(value))>=CHECK_TEXT_CONTRAST]
        if len(observed)==1 and compatible:
            value,where=next(iter(observed.items()))
            for emphasis in vocabulary['emphasis']:
                document['roles'][role][emphasis]['surface']=token('color',value,where)
        else:
            # Keep a separate inferred value so answering cannot rewrite a source token.
            name='surface-'+role
            default=next(iter(compatible),Tokens(document['style']).reference(base['surface'])[1])
            document['style'].setdefault(group,{})[name]={'$type':'color','$value':default}
            for emphasis in vocabulary['emphasis']:document['roles'][role][emphasis]['surface']='{'+group+'.'+name+'}'
            choices=list(dict.fromkeys([default,*observed,*[p['value'] for p in facts['palette'] if len(p['value'])==7],'#ffffff','#fbf6ee']))[:4]
            questions.append({'pointer':pointer('style',group,name,'$value'),'construct':construct,'state':'default','values':choices,
                              'role':role,'property':'surface','reason':'Captured surfaces vary or need a different foreground; retain the legible reusable page pair while component paint stays paired' if observed else 'No captured surface establishes this role pairing'})
    document['components']['page-shell']={'properties':{'background-color':base['surface']}}
    treatments={}
    # Select a representative repeated collection from the widest capture of
    # each page. Keep that group's identity at phone widths, where every group
    # may have one column. Small sidebar groups must not win by traversal order.
    principal_groups={}
    for view in sorted(mappings,key=lambda v:v['width'],reverse=True):
        if view['page'] in principal_groups:continue
        cards={i['selector'] for i in view['instances'] if i['construct']=='card'}
        candidates=[g for g in view.get('groups',[]) if g['members'] and set(g['members'])<=cards]
        if candidates:
            principal_groups[view['page']]=max(candidates,key=lambda g:((g.get('box') or [0,0,0,0])[2],len(g['members'])))['selector']
    for view in mappings:
        # Main/body and complete nested containers own portable page geometry.
        containers=[n for n in view['nodes'] if n['tag'] in {'body','main','div','section'} and px(n.get('styles',{}).get('max-width')) is not None and n.get('box') and n['box'][2]>=min(view['width']*.6,400)]
        if containers:
            container=max(containers,key=lambda n:(n['tag'] in {'body','main'},px(n['styles']['max-width'])))
            measured=properties(view,container,True)
            portable={k:v for k,v in measured.items() if k in {'max-width','padding','padding-inline','padding-block'}}
            x,_,w,_=container['box']
            if abs(x+w/2-view['width']/2)<=2:portable['margin-inline']='auto'
            if view['width']<=768 and x>0 and abs(x+w/2-view['width']/2)<=2 and px(container['styles'].get('padding-left','0px'))==0:
                portable['padding-inline']=space_token(x,origin(view,container,'box'))
            treatments[('page-shell',view['width'])]=portable
            inset=max(0,x)+(px(container['styles'].get('padding-left')) or 0)
            treatments[('nav',view['width'])]={'padding-inline':space_token(inset,origin(view,container,'header container inset'))}
        if 'collection' in vocabulary['constructs']:
            cards = {item['selector'] for item in view['instances'] if item['construct']=='card'}
            groups=[g for g in view.get('groups',[]) if g['members'] and set(g['members'])<=cards]
            groups.sort(key=lambda g:(g['selector']==principal_groups.get(view['page']),(g.get('box') or [0,0,0,0])[2],len(g['members'])),reverse=True)
            for group_measure in groups:
                layout = group_measure['layout']
                evidence = source(view['artifact'],'selector:'+group_measure['selector']+'; group layout; '+view['page']+'@'+str(view['width']))
                if layout['columns']>12:continue
                treatment = {'display':'grid','grid-template-columns':f'repeat({layout["columns"]}, 1fr)'}
                for prop in ('row-gap','column-gap'):
                    if prop in layout:treatment[prop]=space_token(layout[prop],evidence)
                treatments.setdefault(('collection.items',view['width']),treatment)
                break
        for item in view['instances']:
            scope=item['construct']
            item['treatment']={'properties':properties(view,item['root_node'],True) if item.get('root_node') else {},'slots':{}}
            if scope=='nav':
                surfaces={effective_background(n.get('backgrounds',[])) for n in item['nodes'].values()}
                surfaces.discard(None)
                if len(surfaces)==1:
                    painted=next(iter(surfaces));witness=next(iter(item['nodes'].values()))
                    item['treatment']['properties']['background-color']=color_token('#'+''.join(f'{round(c*255):02x}' for c in painted[:3]),origin(view,witness,'backgrounds'))
            if scope=='card':
                owned=[n for n in view.get('structure',view['nodes']) if n['selector'].startswith(item['selector']+' > ')]
                anchors=[n['selector'] for n in item['nodes'].values() if n['tag'] not in {'a','button'}]
                surfaces=[n for n in owned if n['tag'] in {'div','article'} and anchors and all(s==n['selector'] or s.startswith(n['selector']+' > ') for s in anchors)
                          and (px(n.get('styles',{}).get('border-top-width')) or n.get('styles',{}).get('box-shadow','none')!='none')]
                if surfaces:
                    card_surface=min(surfaces,key=lambda n:len(n['selector']))
                    measured=properties(view,card_surface,True)
                    item['treatment']['properties'].update({k:v for k,v in measured.items() if k in {'background-color','border-color','border-width','border-style','border-radius','box-shadow','display','flex-direction','gap','padding','padding-inline','padding-block'}})
            if item.get('root_node'):
                existing=treatments.setdefault((scope,view['width']),{})
                for key,val in item['treatment']['properties'].items():existing.setdefault(key,val)
            for slot,node in item['nodes'].items():
                props=properties(view,node)
                # A media slot wraps an image; its captured fixed pixel width is
                # not a portable text-column width in the reconstruction.
                definition=slot_map(vocabulary['constructs'][scope])[slot]
                if definition['kind']=='media' and definition.get('asset_kind')!='logo':
                    props.pop('width',None);props.update(media_treatment(node))
                    box=node.get('box');container=item.get('box')
                    if box and box[2]>0 and (scope=='card' or container and box[2]<container[2]*.6):
                        # A captured card image is a measured bound even when
                        # its wrapper was unsampled or narrower than the page.
                        props['max-width']=token('dimension',f'{box[2]:g}px',origin(view,node,'measured media width'))
                elif definition['kind']!='media':paint_pair(view,node,props)
                if slot=='links':props={k:v for k,v in props.items() if k in CONTROL_TEXT_PROPERTIES}
                item['treatment']['slots'][slot]={'properties':props}
                if not literal_node(node):
                    portable=deepcopy(props)
                    if definition['role'] in {'title','subtitle'} and semantic_role(node) not in {'title','subtitle'}:
                        # Keep measured paragraph styling in fidelity, not in the
                        # reusable heading slot. Its declared role owns hierarchy.
                        for key in ('font-size','font-weight','line-height'):portable.pop(key,None)
                        notes.append({'rule':'ingest-type-hierarchy','message':node['selector']+': non-heading copy reconstructed as captured; reusable '+scope+'.'+slot+' inherits the heading role scale'})
                    treatments.setdefault((scope+'.'+slot,view['width']),portable)
                if scope=='hero' and slot=='title' and not literal_node(node) and 'background-color' in props:
                    treatments[(scope,view['width'])]['background-color']=treatments[(scope+'.'+slot,view['width'])]['background-color']
            if scope in {'nav','footer'} and 'link' in vocabulary['constructs'][scope].get('parts',{}):
                links=[n for n in view.get('structure',view['nodes']) if n['tag']=='a' and n['selector'].startswith(item['selector']+' > ')]
                if links:
                    native=paint_pair(view,links[0],properties(view,links[0]));portable={k:v for k,v in native.items() if k in CONTROL_TEXT_PROPERTIES|{'background-color','border-color','border-style','border-width','border-radius','padding','padding-inline','padding-block'}}
                    treatments.setdefault((scope+'~link',view['width']),portable)
            for fragments in item.get('fragments',{}).values():
                for fragment in fragments:
                    node=fragment.pop('node')
                    fragment['properties']={k:v for k,v in properties(view,node).items() if k in CONTROL_TEXT_PROPERTIES}

        if view['unmapped']:notes.append({'rule':'ingest-mapping','message':f'{view["page"]}@{view["width"]}: {len(view["unmapped"])} elements have no matching Vocabulary slot','locations':view['unmapped']})
    for scope in sorted({scope for scope,width in treatments}):
        prior={}
        for (target,width),treatment in sorted(treatments.items(),key=lambda item:item[0][1]):
            if target!=scope:continue
            construct,_,slot=scope.partition('.')
            construct,_,part=construct.partition('~')
            component=document['components'].setdefault(construct,{})
            if not prior:
                if part:component.setdefault('parts',{}).setdefault(part,{}).update(treatment)
                else:
                    owner=component.setdefault('slots',{}).setdefault(slot,{}) if slot else component
                    owner.setdefault('properties',{}).update(treatment)
            elif treatment!=prior:
                bp='w'+str(width)
                document['style'].setdefault('breakpoint',{}).setdefault(bp,{'$type':'dimension','$value':f'{width}px'})
                document['overrides'].append({'scope':scope+'@'+bp,'properties':treatment,'reason':'Measured responsive treatment in immutable capture'})
            prior=treatment
    # Reuse observed visual archetypes for otherwise unobserved vocabulary
    # constructs, with inferred provenance rather than pretending they were seen.
    measured_card=document['components'].get('card',{}).get('properties')
    if measured_card:
        for name,spec in vocabulary['constructs'].items():
            if spec['root']=='article' and name not in document['components']:
                document['components'][name]={'properties':deepcopy(measured_card)}
    action_candidates=[]
    for view in mappings:
        for node in view['nodes']:
            if node['tag'] not in {'a','button'}:continue
            bg=hex_color(node.get('normalized_colors',{}).get('background-color',node.get('styles',{}).get('background-color','')))
            if bg and len(bg)==7 and node.get('text','').strip():
                channels=[int(bg[i:i+2],16) for i in (1,3,5)]
                action_candidates.append((max(channels)-min(channels),view,node))
    if action_candidates:
        _,view,node=max(action_candidates,key=lambda item:item[0])
        treatment={k:v for k,v in properties(view,node).items() if k in CONTROL_TEXT_PROPERTIES|{'background-color','border-color','border-width','border-style','border-radius','padding','padding-inline','padding-block'}}
        for name,spec in vocabulary['constructs'].items():
            for slot in spec['slots']:
                if slot['kind']=='action' and slot['element'] in {'a','button'} and not any((name+'.'+slot['id'],v['width']) in treatments for v in mappings):
                    document['components'].setdefault(name,{}).setdefault('slots',{}).setdefault(slot['id'],{})['properties']=deepcopy(treatment)
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
    if sources['views']:
        seen={item['construct'] for view in mappings for item in view['instances']}
        for construct,spec in vocabulary['constructs'].items():
            if construct not in seen and construct!='page-shell':
                name='space-'+construct
                spacing_value=format(Decimal(str(facts['spacing_base'])).normalize(),'f')+'px'
                document['style'].setdefault('space',{})[name]={'$type':'dimension','$value':spacing_value}
                document['components'].setdefault(construct,{}).setdefault('properties',{})['padding']='{space.'+name+'}'
                questions.append({'pointer':pointer('style','space',name,'$value'),'construct':construct,'state':'default',
                                  'values':list(dict.fromkeys([spacing_value,'8px','16px','24px']))[:4],
                                  'reason':'Construct not established by the capture; choose its inferred spacing'})
        for state in vocabulary['states']:
            if state=='default':continue
            scopes=[c for c,spec in vocabulary['constructs'].items() if state in spec['states']]
            if not scopes:continue
            for c in scopes:
                name='surface-'+c+'-'+state
                default_ref=document['components'].get(c,{}).get('properties',{}).get('background-color',base['surface'])
                default=Tokens(document['style']).reference(default_ref)[1]
                document['style'].setdefault(group,{})[name]={'$type':'color','$value':default}
                document['components'].setdefault(c,{}).setdefault('states',{})[state]={'background-color':'{'+group+'.'+name+'}'}
                questions.append({'pointer':pointer('style',group,name,'$value'),'construct':c,'state':state,
                                  'values':list(dict.fromkeys([default,'#edf4f5','#fbf6ee'])),'scopes':[c],
                                  'reason':'Interaction/state appearance not observed; retain this construct’s measured surface until reviewed'})
    for construct,spec in vocabulary['constructs'].items():
        if spec['root']!='article' or 'media' not in slot_map(spec):continue
        if any(item['construct']==construct and item.get('root_node',{}).get('styles',{}).get('display')=='flex'
               and item['root_node']['styles'].get('flex-direction')=='row' for view in mappings for item in view['instances']):
            slots=list(slot_map(spec))
            template='<article>{{slot:media}}<div data-kd-part="content">'+''.join('{{slot:'+slot+'}}' for slot in slots if slot!='media')+'</div></article>'
            document['layout']['variants'][construct]={'captured-side':{'template':template}}
            card=document['components'].setdefault(construct,{});card['variant']='captured-side'
            card.setdefault('parts',{})['content']={'display':'flex','flex-direction':'column'}
    # Reusable constructs need readable defaults even for slots absent from the
    # source page. Work at each declared width so responsive paints stay paired.
    breakpoint_tokens=Tokens(document['style'])
    breakpoints=[None]+[name for _,name in sorted((breakpoint_tokens.breakpoint(name.removeprefix('breakpoint.')),name.removeprefix('breakpoint.')) for name in breakpoint_tokens.nodes if name.startswith('breakpoint.'))]
    def effective(scope,bp):return {k:v['value'] for k,v in resolve(document,vocabulary,scope,breakpoint=bp)['properties'].items()}
    def put_treatment(scope,bp,props,method):
        current=effective(scope,bp);tokens=Tokens(document['style'])
        props={key:value for key,value in props.items() if property_value(document,tokens,key,value)!=current.get(key)}
        if not props:return
        if bp:
            target=scope+'@'+bp
            entry=next((o for o in document['overrides'] if o['scope']==target),None)
            if entry is None:
                entry={'scope':target,'properties':{},'reason':method};document['overrides'].append(entry)
            if method not in entry['reason']:entry['reason']+='; '+method
            entry['properties'].update(props)
        else:
            construct,_,slot=scope.partition('.')
            construct,_,part=construct.partition('~')
            component=document['components'].setdefault(construct,{})
            if part:component.setdefault('parts',{}).setdefault(part,{}).update(props)
            elif slot:component.setdefault('slots',{}).setdefault(slot,{}).setdefault('properties',{}).update(props)
            else:component.setdefault('properties',{}).update(props)
    def readable(scope,bp,props,bg):
        fg=color(props.get('color',''))
        if fg and bg and contrast(fg,bg)>=CHECK_TEXT_CONTRAST:return {}
        if not bg:bg=color('#ffffff')
        chosen=max(('#222222','#ffffff','#000000'),key=lambda candidate:contrast(color(candidate),bg))
        name='legible-'+scope.replace('.','-').replace('~','-')+'-'+(bp or 'base')
        document['style'].setdefault(group,{})[name]={'$type':'color','$value':chosen}
        choices=list(dict.fromkeys([chosen,props.get('color',chosen),'#000000','#ffffff']))
        questions.append({'pointer':pointer('style',group,name,'$value'),'construct':scope.split('.')[0].split('~')[0],
                          'state':'default','values':choices,'reason':'Captured foreground/surface pair is missing or fails contrast here; a legible inferred foreground is used'})
        return {'color':'{'+group+'.'+name+'}'}
    def focus_color(background):
        chosen=max(('#000000','#ffffff'),key=lambda candidate:contrast(color(candidate),background))
        return token('color',chosen)
    def target_dimensions(props):
        def padding(axis,minimum):
            measured=px(props.get(axis)) or px(props.get('padding')) or 0
            # Accessibility additions are inferred spacing, not new source
            # measurements. Round additions up to the captured scale so a 24px
            # target does not introduce 12px/4px steps into an 8px language.
            step=facts['spacing_base']
            value=measured if measured>=minimum else math.ceil(minimum/step)*step
            return token('dimension',f'{value:g}px',spacing=True)
        result={'display':'inline-block',
                'padding-inline':padding('padding-inline',CHECK_TARGET_SIZE/2),
                'padding-block':padding('padding-block',4)}
        line=props.get('line-height');line_px=line*(px(props.get('font-size')) or base_size) if isinstance(line,(int,float)) else px(line)
        if (line_px or 0)<CHECK_TARGET_SIZE:result['line-height']=token('dimension',f'{CHECK_TARGET_SIZE:g}px')
        return result
    for bp in breakpoints:
        canvas=color(effective('page-shell',bp).get('background-color',Tokens(document['style']).reference(base['surface'])[1])) or color('#ffffff')
        for construct,spec in vocabulary['constructs'].items():
            root=effective(construct,bp)
            root_bg=effective_background([{'color':root.get('background-color','#00000000'),'image':'none'},{'color':'#'+''.join(f'{round(c*255):02x}' for c in canvas[:3]),'image':'none'}])
            put_treatment(construct,bp,{'outline-color':focus_color(canvas)},'Focus outline contrast inferred against the surrounding page surface')
            for slot in spec['slots']:
                scope=construct+'.'+slot['id'];props=effective(scope,bp);updates={}
                if slot['kind']=='media' and slot.get('asset_kind')!='logo':
                    if props.get('aspect-ratio','auto')=='auto':
                        updates.update({'aspect-ratio':'16 / 9' if construct=='hero' else '3 / 2','object-fit':'cover'})
                        if bp is None:notes.append({'rule':'ingest-media','message':scope+': no measured media proportion; a bounded neutral proportion and cover fit are inferred'})
                    if construct=='hero' and 'max-width' not in props:updates.update({'max-width':token('dimension','48rem'),'margin-inline':'auto'})
                else:
                    bg=effective_background([{'color':props.get('background-color','#00000000'),'image':'none'},{'color':'#'+''.join(f'{round(c*255):02x}' for c in root_bg[:3]),'image':'none'}])
                    if slot.get('asset_kind')=='logo':
                        # Logo slots also contain the content site's text name.
                        # An icon's own fill does not establish that text color.
                        props['color']=root.get('color',effective(construct+'.links',bp).get('color',props.get('color'))) if 'links' in slot_map(spec) else root.get('color',props.get('color'))
                        updates['color']=token('color',props['color'])
                    updates.update(readable(scope,bp,props,bg))
                    surrounding=root_bg if slot['kind'] in {'action','control'} or slot.get('asset_kind')=='logo' else bg
                    updates['outline-color']=focus_color(surrounding)
                    if slot.get('asset_kind')=='logo' and (px(props.get('width')) or 96)<96:updates['width']=token('dimension','96px')
                if slot['kind']=='action' and slot['element'] in {'a','button'} or slot.get('asset_kind')=='logo':
                    updates.update(target_dimensions(props))
                put_treatment(scope,bp,updates,'Readable contextual paint and minimum target dimensions inferred from captured treatments')
            if 'link' in spec.get('parts',{}):
                scope=construct+'~link';props=effective(scope,bp)
                bg=effective_background([{'color':props.get('background-color','#00000000'),'image':'none'},{'color':'#'+''.join(f'{round(c*255):02x}' for c in root_bg[:3]),'image':'none'}])
                updates=readable(scope,bp,props,bg)
                updates['outline-color']=focus_color(root_bg)
                updates.update(target_dimensions(props))
                put_treatment(scope,bp,updates,'Native navigation links retain measured styling with usable target dimensions')
    questions=deduplicate(document,questions)
    for index,q in enumerate(questions,1):
        q['id']='question-'+str(index)
        q['candidates']=[{'id':'candidate-'+str(n),'value':v} for n,v in enumerate(q.pop('values'),1)]
    return {'document':document,'provenance':complete(document,provenance,[a.get('artifact') for a in sources['tokens']]+list(dict.fromkeys(v['artifact'] for v in sources['views']))),
            'facts':facts,'mappings':[{k:v for k,v in view.items() if k!='structure'} for view in mappings],'questions':questions,'notes':notes,'mapping':'heuristic'}
