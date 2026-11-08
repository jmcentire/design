"""Rendered alternatives and superseding answers in private draft storage."""
from .documents import read_document, write_document
from copy import deepcopy
from ..findings import location
from ..language import validate
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
            trial=deepcopy(document);apply_answer(trial,question,candidate['value'])
            instances=[]
            for target in targets(question):
                contexts=target.get('scopes') or [target['construct']]
                for construct in contexts:
                    instance={'construct':construct,'state':target['state']}
                    if instance not in instances:instances.append(instance)
                    treatment=trial['components'].setdefault(construct,{})
                    if target.get('property')=='surface':
                        pairing=trial['roles'][target['role']]['neutral']['surface']
                        treatment.setdefault('properties',{})['background-color']=pairing
                    if target.get('property')=='font-size':
                        for slot,definition in slot_map(vocabulary['constructs'][construct]).items():
                            if definition['role']==target['role']:
                                ref=trial['roles'][target['role']][definition['emphasis']]['font-size']
                                treatment.setdefault('slots',{}).setdefault(slot,{}).setdefault('properties',{})['font-size']=ref
            relative=f'questions/{question["id"]}/{candidate["id"]}'
            with stage(library,workspace,draft_id,trial) as staged:
                result=validate(staged,draft_id)
                if not result['accepted']:
                    candidate['problems']=result['findings']
                    continue
                files=preview_files(staged,draft_id,{'index.html':{'title':'Visual choice','instances':instances}})
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
    write_document(inside(root,'questions.json'),all_questions)
    from . import summary
    summary(library,workspace,draft_id)
    return {'draft':draft_id,'question':question_id,'candidate':candidate_id,'value':candidate['value']}
