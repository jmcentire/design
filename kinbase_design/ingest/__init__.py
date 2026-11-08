"""Ingest application operations, shared by CLI and the workbench."""
from .documents import read_document, write_document, stored_view
from copy import deepcopy
import json
from pathlib import Path
import shutil
from ..assets import promote
from ..config import ingest_config
from ..findings import Finding,location,report,pointer
from ..language import validate
from ..language.versions import digest
from ..storage import identifier,inside,save_language,load_language
from ..vocabulary import load
from .sources import collect
from .extract import derive
from .adapter import propose
from .provenance import complete,shared
from .staging import folder,load_draft,write_draft,stage
from .questions import render_questions,questions,answer
from .reporting import measured


def summary(library,workspace,draft_id):
    root=folder(workspace,draft_id);document=load_draft(workspace,draft_id);state=read_document(inside(root,'state.json'))
    with stage(library,workspace,draft_id) as staged:validation=validate(staged,draft_id)
    findings=validation['findings']
    checked=inside(root,'checks','report.json')
    if state.get('generation') and checked.exists():
        rendered=read_document(checked)
        if rendered.get('version')==digest(document):findings=rendered['findings']
    for f in findings:f['file']=f'drafts/{draft_id}/working.json'
    generation=state.get('generation')
    if generation and generation['check_status']!='complete':
        findings.append(Finding('missing','generate-checks',f'drafts/{draft_id}/state.json',
                                '/generation/check_status',generation['check_status'],'completed rendered checks',
                                generation.get('error','Rendered checks have not completed')).to_dict())
    for index,note in enumerate(state['notes']):
        findings.append(Finding('coverage',note.get('rule','ingest-coverage'),f'drafts/{draft_id}/state.json',
                                pointer('notes',index),note,'review source fidelity',note['message']).to_dict())
    items=questions(workspace,draft_id)
    result={**report(draft_id,findings),'draft':draft_id,'mapping':'llm' if state['mapping']=='configured-command' else state['mapping'],'facts':state['facts'],
            'measured':measured(document,state['facts']),'assets':state['assets'],'questions':len(items),'question_items':items,'standards':state.get('standards','unknown (Kinbase unconnected)'),
            'views':state['views'],'references':state['references'],'version':digest(document)}
    if state.get('generation'):
        result['generation']=state['generation']
        result['checks_complete']=state['generation']['check_status']=='complete'
    write_document(inside(root,'summary.json'),result)
    return result


def draft(library,workspace,artifact_ids,language_id,settings=None):
    settings=settings or ingest_config()
    identifier(language_id)
    root=folder(workspace,language_id)
    if root.exists() or inside(library,'languages',language_id).exists():raise ValueError('Draft needs a new language id')
    if not artifact_ids:raise ValueError('At least one source artifact is required')
    sources=collect(workspace,artifact_ids);vocabulary=load(library)
    derived=derive(language_id,vocabulary,sources,settings=settings)
    proposal,problem=propose(derived['document'],vocabulary,sources)
    if problem:derived['notes'].append(problem)
    if proposal is not None:
        derived=derive(language_id,vocabulary,sources,proposal,settings)
        derived['mapping']='llm'
        for item in proposal:
            owner=derived['document']['components'].setdefault(item['construct'],{}).setdefault('slots',{}).setdefault(item['slot'],{})
            owner.update(role=item['role'],emphasis=item.get('emphasis','neutral'))
        # Keep accepted adapter evidence private; heuristics still supply missing mappings.
        derived['notes'].append({'rule':'ingest-adapter','message':f'Accepted {len(proposal)} validated semantic role suggestions from the configured command'})
    root.mkdir(parents=True)
    write_draft(workspace,language_id,derived['document'])
    write_document(inside(root,'provenance.json'),complete(derived['document'],derived['provenance'],list(artifact_ids)))
    views=[]
    for index,view in enumerate(derived['mappings']):
        filename=f'views/view-{index+1}.json';write_document(inside(root,filename),stored_view(view))
        views.append({k:view[k] for k in ('artifact','page','width','screenshot')}|{'file':filename})
    notes=derived['notes']+[{'rule':'ingest-capture','message':str(p.get('message',p))} for p in sources['problems']]
    if sources['assets']:notes.append({'rule':'ingest-assets','message':'Found assets are private originals; promotion is offered and has not been performed'})
    if sources['briefs']:notes.append({'rule':'ingest-brief','message':'Brief text retained as source data; heuristic mapping does not execute its instructions'})
    notes=list({json.dumps(note,sort_keys=True):note for note in notes}.values())
    write_document(inside(root,'state.json'),{'artifacts':list(artifact_ids),'facts':derived['facts'],'views':views,'references':sources['references'],
                                         'assets':sources['assets'],'notes':notes,'mapping':derived['mapping'],'proposal':proposal,'settings':settings.to_dict()})
    render_questions(library,workspace,language_id,derived['questions'])
    return summary(library,workspace,language_id)


def save_draft(library,workspace,draft_id):
    document=load_draft(workspace,draft_id);root=folder(workspace,draft_id)
    with stage(library,workspace,draft_id) as staged:
        validation=validate(staged,draft_id)
        if not validation['accepted']:return validation
    target=inside(library,'languages',draft_id)
    if target.exists() and not read_document(inside(root,'state.json')).get('saved'):
        raise ValueError('Language already exists; choose a new draft id')
    assets=inside(root,'assets')
    if assets.exists():shutil.copytree(assets,inside(target,'assets'),dirs_exist_ok=True)
    save_language(library,draft_id,document)
    provenance=complete(document,read_document(inside(root,'provenance.json')),[])
    write_document(inside(root,'provenance.json'),provenance)
    version=digest(document)
    write_document(inside(target,'provenance',version+'.json'),shared(provenance))
    state=read_document(inside(root,'state.json'));state['saved']=version;write_document(inside(root,'state.json'),state)
    return {'language':draft_id,'saved':True,'hash':version}


def promote_draft(library,workspace,draft_id,artifact_id,asset_id,kind,variant,weight=None,style=None,family=None,scope=None):
    root=folder(workspace,draft_id)
    with stage(library,workspace,draft_id) as staged:
        entry=promote(staged,workspace,draft_id,artifact_id,asset_id,kind,variant,weight,style,family)
        document=load_language(staged,draft_id)
        if scope:
            from ..language.resolver import parse_scope
            from ..vocabulary import slot_map
            parsed=parse_scope(scope,load(library,document['vocabulary']))
            if parsed.state or parsed.breakpoint or not parsed.slot:raise ValueError('Asset scope must be construct.slot')
            slot=slot_map(load(library,document['vocabulary'])['constructs'][parsed.construct])[parsed.slot]
            if slot.get('asset_kind')!=kind:raise ValueError('Asset kind does not match the media slot')
            document['components'].setdefault(parsed.construct,{}).setdefault('assets',{})[parsed.slot]=asset_id+':'+variant
        if kind=='font' and family:
            from ..language.tokens import Tokens
            for name,node in Tokens(document['style']).nodes.items():
                if node.get('$type')=='fontFamily' and family in (node['$value'] if isinstance(node['$value'],list) else [node['$value']]):
                    token=document['style']
                    for key in name.split('.'):token=token[key]
                    token.setdefault('$extensions',{})['kinbase-design']={'asset':asset_id}
        shutil.copytree(inside(staged,'languages',draft_id,'assets'),inside(root,'assets'),dirs_exist_ok=True)
        write_draft(workspace,draft_id,document)
    provenance=read_document(inside(root,'provenance.json'))
    provenance[pointer('assets',asset_id)]={'kind':'inferred','method':'Explicit artifact promotion','inputs':[artifact_id]}
    if scope:
        provenance[pointer('components',parsed.construct,'assets',parsed.slot)]={'kind':'inferred','method':'Explicit media binding','inputs':[artifact_id]}
    write_document(inside(root,'provenance.json'),complete(document,provenance,[artifact_id]))
    summary(library,workspace,draft_id)
    return entry
