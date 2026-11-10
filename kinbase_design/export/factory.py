"""Submit an existing Apply branch through Factory's ordinary command line."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
from ..builder import builder_identity, builder_label
from ..config import APPLY_GIT_TIMEOUT_SECONDS, FACTORY_TIMEOUT_SECONDS
from ..language.versions import digest
from ..storage import identifier, inside, load_language, write_json
from .handoff import git, read_handoff, target_directory, target_repository


CONSTRAINTS = [
    'The export files are already committed at the pinned commit under target_dir; do not alter them.',
    "Add the generic semantic hooks from hooks.json (kinbase-hooks/1) to the site's own maintained components: data-kd-construct on each matching component root and construct-qualified data-kd-slot values on its parts. Choose the closest construct for each existing component and list components with no matching construct instead of inventing new ones.",
    "Load the exported stylesheets using the site's existing build conventions.",
    'Do not change text, links, controls, images or reading order. Do not hide or reorder content to achieve a design; hooks are additive attributes.',
    'Resolve or report each hand-off finding listed below with its rule and location.',
    'Validate the real site build after integration; screenshots from the hand-off show stylesheet injection only.',
    'No push, merge, remote pull request or deployment is authorized by this directive.',
]
ACCEPTANCE = [
    'Report the real site build command and its result, plus any integration checks performed.',
    'Confirm that applied construct and slot attributes match the exported hook contract; list unmatched components.',
    'Confirm that the committed export files are unchanged and their stylesheets load through the site build.',
    'Confirm that text, links, controls, images and reading order are preserved, with no hidden or reordered content.',
    'Report the resolution or remaining limitation for every hand-off finding.',
    'The Orchestrator and System One must compare Design attribution with the retained hand-off and pinned export metadata. Report unknown or conflicting provenance without substituting the current installed version or blocking work merely because older provenance is absent.',
    'For any separately authorized resulting PR, preserve the verified Design builder name/version as the producer of the design outputs alongside the actual implementation builder. Never substitute the target project release version or infer an older producer from the current installation.',
]


def committed_file(repo, commit, path):
    """Read exact blob bytes; Apply's text Git helper strips output whitespace."""
    try:
        result = subprocess.run(['git','-c','core.hooksPath=/dev/null','-C',str(repo),
                                 'show',commit+':'+path],capture_output=True,timeout=APPLY_GIT_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        raise ValueError('Export verification timed out') from None
    if result.returncode:raise ValueError('Export file absent at the hand-off commit: '+path)
    return result.stdout


def checked_handoff(library, workspace, handoff_id):
    try:record = read_handoff(workspace,handoff_id)
    except (ValueError,OSError):
        raise ValueError('factory-task requires a hand-off created with --branch') from None
    local = record.get('local_branch') if isinstance(record,dict) else None
    if not isinstance(local,dict) or not local.get('branch') or not local.get('commit'):
        raise ValueError('factory-task requires a hand-off created with --branch')
    language_id, separator, version = str(record.get('language','')).partition('@')
    if not separator:raise ValueError('Stale hand-off: the language version is absent')
    document = load_language(library,language_id)
    if digest(document)!=version:
        raise ValueError('Stale hand-off: the current language version differs')
    repo = target_repository(record['site'])
    branch,commit = local['branch'],local['commit']
    if branch!=record['branch']:raise ValueError('Hand-off branch identity differs')
    git(repo,'check-ref-format','refs/heads/'+branch)
    try:tip = git(repo,'rev-parse','--verify','refs/heads/'+branch)
    except ValueError:raise ValueError('Hand-off local branch was deleted') from None
    if tip!=commit:raise ValueError('Hand-off local branch moved from the recorded commit')
    target = target_directory(record['target_dir'])
    bundle = inside(workspace,'handoffs',identifier(handoff_id))
    names = record.get('export_files')
    if not isinstance(names,list) or not names or any(not isinstance(n,str) or not n for n in names):
        raise ValueError('Hand-off export manifest is missing or invalid')
    if len(set(names))!=len(names) or 'hooks.json' not in names:
        raise ValueError('Hand-off export manifest is incomplete')
    copies = inside(bundle,'export')
    if set(names)!={p.relative_to(copies).as_posix() for p in copies.rglob('*') if p.is_file()}:
        raise ValueError('Hand-off export copies are partial or changed')
    files = []
    export_bytes = {}
    for name in sorted(names):
        name = target_directory(name)
        data = inside(copies,name).read_bytes()
        path = target+'/'+name
        if committed_file(repo,commit,path)!=data:
            raise ValueError('Export differs from the hand-off copy: '+path)
        files.append({'path':path,'sha256':hashlib.sha256(data).hexdigest()})
        export_bytes[name] = data
    # Reuse the bytes already checked against Git. Attribution findings are
    # reported separately; absent historical identity is not an execution gate.
    record = dict(record)
    builder = builder_identity(record.get('builder'))
    lines = export_bytes.get('ATTRIBUTION.txt', b'').decode(errors='replace').splitlines()
    match = re.search(r'(?:^|; )Design artifacts generated by Kinbase Design v([0-9][A-Za-z0-9.+-]*)$',
                      lines[0] if lines else '')
    evidence = [builder, {'name':'Kinbase Design','version':match[1]} if match else None]
    if 'tokens.json' in export_bytes:
        try:
            evidence.append(builder_identity(json.loads(export_bytes['tokens.json'])['$extensions']['kinbase-design'].get('builder')))
        except (ValueError, KeyError, TypeError, AttributeError):
            evidence.append(None)
    known = [value for value in evidence if value is not None]
    conflicting = any(value != known[0] for value in known) or (record.get('builder') is not None and builder is None)
    record['builder_status'] = 'conflicting' if conflicting else 'unknown' if None in evidence else 'consistent'
    record['builder'] = builder if record['builder_status'] == 'consistent' else None
    return record,bundle,repo,document,files


def code(value):
    # Keep arbitrary repository-relative names on one inert Markdown line.
    return '`'+json.dumps(str(value),ensure_ascii=True).replace('`','\\u0060')+'`'


def directive(record, document, files, run_id):
    review = record['findings']
    metadata = {'schema':'kinbase-design-directive/1','handoff':record['id'],
                'language':record['language'],'adapter':record['adapter'],'vocabulary':document['vocabulary'],
                'builder':record['builder'],'builder_status':record['builder_status'],
                'target_dir':record['target_dir'],'branch':record['local_branch']['branch'],
                'commit':record['local_branch']['commit'],'hooks':record['target_dir']+'/hooks.json',
                'files':files,'findings':{'accepted':review['accepted'],'count':len(review['findings'])},
                'constraints':CONSTRAINTS,'acceptance':ACCEPTANCE}
    payload = json.dumps(metadata,ensure_ascii=True,sort_keys=True,indent=2).replace('`','\\u0060')
    lines = ['<!-- kinbase-design-directive/1 -->',
             '# Apply '+code(record['language'])+' to this repository at '+code(record['target_dir']),
             '', builder_label(record['builder']), 'Design attribution: '+record['builder_status'], '', 'Factory run: '+code(run_id), '', '```json kinbase-design-directive',payload,'```','',
             '## Instructions','']
    lines.extend(str(i)+'. '+rule for i,rule in enumerate(CONSTRAINTS,1))
    lines.extend(['','## Hand-off findings',''])
    for finding in review['findings']:
        file = str(finding.get('file',''))
        # Normal Apply findings are already library/repository-relative. Never
        # transport an absolute workspace or library location into a task.
        if Path(file).is_absolute():file = Path(file).name
        lines.append('- '+code(finding['rule'])+' at '+code(file+'#'+finding.get('pointer','')))
    if not review['findings']:lines.append('No hand-off findings.')
    lines.extend(['','## Acceptance',''])
    lines.extend('- '+rule for rule in ACCEPTANCE)
    return ('\n'.join(lines)+'\n').encode('utf-8')


def stderr_tail(stream):
    stream.seek(0,os.SEEK_END)
    stream.seek(max(0,stream.tell()-8000))
    return stream.read().decode('utf-8',errors='replace')[-2000:]


def submit(library, workspace, handoff_id, run_id, factory=None, runs=None, budget=None, dry_run=False):
    if not re.fullmatch(r'[a-z0-9][a-z0-9._-]{0,63}',run_id):
        raise ValueError('RUN_ID must be 1–64 characters of [a-z0-9][a-z0-9._-]*')
    record,bundle,repo,document,files = checked_handoff(library,workspace,handoff_id)
    entrypoint = factory if factory is not None else os.environ.get('KINBASE_DESIGN_FACTORY')
    if not dry_run:
        if not entrypoint:raise ValueError('Factory entrypoint is required (--factory or KINBASE_DESIGN_FACTORY)')
        entrypoint = Path(entrypoint).expanduser().resolve()
        if not entrypoint.is_file() or not os.access(entrypoint,os.X_OK):
            raise ValueError('Factory entrypoint must be an executable regular file')
    data = directive(record,document,files,run_id)
    path = inside(bundle,'directive.md');path.write_bytes(data)
    submission = {'schema':'kinbase-design-factory-submission/1','handoff':handoff_id,'run':run_id,
                  'builder':record['builder'],'builder_status':record['builder_status'],'directive':str(path),'directive_sha256':hashlib.sha256(data).hexdigest(),
                  'repository':None,'commit':record['local_branch']['commit'],
                  'invoked':False,'exit':None,'stderr_tail':''}
    if not dry_run:
        worktree = bundle/'factory-repo'
        if worktree.exists() or worktree.is_symlink():raise ValueError('Factory repository path already exists')
        git(repo,'worktree','add',str(worktree),record['local_branch']['branch'])
        if git(worktree,'rev-parse','HEAD')!=submission['commit']:
            raise ValueError('Hand-off branch moved while creating the Factory worktree')
        submission['repository'] = str(worktree)
        command = [str(entrypoint),run_id,str(path),'--repo',str(worktree)]
        if runs is not None:command.extend(['--runs',str(runs)])
        if budget is not None:command.extend(['--budget',str(budget)])
        with tempfile.TemporaryFile() as errors:
            try:
                result = subprocess.run(command,stdout=subprocess.DEVNULL,stderr=errors,timeout=FACTORY_TIMEOUT_SECONDS)
                submission.update(invoked=True,exit=result.returncode)
            except subprocess.TimeoutExpired:
                submission.update(invoked=True,timeout=True)
            except OSError as exc:
                submission['stderr_tail'] = str(exc)[-2000:]
            if submission['invoked']:submission['stderr_tail'] = stderr_tail(errors)
    write_json(inside(bundle,'factory-submission.json'),submission)
    return submission
