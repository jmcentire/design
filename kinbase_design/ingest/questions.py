"""Rendered alternatives and superseding answers in private draft storage."""
from copy import deepcopy
from ..findings import location
from ..language import validate
from ..render import preview_files
from ..storage import inside,read_json,write_json,identifier
from .provenance import complete,values
from .staging import folder,load_draft,write_draft,stage


def assign(document,pointer,value):
    keys=[p.replace('~1','/').replace('~0','~') for p in pointer.split('/')[1:]]
    actual,_=location(document,pointer)
    if actual!=pointer or not keys:raise ValueError('Question pointer no longer exists')
    owner=document
    for key in keys[:-1]:owner=owner[int(key)] if isinstance(owner,list) else owner[key]
    owner[int(keys[-1]) if isinstance(owner,list) else keys[-1]]=deepcopy(value)


def render_questions(library,workspace,draft_id,questions):
    document=load_draft(workspace,draft_id)
    root=folder(workspace,draft_id)
    for question in questions:
        for candidate in question['candidates']:
            trial=deepcopy(document);assign(trial,question['pointer'],candidate['value'])
            relative=f'questions/{question["id"]}/{candidate["id"]}'
            with stage(library,workspace,draft_id,trial) as staged:
                result=validate(staged,draft_id)
                if not result['accepted']:
                    candidate['problems']=result['findings']
                    continue
                files=preview_files(staged,draft_id,{'index.html':{'title':'Visual choice','instances':[{'construct':question['construct'],'state':question['state']}]}})
                for name,data in files.items():
                    path=inside(root,relative,name);path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
            candidate['preview']=relative+'/index.html'
    write_json(inside(root,'questions.json'),questions)
    return questions


def questions(workspace,draft_id):return read_json(inside(folder(workspace,draft_id),'questions.json'))


def answer(library,workspace,draft_id,question_id,candidate_id):
    all_questions=questions(workspace,draft_id)
    question=next((q for q in all_questions if q['id']==identifier(question_id)),None)
    if question is None:raise ValueError('Unknown visual question')
    candidate=next((c for c in question['candidates'] if c['id']==identifier(candidate_id)),None)
    if candidate is None:raise ValueError('Unknown visual candidate')
    document=load_draft(workspace,draft_id);assign(document,question['pointer'],candidate['value'])
    with stage(library,workspace,draft_id,document) as staged:
        result=validate(staged,draft_id)
        if not result['accepted']:raise ValueError('Candidate does not satisfy language validation')
    write_draft(workspace,draft_id,document)
    root=folder(workspace,draft_id);provenance=read_json(inside(root,'provenance.json'))
    for suffix,_ in values(candidate['value']):provenance[question['pointer']+suffix]={'kind':'chosen','choice':question_id+'/'+candidate_id}
    write_json(inside(root,'provenance.json'),complete(document,provenance,[]))
    question['answer']=candidate_id
    write_json(inside(root,'questions.json'),all_questions)
    return {'draft':draft_id,'question':question_id,'candidate':candidate_id,'value':candidate['value']}
