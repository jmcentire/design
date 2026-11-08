"""Server-rendered ingest journey over the same application operations as the CLI."""
import mimetypes
from urllib.parse import parse_qs
from ..artifacts import import_bytes,read_artifact
from ..artifacts.bundle import metadata,read_member
from ..artifacts.capture import capture
from ..assets import inspect_format
from ..config import MAX_UPLOAD_BYTES,ingest_config
from ..ingest import draft,summary,save_draft,promote_draft,questions,answer
from ..ingest.fidelity import fidelity
from ..ingest.documents import read_document
from ..ingest.staging import folder,stage,load_draft
from ..ingest.provenance import inspect_sources
from ..language.versions import digest
from ..render import preview_files
from ..storage import inside,read_json,identifier
from ..vocabulary import load,slot_map


def fields(environ):
    length=int(environ.get('CONTENT_LENGTH','0'))
    if length<0 or length>65536:raise ValueError('Form exceeds configured size limit')
    if not environ.get('CONTENT_TYPE','').startswith('application/x-www-form-urlencoded'):raise ValueError('Expected a URL-encoded form')
    data=environ['wsgi.input'].read(length)
    if len(data)!=length:raise ValueError('Incomplete form')
    return parse_qs(data.decode(),keep_blank_values=True,max_num_fields=40)


def handle(library,workspace,environ,segments,query,html):
    from . import RequestError,multipart
    method=environ['REQUEST_METHOD'];tail=segments[1:]
    def page(template,**context):return 200,html(template,**context),'text/html; charset=utf-8',[]
    def redirect(path):return 303,b'','text/html; charset=utf-8',[('Location',path)]
    def static(data,name):
        kind=mimetypes.guess_type(name)[0] or 'application/octet-stream'
        return 200,data,kind,[('Content-Security-Policy',"sandbox allow-same-origin; default-src 'none'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; font-src 'self'")]
    if not tail and method=='GET':
        drafts=[];artifacts=[]
        parent=inside(workspace,'drafts')
        for item in sorted(parent.iterdir() if parent.exists() else []):
            if item.is_dir() and (item/'working.json').exists():
                document=load_draft(workspace,item.name);drafts.append({'id':item.name,'name':document['name']})
        parent=inside(workspace,'artifacts')
        for item in sorted(parent.iterdir() if parent.exists() else []):
            if item.is_dir() and item.name.startswith('artifact-'):
                meta=metadata(workspace,item.name);artifacts.append({'id':item.name,'kind':meta.get('kind','asset'),'name':meta.get('filename',meta.get('kind','capture')),'created':meta['created']})
        return page('ingest.html',title='Ingest',drafts=drafts,artifacts=artifacts[-40:],widths=ingest_config().widths)
    if tail==['capture'] and method=='POST':
        data=fields(environ);urls=data.get('urls',[''])[0].split()
        result=capture(workspace,urls,data.get('widths',[''])[0] or None)
        return redirect('/ingest/artifacts/'+result['artifact'])
    if tail==['upload'] and method=='POST':
        data,(body,name)=multipart(environ)
        artifact=import_bytes(workspace,body,name,data.get('kind') or None)
        return redirect('/ingest/artifacts/'+artifact)
    if len(tail)>=2 and tail[0]=='artifacts':
        artifact_id=identifier(tail[1]);meta=metadata(workspace,artifact_id)
        if len(tail)==2 and method=='GET':
            return page('capture.html',title='Review source',artifact=artifact_id,metadata=meta,details=meta.get('details',{}))
        if len(tail)>=4 and tail[2]=='files' and method=='GET':
            name='/'.join(tail[3:])
            if name=='original':
                body,meta=read_artifact(workspace,artifact_id)
                fmt=inspect_format(body,'image')
                return static(body,'image.'+fmt)
            if not name.endswith(('.png','.jpg','.webp')):raise RequestError('Only captured images are served',404)
            return static(read_member(workspace,artifact_id,name),name)
    if tail==['draft'] and method=='POST':
        data=fields(environ);result=draft(library,workspace,data.get('artifact',[]),data.get('language',[''])[0])
        return redirect('/ingest/drafts/'+result['draft'])
    if len(tail)>=2 and tail[0]=='drafts':
        draft_id=identifier(tail[1]);root=folder(workspace,draft_id);load_draft(workspace,draft_id)
        action=tail[2] if len(tail)>=3 else None
        if action is None and method=='GET':
            result=summary(library,workspace,draft_id)
            slots=[{'scope':c+'.'+s['id'],'kind':s['asset_kind']} for c,v in load(library)['constructs'].items() for s in v['slots'] if s.get('asset_kind')]
            return page('draft.html',title='Draft '+draft_id,result=result,slots=slots,provenance_entries=inspect_sources(workspace,read_document(inside(root,'provenance.json'))))
        if action=='preview' and method=='GET' and len(tail)>=4:
            with stage(library,workspace,draft_id) as staged:files=preview_files(staged,draft_id)
            name='/'.join(tail[3:])
            if name not in files:raise RequestError('Unknown draft preview file',404)
            return static(files[name],name)
        if action=='promote' and method=='POST':
            data={k:v[0] for k,v in fields(environ).items()}
            promote_draft(library,workspace,draft_id,data['artifact'],data['asset_id'],data['kind'],data['variant'],
                          int(data['weight']) if data.get('weight') else None,data.get('style') or None,data.get('family') or None,data.get('scope') or None)
            return redirect('/ingest/drafts/'+draft_id)
        if action=='fidelity':
            if method=='POST':fidelity(library,workspace,draft_id);return redirect('/ingest/drafts/'+draft_id+'/fidelity')
            if method=='GET':
                path=inside(root,'fidelity','report.json');result=read_document(path) if path.exists() else None
                return page('fidelity.html',title='Fidelity review',draft_id=draft_id,result=result,stale=bool(result and result['version']!=digest(load_draft(workspace,draft_id))))
        if action=='questions' and method=='GET':
            return page('questions.html',title='Visual questions',draft_id=draft_id,questions=questions(workspace,draft_id))
        if action=='answer' and method=='POST':
            data=fields(environ);answer(library,workspace,draft_id,data['question'][0],data['candidate'][0])
            return redirect('/ingest/drafts/'+draft_id+'/questions')
        if action=='save' and method=='POST':
            result=save_draft(library,workspace,draft_id)
            if not result.get('saved'):raise RequestError('Draft has validation findings; review them before saving',422)
            return redirect('/languages/'+draft_id)
        if action=='files' and method=='GET' and len(tail)>=5:
            name='/'.join(tail[3:])
            if tail[3] not in {'questions','fidelity'} or not name.endswith(('.html','.css','.png','.jpg','.webp','.svg','.woff2','.woff','.ttf','.otf')):
                raise RequestError('Unknown draft artifact',404)
            return static(inside(root,name).read_bytes(),name)
    raise RequestError('Unknown ingest route',404)
