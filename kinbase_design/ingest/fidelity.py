"""Private reconstruction and measured fidelity, using the shared preview renderer."""
from copy import deepcopy
import json
from pathlib import Path
from ..artifacts import read_artifact
from ..artifacts.bundle import read_member
from ..artifacts.runtime import run_job
from ..assets import inspect_format
from ..config import CAPTURE_WIDTHS, INGEST_COLOR_DELTA_E, INGEST_TYPE_RATIO_TOLERANCE, INGEST_SPACE_TOLERANCE_PX, INGEST_TYPE_TOLERANCE_PX
from ..findings import Finding,report
from ..language.versions import digest
from ..language.tokens import Tokens
from ..render import preview_files
from ..render.styles import FONT_FORMAT_HINTS
from ..storage import inside,read_json,write_json
from .staging import folder,load_draft,stage
from .quantize import measurements,delta_e


def compare(source,reconstructed):
    source_facts=measurements([source]);actual=measurements([reconstructed]);issues=[]
    palette=[]
    for entry in source_facts['palette']:
        nearest=min(actual['palette'],key=lambda item:delta_e(entry['value'],item['value']),default=None)
        distance=round(delta_e(entry['value'],nearest['value']),4) if nearest else None
        palette.append({'source':entry['value'],'reconstruction':nearest['value'] if nearest else None,'delta_e':distance})
        if distance is None or distance>INGEST_COLOR_DELTA_E:issues.append('Palette divergence: '+entry['value'])
        if len(entry['value'])==9:issues.append('Translucent colour requires review against its captured surface: '+entry['value'])
    fonts=[]
    normalized=lambda family:tuple(f.strip().strip('\"\'').lower() for f in family.split(','))
    source_loaded={f.get('family','').strip('\"\'').lower() for f in source.get('font_faces',[]) if f.get('status')=='loaded'}
    actual_loaded={f.get('family','').strip('\"\'').lower() for f in reconstructed.get('font_faces',[]) if f.get('status')=='loaded'}
    for family in source_facts['font_families']:
        first=normalized(family)[0]
        match=normalized(family) in [normalized(f) for f in actual['font_families']] and (first not in source_loaded or first in actual_loaded)
        fonts.append({'source':family,'match':match,'face_loaded':first in actual_loaded if first in source_loaded else None})
        if not match:issues.append('Font family differs: '+family)
    ratios=[]
    sizes=[]
    for size in source_facts['type_scale']:
        nearest=min(actual['type_scale'],key=lambda s:abs(s-size),default=None)
        sizes.append({'source':size,'reconstruction':nearest,'ratio':nearest/size if nearest is not None and size else None})
        if nearest is None or abs(size-nearest)>INGEST_TYPE_TOLERANCE_PX:issues.append('Type size differs: '+str(size)+'px')
    for ratio in source_facts['type_scale_ratios']:
        nearest=min(actual['type_scale_ratios'],key=lambda r:abs(r-ratio),default=None)
        ratios.append({'source':ratio,'reconstruction':nearest})
        if nearest is None or abs(ratio-nearest)>INGEST_TYPE_RATIO_TOLERANCE:issues.append('Type scale ratio differs: '+str(ratio))
    spacing={'source':source_facts['spacing_base'],'reconstruction':actual['spacing_base']}
    if abs(spacing['source']-spacing['reconstruction'])>INGEST_SPACE_TOLERANCE_PX:issues.append('Spacing base differs')
    return {'palette':palette,'font_family_match':fonts,'type_scale_ratio':ratios,'type_scale':sizes,'spacing_base':spacing,
            'source':source_facts,'reconstruction':actual},issues


def reconstruct(library,workspace,draft_id):
    root=folder(workspace,draft_id);state=read_json(inside(root,'state.json'));document=load_draft(workspace,draft_id)
    output=inside(root,'fidelity');output.mkdir(parents=True,exist_ok=True)
    compositions={};pairs=[];private_files={};notes=[]
    assets={a.get('url'):a for a in state['assets'] if a.get('url')}
    for index,entry in enumerate(state['views'],1):
        view=read_json(inside(root,entry['file']));instances=[]
        for original in view['instances']:
            item={k:deepcopy(original[k]) for k in ('construct','values')};item['media']={}
            for slot,images in original['media'].items():
                if slot in document.get('components',{}).get(item['construct'],{}).get('assets',{}):continue
                for image in images:
                    candidate=assets.get(image['url'])
                    if candidate:
                        data,meta=read_artifact(workspace,candidate['artifact'])
                        try:fmt=inspect_format(data,'image')
                        except Exception as exc:
                            notes.append('Captured image unavailable for reconstruction: '+str(exc)[:150]);continue
                        name='assets/reference-'+meta['sha256']+'.'+fmt;private_files[name]=data
                        item['media'].setdefault(slot,[]).append({'src':name,'alt':image['alt']})
                    else:notes.append('Captured media was not downloaded; retained as a fidelity gap')
            instances.append(item)
        filename=f'page-{index}.html';compositions[filename]={'title':view.get('title',view['page']),'instances':instances}
        capture=f'capture-{index}.png';private_files[capture]=read_member(workspace,entry['artifact'],entry['screenshot'])
        pairs.append({'page':view['page'],'width':view['width'],'capture':capture,'html':filename,
                      'reconstruction':f'reconstruction-{index}.png','source':entry['file']})
    if not pairs:
        for index,reference in enumerate(state['references'],1):
            data,meta=read_artifact(workspace,reference['artifact']);fmt=inspect_format(data,'image')
            capture=f'reference-{index}.{fmt}';private_files[capture]=data
            for width in CAPTURE_WIDTHS:
                filename=f'reference-{index}-{width}.html';compositions[filename]={'title':'Imported visual reference','instances':[{'construct':'content-section'}]}
                pairs.append({'page':f'reference-{index}','width':width,'capture':capture,'html':filename,'reconstruction':f'reference-{index}-{width}.png','source':None})
        if not pairs:
            compositions['index.html']={'title':'Draft visual review','instances':[{'construct':'content-section'},{'construct':'listing-card'}]}
            notes.append('No captured page or image reference is available; comparisons require a visual source')
    with stage(library,workspace,draft_id) as staged:files=preview_files(staged,draft_id,compositions)
    # Private captured fonts may be used for review without entering the shared asset manifest.
    faces=[];used=set()
    tokens=Tokens(document['style'])
    bound_families={tokens.evaluate(name)[1].split(',')[0].strip('\"\'') for name,node in tokens.nodes.items()
                    if node.get('$type')=='fontFamily' and tokens.font_asset(name)}
    for entry in state['views']:
        view=read_json(inside(root,entry['file']))
        for face in view.get('font_faces',[]):
            family=face.get('family','').strip('\"\'')
            if family in bound_families:continue
            if not face.get('src') and any(f.get('src') and f.get('family','').strip('\"\'')==family for f in view.get('font_faces',[])):continue
            candidates=[a for a in state['assets'] if a['kind']=='font' and (a.get('filename','') in face.get('src','') or family.replace(' ','').lower() in a.get('filename','').replace('-','').lower())]
            if len(candidates)!=1:
                if family:notes.append('Captured font face not uniquely matched to an original: '+family)
                continue
            candidate=candidates[0]
            key=(family,face.get('weight') or '400',face.get('style') or 'normal',candidate['artifact'])
            if key in used:continue
            used.add(key)
            data,meta=read_artifact(workspace,candidate['artifact'])
            try:fmt=inspect_format(data,'font')
            except Exception as exc:notes.append('Captured font unavailable: '+str(exc)[:150]);continue
            name='assets/reference-'+meta['sha256']+'.'+fmt;private_files[name]=data
            # CSS strings are encoded, never interpolated as executable declarations.
            import re
            if not re.fullmatch(r'[\w -]+',family) or not re.fullmatch(r'\d+(?: \d+)?',key[1]) or key[2] not in {'normal','italic'}:continue
            faces.append('@font-face{font-family:'+json.dumps(family)+';src:url("'+name+'") format("'+FONT_FORMAT_HINTS[fmt]+'");font-weight:'+key[1]+';font-style:'+key[2]+'}')
    files['language.css']+=('\n'+'\n'.join(faces)).encode()
    if any(name.startswith('assets/reference-') for name in private_files):
        notes.append('Unpromoted source assets are used privately for this reconstruction; promote them to include them in the shared language')
    files.update(private_files)
    for name,data in files.items():
        path=inside(output,name);path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
    return {'draft':draft_id,'output':str(output),'root':str(root),'pairs':pairs,'notes':notes,'version':digest(document)}


def fidelity(library,workspace,draft_id):
    job=reconstruct(library,workspace,draft_id)
    rendered=run_job('kinbase_design.ingest.fidelity_worker',job)
    document=load_draft(workspace,draft_id);findings=[]
    for note in job['notes']+rendered['issues']:
        findings.append(Finding('coverage','fidelity',f'drafts/{draft_id}/working.json','',document,
                                'reconstruction within measured tolerances',note).to_dict())
    result={**report(draft_id,findings),'draft':draft_id,'version':job['version'],'pairs':rendered['pairs'],
            'tolerances':{'color_delta_e':INGEST_COLOR_DELTA_E,'type_ratio':INGEST_TYPE_RATIO_TOLERANCE,'space_px':INGEST_SPACE_TOLERANCE_PX},
            'standards':'unknown (Kinbase unconnected)'}
    write_json(inside(job['output'],'report.json'),result)
    return result
