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
from .specimens import compositions

SPECIMEN_REVISION = 3


def materialize(library,workspace,state,values):
    document,_,_=language('candidate',load(library),values,state['resources'])
    version=digest(document);target=inside(folder(workspace,state['id']),'candidates',version)
    # Preview URLs and package paths serve different consumers. Keep both, also
    # repairing cached candidates created before package assets were materialized.
    shutil.copytree(inside(folder(workspace,state['id']),'assets'),inside(target,'assets'),dirs_exist_ok=True)
    marker=target/'specimen.json'
    current=read_json(marker).get('revision') if marker.exists() else None
    if current!=SPECIMEN_REVISION or not (target/'sample.html').exists() or not (target/'swatch.html').exists():
        with TemporaryDirectory(prefix='kinbase-candidate-') as temporary:
            stage=Path(temporary);shutil.copytree(inside(library,'vocabulary'),stage/'vocabulary')
            save_language(stage,'candidate',document)
            shutil.copytree(inside(folder(workspace,state['id']),'assets'),stage/'languages/candidate/assets')
            build_preview(stage,'candidate',target)
            # Vocabulary defaults supply public hooks for every advertised effect:
            # error-state.title is attention; listing-card.price is a label;
            # hero/card/form exercise type, surface, spacing, actions and shape.
            specimens=[{'construct':c} for c in ('hero','error-state','listing-card','form')]
            files=preview_files(stage,'candidate',{
                'sample.html':{'title':'Direction sample','instances':[{'construct':'nav'},*specimens,{'construct':'footer'}]},
                'swatch.html':{'title':'Direction specimen','instances':specimens},**compositions(document)})
            for name,data in files.items():
                if name.endswith('.html'):(target/name).write_bytes(data)
        save_working(target/'working.json','candidate',document)
        write_json(marker,{'revision':SPECIMEN_REVISION})
        write_json(target/'values.json',values)
    return {'hash':version,'preview':str(target.relative_to(Path(workspace).resolve())),'values':dict(values)}
