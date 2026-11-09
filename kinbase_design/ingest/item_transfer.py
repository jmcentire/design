"""Keep repeated-item paint and prose evidence attached to their source groups."""
from collections import Counter
from statistics import median
from .quantize import px,hex_color
from .presentation import visible_text


def select(view,principal_group=None):
    nodes=view.get('structure',view['nodes']);items={i['selector']:i for i in view['instances'] if i['construct']=='card'}
    groups=[g for g in view.get('groups',[]) if g['members'] and set(g['members'])<=items.keys()]
    group=max(groups,key=lambda g:(g['selector']==principal_group,(g.get('box') or [0,0,0,0])[2],len(g['members'])),default=None)
    def surface(item):
        anchors=[n['selector'] for n in item['nodes'].values() if n['tag'] not in {'a','button'}]
        candidates=[n for n in nodes if (n['selector']==item['selector'] or n['selector'].startswith(item['selector']+' > '))
                    and n['tag'] in {'div','article','li','section','a'} and anchors
                    and all(s==n['selector'] or s.startswith(n['selector']+' > ') for s in anchors)]
        painted=[n for n in candidates if (px(n.get('styles',{}).get('border-top-width')) or 0)>0
                 or n.get('styles',{}).get('box-shadow','none')!='none'
                 or hex_color(n.get('styles',{}).get('background-color')) not in {None,'#00000000'}]
        return min(painted,key=lambda n:len(n['selector']),default=item.get('root_node',{}))
    chosen=[{**items[s],'root_node':surface(items[s])} for s in group['members']] if group else []
    return group,chosen


def transfer(document,vocabulary,view,treatments,properties,token,space_token,origin,questions,corrections,selection):
    nodes=view.get('structure',view['nodes']);by={n['selector']:n for n in nodes};width=view['width']
    group,items=selection;item=items[0] if items else None
    def props(scope):return treatments.setdefault((scope,width),{})
    clear={'background-color':token('color','#00000000'),'border-style':'none','border-width':token('dimension','0px'),'box-shadow':'none'}
    zero=space_token(0,{'kind':'inferred','method':'One owner for the content inset'})
    def own_paint(scope,node):
        measured=properties(view,node) if node else {}
        props(scope).update(clear)
        props(scope).update({k:v for k,v in measured.items() if k in {'background-color','border-style','border-width','border-color','border-radius','box-shadow'}})
    def within(node,root):return node['selector']==root or node['selector'].startswith(root+' > ')
    def excluded(node):
        current=node
        while current:
            if current['tag'] in {'aside','nav','footer','header','time','small','figcaption'}:return True
            current=by.get(current.get('parent'))
        return False
    body=next((n for n in nodes if n['tag']=='body'),{})
    body_color=hex_color(body.get('styles',{}).get('color')) or '#222222'
    prose=[n for n in nodes if n['tag']=='p' and visible_text(n) and not excluded(n)
           and not any(within(n,i['selector']) for i in items)
           and not any(within(n,i['selector']) for i in view['instances'] if i['construct']=='hero')]
    # Body-colored main-flow paragraphs establish the prose scale. Dates and
    # metadata cannot outvote body copy merely by being encountered first.
    normal=[n for n in prose if hex_color(n.get('styles',{}).get('color'))==body_color]
    weights=Counter()
    for n in normal:weights[px(n['styles'].get('font-size')) or 16]+=len(n.get('text',''))
    body_size=max(weights,key=weights.get) if weights else px(body.get('styles',{}).get('font-size')) or 16
    def paragraph(scope,node=None):
        own_paint(scope,None)
        measured=properties(view,node) if node else {}
        props(scope).update({k:v for k,v in measured.items() if k in {'font-size','font-family','font-weight','line-height','color'}})
        if node and (size:=px(node.get('styles',{}).get('font-size'))) is not None:props(scope)['font-size']=token('dimension',f'{size:g}px',origin(view,node,'font-size'))
        if node and (color:=hex_color(node.get('styles',{}).get('color'))):props(scope)['color']=token('color',color,origin(view,node,'color'))
        props(scope).setdefault('font-size',token('dimension',f'{body_size:g}px'))
        if node is None:props(scope).update({'font-size':token('dimension',f'{body_size:g}px'),'color':token('color',body_color)})
        props(scope).update({'padding':zero,'padding-inline':zero,'padding-block':zero})
        # The measure belongs to this paragraph role's measured type, rather
        # than the broad role assignment that preceded the group transfer.
        from .composition import correction
        witnesses=[node] if node and node.get('box') else [n for n in normal if n.get('box')]
        observed=median(n['box'][2] for n in witnesses) if witnesses else body_size*36
        size=px(node.get('styles',{}).get('font-size')) if node else body_size
        chosen=max((size or body_size)*vocabulary.get('measure_minimum_em',0),min(observed,(size or body_size)*40))
        name='prose-'+scope.replace('.','-')+'-'+str(width)
        document['style'].setdefault('flow',{})[name]={'$type':'dimension','$value':f'{chosen:g}px'}
        props(scope)['max-width']='{flow.'+name+'}'
        if observed!=chosen:
            question={'pointer':'/style/flow/'+name+'/$value','construct':scope.split('.')[0],'state':'default',
                      'values':[f'{chosen:g}px',f'{observed:g}px'],'reason':'Keep the paragraph cap within the permitted measure of its transferred font size; narrower columns still constrain its actual width'}
            questions.append(question)
            for witness in witnesses:
                if witness['box'][2]>(size or body_size)*40 or witness['box'][2]<(size or body_size)*vocabulary.get('measure_minimum_em',0):
                    correction(corrections,question,'measure',witness['selector'],f'{witness["box"][2]:g}px',f'{chosen:g}px')
    # Find the lead in the actual leading-heading group, independent of which
    # representative paragraph the broad semantic mapper chose for hero.body.
    heading=next((n for n in nodes if n['tag']=='h1'),None);ancestor=by.get(heading.get('parent')) if heading else None
    lead=None
    while ancestor and ancestor['tag'] not in {'body','html'}:
        candidates=[n for n in nodes if n['tag']=='p' and visible_text(n) and within(n,ancestor['selector'])
                    and not any(within(n,i['selector']) for i in items)]
        if candidates:lead=candidates[0];break
        ancestor=by.get(ancestor.get('parent'))
    paragraph('hero.body',lead)
    paragraph('content-section.body')
    # Unobserved ordinary sections are not aliases for an aside or notice panel.
    sections=[i for i in view['instances'] if i['construct']=='content-section' and i.get('nodes',{}).get('title',{}).get('tag')=='h2'
              and not excluded(i.get('root_node',{})) and any(within(p,i['selector']) for p in normal)]
    section=max(sections,key=lambda i:len(i.get('values',{}).get('body','')),default=None)
    own_paint('content-section',section.get('root_node') if section else None)
    if item:
        surface=item['root_node'];measured=properties(view,surface,True)
        root=props('card');root.update(clear)
        root.update({k:v for k,v in measured.items() if k in {'background-color','border-color','border-width','border-style','border-radius','box-shadow','padding','padding-inline','padding-block'}})
        inner=props('card~content')
        # A root inset belongs to every child, including inset media. Otherwise
        # the text wrapper supplies the sole inset beside full-bleed media.
        for axis,side in [('padding-inline','padding-left'),('padding-block','padding-top')]:
            amount=px(surface.get('styles',{}).get(side)) or 0
            root[axis]=space_token(amount,origin(view,surface,side))
            if amount>0:inner[axis]=zero
        owned=[n for n in nodes if within(n,surface['selector'])]
        paragraphs=[n for n in owned if n['tag']=='p' and visible_text(n)]
        primary=[n for n in paragraphs if hex_color(n.get('styles',{}).get('color'))==body_color]
        card_body=max(primary or paragraphs,key=lambda n:len(n.get('text','')),default=None)
        for slot in vocabulary['constructs']['card']['slots']:
            if slot['kind']!='text':continue
            scope='card.'+slot['id'];witness=item['nodes'].get(slot['id'])
            own_paint(scope,witness)
            if witness:
                props(scope).update({k:v for k,v in properties(view,witness).items() if k in {'font-family','font-weight','color'}})
            props(scope).update({'padding':zero,'padding-inline':zero,'padding-block':zero})
        paragraph('card.body',card_body)
        # Meta is a new semantic list, not the painted paragraph used as its
        # textual source; only an actual painted dl establishes a nested panel.
        def inner_group(children):
            candidates=[n for n in owned if n['selector']!=surface['selector'] and children
                        and all(c['selector'].startswith(n['selector']+' > ') for c in children)]
            return max(candidates,key=lambda n:len(n['selector']),default=None)
        dl=next((n for n in owned if n['tag']=='dl'),None)
        pair=[n for n in owned if dl and within(n,dl['selector']) and n['tag'] in {'dt','dd'}][:2]
        pair_group=inner_group(pair)
        own_paint('card.meta',dl)
        own_paint('card~pair',pair_group if pair_group!=dl else None)
        text=[n for n in item['nodes'].values() if n['tag'] not in {'a','button','img','svg'}]
        own_paint('card~content',inner_group(text))
        actions=[by[a['selector']] for group in item.get('action_items',{}).values() for a in group if a['selector'] in by]
        action_group=inner_group(actions)
        if action_group and any(visible_text(n) and within(n,action_group['selector']) and not any(within(n,a['selector']) for a in actions) for n in owned):action_group=None
        own_paint('card~actions',action_group)
        props('listing-card').update({k:v for k,v in root.items() if k in set(clear)|{'border-color','border-radius','padding','padding-inline','padding-block'}})
        props('listing-card~content').update({k:v for k,v in inner.items() if k in set(clear)|{'border-color','border-radius','padding','padding-inline','padding-block'}})
        for slot in vocabulary['constructs']['listing-card']['slots']:
            if slot['kind']=='text':own_paint('listing-card.'+slot['id'],None)
    if group and items:
        # Framework columns can touch while their bordered children have gutters.
        # Measure those visible item boxes rather than the outer column boxes.
        from .arrangement import gutters
        boxes=[i['root_node']['box'] for i in items if i['root_node'].get('box')]
        for prop,values in gutters(boxes).items():
            if values:props('collection.items')[prop]=space_token(max(0,median(values)),origin(view,by.get(group['selector'],items[0]['root_node']),prop))
