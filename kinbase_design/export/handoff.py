"""Private Apply bundles and explicitly requested local branches, never remotes."""
from datetime import datetime,timezone
import logging
from pathlib import Path,PurePosixPath
import subprocess
from uuid import uuid4
from ..config import APPLY_GIT_TIMEOUT_SECONDS,APPLY_DEFAULT_TARGET_DIR
from ..inventory import INVENTORY_FILE,inventory_check
from ..language.versions import digest
from ..storage import inside,load_language,read_json,write_json,identifier
from . import export,export_files
from .adapters import ADAPTERS,metadata
from .screenshots import screenshots


def git(repo, *args):
    try:
        result=subprocess.run(['git','-c','core.hooksPath=/dev/null','-C',str(repo),*args],capture_output=True,text=True,
                              timeout=APPLY_GIT_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired as exc:raise ValueError('Local Git operation timed out') from exc
    if result.returncode:raise ValueError('Local Git operation failed: '+(result.stderr or result.stdout)[:1500])
    return result.stdout.strip()


def target_repository(site):
    root=Path(site).expanduser().resolve()
    actual=Path(git(root,'rev-parse','--show-toplevel')).resolve()
    if actual!=root:raise ValueError('--site must name the target repository root')
    return root


def target_directory(value):
    value=value or APPLY_DEFAULT_TARGET_DIR
    path=PurePosixPath(value)
    if path.is_absolute() or str(path)!=value or not path.parts or any(p in {'.','..','.git'} for p in path.parts) or '\\' in value or '\x00' in value:
        raise ValueError('Target directory must be a relative path inside the site repository')
    return value


def review(library,language_id,site):
    site=target_repository(site)
    return {'site':str(site),**inventory_check(library,language_id,site/INVENTORY_FILE)}


def write_generated_json(path,value,reference,adapter):
    write_json(path,{**metadata(reference,adapter),**value})


def task_text(record):
    identity=metadata(record['language'],record['adapter'])['$description']
    lines=['<!-- '+identity+' -->','# Apply Kinbase Design',
           '',f'Target repository: `{record["site"]}`',f'Local branch: `{record["branch"]}`',
           f'Target directory: `{record["target_dir"]}`',f'Language: `{record["language"]}`',
           f'Adapter: `{record["adapter"]}`','',
           'Integrate the exported tokens and treatments with the site using its existing build conventions.',
           'Keep the inventory current. Resolve uncovered missing/violation findings and review unresolved evidence.',
           'Validate the real site after integration. Before/after images show stylesheet injection only, not the site’s real build.',
           'No push, merge, remote PR, or deployment is authorized by this hand-off.','']
    if record['adapter'].startswith('dtcg-tailwind@'):
        lines.extend([
            '## Verification gap', '',
            'The export is browser-ready without compilation. No Tailwind compiler is provided or required offline.',
            'Tailwind consumption of the @theme block is unverified: verify it in the target design-system repository during integration.', '',
        ])
    lines.extend(['## Export files',''])
    lines.extend('- `'+record['target_dir']+'/'+name+'`' for name in record['export_files'])
    lines.extend(['','## Findings to resolve',''])
    for finding in record['findings']['findings']:
        lines.append('- '+finding['type']+' '+finding['rule']+' ('+finding['source']+') at `'+finding['file']+'#'+finding['pointer']+'`: '+finding['message']+
                     (' (covered by '+str(finding['exception'])+')' if finding.get('exception') else ''))
    if not record['findings']['findings']:lines.append('No inventory or static validation findings.')
    lines.extend(['','See findings.json for measured evidence and exception details.',''])
    return '\n'.join(lines)


def local_branch(record,bundle):
    site=Path(record['site']);branch=record['branch'];worktree=inside(bundle,'branch')
    # Fail before changing anything when the requested branch already exists.
    existing=git(site,'branch','--list',branch)
    if existing:raise ValueError('Local branch already exists: '+branch)
    git(site,'worktree','add','-b',branch,str(worktree),'HEAD')
    try:
        target=inside(worktree,record['target_dir'])
        for name in record['export_files']:
            output=inside(target,name);output.parent.mkdir(parents=True,exist_ok=True)
            output.write_bytes(inside(bundle,'export',name).read_bytes())
        paths=[record['target_dir']+'/'+name for name in record['export_files']]
        git(worktree,'add','--',*paths)
        git(worktree,'-c','core.hooksPath=/dev/null','-c','commit.gpgsign=false','commit','-m','Apply '+record['language']+' with '+record['adapter'])
        commit=git(worktree,'rev-parse','HEAD')
    finally:
        # Only this newly created, isolated worktree is removed; the named branch remains local.
        git(site,'worktree','remove','--force',str(worktree))
    return {'branch':branch,'commit':commit}


def apply(library,workspace,language_id,site,adapter,target_dir=None,page_urls=(),branch=False):
    if adapter not in ADAPTERS:raise ValueError('Unknown export adapter: '+adapter)
    site=target_repository(site);target_dir=target_directory(target_dir)
    inside(site,target_dir)
    findings=review(library,language_id,site)
    document=load_language(library,language_id);version=digest(document)
    files=export_files(library,language_id,adapter)
    handoff_id=identifier(language_id+'-'+version[:8]+'-'+uuid4().hex[:8])
    bundle=inside(workspace,'handoffs',handoff_id)
    capture,images=screenshots(workspace,page_urls,files,adapter) if page_urls else ({'pairs':[],'problems':[]},{})
    exported=export(library,language_id,adapter,inside(bundle,'export'))
    record={'id':handoff_id,'language':exported['language'],'adapter':exported['adapter'],'site':str(site),
            'target_dir':target_dir,'branch':'kinbase-design/'+language_id+'-'+version[:8],
            'export_files':sorted(files),'findings':findings,'screenshots':capture,
            'created':datetime.now(timezone.utc).isoformat(),'local_branch':None}
    for name,data in images.items():
        path=inside(bundle,name);path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
    write_generated_json(inside(bundle,'findings.json'),findings,record['language'],record['adapter'])
    inside(bundle,'TASK.md').write_text(task_text(record))
    if branch:record['local_branch']=local_branch(record,bundle)
    record['files']=['TASK.md','findings.json',*['export/'+name for name in files],*images]
    write_generated_json(inside(bundle,'handoff.json'),record,record['language'],record['adapter'])
    logging.getLogger(__name__).info('apply language=%s adapter=%s branch=%s bundle=%s',language_id,adapter,bool(branch),handoff_id)
    return {'bundle':str(bundle),'handoff':handoff_id,'accepted':findings['accepted'],'branch':record['local_branch']}


def read_handoff(workspace,handoff_id):
    return read_json(inside(workspace,'handoffs',identifier(handoff_id),'handoff.json'))


def prepare(library,workspace,language_id,site,adapter,target_dir=None,page_urls=(),branch=False):
    """Persist the user's Apply selection so every browser step can redirect."""
    from ..artifacts.capture import public_url
    if adapter not in ADAPTERS:raise ValueError('Unknown export adapter: '+adapter)
    findings=review(library,language_id,site)
    document=load_language(library,language_id)
    value={'id':'apply-'+uuid4().hex,'language_id':language_id,'version':digest(document),
           'site':findings['site'],'adapter':adapter,'target_dir':target_directory(target_dir),
           'page_urls':[public_url(url) for url in page_urls],'branch':bool(branch),'review':findings}
    write_generated_json(inside(workspace,'apply',value['id'],'selection.json'),value,
                         language_id+'@'+value['version'],adapter+'@'+ADAPTERS[adapter].version)
    return value


def read_selection(library,workspace,selection_id):
    value=read_json(inside(workspace,'apply',identifier(selection_id),'selection.json'))
    if digest(load_language(library,value['language_id']))!=value['version']:
        raise ValueError('Language changed since Apply review; start a new review')
    return value
