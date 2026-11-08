"""Immutable capture publication and the public capture.json projection."""
import json
from ..assets import inspect_format
from . import read_artifact
from .bundle import import_bundle
from .capture import group_problems


def publish_capture(workspace,files,pages,problems,assets):
    urls={page['id']:page['url'] for page in pages}
    problems=group_problems([{**item,'url':item.get('url',urls.get(item.get('page'),''))} for item in problems])
    for item in problems:item['width']=item['widths'][0] if item['widths'] else None
    captured=[];queries=set();fonts={};public_assets=[]
    for page in pages:
        if not page['views']:continue
        widths={}
        for view in page['views']:
            prefix=f'pages/{page["id"]}@{view["width"]}'
            paths={'screenshot':prefix+'.png','dom':prefix+'.html','styles':prefix+'.styles.json'}
            for field,source in [('screenshot','screenshot'),('dom','dom'),('styles','data')]:
                old=view[source]
                if old!=paths[field]:files[paths[field]]=files.pop(old)
                view[source]=paths[field]
            data=json.loads(files[paths['styles']]);queries.update(data.get('media_queries',[]))
            for face in data.get('font_faces',[]):
                face={**dict.fromkeys(('family','weight','style','src'),''),**face}
                fonts[json.dumps(face,sort_keys=True)]=face
            widths[str(view['width'])]=paths
        captured.append({**page,'name':page['id'],'widths':widths})
    for asset in assets:
        if asset['kind']=='font':continue
        data,meta=read_artifact(workspace,asset['artifact'])
        try:extension=inspect_format(data,asset['kind'])
        except ValueError:
            problems.append({'url':asset.get('url',''),'width':None,'widths':[],'pages':[],
                             'message':'Candidate format is not supported; original retained in its source artifact'})
            continue
        filename='assets/'+meta['sha256']+'.'+extension;files[filename]=data
        public_assets.append({**asset,'src':asset.get('url',''),'file':filename})
    document={'kind':'capture','pages':captured,'media_queries':sorted(queries),
              'fonts':list(fonts.values()),'assets':public_assets,'problems':problems}
    files['capture.json']=json.dumps(document,ensure_ascii=False).encode()
    # Internal details retain font originals and view references for the same
    # extraction path; capture.json is the pinned public projection of that data.
    details={'pages':captured,'problems':problems,'assets':assets}
    artifact=import_bundle(workspace,files,'capture',details)
    return {'artifact':artifact,'pages':[page['name'] for page in captured],'problems':problems}
