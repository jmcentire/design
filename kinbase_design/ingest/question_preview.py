"""Expose a question's changed treatment on its specimen despite responsive masks."""
from copy import deepcopy
import re
from ..language.properties import property_value
from ..language.resolver import parse_scope
from ..language.tokens import Tokens
from ..vocabulary import slot_map


def usable(document,vocabulary,question):
    """A heading correction must remain compliant after preview exposure."""
    from ..language.resolver import Resolver
    from .composition import pixels
    resolver=Resolver(document,vocabulary)
    for target in question.get('targets') or [question]:
        if 'flow-binding-' not in target['pointer']:continue
        construct=target['construct'];parts=vocabulary['constructs'][construct].get('parts',{})
        content=construct+'~content' if 'content' in parts else construct
        heading=construct+'~heading' if 'heading' in parts else content
        for bp in [None,*[name.removeprefix('breakpoint.') for name in resolver.tokens.nodes if name.startswith('breakpoint.')]]:
            def props(scope):return {k:v['value'] for k,v in resolver.resolve(scope,breakpoint=bp)['properties'].items()}
            before=props(heading);after=props(content);title=props(construct+'.title')
            leading=(pixels(before.get('row-gap',before.get('gap'))) or 0)+(pixels(title.get('margin-block-start',title.get('margin-block'))) or 0)
            trailing=(pixels(after.get('row-gap',after.get('gap'))) or 0)+(pixels(title.get('margin-block-end',title.get('margin-block'))) or 0)
            if leading<=trailing:return False
    return True


def expose(before,after,vocabulary,instances,question):
    left,right=Tokens(before['style']),Tokens(after['style'])
    targets=question.get('targets') or [question]
    chosen_tokens={'.'.join(t['pointer'].split('/')[2:t['pointer'].split('/').index('$value')])
                   for t in targets if t['pointer'].startswith('/style/') and '/$value' in t['pointer']}
    requested=set()
    for target in targets:
        path=[p.replace('~1','/').replace('~0','~') for p in target['pointer'].split('/')[1:]]
        if path[0]=='overrides' and len(path)>=4:
            scope=parse_scope(after['overrides'][int(path[1])]['scope'],vocabulary)
            requested.add((scope.construct+('~'+scope.part if scope.part else '.'+scope.slot if scope.slot else ''),path[3]))
        elif path[0]=='components' and len(path)>=4:
            scope=path[1]+('~'+path[3] if path[2]=='parts' else '.'+path[3] if path[2]=='slots' else '')
            requested.add((scope,path[-1]))
    def uses_choice(raw,seen=frozenset()):
        for name in re.findall(r'\{([a-zA-Z0-9_.-]+)\}',str(raw)):
            if name in chosen_tokens:return True
            if name not in seen and name in right.nodes and uses_choice(right.nodes[name]['$value'],seen|{name}):return True
        return False
    changes={}
    def inspect(scope,old,new):
        for prop,raw in new.items():
            if prop=='surface':continue  # Pairing is exposed on the root by render_questions.
            try:
                a=property_value(before,left,prop,old[prop]) if prop in old else None
                b=property_value(after,right,prop,raw)
            except (KeyError,ValueError,TypeError):continue  # Validation selects the fallback.
            if a!=b or uses_choice(raw) or (scope,prop) in requested:changes.setdefault(scope,{})[prop]=raw
    for construct,spec in vocabulary['constructs'].items():
        old=before['components'].get(construct,{});new=after['components'].get(construct,{})
        inspect(construct,old.get('properties',{}),new.get('properties',{}))
        for state,props in new.get('states',{}).items():inspect(construct,old.get('states',{}).get(state,{}),props)
        for part,props in new.get('parts',{}).items():inspect(construct+'~'+part,old.get('parts',{}).get(part,{}),props)
        for slot,definition in slot_map(spec).items():
            a=old.get('slots',{}).get(slot,{});b=new.get('slots',{}).get(slot,{})
            role=b.get('role',definition['role']);emphasis=b.get('emphasis',definition['emphasis'])
            inspect(construct+'.'+slot,before['roles'][role][emphasis],after['roles'][role][emphasis])
            inspect(construct+'.'+slot,a.get('properties',{}),b.get('properties',{}))
            for state,props in b.get('states',{}).items():inspect(construct+'.'+slot,a.get('states',{}).get(state,{}),props)
    for index,override in enumerate(after.get('overrides',[])):
        target=parse_scope(override['scope'],vocabulary)
        scope=target.construct+('~'+target.part if target.part else '.'+target.slot if target.slot else '')
        previous=before.get('overrides',[])
        inspect(scope,previous[index]['properties'] if index<len(previous) and previous[index]['scope']==override['scope'] else {},override['properties'])
    represented={i['construct'] for i in instances}
    relevant={scope:props for scope,props in changes.items() if scope.split('.')[0].split('~')[0] in represented}
    if not relevant:relevant=changes
    # A short caption never reaches its max-width. Give measure questions enough
    # neutral copy and an intrinsic width to demonstrate each cap, including the
    # current value, rather than producing identical one-line labels.
    sizes=[float(m[1])*(16 if m[2]=='rem' else 1) for c in question['candidates']
           if isinstance(c['value'],str) and (m:=re.fullmatch(r'([\d.]+)(px|rem)',c['value']))]
    width_group='question-preview'
    while width_group in after['style']:width_group+='-local'
    width_ref='{'+width_group+'.measure}'
    for scope,props in relevant.items():
        target=parse_scope(scope,vocabulary)
        if target.construct not in represented:
            instances.append({'construct':target.construct,'state':'default'});represented.add(target.construct)
        if 'max-width' in props and target.slot:
            after['style'][width_group]={'measure':{'$type':'dimension','$value':f'{max([1280,*sizes])+32:g}px'}}
            props['width']=width_ref
            definition=slot_map(vocabulary['constructs'][target.construct])[target.slot]
            if definition['kind']=='text':
                for instance in instances:
                    if instance['construct']==target.construct:instance.setdefault('values',{})[target.slot]=(vocabulary['context']['copy']['body']+' ')*3
        component=after['components'].setdefault(target.construct,{})
        if target.part:destination=component.setdefault('parts',{}).setdefault(target.part,{})
        else:
            entry=component.setdefault('slots',{}).setdefault(target.slot,{}) if target.slot else component
            destination=entry.setdefault('properties',{})
            for state in entry.get('states',{}).values():
                for prop,raw in props.items():
                    if prop in state:state[prop]=deepcopy(raw)
        destination.update(deepcopy(props))
        for override in after.get('overrides',[]):
            other=parse_scope(override['scope'],vocabulary)
            if (other.construct,other.slot,other.part)==(target.construct,target.slot,target.part):
                for prop,raw in props.items():
                    if prop in override['properties']:override['properties'][prop]=deepcopy(raw)


def render(job):
    """Compare actual local previews in one bounded, offline browser session."""
    import hashlib
    from io import BytesIO
    from PIL import Image
    from ..artifacts.runtime import chromium
    from ..checks.browser import prepare
    from ..config import CHECK_TIMEOUT_MS
    from ..storage import inside
    result=[]
    with chromium(timeout_ms=CHECK_TIMEOUT_MS) as browser:
        context=browser.new_context(java_script_enabled=False,viewport={'width':320,'height':352})
        context.route('**/*',lambda route:route.continue_() if route.request.url.startswith(('file:','data:')) else route.abort())
        try:
            page=context.new_page()
            for candidate in job['candidates']:
                prepare(page,inside(job['root'],candidate['preview']))
                if not page.locator('[data-kd-construct]').count():raise ValueError('The advertised question specimen is absent')
                pixels=Image.open(BytesIO(page.screenshot(full_page=True,animations='disabled',timeout=CHECK_TIMEOUT_MS))).convert('RGB')
                digest=hashlib.sha256(str(pixels.size).encode()+pixels.tobytes())
                result.append({'question':candidate['question'],'candidate':candidate['candidate'],'pixels':digest.hexdigest()})
        finally:context.close()
    return {'candidates':result}


if __name__=='__main__':
    import json
    import sys
    from pathlib import Path
    from ..artifacts.runtime import read_job,watch_parent
    watch_parent()
    try:print(json.dumps(render(read_job(Path(sys.argv[1])))))
    except Exception as exc:print(json.dumps({'error':str(exc)}));sys.exit(2)
