"""Public, unauthenticated URL capture. Extraction never returns to these URLs."""
import re
import json
from urllib.parse import urlsplit
from ..config import CAPTURE_WIDTHS, CAPTURE_MAX_WIDTHS, CHECK_MAX_WIDTH, ingest_config
from .runtime import run_job


def public_url(url):
    """Public means unauthenticated; local development and LAN hosts are valid."""
    parts=urlsplit(url)
    if parts.scheme not in {'http','https'} or not parts.hostname:
        raise ValueError('Capture requires an http or https URL')
    if parts.username is not None or parts.password is not None:
        raise ValueError('Capture refuses URLs with embedded credentials')
    _=parts.port  # Validate a supplied port without contacting the host.
    return url


def anonymous_headers(headers):
    return {key:value for key,value in headers.items()
            if key.lower() not in {'cookie','authorization','proxy-authorization'}}


def group_problems(problems):
    """One actionable problem with all of its affected pages and widths."""
    grouped={}
    for problem in problems:
        core={key:value for key,value in problem.items() if key not in {'page','width','pages','widths'}}
        key=json.dumps(core,sort_keys=True)
        entry=grouped.setdefault(key,{**core,'pages':[],'widths':[]})
        for page in problem.get('pages',[])+([problem['page']] if 'page' in problem else []):
            if page not in entry['pages']:entry['pages'].append(page)
        for width in problem.get('widths',[])+([problem['width']] if 'width' in problem else []):
            if width not in entry['widths']:entry['widths'].append(width)
    for entry in grouped.values():entry['widths'].sort()
    return list(grouped.values())


def widths(value=None):
    values=list(CAPTURE_WIDTHS) if value is None else [int(v) for v in value.split(',')] if isinstance(value,str) else list(value)
    if not values or len(values)>CAPTURE_MAX_WIDTHS or any(type(v)!=int or not 1<=v<=CHECK_MAX_WIDTH for v in values):
        raise ValueError('Capture widths exceed configured bounds')
    return sorted(set(values))


def media_widths(queries):
    return sorted({round(float(value)*(16 if unit=='rem' or unit=='em' else 1))
                   for query in queries for value,unit in re.findall(r'(?:min-|max-)?width\s*[:<>=]+\s*(\d+(?:\.\d+)?)(px|rem|em)',query)
                   if 1<=float(value)*(16 if unit in {'rem','em'} else 1)<=CHECK_MAX_WIDTH})


def capture(workspace, urls, requested_widths=None, settings=None):
    settings=settings or ingest_config()
    urls=list(dict.fromkeys(public_url(url) for url in urls))
    if not urls or len(urls)>settings.max_pages:raise ValueError(f'Capture requires 1–{settings.max_pages} URLs')
    return run_job('kinbase_design.artifacts.capture_worker',{'workspace':str(workspace),'urls':urls,
                   'widths':widths(settings.widths if requested_widths is None else requested_widths),'settings':settings.to_dict()})
