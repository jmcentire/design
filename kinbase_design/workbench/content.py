"""No-JavaScript content viewer over the same portable page assembly operation."""
import hashlib
import mimetypes
from ..content import page_files
from ..storage import inside, identifier, load_language


def handle(library, workspace, environ, segments, query, html):
    from . import RequestError
    if environ.get('REQUEST_METHOD','GET')!='GET':raise RequestError('Method not allowed',405)
    root = inside(workspace,'content')
    documents = {}
    if root.is_dir():
        for path in sorted(root.rglob('*.json')):
            if len(documents)>=200:break
            if path.is_symlink() or not path.is_file():continue
            relative = str(path.relative_to(root))
            inside(root,relative)
            key = hashlib.sha256(relative.encode()).hexdigest()[:16]
            documents[key] = {'name':relative,'path':path}
    if len(segments)==5 and segments[1]=='preview':
        language_id, key, filename = segments[2:]
        tail = filename
    elif len(segments)>5 and segments[1]=='preview':
        language_id,key = segments[2:4];tail = '/'.join(segments[4:])
    else:language_id = key = tail = None
    if tail is not None:
        if key not in documents:raise RequestError('Unknown content document',404)
        result, files = page_files(library,identifier(language_id),documents[key]['path'])
        if not result['validated']:raise RequestError('Content preview rejected; inspect the viewer findings',400)
        if tail not in files:raise RequestError('Unknown bundle resource',404)
        return 200,files[tail],mimetypes.guess_type(tail)[0] or 'application/octet-stream',[]
    if segments!=['content']:raise RequestError('Unknown content route',404)
    languages = []
    for folder in sorted(inside(library,'languages').iterdir()):
        if folder.is_dir() and (folder/'working.json').is_file():
            d = load_language(library,identifier(folder.name))
            languages.append({'id':folder.name,'name':d.get('name',folder.name)})
    key = query.get('document',[next(iter(documents),'')])[0]
    if key and key not in documents:raise RequestError('Unknown content document',404)
    ids = {d['id'] for d in languages}
    a = query.get('a',[languages[0]['id'] if languages else ''])[0]
    b = query.get('b',[''])[0]
    if (a and a not in ids) or (b and b not in ids):raise RequestError('Unknown language')
    try:width = int(query.get('width',['1280'])[0])
    except ValueError:raise RequestError('Invalid width') from None
    widths = [320,375,768,1280]
    if width not in widths:raise RequestError('Choose a supported viewport width')
    previews = []
    if key:
        for language_id in dict.fromkeys([a,b]):
            if not language_id:continue
            result, _ = page_files(library,language_id,documents[key]['path'])
            previews.append({'id':language_id,'report':result,'src':f'/content/preview/{language_id}/{key}/index.html'})
    return 200,html('content.html',title='Content pages',documents=documents,languages=languages,
                    selected=key,a=a,b=b,width=width,widths=widths,previews=previews), 'text/html; charset=utf-8',[]
