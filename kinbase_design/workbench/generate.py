"""No-JavaScript generate journey; every POST calls the CLI's application operation."""
import json
import mimetypes
from .. import generate
from ..artifacts import import_bytes
from ..checks import CheckUnavailable
from ..generate.sessions import read,folder,choices,effective
from ..ingest import summary,save_draft
from ..ingest.staging import folder as draft_folder
from ..storage import inside,identifier
from .ingest import fields


def handle(library,workspace,environ,segments,query,html):
    from . import RequestError,multipart
    tail=segments[1:];method=environ['REQUEST_METHOD']
    def page(template,**context):return 200,html(template,**context),'text/html; charset=utf-8',[]
    def redirect(path):return 303,b'','text/html; charset=utf-8',[('Location',path)]
    def static(root,name):
        if not name.endswith(('.html','.css','.png','.jpg','.webp','.svg','.woff','.woff2','.ttf','.otf','.json')):raise RequestError('Unknown generated artifact',404)
        return 200,inside(root,name).read_bytes(),mimetypes.guess_type(name)[0] or 'application/octet-stream',[]
    if not tail:
        if method!='GET':raise RequestError('Unknown generate route',404)
        parent=inside(workspace,'sessions');sessions=[]
        for path in sorted(parent.iterdir() if parent.exists() else []):
            if path.is_dir() and (path/'session.json').exists():sessions.append(read(workspace,path.name))
        return page('generate-start.html',title='Generate a language',sessions=sessions)
    if tail==['start'] and method=='POST':
        if environ.get('CONTENT_TYPE','').startswith('multipart/form-data'):
            data,upload=multipart(environ,('brief','artifacts'),require_file=False)
        else:data={k:v[0] for k,v in fields(environ).items()};upload=None
        artifacts=data.get('artifacts','').split()
        if upload:artifacts.append(import_bytes(workspace,*upload,data.get('kind') or None))
        result=generate.start(library,workspace,data.get('brief',''),artifacts)
        return redirect('/generate/'+result['session']+'/interview')
    session=identifier(tail[0]);state=read(workspace,session);base='/generate/'+session
    action=tail[1] if len(tail)>1 else 'interview'
    if action=='candidates' and len(tail)>=4 and method=='GET':
        candidate=identifier(tail[2]);name='/'.join(tail[3:])
        return static(inside(folder(workspace,session),'candidates',candidate),name)
    if action=='assets' and len(tail)==3 and method=='GET':
        asset=state['resources']['assets'].get(tail[2])
        if asset is None:raise RequestError('Unknown session asset',404)
        detail=asset['variants']['primary'];path=inside(folder(workspace,session),'assets',detail['file'])
        kind=mimetypes.guess_type('asset.'+detail['format'])[0] or 'application/octet-stream'
        return 200,path.read_bytes(),kind,[]
    if len(tail)>2 and action=='checks' and method=='GET' and state.get('draft'):
        return static(inside(draft_folder(workspace,state['draft']),'checks'),'/'.join(tail[2:]))
    if len(tail)>2:raise RequestError('Unknown generate route',404)
    if action=='interview':
        if method=='POST':
            data=fields(environ)
            answers=json.loads(data['answers'][0]) if 'answers' in data else {d:json.loads(v[0]) for d,v in data.items()}
            generate.interview(workspace,session,answers);return redirect(base+'/moodboard')
        return page('generate-interview.html',title='Visual interview',state=state,questions=generate.interview_samples(library,workspace,session))
    if action=='moodboard':
        if method=='POST':
            data=fields(environ);generate.moodboard(library,workspace,session,data.get('pin',[None])[0],data.get('remove',[None])[0])
            return redirect(base+'/moodboard')
        return page('generate-moodboard.html',title='Mood board',state=state,items=generate.moodboard(library,workspace,session))
    if action=='pair' and method=='GET':
        result=generate.pair(library,workspace,session);state=read(workspace,session)
        return page('generate-pair.html',title='Compare directions',state=state,pair=result,
                    settled=generate.settled(workspace,session),history=effective(choices(workspace,session)))
    if action=='choose' and method=='POST':
        data=fields(environ)
        generate.choose(workspace,session,data['pair'][0],data['choice'][0],data.get('comment',[''])[0],data.get('supersedes',[None])[0] or None)
        return redirect(base+'/pair')
    if action=='derive' and method=='POST':
        data=fields(environ);draft=data.get('language',[state.get('draft','direction-'+session.removeprefix('session-'))])[0]
        try:generate.derive(library,workspace,session,draft)
        except CheckUnavailable:pass  # Draft review displays the persisted environment error, never a pass.
        return redirect(base+'/review')
    if action=='review' and method=='GET':
        result=summary(library,workspace,state['draft']) if state.get('draft') else None
        return page('generate-review.html',title='Review generated language',state=state,result=result)
    if action=='save' and method=='POST':
        if not state.get('draft'):raise ValueError('Derive a language first')
        result=save_draft(library,workspace,state['draft'])
        if not result.get('saved'):raise RequestError('Draft has validation findings; review before saving',422)
        return redirect('/languages/'+state['draft'])
    raise RequestError('Unknown generate route',404)
