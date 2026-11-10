"""Rendered alternatives and superseding answers in private draft storage."""
from .documents import read_document, write_document
from copy import deepcopy
from ..findings import location
from ..language import validate
from ..language.resolver import parse_scope
from ..render import preview_files
from ..storage import inside,identifier
from ..vocabulary import load,slot_map
from .provenance import complete,values
from .staging import folder,load_draft,write_draft,stage


def assign(document,pointer,value):
    keys=[p.replace('~1','/').replace('~0','~') for p in pointer.split('/')[1:]]
    actual,_=location(document,pointer)
    if actual!=pointer or not keys:raise ValueError('Question pointer no longer exists')
    owner=document
    for key in keys[:-1]:owner=owner[int(key)] if isinstance(owner,list) else owner[key]
    owner[int(keys[-1]) if isinstance(owner,list) else keys[-1]]=deepcopy(value)


def targets(question):
    return question.get('targets') or [question]


def apply_answer(document,question,value):
    for target in targets(question):assign(document,target['pointer'],value)


def render_questions(library,workspace,draft_id,questions):
    document=load_draft(workspace,draft_id)
    root=folder(workspace,draft_id)
    vocabulary=load(library,document['vocabulary'])
    for question in questions:
        offered=[];evidence=[]
        candidates={c['id']:c for c in [*question['candidates'],*question.get('evidence_candidates',[])]}
        for candidate in candidates.values():
            for key in ('preview_kind','preview_note','problems','preview','preview_pixels'):candidate.pop(key,None)
            trial=deepcopy(document)
            unmeasured=candidate['value'] is None
            if not unmeasured:apply_answer(trial,question,candidate['value'])
            instances=[]
            def present(construct,slot,prop,ref):
                # Preview the advertised role even when measured construct or
                # heading overrides normally take precedence over that role.
                for override in trial.get('overrides',[]):
                    scope=parse_scope(override['scope'],vocabulary)
                    if scope.construct==construct and scope.slot==slot and scope.part is None and prop in override['properties']:
                        override['properties'][prop]=ref
            for target in targets(question):
                contexts=target.get('scopes') or [target['construct']]
                for construct in contexts:
                    instance={'construct':construct,'state':target['state']}
                    if instance not in instances:instances.append(instance)
                    if unmeasured:continue
                    treatment=trial['components'].setdefault(construct,{})
                    if target.get('property')=='surface':
                        pairing=trial['roles'][target['role']]['neutral']['surface']
                        treatment.setdefault('properties',{})['background-color']=pairing
                        present(construct,None,'background-color',pairing)
                    if target.get('property')=='font-size':
                        for slot,definition in slot_map(vocabulary['constructs'][construct]).items():
                            if definition['role']==target['role']:
                                ref=trial['roles'][target['role']][definition['emphasis']]['font-size']
                                treatment.setdefault('slots',{}).setdefault(slot,{}).setdefault('properties',{})['font-size']=ref
                                present(construct,slot,'font-size',ref)
                                if slot=='links' and 'link' in vocabulary['constructs'][construct].get('parts',{}):
                                    treatment.setdefault('parts',{}).setdefault('link',{})['font-size']=ref
                                    for override in trial.get('overrides',[]):
                                        scope=parse_scope(override['scope'],vocabulary)
                                        if scope.construct==construct and scope.part=='link' and 'font-size' in override['properties']:
                                            override['properties']['font-size']=ref
            relative=f'questions/{question["id"]}/{candidate["id"]}'
            advertised={(i['construct'],i['state']) for i in instances}
            if not unmeasured:
                from .question_preview import expose,usable
                expose(document,trial,vocabulary,instances,question)
                instances=[i for i in instances if (i['construct'],i.get('state','default')) in advertised]
            composition={'index.html':{'title':'Visual choice','instances':instances}}
            files=None
            if unmeasured:
                candidate.update(preview_kind='evidence',preview_note='Unmeasured value retained as source evidence.')
            else:
                with stage(library,workspace,draft_id,trial) as staged:
                    result=validate(staged,draft_id)
                    if result['accepted'] and usable(trial,vocabulary,question):
                        files=preview_files(staged,draft_id,composition)
                        candidate['preview_kind']='candidate'
                    elif not result['accepted']:
                        candidate['problems']=result['findings']
                        finding=next(f for f in result['findings'] if f['type'] in {'missing','violation'} and not f.get('exception'))
                        reason=f'{finding["rule"]} {finding["pointer"]}: {finding["message"]}'
                        candidate.update(preview_kind='evidence',preview_note='Candidate failed validation: '+reason[:240])
                    else:
                        candidate.update(preview_kind='evidence',preview_note='Measured spacing does not satisfy heading binding.')
            if files is None:
                evidence.append(candidate);continue
            for name,data in files.items():
                path=inside(root,relative,name);path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
            candidate['preview']=relative+'/index.html'
            offered.append(candidate)
        question['candidates']=offered
        question['evidence_candidates']=evidence
        question['visual']=False
        question.pop('preview_problem',None)
    pending=[{'question':q['id'],'candidate':c['id'],'preview':c['preview']}
             for q in questions for c in q['candidates'] if len(q['candidates'])>=2]
    if pending:
        from ..artifacts.runtime import run_job
        try:
            observations=run_job('kinbase_design.ingest.question_preview',{'root':str(root),'candidates':pending})['candidates']
        except ValueError as exc:
            for question in questions:
                if len(question['candidates'])>=2:question['preview_problem']='Visual choices could not be verified: '+str(exc)
        else:
            signatures={(o['question'],o['candidate']):o['pixels'] for o in observations}
            for question in questions:
                seen=set();distinct=[]
                for candidate in question['candidates']:
                    signature=signatures.get((question['id'],candidate['id']))
                    if signature is None:continue
                    candidate['preview_pixels']=signature
                    if signature in seen:
                        candidate.update(preview_kind='evidence',preview_note='Same rendered appearance as another candidate.')
                        question['evidence_candidates'].append(candidate)
                    elif len(distinct)>=4:
                        candidate.update(preview_kind='evidence',preview_note='Additional usable alternative retained outside the four-choice limit.')
                        question['evidence_candidates'].append(candidate)
                    else:seen.add(signature);distinct.append(candidate)
                if len(question['candidates'])>=2:question['candidates']=distinct
                question['visual']=len(distinct)>=2
    write_document(inside(root,'questions.json'),questions)
    return [q for q in questions if q['visual']]


def questions(workspace,draft_id):return [q for q in read_document(inside(folder(workspace,draft_id),'questions.json')) if q.get('visual',True)]


def answer(library,workspace,draft_id,question_id,candidate_id):
    all_questions=read_document(inside(folder(workspace,draft_id),'questions.json'))
    question=next((q for q in all_questions if q['id']==identifier(question_id)),None)
    if question is None:raise ValueError('Unknown visual question')
    candidate=next((c for c in [*question['candidates'],*question.get('evidence_candidates',[])] if c['id']==identifier(candidate_id)),None)
    if candidate is None:raise ValueError('Unknown visual candidate')
    if candidate['value'] is None:raise ValueError('An unmeasured alternative is evidence, not an applicable value')
    document=load_draft(workspace,draft_id);apply_answer(document,question,candidate['value'])
    with stage(library,workspace,draft_id,document) as staged:
        result=validate(staged,draft_id)
        if not result['accepted']:raise ValueError('Candidate does not satisfy language validation')
    from .question_preview import usable
    if not usable(document,load(library,document['vocabulary']),question):raise ValueError('Candidate does not satisfy heading binding')
    write_draft(workspace,draft_id,document)
    root=folder(workspace,draft_id);provenance=read_document(inside(root,'provenance.json'))
    for target in targets(question):
        for suffix,_ in values(candidate['value']):provenance[target['pointer']+suffix]={'kind':'chosen','choice':question_id+'/'+candidate_id}
    write_document(inside(root,'provenance.json'),complete(document,provenance,[]))
    question['answer']=candidate_id
    question['value']=candidate['value']
    render_questions(library,workspace,draft_id,all_questions)
    from . import summary
    summary(library,workspace,draft_id)
    return {'draft':draft_id,'question':question_id,'candidate':candidate_id,'value':candidate['value']}
