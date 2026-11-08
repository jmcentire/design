"""Promote fixed inputs through the existing asset operation; retain original source tokens."""
from copy import deepcopy
from io import BytesIO
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory
from fontTools.ttLib import TTFont
from ..artifacts import import_bytes,read_artifact
from ..assets import promote,asset_path
from ..ingest.sources import collect
from ..storage import inside,save_language,load_language
from .sessions import folder

LOGO=b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 40"><path d="M4 16 Q18 0 32 16 T60 16 T88 16 T116 16 M4 28 Q18 12 32 28 T60 28 T88 28 T116 28" fill="none" stroke="#17656e" stroke-width="5"/></svg>'
IMAGE=b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 600 400"><rect width="600" height="400" fill="#d7eff2"/><circle cx="480" cy="80" r="35" fill="#f6cf65"/><path d="M0 190 Q150 150 300 190 T600 190 V400 H0Z" fill="#459b9b"/><path d="M0 300 Q150 220 330 290 T600 270 V400 H0Z" fill="#f5e4be"/></svg>'


def prepare(library,workspace,session,artifacts):
    root=folder(workspace,session);sources=collect(workspace,artifacts)
    result={'tokens':sources['tokens'],'assets':{},'bindings':{},'origins':{},'notes':sources['problems'],
            'briefs':sources['briefs'],'colors':sources['colors']}
    with TemporaryDirectory(prefix='kinbase-generate-assets-') as temp:
        temp=Path(temp);save_language(temp,'resources',{'id':'resources','assets':{}})
        def add(artifact,asset,kind,weight=None,family=None):
            promote(temp,workspace,'resources',artifact,asset,kind,'primary',weight,'normal',family)
            result['origins'][asset]=artifact
            if kind!='font':result['bindings'][kind]=asset+':primary'
        for kind,data in [('logo',LOGO),('image',IMAGE)]:
            artifact=import_bytes(workspace,data,'sample-'+kind+'.svg','asset')
            add(artifact,'sample-'+kind,kind)
        supplied=list(sources['assets'])
        for reference in sources['references']:
            if not any(item.get('artifact')==reference['artifact'] for item in supplied):
                supplied.append({**reference,'kind':'image'})
        for index,item in enumerate(supplied):
            artifact=item.get('artifact')
            if not artifact:continue
            data,meta=read_artifact(workspace,artifact);kind=item.get('kind','image')
            # A named logo (or SVG asset) is treated as a logo; raster images remain imagery.
            if kind!='font' and ('logo' in meta['filename'].lower() or meta.get('kind')=='asset' and meta['filename'].lower().endswith('.svg')):kind='logo'
            asset='supplied-'+str(index+1)
            if kind=='font':
                family='Supplied Font '+str(index+1);weight=400
                try:
                    with TTFont(BytesIO(data)) as font:
                        family=font['name'].getDebugName(1) or family
                        weight=int(font['OS/2'].usWeightClass)
                except (ImportError,KeyError):
                    result['notes'].append({'message':'Font metadata decoder unavailable; original font registered under a local family alias at weight 400'})
                # CSS registration may use an alias even when original metadata has punctuation.
                import re
                family=re.sub(r'[^\w -]','',family) or 'Supplied Font'
                add(artifact,asset,kind,weight,family)
                result['font']={'asset':asset,'artifact':artifact,'family':family,'weight':weight}
            else:add(artifact,asset,kind)
        result['assets']=load_language(temp,'resources')['assets']
        shutil.copytree(temp/'languages/resources/assets',inside(root,'assets'),dirs_exist_ok=True)
    return result
