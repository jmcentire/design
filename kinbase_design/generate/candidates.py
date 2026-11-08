"""Inspectable candidates use the normal language writer, validator and preview renderer."""
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory
from ..language.versions import digest
from ..render import build_preview,preview_files
from ..storage import inside,save_language,save_working,read_json,write_json
from ..vocabulary import load
from .sessions import folder
from .theory import language


def materialize(library,workspace,state,values):
    document,_,_=language('candidate',load(library),values,state['resources'])
    version=digest(document);target=inside(folder(workspace,state['id']),'candidates',version)
    # Preview URLs and package paths serve different consumers. Keep both, also
    # repairing cached candidates created before package assets were materialized.
    shutil.copytree(inside(folder(workspace,state['id']),'assets'),inside(target,'assets'),dirs_exist_ok=True)
    if not (target/'sample.html').exists() or not (target/'swatch.html').exists():
        with TemporaryDirectory(prefix='kinbase-candidate-') as temporary:
            stage=Path(temporary);shutil.copytree(inside(library,'vocabulary'),stage/'vocabulary')
            save_language(stage,'candidate',document)
            shutil.copytree(inside(folder(workspace,state['id']),'assets'),stage/'languages/candidate/assets')
            build_preview(stage,'candidate',target)
            swatch=preview_files(stage,'candidate',{'swatch.html':{'title':'Direction specimen','instances':[
                {'construct':'hero'},{'construct':'listing-card'},{'construct':'form'}]}})
            (target/'swatch.html').write_bytes(swatch['swatch.html'])
        save_working(target/'working.json','candidate',document)
        (target/'sample.html').write_bytes((target/'index.html').read_bytes())
        write_json(target/'values.json',values)
    return {'hash':version,'preview':str(target.relative_to(Path(workspace).resolve())),'values':dict(values)}
