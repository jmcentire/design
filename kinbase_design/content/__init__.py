"""Shared offline content-page operations for CLI and workbench."""
import json
import logging
from pathlib import Path
from ..assets import package_notices, inspect_format
from ..builder import current_builder, builder_label
from ..language import validate
from ..language.versions import digest
from ..render import preview_files
from ..storage import inside, load_language, read_json, write_json
from ..findings import Finding, pointer
from ..vocabulary import load, samples, hook_contract
from .composition import compile_page
from .validation import validate_content

MARKER = '.kinbase-content-bundle.json'


def page_files(library, language_id, content, document=None):
    """Return a report and a portable file map; invalid input never yields a bundle."""
    content = Path(content).resolve()
    document = load_language(library, language_id) if document is None else document
    from ..checks import rendered_status
    status=rendered_status(library,language_id,digest(document))
    try:
        source = read_json(content)
    except ValueError as exc:
        return {'language':language_id,'validated':False,'accepted':False,'rendered_check':status,
                'findings':[Finding('violation','content-parse',str(content),'',None,
                    'a valid content JSON document',str(exc)).to_dict()]}, {}
    result, normalized, images = validate_content(source, content)
    result.update(language=language_id,validated=False,rendered_check=status)
    if not result['accepted']:return result, {}
    try:vocabulary=load(library,document.get('vocabulary'))
    except (OSError,ValueError,TypeError,AttributeError):vocabulary=None
    checked = validate(library, language_id, document,vocabulary=vocabulary)
    result['findings'].extend(checked['findings'])
    result.update(accepted=checked['accepted'],version=digest(document) if checked['accepted'] else None)
    if not checked['accepted']:return result, {}
    sample_set=samples(library,document['vocabulary'])
    version = document['vocabulary']
    if not vocabulary.get('content_pages'):
        result['findings'].append(Finding('violation','content-vocabulary',f'languages/{language_id}/working.json',
            '/vocabulary',version,'a vocabulary defining content-page hooks',
            'This vocabulary has no content-page contract.').to_dict())
        result['accepted']=False
        return result, {}
    composition = compile_page(normalized)
    def constructs(items):
        for item in items:
            yield item['construct']
            yield from constructs(item.get('children',[]))
    for name in sorted(set(constructs(composition['instances']))):
        component = document.get('components',{}).get(name,{})
        variant = component.get('variant','default')
        if variant!='default':
            template = document.get('layout',{}).get('variants',{}).get(name,{}).get(variant,{}).get('template')
            if template!=vocabulary['constructs'][name].get('content-template'):
                result['findings'].append(Finding('coverage','content-variant',f'languages/{language_id}/working.json',
                    pointer('components',name,'variant'),variant,'vocabulary-owned content markup',
                    f'{name}: variant markup is not used on content pages; review CSS treatment against the fixed vocabulary wrappers.').to_dict())
    builder = current_builder()
    files = preview_files(library, language_id, {'index.html':composition}, vocabulary_version=version, builder=builder, document=document,vocabulary=vocabulary,sample_set=sample_set)
    # Language assets are approved, but a portable offline bundle still cannot
    # contain an image that executes code or fetches a remote subresource.
    for asset, entry in document.get('assets',{}).items():
        if entry['kind'] != 'font':
            for variant, detail in entry['variants'].items():
                inspect_format(files[f'assets/{asset}-{variant}.{detail["format"]}'], 'image')
    files.update(images)
    files['hooks.json'] = (json.dumps(hook_contract(vocabulary),ensure_ascii=False,indent=2)+'\n').encode()
    notices = normalized.get('footer',{}).get('notices',[]) + package_notices(library,language_id,document)
    files['ATTRIBUTION.txt'] = (builder_label(builder)+'\n\n'+'\n\n'.join(notices)+'\n').encode()
    from ..render.identity import inputs
    result.update(builder=builder,vocabulary=version,validated=True,rendered_check=status,accepted=status=='accepted',
                  render_inputs=inputs(document,vocabulary,sample_set,{'index.html':composition},files,builder))
    return result, files


def bundle_destination(out, library, content):
    root = Path(out).expanduser().resolve()
    library, content = Path(library).resolve(), Path(content).resolve()
    if root == library or root in library.parents or root == content or root in content.parents or any(root == inside(library,s) or inside(library,s) in root.parents for s in ('languages','vocabulary')):
        raise ValueError('Bundle output must not overwrite source content or the language library')
    if root.exists():
        if not root.is_dir():raise ValueError('Bundle output must be a directory')
        existing = list(root.rglob('*'))
        if any(p.is_symlink() for p in existing):raise ValueError('Bundle output must not contain symlinks')
        if existing:
            marker = root/MARKER
            if not marker.is_file():raise ValueError('Nonempty output is not a previous content bundle')
            previous = read_json(marker)
            if not isinstance(previous,dict) or previous.get('schema')!='kinbase-content-bundle/1' or not isinstance(previous.get('files'),list) or any(not isinstance(name,str) for name in previous['files']):raise ValueError('Invalid previous content bundle marker')
            expected = set(previous['files']) | {MARKER}
            if any(str(p.relative_to(root)) not in expected for p in existing if p.is_file()):raise ValueError('Output contains files not owned by the previous bundle')
    return root


def render_page(library, language_id, content, out, document=None):
    root = bundle_destination(out, library, content)
    document = load_language(library, language_id) if document is None else document
    result, files = page_files(library, language_id, content, document=document)
    result['out'] = str(root)
    if not result['validated']:return result
    # page_files validated this exact snapshot against its captured vocabulary.
    from ..language.versions import archive
    archive(library,language_id,document)
    root.mkdir(parents=True,exist_ok=True)
    for name, data in sorted(files.items()):
        path = inside(root,name)
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_bytes(data)
    old = read_json(root/MARKER).get('files',[]) if (root/MARKER).exists() else []
    for name in set(old)-files.keys():
        path = inside(root,name)
        if path.is_file():path.unlink()
    write_json(root/MARKER, {'schema':'kinbase-content-bundle/1','builder':result['builder'],'files':sorted(files),'render_inputs':result['render_inputs']})
    logging.getLogger(__name__).info('render_page language=%s files=%d',language_id,len(files))
    return {**result,'files':sorted(files)}
