"""Rendered-check orchestration and canonical report storage."""
import json
import logging
import os
from pathlib import Path
import signal
import subprocess
import sys
from tempfile import TemporaryDirectory
from ..config import CHECK_WIDTHS, CHECK_MAX_WIDTH, CHECK_MAX_WIDTHS, CHECK_TOTAL_TIMEOUT_SECONDS
from ..findings import report
from ..language import validate
from ..language.versions import digest
from ..render import build_preview
from ..storage import identifier, inside, load_language, read_json, write_json
from ..vocabulary import load
from .grouping import screenshots

log=logging.getLogger(__name__)


class CheckUnavailable(ValueError):
    """An environment failure, never a passed or rejected language."""


def parse_widths(value=None):
    if value is None:
        return list(CHECK_WIDTHS)
    try:
        widths=[int(v) for v in value.split(',')] if isinstance(value,str) else list(value)
    except (ValueError,TypeError):
        raise ValueError('Widths must be comma-separated positive CSS-pixel integers') from None
    if not widths or len(widths)>CHECK_MAX_WIDTHS or any(type(w) is not int or not 1<=w<=CHECK_MAX_WIDTH for w in widths) or len(set(widths))!=len(widths):
        raise ValueError(f'Provide 1–{CHECK_MAX_WIDTHS} distinct widths between 1 and {CHECK_MAX_WIDTH}')
    return widths


def report_folder(library, language_id, version):
    return inside(library,'generated',identifier(language_id),'checks',identifier(version))


def record_outcome(library,language_id,version,result):
    # Store only version/status for private content checks; no content, paths or
    # screenshots cross into the shared library.
    write_json(inside(library,'generated',language_id,'checks','outcome.json'),
               {'version':version,'accepted':bool(result['accepted'])})


def rendered_status(library,language_id,version):
    path=inside(library,'generated',language_id,'checks','outcome.json')
    latest=read_json(path) if path.exists() else latest_report(library,language_id)
    if not latest or latest.get('version')!=version:return 'unchecked'
    return 'accepted' if latest.get('accepted') is True else 'rejected'


def save_report(library, language_id, version, out, result):
    """Store one result; custom output is also mirrored for the workbench."""
    canonical=report_folder(library,language_id,version)
    canonical.mkdir(parents=True,exist_ok=True)
    if canonical.resolve()!=Path(out).resolve():
        for finding in result['findings']:
            for screenshot in screenshots(finding):
                source=inside(out,screenshot)
                if source.is_file(): inside(canonical,screenshot).write_bytes(source.read_bytes())
        for page in result['checked']['pages']:
            for width in result['checked']['widths']:
                name=page.removesuffix('.html')+f'@{width}.png'
                source=inside(out,name)
                if source.is_file(): inside(canonical,name).write_bytes(source.read_bytes())
    write_json(inside(out,'report.json'),result)
    if canonical.resolve()!=Path(out).resolve(): write_json(inside(canonical,'report.json'),result)
    write_json(inside(library,'generated',language_id,'checks','latest.json'),{'version':version})
    if version!='invalid' and result.get('version')==version:record_outcome(library,language_id,version,result)


def latest_report(library,language_id):
    index=inside(library,'generated',identifier(language_id),'checks','latest.json')
    if not index.exists():return None
    version=read_json(index)['version']
    return read_json(inside(report_folder(library,language_id,version),'report.json'))


def check(library,language_id,out=None,widths=None,content=None):
    widths=parse_widths(widths)
    static=validate(library,language_id)
    content_files=None
    if content:
        from ..content import page_files
        if not out:raise ValueError('Content checks require an explicit private --out directory')
        static,content_files=page_files(library,language_id,content)
    if not static.get('validated',static['accepted']):
        result={**static,'checked':{'pages':[],'widths':widths},'version':None}
        output=Path(out).resolve() if out else report_folder(library,language_id,'invalid')
        if content:write_json(inside(output,'report.json'),result)
        else:save_report(library,language_id,'invalid',output,result)
        return result
    document=load_language(library,language_id)
    vocabulary=load(library,document['vocabulary'])
    if content:
        vocabulary['context']['pages']={'index.html':'Content page'}
    version=digest(document)
    output=Path(out).resolve() if out else report_folder(library,language_id,version)
    output.mkdir(parents=True,exist_ok=True)
    with TemporaryDirectory(prefix='kinbase-check-') as temporary:
        temporary=Path(temporary)
        preview=temporary/'preview'
        if content_files is not None:
            for name,data in content_files.items():
                target=inside(preview,name);target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
        else:build_preview(library,language_id,preview)
        job=temporary/'job.json'
        write_json(job,{'document':document,'vocabulary':vocabulary,'preview':str(preview),'output':str(output),'widths':widths})
        worker=subprocess.Popen([sys.executable,'-m','kinbase_design.checks.worker',str(job)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,start_new_session=os.name=='posix')
        try:
            stdout,stderr=worker.communicate(timeout=CHECK_TOTAL_TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired as exc:
            if os.name=='posix':os.killpg(worker.pid,signal.SIGKILL)
            else:worker.kill()
            worker.communicate()
            raise CheckUnavailable(f'Rendered check exceeded {CHECK_TOTAL_TIMEOUT_SECONDS}s and was terminated') from exc
        if worker.returncode:
            try:message=json.loads(stdout).get('error',stdout)
            except ValueError:message=stderr or stdout
            raise CheckUnavailable('Rendered checks unavailable: '+message[:2000])
        rendered=json.loads(stdout)['findings']
    result=report(language_id,static['findings']+rendered)
    result.update(checked={'pages':list(vocabulary['context']['pages']),'widths':widths},version=version)
    if content:
        write_json(inside(output,'report.json'),result)
        record_outcome(library,language_id,version,result)
    else:save_report(library,language_id,version,output,result)
    log.info('check language=%s accepted=%s findings=%d needs_review=%d',language_id,result['accepted'],len(result['findings']),result['needs_review'])
    return result
