"""Theory-derived drafts and bounded repairs over the shared validation/check path."""
from copy import deepcopy
import shutil
from .. import checks
from ..checks.math import color,contrast
from ..findings import location
from ..ingest import summary
from ..ingest.documents import read_document,write_document
from ..ingest.provenance import record_at,complete
from ..ingest.quantize import measurements,px
from ..ingest.staging import folder,stage,write_draft,load_draft
from ..language import validate
from ..language.tokens import Tokens
from ..render import build_preview
from ..storage import inside,identifier
from ..vocabulary import load
from .sessions import read,write,settled
from .planning import baseline
from .theory import language


def facts(document,values):
    tokens=Tokens(document['style']);groups={}
    for name in tokens.nodes:
        kind,value=tokens.evaluate(name);groups.setdefault(kind,[]).append(value)
    result=measurements([],groups.get('color',[]))
    result.update(font_families=list(dict.fromkeys(groups.get('fontFamily',[]))),
                  type_scale=sorted({px(tokens.evaluate('type.'+r)[1]) for r in ('body','subtitle','title')}),
                  spacing_base=values['density'],spacing=[values['density']*i for i in (1,2,3,4)],
                  radii=[values['shape']],breakpoints=[768,1200],type_base_px=16,
                  type_scale_ratios=[values['type-scale']]*2)
    return result


def repair(document,provenance,result,vocabulary):
    """Repair only inferred/generated values; fixed source evidence is immutable."""
    from ..language.resolver import resolve,property_pointer
    changed=False
    for finding in result['findings']:
        if finding['type'] not in {'violation','missing'} or finding.get('exception'):continue
        target=finding.get('target','')
        if finding['rule']=='contrast' and '.' in target:
            try:
                resolved=resolve(document,vocabulary,target)['properties']
                ref_path=property_pointer(document,vocabulary,'color',resolved['color'])
                # Pointer helper returns the authored member; resolve its token reference.
                _,ref=location(document,ref_path)
                if not isinstance(ref,str) or not ref.startswith('{'):continue
                token_path='/style/'+ref[1:-1].replace('.','/')
                if record_at(provenance,token_path).get('kind')=='source':continue
                _,node=location(document,token_path)
                if not isinstance(node,dict) or '$value' not in node:continue
                surface='{color.paper}'
                background=Tokens(document['style']).reference(surface)[1]
                value=max(('#000000','#ffffff'),key=lambda v:contrast(color(v),color(background)))
                if node['$value']!=value:
                    node['$value']=value;provenance[token_path]={'kind':'inferred','method':'WCAG contrast repair of an unsupplied value','inputs':[]};changed=True
            except (KeyError,ValueError,TypeError):continue
        elif finding['rule']=='target-size' and '.' in target:
            construct,slot=target.split('.',1)
            if construct not in vocabulary['constructs']:continue
            path='/components/'+construct+'/slots/'+slot
            if (record_at(provenance,path) or {}).get('kind')=='source':continue
            props=document['components'].setdefault(construct,{}).setdefault('slots',{}).setdefault(slot,{}).setdefault('properties',{})
            if props.get('padding')=='{space.target-repair}':continue
            document['style']['space']['target-repair']={'$type':'dimension','$value':'12px'}
            props['padding']='{space.target-repair}';changed=True
    return changed


def derive(library,workspace,session,language_id):
    identifier(language_id);state=read(workspace,session);root=folder(workspace,language_id)
    if inside(library,'languages',language_id).exists():raise ValueError('Derive needs a new language id')
    if root.exists() and state.get('draft')!=language_id:raise ValueError('Draft id already exists')
    values=baseline(workspace,session);preferences=settled(workspace,session)['settled'];vocabulary=load(library)
    document,provenance,_=language(language_id,vocabulary,values,state['resources'],preferences)
    write_draft(workspace,language_id,document)
    from .sessions import folder as session_folder
    shutil.copytree(inside(session_folder(workspace,session),'assets'),inside(root,'assets'),dirs_exist_ok=True)
    draft_state={'artifacts':state['artifacts'],'facts':facts(document,values),'views':[],'references':[],
                 'assets':[],'notes':[{'rule':'generate-input','message':note['message']} for note in state['resources'].get('notes',[])],
                 'mapping':'heuristic','generation':{'session':session,'values':values,'repairs':[],'check_status':'pending'}}
    write_document(root/'provenance.json',provenance);write_document(root/'questions.json',[])
    write_document(root/'state.json',draft_state);state['draft']=language_id;write(workspace,state)
    for iteration in range(state['settings']['repair_iterations']+1):
        write_draft(workspace,language_id,document)
        write_document(root/'provenance.json',complete(document,provenance,state['artifacts']))
        with stage(library,workspace,language_id) as staged:
            result=validate(staged,language_id)
            if result['accepted']:
                build_preview(staged,language_id,root/'preview')
                try:result=checks.check(staged,language_id,root/'checks')
                except checks.CheckUnavailable as exc:
                    draft_state['generation'].update(check_status='unavailable',error=str(exc))
                    draft_state['facts']=facts(document,values)
                    write_document(root/'state.json',draft_state);summary(library,workspace,language_id)
                    raise checks.CheckUnavailable(str(exc)+'; draft retained at drafts/'+language_id) from exc
        if result['accepted'] or iteration>=state['settings']['repair_iterations']:break
        if not repair(document,provenance,result,vocabulary):break
        draft_state['generation']['repairs'].append({'iteration':iteration+1,'rules':sorted({f['rule'] for f in result['findings'] if f['type']=='violation'})})
    draft_state['generation']['check_status']='complete' if result.get('checked',{}).get('pages') else 'blocked'
    draft_state['facts']=facts(document,values)
    write_document(root/'state.json',draft_state)
    final=summary(library,workspace,language_id)
    return {**final,'generation':draft_state['generation']}
