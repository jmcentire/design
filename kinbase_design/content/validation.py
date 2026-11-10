"""Presentation-independent validation of kinbase-content/1 and local media."""
from copy import deepcopy
import hashlib
from pathlib import Path, PurePosixPath
import re
from urllib.parse import urlsplit
from xml.etree.ElementTree import ParseError
from ..assets import inspect_format
from ..config import MAX_UPLOAD_BYTES
from ..findings import Finding, location, pointer
from ..storage import inside


# Structural paths shared with the declarative mapper. Leaf value validation
# remains below, so source text is reported without coercion.
INLINE = [{'text':None,'href':None,'em':None,'strong':None}]
LINK = {'text':None,'href':None}
MEDIA = dict.fromkeys(('src','alt','decorative','caption','credit'))
CARD = {'title':None,'eyebrow':None,'body':INLINE,'media':MEDIA,'facts':[{'label':None,'value':None}],'action':LINK}
ENTRY = {'paragraph':INLINE,'media':MEDIA,'list':{'ordered':None,'items':[INLINE]},'quote':{'text':INLINE,'cite':None}}
BLOCK_FIELDS = {
    'hero':{'eyebrow':None,'title':None,'body':INLINE,'media':MEDIA,'actions':[LINK]},
    'section':{'eyebrow':None,'title':None,'content':[ENTRY]},
    'collection':{'title':None,'intro':INLINE,'items':[CARD]},
    'cta':{'title':None,'body':INLINE,'actions':[LINK]}}
PAGE_FIELDS = {'page':dict.fromkeys(('title','lang','description')),
               'site':{'name':None,'logo':MEDIA,'nav':[LINK]},
               'footer':{'text':INLINE,'links':[LINK],'notices':[None]}}


def content_field_path(kind,path,item=False):
    keys=path.split('/')
    if not item and (not isinstance(kind,str) or kind not in BLOCK_FIELDS or keys[0] in PAGE_FIELDS and len(keys)==1):return False
    shape=CARD if item else {**BLOCK_FIELDS[kind],'id':None,**PAGE_FIELDS}
    for key in keys:
        if isinstance(shape,dict) and key in shape:shape=shape[key]
        elif isinstance(shape,list) and re.fullmatch(r'0|[1-9][0-9]*',key) and int(key)<=1000:shape=shape[0]
        else:return False
    return True


def safe_href(value):
    if not isinstance(value, str) or not value.strip() or any(ord(c) < 32 for c in value) or '\\' in value:
        return False
    try:
        parts = urlsplit(value)
        return parts.scheme.lower() in {'', 'https', 'http', 'mailto', 'tel'} and not parts.username and not parts.password
    except ValueError:
        return False


class ContentValidator:
    def __init__(self, document, file, check_images=True):
        self.document, self.file = document, Path(file)
        self.findings, self.files, self.media_paths = [], {}, {}
        self.check_images = check_images
        self.ids = set()

    def issue(self, path, expected, rule='content-schema', kind='violation', message=None):
        path, value = location(self.document, path)
        finding = Finding(kind, rule, str(self.file), path, value, expected, message or expected).to_dict()
        if finding not in self.findings:
            self.findings.append(finding)

    def obj(self, value, path, allowed, required=()):
        if not isinstance(value, dict):
            self.issue(path, 'an object')
            return False
        for key in value.keys() - set(allowed):
            self.issue(path + pointer(key), 'a declared field')
        for key in set(required) - value.keys():
            self.issue(path, 'required field: ' + key)
        return True

    def text(self, value, path, nonempty=False):
        if not isinstance(value, str) or '\x00' in value or (nonempty and not value.strip()):
            self.issue(path, 'a nonempty string' if nonempty else 'a string without NUL')
            return False
        return True

    def array(self, value, path, visit):
        if not isinstance(value, list):
            self.issue(path, 'an array')
            return
        for i, item in enumerate(value):
            visit(item, path + pointer(i))

    def inline(self, value, path):
        if isinstance(value, str):
            self.text(value, path)
            return
        def run(item, p):
            if isinstance(item, str):
                self.text(item, p)
            elif self.obj(item, p, {'text', 'href', 'em', 'strong'}, {'text'}):
                if 'text' in item:self.text(item['text'], p+'/text')
                if 'href' in item:self.href(item['href'], p+'/href')
                for key in ('em', 'strong'):
                    if key in item and item[key] is not True:self.issue(p+'/'+key, 'true when present')
        self.array(value, path, run)

    def href(self, value, path):
        if not safe_href(value):self.issue(path, 'an ordinary relative, fragment, HTTP(S), mailto or tel link')

    def link(self, value, path):
        if self.obj(value, path, {'text', 'href'}, {'text', 'href'}):
            if 'text' in value:self.text(value['text'], path+'/text', True)
            if 'href' in value:self.href(value['href'], path+'/href')

    def media(self, value, path):
        if not self.obj(value, path, {'src','alt','decorative','caption','credit'}, {'src','alt'}):return
        for key in ('alt','caption','credit'):
            if key in value:self.text(value[key], path+'/'+key)
        if 'decorative' in value and type(value['decorative']) is not bool:self.issue(path+'/decorative', 'a boolean')
        if value.get('alt') == '' and value.get('decorative') is not True:self.issue(path+'/alt', 'nonempty alt text, or decorative: true')
        src = value.get('src')
        if not self.check_images:
            if 'src' in value:self.text(src,path+'/src',True)
            return
        if not isinstance(src, str) or not src or '\\' in src or '\x00' in src or ':' in src or PurePosixPath(src).is_absolute() or '..' in PurePosixPath(src).parts:
            self.issue(path+'/src', 'a local relative image path inside the content directory', 'content-image')
            return
        try:
            source = inside(self.file.parent, src)
            extensions = {'.png':'png','.jpg':'jpg','.jpeg':'jpg','.webp':'webp','.svg':'svg'}
            if source.suffix.lower() not in extensions:raise ValueError('Image needs a supported filename extension')
            if source.stat().st_size > MAX_UPLOAD_BYTES:raise ValueError('Image exceeds upload byte limit')
            data = source.read_bytes()
            fmt = inspect_format(data, 'image')
            if fmt!=extensions[source.suffix.lower()]:raise ValueError('Image bytes do not match the filename extension')
            name = 'content-assets/' + hashlib.sha256(data).hexdigest() + '.' + fmt
            self.files[name] = data
            self.media_paths[path] = name
        except (OSError, ValueError, ParseError) as exc:
            self.issue(path+'/src', 'a readable, decodable PNG, JPEG, WebP or safe SVG', 'content-image', 'missing', str(exc)[:300])

    def entry(self, value, path):
        if not self.obj(value, path, {'paragraph','list','media','quote'}):return
        if len(value) != 1:
            self.issue(path, 'exactly one paragraph, list, media or quote')
            return
        if 'paragraph' in value:self.inline(value['paragraph'], path+'/paragraph')
        elif 'media' in value:self.media(value['media'], path+'/media')
        elif 'list' in value:
            item = value['list']; p = path+'/list'
            if self.obj(item, p, {'ordered','items'}, {'items'}):
                if 'ordered' in item and type(item['ordered']) is not bool:self.issue(p+'/ordered', 'a boolean')
                if 'items' in item:self.array(item['items'], p+'/items', self.inline)
        elif 'quote' in value:
            item = value['quote']; p = path+'/quote'
            if self.obj(item, p, {'text','cite'}, {'text'}):
                if 'text' in item:self.inline(item['text'], p+'/text')
                if 'cite' in item:self.text(item['cite'], p+'/cite')

    def card(self, value, path):
        if not self.obj(value, path, set(CARD), {'title'}):return
        for key in ('title','eyebrow'):
            if key in value:self.text(value[key], path+'/'+key, key=='title')
        if 'body' in value:self.inline(value['body'], path+'/body')
        if 'media' in value:self.media(value['media'], path+'/media')
        if 'action' in value:self.link(value['action'], path+'/action')
        def fact(item, p):
            if self.obj(item,p,{'label','value'},{'label','value'}):
                for key in ('label','value'):
                    if key in item:self.text(item[key], p+'/'+key)
        if 'facts' in value:self.array(value['facts'], path+'/facts', fact)

    def block(self, value, path):
        fields = BLOCK_FIELDS
        if not isinstance(value, dict):
            self.issue(path, 'a block object');return
        kind = value.get('type')
        if not isinstance(kind,str) or kind not in fields:
            self.issue(path+'/type', 'hero, section, collection or cta');return
        self.obj(value, path, set(fields[kind]) | {'type','id'}, {'type'} | ({'title'} if kind in {'hero','cta'} else set()))
        for key in ('title','eyebrow','id'):
            if key in value:self.text(value[key], path+'/'+key, True)
        if 'id' in value and isinstance(value['id'],str):
            if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_.:-]*',value['id']) or value['id'] in self.ids:
                self.issue(path+'/id', 'a unique fragment id beginning with a letter')
            self.ids.add(value['id'])
        for key in ('body','intro'):
            if key in value:self.inline(value[key], path+'/'+key)
        if 'media' in value:self.media(value['media'], path+'/media')
        if 'actions' in value:self.array(value['actions'], path+'/actions', self.link)
        if 'content' in value:self.array(value['content'], path+'/content', self.entry)
        if 'items' in value:self.array(value['items'], path+'/items', self.card)

    def run(self):
        d = self.document
        if not self.obj(d, '', {'schema','page','site','blocks','footer'}, {'schema','page','site','blocks'}):return
        if d.get('schema') != 'kinbase-content/1':self.issue('/schema', 'kinbase-content/1')
        if 'page' in d and self.obj(d['page'], '/page', {'title','lang','description'}, {'title'}):
            for key, value in d['page'].items():self.text(value, '/page/'+key, key!='description')
            if isinstance(d['page'].get('lang'),str) and not re.fullmatch(r'[A-Za-z]{2,8}(?:-[A-Za-z0-9]{1,8})*',d['page']['lang']):self.issue('/page/lang', 'a language tag such as en or en-US')
        if 'site' in d and self.obj(d['site'], '/site', {'name','logo','nav'}, {'name'}):
            if 'name' in d['site']:self.text(d['site']['name'], '/site/name', True)
            if 'logo' in d['site']:self.media(d['site']['logo'], '/site/logo')
            if 'nav' in d['site']:self.array(d['site']['nav'], '/site/nav', self.link)
        if 'blocks' in d:
            self.array(d['blocks'], '/blocks', self.block)
            if d['blocks'] == []:self.issue('/blocks', 'at least one block')
        if 'footer' in d and self.obj(d['footer'], '/footer', {'text','links','notices'}):
            f = d['footer']
            if 'text' in f:self.inline(f['text'], '/footer/text')
            if 'links' in f:self.array(f['links'], '/footer/links', self.link)
            if 'notices' in f:self.array(f['notices'], '/footer/notices', self.text)


def validate_content(document, file, check_images=True):
    validator = ContentValidator(document, file, check_images)
    validator.run()
    result = {'accepted':not validator.findings, 'findings':validator.findings}
    normalized = deepcopy(document)
    if not validator.findings and check_images:
        for path, src in validator.media_paths.items():
            _, media = location(normalized, path)
            media['src'] = src
    return result, normalized, validator.files
