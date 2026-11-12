"""Does a site's own page comply with a language? The verification Factory can run.

Three questions, asked of the real rendered page:
- Where the page uses a construct, is its markup the Vocabulary's contract, and do its
  computed styles equal the language's resolved treatment?
- Everywhere else, does every colour, type and spacing value belong to the language?
- Does the page pass the same rendered checks a language's own preview must pass?

The page is the site's; the judgment uses the same resolver and checks as a preview.
"""
import json
import logging
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
from tempfile import TemporaryDirectory
from urllib.parse import urlsplit
from uuid import uuid4
from ..artifacts.capture import public_url
from ..checks import CheckUnavailable, parse_widths
from ..config import CAPTURE_MAX_PAGES, CHECK_TOTAL_TIMEOUT_SECONDS
from ..findings import report
from ..language import validate
from ..language.versions import MEMBERS, digest
from ..render import build_preview
from ..storage import ID, identifier, inside, load_language, read_json, save_language, write_json
from ..vocabulary import load

log = logging.getLogger(__name__)


def load_reference(library, reference):
    """A working language by id, or an immutable minted version as id@hash."""
    language_id, _, version = reference.partition('@')
    identifier(language_id)
    if not version:
        document = load_language(library, language_id)
        return language_id, document, digest(document)
    if not re.fullmatch(r'[0-9a-f]{64}', version):
        raise ValueError('A pinned language is id@<64 hex characters>')
    path = inside(library, 'languages', language_id, 'versions', version + '.json')
    if not path.is_file():
        raise ValueError('No minted version ' + reference + ' in this library')
    document = {'id': language_id, 'name': language_id, **{key: value for key, value in read_json(path).items() if key in MEMBERS}}
    if digest(document) != version:
        raise ValueError('Minted version content does not match its hash')
    return language_id, document, version


def page_targets(pages):
    """Each page is an http(s) address or a local HTML file; ids name its evidence."""
    if not pages or len(pages) > CAPTURE_MAX_PAGES:
        raise ValueError(f'Verification needs 1–{CAPTURE_MAX_PAGES} pages')
    targets, used = [], set()
    for value in pages:
        if '://' in value:
            parts = urlsplit(public_url(value))
            stem = (parts.path.rstrip('/').rsplit('/', 1)[-1] or parts.hostname or 'page').rsplit('.', 1)[0]
            target = value
        else:
            file = Path(value).expanduser().resolve()
            if not file.is_file():
                raise ValueError('Page is not an http(s) address or an existing file: ' + value)
            stem, target = file.stem, file.as_uri()
        base = re.sub(r'[^a-z0-9]+', '-', stem.lower()).strip('-') or 'page'
        name, serial = base, 2
        while name in used or not ID.fullmatch(name):
            name, serial = f'{base if ID.fullmatch(base) else "page"}-{serial}', serial + 1
        used.add(name)
        targets.append({'id': name, 'target': target, 'page': value})
    return targets


def excepted(findings, inventory):
    """Apply the site's justified exceptions: a scope, a rule and a nonempty reason."""
    if not inventory:
        return
    document = read_json(Path(inventory).expanduser().resolve())
    exceptions = document.get('exceptions', []) if isinstance(document, dict) else []
    for finding in findings:
        if finding['type'] not in {'violation', 'missing'} or finding.get('exception'):
            continue
        measured = finding.get('measured') if isinstance(finding.get('measured'), dict) else {}
        scopes = {finding.get('target'), str(finding.get('page')) + '/' + str(finding.get('target')), measured.get('value')}
        for index, entry in enumerate(exceptions if isinstance(exceptions, list) else []):
            if (isinstance(entry, dict) and isinstance(entry.get('reason'), str) and entry['reason'].strip()
                    and entry.get('rule') in {finding['rule'], finding['type']} and entry.get('scope') in scopes):
                finding['exception'] = f'inventory:/exceptions/{index}'
                break


def verify(library, workspace, reference, pages, out=None, widths=None, inventory=None, javascript=True):
    widths = parse_widths(widths)
    language_id, document, version = load_reference(library, reference)
    targets = page_targets(pages)
    static = validate(library, language_id, document)
    for finding in static['findings']:
        finding['source'] = 'language'
    output = Path(out).expanduser().resolve() if out else inside(workspace, 'verify', f'{language_id}-{version[:8]}-{uuid4().hex[:8]}')
    output.mkdir(parents=True, exist_ok=True)
    checked = {'pages': [{'id': item['id'], 'page': item['page']} for item in targets], 'widths': widths, 'javascript': javascript}
    if not static['accepted']:
        result = {**static, 'language': language_id + '@' + version, 'checked': {**checked, 'pages': []}, 'summary': None, 'out': str(output)}
        write_json(inside(output, 'report.json'), result)
        return result
    vocabulary = load(library, document['vocabulary'])
    with TemporaryDirectory(prefix='kinbase-verify-') as temporary:
        # Stage exactly the judged version, so a pinned reference previews as it was minted.
        staged = Path(temporary) / 'library'
        shutil.copytree(inside(library, 'vocabulary'), staged / 'vocabulary')
        save_language(staged, language_id, document)
        assets = inside(library, 'languages', language_id, 'assets')
        if assets.is_dir():
            shutil.copytree(assets, staged / 'languages' / language_id / 'assets')
        preview = Path(temporary) / 'preview'
        build_preview(staged, language_id, preview)
        job = Path(temporary) / 'job.json'
        write_json(job, {'document': document, 'vocabulary': vocabulary, 'pages': targets, 'output': str(output),
                         'widths': widths, 'javascript': javascript, 'preview': str(preview)})
        worker = subprocess.Popen([sys.executable, '-m', 'kinbase_design.verify.worker', str(job)], stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE, text=True, start_new_session=os.name == 'posix')
        try:
            stdout, stderr = worker.communicate(timeout=CHECK_TOTAL_TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired as exc:
            if os.name == 'posix':
                os.killpg(worker.pid, signal.SIGKILL)
            else:
                worker.kill()
            worker.communicate()
            raise CheckUnavailable(f'Verification exceeded {CHECK_TOTAL_TIMEOUT_SECONDS}s and was terminated') from exc
        if worker.returncode:
            try:
                message = json.loads(stdout).get('error', stdout)
            except ValueError:
                message = stderr or stdout
            raise CheckUnavailable('Verification unavailable: ' + message[:2000])
        rendered = json.loads(stdout)
    findings = static['findings'] + rendered['findings']
    excepted(findings, inventory)
    summary = rendered['summary']
    unhooked = summary['text_elements'] - summary['hooked_text_elements']
    summary['off_language_values'] = len({json.dumps(f['measured'].get('value')) for f in findings
                                          if f['rule'].startswith('off-language') and isinstance(f.get('measured'), dict)})
    if unhooked:
        findings.append({'type': 'coverage', 'rule': 'site-hooks', 'file': f'languages/{language_id}/working.json', 'pointer': '/components',
                         'observed': unhooked, 'expected': 'text inside Vocabulary slots', 'source': 'site',
                         'message': f'{unhooked} of {summary["text_elements"]} text elements are outside any Vocabulary slot; '
                                    'they were judged against the language\'s closed set only'})
    result = report(language_id, findings)
    result.update(language=language_id + '@' + version, checked=checked, summary=summary, out=str(output))
    write_json(inside(output, 'report.json'), result)
    log.info('verify language=%s pages=%d accepted=%s findings=%d', language_id, len(targets), result['accepted'], len(findings))
    return result
