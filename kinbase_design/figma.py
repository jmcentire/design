"""Explicit read-only Figma snapshots. Credentials never enter artifacts or logs."""
import json
import os
import re
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, build_opener, HTTPRedirectHandler
from .artifacts import import_bytes
from .artifacts.bundle import import_bundle

MAX_RESPONSE = 100 * 1024 * 1024


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class Client:
    def __init__(self, token):
        if not token or '\n' in token or '\r' in token:
            raise ValueError('Set FIGMA_ACCESS_TOKEN for the intended Figma account')
        self.token = token
        self.opener = build_opener(NoRedirect())

    def get(self, path, **query):
        url = 'https://api.figma.com/v1/' + path
        if query:
            url += '?' + urlencode(query)
        request = Request(url, headers={'X-Figma-Token': self.token, 'Accept': 'application/json'})
        try:
            with self.opener.open(request, timeout=30) as response:
                data = response.read(MAX_RESPONSE + 1)
        except HTTPError as exc:
            raise ValueError(f'Figma request failed (HTTP {exc.code}); check account access, scopes or rate limit') from None
        except (URLError, TimeoutError, OSError):
            raise ValueError('Figma request failed; check connectivity') from None
        if len(data) > MAX_RESPONSE:
            raise ValueError('Figma response exceeds 100 MiB')
        try:
            value = json.loads(data)
        except (ValueError, UnicodeError):
            raise ValueError('Figma returned invalid JSON') from None
        if not isinstance(value, dict):
            raise ValueError('Figma returned an unexpected response')
        return value


def client():
    # Deliberately no fallback to credentials belonging to another project.
    return Client(os.environ.get('FIGMA_ACCESS_TOKEN'))


def identifier(value):
    if not re.fullmatch(r'[A-Za-z0-9_-]+', value):
        raise ValueError('Expected a Figma file key or version, not a URL')
    return value


def tokens_from(document):
    """Observed node-local values, not inferred brand rules or authority."""
    tokens = {}
    stack = [document]
    count = 0
    while stack:
        node = stack.pop()
        if not isinstance(node, dict):
            continue
        count += 1
        if count > 100000:
            raise ValueError('Figma document exceeds node limit')
        stack.extend(node.get('children', []))
        node_id = str(node.get('id', ''))
        key = 'node_' + node_id.encode().hex()
        values = {}
        for index, paint in enumerate(node.get('fills', [])):
            if paint.get('type') != 'SOLID' or paint.get('visible') is False:
                continue
            color = paint.get('color', {})
            if all(k in color for k in ('r', 'g', 'b')):
                channels = [color[k] for k in ('r', 'g', 'b')]
                channels.append(color.get('a', 1) * paint.get('opacity', 1))
                rgba = '#' + ''.join(f'{round(max(0, min(1, v))*255):02x}' for v in channels)
                values['fill_'+str(index)] = {'$type': 'color', '$value': rgba}
        style = node.get('style', {})
        if style.get('fontFamily'):
            values['font_family'] = {'$type': 'fontFamily', '$value': [style['fontFamily']]}
        for field, name in (('fontSize', 'type_size'),):
            if isinstance(style.get(field), (int, float)):
                values[name] = {'$type': 'dimension', '$value': str(style[field])+'px'}
        if values:
            values['$extensions'] = {'figma': {'nodeId': node_id, 'name': node.get('name', '')}}
            tokens[key] = values
    return tokens


def snapshot(workspace, file_key, version=None, api=None, nodes=(), variables=False, comments=False):
    """Fetch a versioned source and feed observed tokens into existing import/draft."""
    file_key = identifier(file_key)
    if version:
        identifier(version)
    api = api or client()
    source = api.get('files/'+file_key, **({'version': version} if version else {}))
    actual = source.get('version')
    if not actual or not isinstance(source.get('document'), dict):
        raise ValueError('Figma file response lacks document or version')
    if version and actual != version:
        raise ValueError('Figma returned a different version than requested')
    tokens = tokens_from(source['document'])
    encode = lambda value: json.dumps(value, sort_keys=True, ensure_ascii=False).encode()
    children = []
    if tokens:
        child = import_bytes(workspace, encode(tokens), 'tokens.json', 'dtcg')
        children.append({'artifact': child, 'location': 'tokens.json'})
    from .figma_extra import acquire
    files, extras, observations, gaps = acquire(api, workspace, file_key, actual, source['document'], nodes, variables, comments)
    children.extend(extras)
    files.update({'figma.json': encode(source), 'tokens.json': encode(tokens), 'observations.json': encode(observations)})
    artifact = import_bundle(workspace, files,
                             'figma-export', {'children': children, 'source': {'provider': 'figma',
                             'file_key': file_key, 'version': actual}, 'authority': 'observation-only', 'observations': observations, 'gaps': gaps})
    return {'artifact': artifact, 'version': actual, 'observed_token_groups': len(tokens),
            'learning': 'Not submitted to Kinbase; source observations are not approved standards',
            'gaps': gaps + ['Visual references feed existing image sampling; semantic vision interpretation is not enabled',
                            'Comments are private observations, not approved standards']}
