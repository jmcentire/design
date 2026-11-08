"""Server-rendered local workbench; WSGI makes every route testable without sockets."""
from collections import Counter
from email.parser import BytesParser
from email.policy import default
import logging
import mimetypes
from pathlib import Path
from urllib.parse import parse_qs, unquote
from jinja2 import Environment, FileSystemLoader, select_autoescape
from ..artifacts import import_bytes
from ..assets import promote
from ..config import roots, MAX_UPLOAD_BYTES, VIEWPORTS, DEFAULT_VIEWPORT
from ..kinbase import status as kinbase_status
from ..language import validate
from ..language.versions import digest
from ..checks import check, latest_report, report_folder
from ..checks.grouping import screenshots
from ..language.tokens import Tokens
from ..storage import identifier, inside, load_language, read_json
from ..vocabulary import load as load_vocabulary

log = logging.getLogger(__name__)
CSP = "default-src 'self'; script-src 'none'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; object-src 'none'; base-uri 'none'; form-action 'self'; frame-ancestors 'self'"


class RequestError(ValueError):
    def __init__(self, message, status=400):
        self.status = status
        super().__init__(message)


def multipart(environ):
    try:
        length = int(environ.get('CONTENT_LENGTH', '0'))
    except ValueError:
        raise RequestError('Invalid Content-Length') from None
    if length <= 0:
        raise RequestError('Upload body is required')
    if length > MAX_UPLOAD_BYTES + 65536:
        raise RequestError('Upload exceeds configured size limit', 413)
    content_type = environ.get('CONTENT_TYPE', '')
    if '\r' in content_type or '\n' in content_type or not content_type.startswith('multipart/form-data;'):
        raise RequestError('Expected multipart/form-data')
    data = environ['wsgi.input'].read(length)
    if len(data) != length:
        raise RequestError('Incomplete upload')
    message = BytesParser(policy=default).parsebytes(('Content-Type: ' + content_type + '\r\nMIME-Version: 1.0\r\n\r\n').encode('ascii') + data)
    if not message.is_multipart() or message.defects:
        raise RequestError('Malformed multipart upload')
    fields = {}
    upload = None
    for part in message.iter_parts():
        name = part.get_param('name', header='content-disposition')
        if name not in {'file','asset_id','kind','variant','weight','style','family'} or name in fields:
            raise RequestError('Unexpected or repeated upload field')
        content = part.get_payload(decode=True)
        if content is None:
            raise RequestError('Malformed multipart field')
        if name == 'file':
            if len(content) > MAX_UPLOAD_BYTES:
                raise RequestError('Upload exceeds configured size limit', 413)
            upload = (content, part.get_filename())
            fields[name] = True
        else:
            if len(content) > 2048:
                raise RequestError('Upload field is too long')
            fields[name] = content.decode('utf-8').strip()
    if not upload:
        raise RequestError('A file is required')
    return fields, upload


def create_app(library: str | Path, workspace: str | Path):
    library, workspace = roots(library, workspace)
    environment = Environment(loader=FileSystemLoader(Path(__file__).parent / 'templates'), autoescape=select_autoescape(['html']))

    def html(template, **context):
        return environment.get_template(template).render(**context).encode('utf-8')

    def parameters(query, pages):
        page = query.get('page', ['index.html'])[0]
        if page not in pages:
            raise RequestError('Unknown preview page')
        try:
            width = int(query.get('width', [str(DEFAULT_VIEWPORT)])[0])
        except ValueError:
            raise RequestError('Invalid viewport width') from None
        if width not in VIEWPORTS:
            raise RequestError('Width must be 320, 768 or 1280 CSS px')
        return page, width

    def app(environ, start_response):
        code, content_type, headers = 200, 'text/html; charset=utf-8', []
        language_id = '-'
        try:
            method = environ.get('REQUEST_METHOD', 'GET')
            path = unquote(environ.get('PATH_INFO', '/'))
            if '\x00' in path or '\\' in path or any(s in {'.','..'} for s in path.split('/')):
                raise RequestError('Unknown route', 404)
            query = parse_qs(environ.get('QUERY_STRING', ''), max_num_fields=20)
            segments = path.strip('/').split('/')
            if segments[0] == 'ingest':
                from .ingest import handle
                code,body,content_type,headers=handle(library,workspace,environ,segments,query,html)
            elif method == 'GET' and path == '/workbench.css':
                content_type = 'text/css; charset=utf-8'
                body = Path(__file__).with_name('workbench.css').read_bytes()
            elif method == 'GET' and path == '/':
                cards = []
                languages = inside(library, 'languages')
                for folder in sorted(languages.iterdir() if languages.exists() else []):
                    if not folder.is_dir():
                        continue
                    try:
                        language_id = identifier(folder.name)
                        doc = load_language(library, language_id)
                        result = validate(library, language_id, doc)
                        if not isinstance(doc, dict):
                            raise ValueError('schema /: language must be an object')
                        latest = latest_report(library, language_id)
                        summary = latest or result
                        colors = []
                        if result['accepted']:
                            tokens = Tokens(doc.get('style', {}))
                            colors = [tokens.evaluate(n)[1] for n,t in tokens.nodes.items() if t['$type'] == 'color'][:5]
                        provenance = doc.get('provenance', {})
                        cards.append({'id':language_id, 'name':doc.get('name',language_id), 'description':doc.get('description',''),
                                      'provenance':provenance.get('method','Not recorded') if isinstance(provenance,dict) else 'Not recorded',
                                      'counts':{t:Counter(f['type'] for f in summary['findings'])[t] for t in ('violation','missing','needs-review','coverage')},
                                      'colors':colors, 'kinbase':kinbase_status(), 'latest':latest, 'stale':bool(latest and latest.get('version') != digest(doc))})
                    except (OSError, ValueError) as exc:
                        cards.append({'id':folder.name,'name':folder.name,'description':str(exc),'provenance':'Unknown', 'colors':[], 'counts':{'violation':1}})
                body = html('grid.html', title='Library', cards=cards)
            elif method == 'GET' and len(segments) == 2 and segments[0] == 'languages':
                language_id = identifier(segments[1])
                doc = load_language(library, language_id)
                result = validate(library, language_id, doc)
                if not isinstance(doc, dict):
                    raise RequestError('schema /: language must be an object')
                try:
                    pages = load_vocabulary(library, doc.get('vocabulary'))['context']['pages']
                except (ValueError, OSError, KeyError):
                    pages = load_vocabulary(library)['context']['pages']
                # Malformed asset entries remain visible in findings, not template exceptions.
                raw_assets = doc.get('assets', {})
                display_assets = {}
                if isinstance(raw_assets, dict):
                    for name, entry in raw_assets.items():
                        if isinstance(entry, dict) and isinstance(entry.get('variants'), dict):
                            display_assets[name] = {**entry, 'variants':{k:v for k,v in entry['variants'].items() if isinstance(v,dict)}}
                doc = {**doc, 'id':language_id, 'name':doc.get('name',language_id), 'assets':display_assets}
                page, width = parameters(query, pages)
                gaps = [f for f in result['findings'] if f['type']=='missing' and (f['rule']=='asset-font' or '/assets' in f['pointer'] or '$extensions' in f['pointer'] or (isinstance(f['observed'],str) and f['observed'].startswith('asset:')))]
                latest = latest_report(library, language_id)
                groups = {kind:[f for f in (latest or {}).get('findings',[]) if f['type']==kind] for kind in ('violation','missing','needs-review','coverage')}
                from ..ingest.provenance import inspect_sources
                from ..ingest.documents import read_document
                provenance_entries=[]
                if result['accepted']:
                    provenance_file=inside(library,'languages',language_id,'provenance',digest(load_language(library,language_id))+'.json')
                    if provenance_file.exists():provenance_entries=inspect_sources(workspace,read_document(provenance_file))
                body = html('viewer.html', provenance_entries=provenance_entries, latest=latest, groups=groups, stale=bool(latest and result['accepted'] and latest.get('version')!=digest(load_language(library,language_id))), title=doc['name'], language=doc, report=result, gaps=gaps,
                            pages=pages, page=page, width=width, widths=VIEWPORTS,
                            annotations=query.get('annotations',['0'])[0]=='1', upload_mb=MAX_UPLOAD_BYTES//(1024*1024))
            elif method == 'POST' and len(segments) == 3 and segments[0] == 'languages' and segments[2] == 'check':
                language_id = identifier(segments[1])
                check(library, language_id)
                code, body = 303, b''
                headers.append(('Location','/languages/' + language_id))
            elif method == 'POST' and len(segments) == 3 and segments[0] == 'languages' and segments[2] == 'assets':
                language_id = identifier(segments[1])
                load_language(library, language_id)
                fields, (data, filename) = multipart(environ)
                for field in ('asset_id','kind','variant'):
                    if not fields.get(field):
                        raise RequestError('Missing upload field: ' + field)
                identifier(fields['asset_id'])
                identifier(fields['variant'])
                weight = int(fields['weight']) if fields.get('weight') else None
                artifact = import_bytes(workspace, data, filename)
                promote(library, workspace, language_id, artifact, fields['asset_id'], fields['kind'], fields['variant'], weight, fields.get('style') or None, fields.get('family') or None)
                code, body = 303, b''
                headers.append(('Location', '/languages/' + language_id))
            elif method == 'GET' and path == '/compare':
                a = load_language(library, identifier(query.get('a',[''])[0]))
                b = load_language(library, identifier(query.get('b',[''])[0]))
                pages = load_vocabulary(library, a['vocabulary'])['context']['pages']
                page, width = parameters(query, pages)
                body = html('compare.html', title='Compare', a=a, b=b, ra=validate(library,a['id'],a), rb=validate(library,b['id'],b),
                            page=page, width=width, pages=pages, widths=VIEWPORTS)
            elif method == 'GET' and len(segments) == 4 and segments[0] == 'checks':
                language_id = identifier(segments[1])
                folder = report_folder(library, language_id, segments[2])
                result = read_json(inside(folder,'report.json'))
                allowed = {page.removesuffix('.html') + f'@{width}.png' for page in result['checked']['pages'] for width in result['checked']['widths']}
                allowed.update(name for finding in result['findings'] for name in screenshots(finding))
                if segments[3] == 'report.json':
                    content_type = 'application/json; charset=utf-8'
                elif segments[3] in allowed:
                    content_type = 'image/png'
                else:
                    raise RequestError('Unknown check artifact',404)
                body = inside(folder,segments[3]).read_bytes()
            elif method == 'GET' and len(segments) >= 3 and segments[0] == 'preview':
                from ..render import preview_files, InvalidLanguage
                language_id = identifier(segments[1])
                try:
                    files = preview_files(library, language_id)
                except InvalidLanguage as exc:
                    raise RequestError('Preview cannot be built: ' + '; '.join(f['rule']+' '+f['pointer']+' '+f['message'] for f in exc.report['findings']), 422) from exc
                filename = '/'.join(segments[2:])
                if filename not in files:
                    raise RequestError('Unknown preview file', 404)
                body = files[filename]
                content_type = mimetypes.guess_type(filename)[0] or 'application/octet-stream'
                if filename.endswith('.svg'):
                    headers.append(('Content-Security-Policy', "sandbox; default-src 'none'; style-src 'unsafe-inline'"))
            else:
                raise RequestError('Unknown route', 404)
        except FileNotFoundError as exc:
            code = 404
            body = html('error.html', title='Not found', message=str(exc))
        except (RequestError, ValueError, OSError, KeyError) as exc:
            code = exc.status if isinstance(exc, RequestError) else 400
            body = html('error.html', title='Unable to complete request', message=str(exc))
            log.warning('request_failed language=%s status=%s error=%s', language_id, code, str(exc)[:300])
        status_text = {200:'OK',303:'See Other',400:'Bad Request',404:'Not Found',413:'Content Too Large',422:'Unprocessable Content'}[code]
        headers.extend([('Content-Type',content_type),('Content-Length',str(len(body))),('X-Content-Type-Options','nosniff'),('Cache-Control','no-store')])
        if not any(key == 'Content-Security-Policy' for key,_ in headers):
            headers.append(('Content-Security-Policy',CSP))
        start_response(f'{code} {status_text}', headers)
        log.info('request language=%s method=%s status=%s bytes=%d', language_id, environ.get('REQUEST_METHOD','GET'), code, len(body))
        return [body]
    return app
