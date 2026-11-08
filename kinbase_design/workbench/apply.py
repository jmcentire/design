"""Server-rendered Apply selection, findings, export and hand-off."""
import mimetypes
from ..export import export
from ..export.adapters import ADAPTERS
from ..export.handoff import prepare,read_selection,apply,read_handoff
from ..storage import inside,identifier,load_language
from .ingest import fields


def handle(library,workspace,environ,segments,query,html):
    from . import RequestError
    method=environ['REQUEST_METHOD'];tail=segments[1:]
    def page(template,**context):return 200,html(template,**context),'text/html; charset=utf-8',[]
    def redirect(path):return 303,b'','text/html; charset=utf-8',[('Location',path)]
    if not tail:
        if method=='GET':
            languages=[];root=inside(library,'languages')
            for folder in sorted(root.iterdir() if root.exists() else []):
                if (folder/'working.json').is_file():languages.append(load_language(library,folder.name))
            return page('apply-start.html',title='Apply a language',languages=languages,adapters=ADAPTERS)
        if method=='POST':
            data={k:v[0] for k,v in fields(environ).items()}
            if data.get('action','handoff')=='handoff':
                result=apply(library,workspace,data['language'],data['site'],data['adapter'],
                             data.get('target_dir'),data.get('page_urls','').split(),data.get('branch')=='yes')
                return redirect('/apply/handoffs/'+result['handoff'])
            if data['action']!='review':raise RequestError('Unknown Apply action')
            selection=prepare(library,workspace,data['language'],data['site'],data['adapter'],
                              data.get('target_dir'),data.get('page_urls','').split(),data.get('branch')=='yes')
            return redirect('/apply/reviews/'+selection['id'])
    if len(tail)>=2 and tail[0]=='reviews':
        selection_id=identifier(tail[1]);selection=read_selection(library,workspace,selection_id)
        base='/apply/reviews/'+selection_id
        if len(tail)==2 and method=='GET':
            exported=inside(workspace,'apply',selection_id,'export').is_dir()
            return page('apply-review.html',title='Apply findings',selection=selection,exported=exported)
        if len(tail)==3 and method=='POST':
            if tail[2]=='export':
                export(library,selection['language_id'],selection['adapter'],inside(workspace,'apply',selection_id,'export'))
                return redirect(base)
            if tail[2]=='handoff':
                result=apply(library,workspace,selection['language_id'],selection['site'],selection['adapter'],
                             selection['target_dir'],selection['page_urls'],selection['branch'])
                return redirect('/apply/handoffs/'+result['handoff'])
    if len(tail)>=2 and tail[0]=='handoffs' and method=='GET':
        handoff_id=identifier(tail[1]);record=read_handoff(workspace,handoff_id)
        if len(tail)==2:return page('apply-handoff.html',title='Apply hand-off',record=record)
        name='/'.join(tail[2:])
        if name not in record['files'] and name!='handoff.json':raise RequestError('Unknown hand-off file',404)
        path=inside(workspace,'handoffs',handoff_id,name)
        return 200,path.read_bytes(),mimetypes.guess_type(name)[0] or 'application/octet-stream',[]
    raise RequestError('Unknown Apply route',404)
