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
        for candidate in question['candidates']:
            for key in ('preview_kind','preview_note','problems'):candidate.pop(key,None)
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
            relative=f'questions/{question["id"]}/{candidate["id"]}'
            original_instances=deepcopy(instances)
            if not unmeasured:
                from .question_preview import expose
                expose(document,trial,vocabulary,instances,question)
            composition={'index.html':{'title':'Visual choice','instances':instances}}
            files=None
            if unmeasured:
                candidate.update(preview_kind='current-draft',preview_note='Unmeasured value; preview shows the current draft unchanged.')
            else:
                with stage(library,workspace,draft_id,trial) as staged:
                    result=validate(staged,draft_id)
                    if result['accepted']:
                        files=preview_files(staged,draft_id,composition)
                        candidate['preview_kind']='candidate'
                    else:
                        candidate['problems']=result['findings']
                        finding=next(f for f in result['findings'] if f['type'] in {'missing','violation'} and not f.get('exception'))
                        reason=f'{finding["rule"]} {finding["pointer"]}: {finding["message"]}'
                        candidate.update(preview_kind='current-draft',preview_note='Preview shows the current draft unchanged; candidate failed validation: '+reason[:240])
            if files is None:
                # The alternative remains evidence, but an invalid value must
                # never enter the language passed to the shared renderer.
                with stage(library,workspace,draft_id,document) as staged:
                    files=preview_files(staged,draft_id,{'index.html':{'title':'Visual choice','instances':original_instances}})
            for name,data in files.items():
                path=inside(root,relative,name);path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
            candidate['preview']=relative+'/index.html'
    write_document(inside(root,'questions.json'),questions)
    return questions


def questions(workspace,draft_id):return read_document(inside(folder(workspace,draft_id),'questions.json'))


def answer(library,workspace,draft_id,question_id,candidate_id):
    all_questions=questions(workspace,draft_id)
    question=next((q for q in all_questions if q['id']==identifier(question_id)),None)
    if question is None:raise ValueError('Unknown visual question')
    candidate=next((c for c in question['candidates'] if c['id']==identifier(candidate_id)),None)
    if candidate is None:raise ValueError('Unknown visual candidate')
    if candidate['value'] is None:raise ValueError('An unmeasured alternative is evidence, not an applicable value')
    document=load_draft(workspace,draft_id);apply_answer(document,question,candidate['value'])
    with stage(library,workspace,draft_id,document) as staged:
        result=validate(staged,draft_id)
        if not result['accepted']:raise ValueError('Candidate does not satisfy language validation')
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
