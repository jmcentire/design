"""Before/after injection through the same anonymous browser capture boundary."""
import base64
import json
import mimetypes
from ..artifacts.bundle import read_member
from ..artifacts.capture import public_url, widths
from ..artifacts.runtime import run_job
from ..config import ingest_config


def injected_css(files, adapter):
    names=['tokens.css','roles.css'] if adapter=='generic' else ['theme.css']
    css='\n'.join(files[name].decode() for name in names)
    for name,data in sorted(files.items()):
        if not name.startswith('assets/'):continue
        mime=mimetypes.guess_type(name)[0] or 'application/octet-stream'
        uri='data:'+mime+';base64,'+base64.b64encode(data).decode()
        css=css.replace('url("'+name+'")','url("'+uri+'")')
    return css


def screenshots(workspace, urls, files, adapter):
    settings=ingest_config()
    urls=list(dict.fromkeys(public_url(url) for url in urls))
    if not urls or len(urls)>settings.max_pages:raise ValueError(f'Apply screenshots require 1–{settings.max_pages} page URLs')
    result=run_job('kinbase_design.artifacts.capture_worker',{
        'workspace':str(workspace),'urls':urls,'widths':widths(settings.widths),
        'settings':settings.to_dict(),'injected_css':injected_css(files,adapter)})
    captured=json.loads(read_member(workspace,result['artifact'],'capture.json'))
    pairs=[];images={}
    for page in captured['pages']:
        for view in page['views']:
            if not view.get('injected'):raise ValueError('Injected preview could not be rendered: '+json.dumps(result['problems']))
            prefix=page['name']+'@'+str(view['width'])
            before='screenshots/'+prefix+'-before.png';after='screenshots/'+prefix+'-injected.png'
            images[before]=read_member(workspace,result['artifact'],view['screenshot'])
            images[after]=read_member(workspace,result['artifact'],view['injected'])
            pairs.append({'url':page['url'],'page':page['name'],'width':view['width'],'before':before,'after':after,
                          'label':'Injected preview — exported stylesheet, not the site’s real build'})
    if {p['url'] for p in captured['pages']} != set(urls):
        raise ValueError('Some Apply pages could not be captured: '+json.dumps(result['problems']))
    return {'pairs':pairs,'problems':result['problems'],'artifact':result['artifact']},images
