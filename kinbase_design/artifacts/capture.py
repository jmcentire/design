"""Public, unauthenticated URL capture. Extraction never returns to these URLs."""
import ipaddress
import re
from urllib.parse import urlsplit
from ..config import CAPTURE_WIDTHS, CAPTURE_MAX_WIDTHS, CAPTURE_MAX_PAGES, CHECK_MAX_WIDTH
from .runtime import run_job


def public_url(url):
    parts=urlsplit(url)
    if parts.scheme not in {'http','https'} or not parts.hostname or parts.username or parts.password:
        raise ValueError('Capture requires public http(s) URLs without credentials')
    host=parts.hostname.lower()
    if host=='localhost' or host.endswith(('.localhost','.local','.internal')):
        raise ValueError('Capture requires a public host')
    try:address=ipaddress.ip_address(host)
    except ValueError:address=None
    if address and not address.is_global:raise ValueError('Capture requires a public IP address')
    return url


def widths(value=None):
    values=list(CAPTURE_WIDTHS) if value is None else [int(v) for v in value.split(',')] if isinstance(value,str) else list(value)
    if not values or len(values)>CAPTURE_MAX_WIDTHS or any(type(v)!=int or not 1<=v<=CHECK_MAX_WIDTH for v in values):
        raise ValueError('Capture widths exceed configured bounds')
    return sorted(set(values))


def media_widths(queries):
    return sorted({round(float(value)*(16 if unit=='rem' or unit=='em' else 1))
                   for query in queries for value,unit in re.findall(r'(?:min-|max-)?width\s*[:<>=]+\s*(\d+(?:\.\d+)?)(px|rem|em)',query)
                   if 1<=float(value)*(16 if unit in {'rem','em'} else 1)<=CHECK_MAX_WIDTH})


def capture(workspace, urls, requested_widths=None):
    urls=list(dict.fromkeys(public_url(url) for url in urls))
    if not urls or len(urls)>CAPTURE_MAX_PAGES:raise ValueError(f'Capture requires 1–{CAPTURE_MAX_PAGES} URLs')
    return run_job('kinbase_design.artifacts.capture_worker',{'workspace':str(workspace),'urls':urls,'widths':widths(requested_widths)})
