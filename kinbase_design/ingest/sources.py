"""Read immutable captures and imports. No extraction step accesses the network."""
from io import BytesIO
import json
from pathlib import Path
from PIL import Image
from ..artifacts import read_artifact
from ..artifacts.bundle import metadata, read_member
from ..artifacts.capture import media_widths, group_problems
from ..config import INGEST_IMAGE_SAMPLE_SIZE
from ..language.tokens import Tokens
from .quantize import px
from .dom import content_nodes


def image_colors(data):
    with Image.open(BytesIO(data)) as image:
        image.thumbnail((INGEST_IMAGE_SAMPLE_SIZE,INGEST_IMAGE_SAMPLE_SIZE))
        samples=image.convert('RGB').quantize(colors=16).convert('RGB').getcolors(INGEST_IMAGE_SAMPLE_SIZE**2) or []
        return ['#'+''.join(f'{c:02x}' for c in rgb) for count,rgb in sorted(samples,reverse=True)]


def collect(workspace, artifact_ids):
    result={'views':[],'tokens':[],'colors':[],'assets':[],'references':[],'problems':[],'briefs':[],
            'source_facts':{'font_families':[],'type_scale':[],'spacing':[],'radii':[],'breakpoints':[]}}
    seen=set()
    def visit(artifact,source_artifact=None,source_location=''):
        if artifact in seen:return
        seen.add(artifact);meta=metadata(workspace,artifact);kind=meta.get('kind','asset')
        source_artifact=source_artifact or artifact
        if kind=='capture':
            details=meta['details'];result['assets'].extend(details.get('assets',[]));result['problems'].extend(details.get('problems',[]))
            for page in details['pages']:
                for view in page['views']:
                    data=json.loads(read_member(workspace,artifact,view['data']))
                    if view.get('dom') in meta.get('members',{}):
                        data['structure']=content_nodes(data,read_member(workspace,artifact,view['dom']).decode('utf-8',errors='replace'))
                    result['views'].append({**data,**view,'page':page['id'],'artifact':artifact,'url':page['url'],
                                            'breakpoints':media_widths(data.get('media_queries',[]))})
        elif kind=='figma-export':
            for child in meta['details']['children']:visit(child['artifact'],source_artifact,child['location'])
        else:
            data,meta=read_artifact(workspace,artifact)
            filename=meta['filename'];suffix=Path(filename).suffix.lower()
            if kind=='dtcg' or suffix=='.json':
                try:
                    tree=json.loads(data)
                    if not isinstance(tree,dict):raise ValueError('DTCG import must be an object')
                    result['tokens'].append({'artifact':source_artifact,'location':source_location,'tree':tree})
                    tokens=Tokens(tree)
                    for name in tokens.nodes:
                        try:
                            token_type,value=tokens.evaluate(name)
                            if token_type=='color':result['colors'].append(value)
                            elif token_type=='fontFamily':result['source_facts']['font_families'].append(value)
                            elif token_type=='dimension':
                                number=px(value) if value.endswith('px') else float(value[:-3])*16
                                # A type size is positive and is not a tracking or leading value that
                                # happens to carry "text" in its name ("text-title--letter-spacing").
                                sized=number>0 and not any(s in name.lower() for s in ('letter-spacing','tracking','line-height','leading'))
                                group='breakpoints' if name.startswith('breakpoint.') else 'spacing' if name.startswith('space.') else 'radii' if 'radius' in name or 'radii' in name else 'type_scale' if sized and any(s in name.lower() for s in ('font','type','text')) else None
                                if group:result['source_facts'][group].append(number)
                        except (ValueError,KeyError) as exc:result['problems'].append({'artifact':artifact,'message':f'{name}: {exc}'})
                except (ValueError,UnicodeError) as exc:result['problems'].append({'artifact':artifact,'message':str(exc)})
            elif kind=='brief':
                result['briefs'].append({'artifact':artifact,'text':data.decode('utf-8',errors='replace')})
            if kind in {'image','mock','wireframe'} or suffix in {'.png','.jpg','.jpeg','.webp'}:
                try:
                    result['colors'].extend(image_colors(data))
                    result['references'].append({'artifact':artifact,'filename':filename})
                except (OSError,ValueError) as exc:result['problems'].append({'artifact':artifact,'message':'Image sampling: '+str(exc)})
            if kind in {'asset','image'}:
                result['assets'].append({'artifact':artifact,'kind':'font' if suffix in {'.woff','.woff2','.ttf','.otf'} else 'image','filename':filename})
    for artifact in artifact_ids:visit(artifact)
    result['problems']=group_problems(result['problems'])
    return result
