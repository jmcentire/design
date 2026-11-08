"""Private reconstruction and measured fidelity, using the shared preview renderer."""
from .documents import read_document, write_document
from copy import deepcopy
from dataclasses import replace
import json
import hashlib
import re
from pathlib import Path
from ..artifacts import read_artifact
from ..artifacts.bundle import read_member
from ..artifacts.runtime import run_job
from ..assets import inspect_format
from ..artifacts.media import image_format
from ..config import IngestConfig, ingest_config, INGEST_FULL_RADIUS_PX, INGEST_ROW_TOLERANCE_PX
from ..findings import Finding,report,pointer,location
from ..language.versions import digest
from ..language.tokens import Tokens
from ..render import preview_files
from ..render.styles import FONT_FORMAT_HINTS
from ..storage import inside
from .staging import folder,load_draft,stage
from .quantize import measurements,delta_e,color_distance_key
from .reporting import fidelity_facts
from .arrangement import compose


def compare(source,reconstructed,settings=None,draft_palette=None):
    settings=settings or IngestConfig()
    source_facts=measurements([source],settings=settings);actual=measurements([reconstructed],settings=settings);issues=[];divergences=[]
    def issue(message,*path):
        issues.append(message);divergences.append({'message':message,'pointer':pointer(*path)})
    exact=replace(settings,type_size_px=0,radius_px=0)
    source_values=measurements([source],settings=exact);actual_values=measurements([reconstructed],settings=exact)
    palette=[]
    choices=[m['value'] for group in actual['palette'] for m in group['members']]
    for value in dict.fromkeys(m['value'] for group in source_facts['palette'] for m in group['members']):
        nearest=min(choices,key=lambda item:color_distance_key(value,item),default=None)
        distance=round(delta_e(value,nearest),4) if nearest else None
        entry={'source':value,'reconstruction':nearest,'delta_e':distance}
        if draft_palette is not None:
            token=min(draft_palette,key=lambda item:color_distance_key(value,item),default=None)
            token_distance=round(delta_e(value,token),4) if token else None
            entry.update(token_value=token,token_delta_e=token_distance)
            if token_distance is None or token_distance>settings.color_delta_e:issue('Draft palette token divergence: '+value,'palette',len(palette),'token_delta_e')
        palette.append(entry)
        if distance is None or distance>settings.color_delta_e:issue('Palette divergence: '+value,'palette',len(palette)-1,'delta_e')
        if len(value)==9:issue('Translucent colour requires review against its captured surface: '+value,'palette',len(palette)-1,'source')
    fonts=[]
    normalized=lambda family:tuple(f.strip().strip('\"\'').lower() for f in family.split(','))
    source_loaded={f.get('family','').strip('\"\'').lower() for f in source.get('font_faces',[]) if f.get('status')=='loaded'}
    actual_loaded={f.get('family','').strip('\"\'').lower() for f in reconstructed.get('font_faces',[]) if f.get('status')=='loaded'}
    for family in source_facts['font_families']:
        first=normalized(family)[0]
        match=normalized(family) in [normalized(f) for f in actual['font_families']] and (first not in source_loaded or first in actual_loaded)
        rendered=next((f for f in actual['font_families'] if normalized(f)==normalized(family)),next(iter(actual['font_families']),None))
        fonts.append({'source':family,'reconstruction':rendered,'match':match,'face_loaded':first in actual_loaded if first in source_loaded else None})
        if not match:issue('Font family differs: '+family,'font_family_match',len(fonts)-1,'match')
    ratios=[]
    sizes=[]
    for size in source_values['type_scale']:
        nearest=min(actual_values['type_scale'],key=lambda s:abs(s-size),default=None)
        sizes.append({'source':size,'reconstruction':nearest,'ratio':nearest/size if nearest is not None and size else None})
        if nearest is None or abs(size-nearest)>settings.type_size_px:issue('Type size differs: '+str(size)+'px','type_scale',len(sizes)-1,'reconstruction')
    for ratio in source_facts['type_scale_ratios']:
        nearest=min(actual['type_scale_ratios'],key=lambda r:abs(r-ratio),default=None)
        ratios.append({'source':ratio,'reconstruction':nearest})
        if nearest is None or abs(ratio-nearest)>settings.type_ratio:issue('Type scale ratio differs: '+str(ratio),'type_scale_ratio',len(ratios)-1,'reconstruction')
    spacing={'source':source_facts['spacing_base'],'reconstruction':actual['spacing_base']}
    if abs(spacing['source']-spacing['reconstruction'])>settings.spacing_px:issue('Spacing base differs','spacing_base','reconstruction')
    radii=[]
    actual_radii=[INGEST_FULL_RADIUS_PX if r=='full' else r for r in actual_values['radii']]
    for radius in source_values['radii']:
        radius=INGEST_FULL_RADIUS_PX if radius=='full' else radius
        nearest=min(actual_radii,key=lambda r:abs(r-radius),default=None)
        radii.append({'source':radius,'reconstruction':nearest})
        if nearest is None or abs(radius-nearest)>settings.radius_px:issue('Radius differs: '+str(radius)+'px','radii',len(radii)-1,'reconstruction')
    return {'palette':palette,'font_family_match':fonts,'type_scale_ratio':ratios,'type_scale':sizes,'spacing_base':spacing,
            'radii':radii,'source':source_facts,'reconstruction':actual,'divergences':divergences},issues


def reconstruct(library,workspace,draft_id,settings=None):
    settings=settings or ingest_config()
    root=folder(workspace,draft_id);state=read_document(inside(root,'state.json'));document=load_draft(workspace,draft_id)
    output=inside(root,'fidelity');output.mkdir(parents=True,exist_ok=True)
    compositions={};pairs=[];private_files={};notes=[]
    assets={a.get('url'):a for a in state['assets'] if a.get('url')}
    responsive={};inline_images={}
    for entry in state['views']:
        source_view=read_document(inside(root,entry['file']))
        for candidate in source_view.get('candidates',[]):
            if candidate.get('url') in assets:responsive.setdefault((entry['page'],candidate.get('selector')),[]).append(candidate['url'])
            if candidate.get('inline'):inline_images[candidate['url']]=candidate['inline']
    def reference(image,page):
        if image['url'] in inline_images:
            data=inline_images[image['url']]
            if re.fullmatch(r'#[0-9a-fA-F]{6}(?:[0-9a-fA-F]{2})?',image.get('color') or ''):data=data.replace('currentColor',image['color'])
            data=data.encode('utf-8')
            try:fmt=inspect_format(data,'image')
            except ValueError:
                notes.append('Captured inline image is not safe for reconstruction');return None
            name='assets/reference-'+hashlib.sha256(data).hexdigest()+'.'+fmt;private_files[name]=data
            return {'src':name,'alt':image.get('alt','')}
        candidate=assets.get(image['url'])
        if not candidate and responsive.get((page,image.get('selector'))):
            candidate=assets[responsive[page,image['selector']][0]]
            notes.append('Responsive source image reused from another captured width: '+page)
        if not candidate:
            notes.append('Captured media was not downloaded; retained as a fidelity gap');return None
        data,meta=read_artifact(workspace,candidate['artifact'])
        try:fmt=image_format(data)
        except Exception as exc:
            notes.append('Captured image unavailable for reconstruction: '+str(exc)[:150]);return None
        name='assets/reference-'+meta['sha256']+'.'+fmt;private_files[name]=data
        return {'src':name,'alt':image.get('alt','')}
    for index,entry in enumerate(state['views'],1):
        view=read_document(inside(root,entry['file']));instances=[]
        for original in view['instances']:
            item={k:deepcopy(original[k]) for k in ('construct','values')};item['media']={}
            for key in ('selector','parent','box','treatment','hrefs','accessible_names','fragments','flow','heading_levels'):
                if key in original:item[key]=deepcopy(original[key])
            item['action_icons']={}
            for slot,icon in original.get('action_icons',{}).items():
                rendered=reference(icon,view['page'])
                if rendered:
                    rendered['element']=icon.get('element','a')
                    box=icon.get('box');parent_box=original.get('box')
                    if box:rendered.update(width=box[2],height=box[3])
                    if box and parent_box:rendered.update(top=max(0,box[1]-parent_box[1]),right=max(0,parent_box[0]+parent_box[2]-box[0]-box[2]))
                    item['action_icons'][slot]=rendered
            if original.get('background_media'):item['background']=reference(original['background_media'],view['page'])
            for slot,images in original['media'].items():
                if slot in document.get('components',{}).get(item['construct'],{}).get('assets',{}):
                    # Keep approved bindings visible even when no captured copy is supplied.
                    binding=document['components'][item['construct']]['assets'][slot];asset,variant=binding.split(':')
                    detail=document['assets'][asset]['variants'][variant]
                    item['media'][slot]=[{'src':f'assets/{asset}-{variant}.{detail["format"]}','alt':images[0].get('alt','') if images else ''}];continue
                for image in images:
                    rendered=reference(image,view['page'])
                    if rendered:
                        if image.get('aspect_ratio'):rendered['aspect_ratio']=image['aspect_ratio']
                        item['media'].setdefault(slot,[]).append(rendered)
            instances.append(item)
        top=compose(instances,view.get('groups',[]))
        for item in instances:
            measured=[child for child in item.get('children',[]) if child.get('box')]
            if measured and not item.get('flow'):
                y=min(child['box'][1] for child in measured)
                item['columns']=sum(abs(child['box'][1]-y)<=INGEST_ROW_TOLERANCE_PX for child in measured)
        bottom=0
        for item in top:
            box=item.get('box')
            if not box:continue
            if item.get('construct')=='nav' and any(other.get('background') and other.get('box') and other['box'][1]<box[1]+box[3] for other in top):
                item['geometry']={'overlay':True};continue
            inset=max(0,min(box[0],view['width']-box[0]-box[2]))
            item['geometry']={'inset':inset,'gap':max(0,box[1]-bottom),'height':box[3]}
            bottom=max(bottom,box[1]+box[3])
        filename=f'page-{index}.html';compositions[filename]={'title':view.get('title',view['page']),'instances':top,'captured':True,
                                                           'spacing_base':measurements([view],settings=settings)['spacing_base']}
        capture=f'capture-{index}.png';private_files[capture]=read_member(workspace,entry['artifact'],entry['screenshot'])
        pairs.append({'page':view['page'],'width':view['width'],'capture':capture,'html':filename,
                      'reconstruction':f'reconstruction-{index}.png','source':entry['file']})
    if not pairs:
        for index,reference in enumerate(state['references'],1):
            data,meta=read_artifact(workspace,reference['artifact']);fmt=inspect_format(data,'image')
            if fmt!='png':
                from io import BytesIO
                from PIL import Image
                with Image.open(BytesIO(data)) as image:
                    output_png=BytesIO();image.convert('RGBA').save(output_png,format='PNG');data=output_png.getvalue()
            capture=f'reference-{index}.png';private_files[capture]=data
            for width in settings.widths:
                filename=f'reference-{index}-{width}.html';compositions[filename]={'title':'Imported visual reference','instances':[{'construct':'content-section'}]}
                pairs.append({'page':f'reference-{index}','width':width,'capture':capture,'html':filename,'reconstruction':f'reference-{index}-{width}.png','source':None})
        if not pairs:
            compositions['index.html']={'title':'Draft visual review','instances':[{'construct':'content-section'},{'construct':'card'}]}
            notes.append('No captured page or image reference is available; comparisons require a visual source')
    with stage(library,workspace,draft_id) as staged:files=preview_files(staged,draft_id,compositions)
    # Private captured fonts may be used for review without entering the shared asset manifest.
    faces=[];used=set()
    tokens=Tokens(document['style'])
    bound_families={tokens.evaluate(name)[1].split(',')[0].strip('\"\'') for name,node in tokens.nodes.items()
                    if node.get('$type')=='fontFamily' and tokens.font_asset(name)}
    for entry in state['views']:
        view=read_document(inside(root,entry['file']))
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
            if not re.fullmatch(r'[\w -]+',family) or not re.fullmatch(r'\d+(?: \d+)?',key[1]) or key[2] not in {'normal','italic'}:continue
            faces.append('@font-face{font-family:'+json.dumps(family)+';src:url("'+name+'") format("'+FONT_FORMAT_HINTS[fmt]+'");font-weight:'+key[1]+';font-style:'+key[2]+'}')
    files['language.css']+=('\n'+'\n'.join(faces)).encode()
    if any(name.startswith('assets/reference-') for name in private_files):
        notes.append('Unpromoted source assets are used privately for this reconstruction; promote them to include them in the shared language')
    files.update(private_files)
    for name,data in files.items():
        path=inside(output,name);path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
    return {'draft':draft_id,'output':str(output),'root':str(root),'pairs':pairs,'notes':notes,'version':digest(document),
            'settings':settings.to_dict(),'palette':[value for name in tokens.nodes for kind,value in [tokens.evaluate(name)] if kind=='color']}


def fidelity(library,workspace,draft_id,settings=None):
    settings=settings or ingest_config()
    job=reconstruct(library,workspace,draft_id,settings)
    rendered=run_job('kinbase_design.ingest.fidelity_worker',job)
    findings=[];described=set();file=f'drafts/{draft_id}/fidelity/report.json'
    for index,pair in enumerate(rendered['pairs']):
        for entry in (pair.get('facts') or {}).get('divergences',[]):
            path,observed=location(pair['facts'],entry['pointer'])
            message=f'{pair["page"]}@{pair["width"]}: '+entry['message'];described.add(message)
            findings.append(Finding('coverage','fidelity',file,pointer('pairs',index,'facts')+path,observed,
                                    'reconstruction within measured tolerances',message).to_dict())
    notes=list(dict.fromkeys(job['notes']+[note for note in rendered['issues'] if note not in described]))
    for index,note in enumerate(notes):
        findings.append(Finding('coverage','fidelity',file,pointer('notes',index),note,
                                'reconstruction within measured tolerances',note).to_dict())
    result={**report(draft_id,findings),'draft':draft_id,'version':job['version'],'pairs':rendered['pairs'],
            'facts':fidelity_facts(rendered['pairs']),'tolerances':settings.to_dict(),'notes':notes,
            'standards':'unknown (Kinbase unconnected)'}
    write_document(inside(job['output'],'report.json'),result)
    return result
