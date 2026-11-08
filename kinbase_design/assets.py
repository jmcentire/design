"""Promotion is the single write path for approved, content-addressed assets."""
import hashlib
from io import BytesIO
import logging
import re
import struct
import xml.etree.ElementTree as ET
from fontTools.ttLib import TTFont, TTLibError
from PIL import Image
from .artifacts import read_artifact
from .storage import identifier, inside, load_language, save_language

KINDS = {'logo', 'font', 'image', 'icon'}
FORMATS = {'svg', 'png', 'jpg', 'webp', 'woff2', 'woff', 'ttf', 'otf'}
HASH_FILE = re.compile(r'^sha256/[0-9a-f]{64}$')
log = logging.getLogger(__name__)


def inspect_format(data, kind):
    if kind == 'font':
        # WOFF2 decoding needs optional Brotli, unavailable in the offline runtime.
        # Validate the fixed container header without changing the original bytes.
        if data[:4] == b'wOF2':
            if len(data) < 48:
                raise ValueError('Truncated WOFF2 header')
            length, tables, reserved, sfnt_size, compressed = struct.unpack('>IHHII', data[8:24])
            if length != len(data) or not tables or reserved or not sfnt_size or not 0 < compressed <= len(data) - 48:
                raise ValueError('Invalid WOFF2 container header')
            return 'woff2'
        with TTFont(BytesIO(data)) as font:
            if font.flavor in {'woff', 'woff2'}:
                return font.flavor
            return 'otf' if font.sfntVersion == 'OTTO' else 'ttf'
    if data.lstrip().startswith((b'<svg', b'<?xml')):
        if b'<!DOCTYPE' in data.upper() or b'<!ENTITY' in data.upper():
            raise ValueError('SVG entities and external declarations are not supported')
        root = ET.fromstring(data)
        if root.tag.split('}')[-1] != 'svg':
            raise ValueError('Expected SVG root')
        for node in root.iter():
            if node.tag.split('}')[-1] in {'script', 'foreignObject', 'style', 'iframe', 'animate', 'set'}:
                raise ValueError('Active SVG content is not supported')
            for key, value in node.attrib.items():
                if key.lower().startswith('on') or (key.split('}')[-1] == 'href' and not value.startswith('#')) or 'url(' in value.lower():
                    raise ValueError('SVG must not execute code or fetch external resources')
        return 'svg'
    with Image.open(BytesIO(data)) as image:
        fmt = {'JPEG': 'jpg', 'PNG': 'png', 'WEBP': 'webp'}.get(image.format)
        image.verify()
        if not fmt:
            raise ValueError('Unsupported image format')
        return fmt


def promote(library, workspace, language_id, artifact_id, asset_id, kind, variant,
            weight=None, style=None, family=None):
    identifier(asset_id)
    identifier(variant)
    if kind not in KINDS:
        raise ValueError('Unknown asset kind')
    document = load_language(library, language_id)
    data, metadata = read_artifact(workspace, artifact_id)
    try:
        fmt = inspect_format(data, kind)
    except (TTLibError, ET.ParseError, ImportError) as exc:
        raise ValueError('Invalid or unsupported asset bytes: ' + str(exc)) from exc
    entry = document.setdefault('assets', {}).setdefault(asset_id, {'kind': kind, 'variants': {}})
    if entry['kind'] != kind:
        raise ValueError('An asset cannot change kind')
    detail = {'file': 'sha256/' + metadata['sha256'], 'format': fmt}
    if kind == 'font':
        if weight is None or isinstance(weight, bool) or not 1 <= int(weight) <= 1000:
            raise ValueError('Font promotion requires --weight between 1 and 1000')
        if style not in {None, 'normal', 'italic'}:
            raise ValueError('Unsupported font style')
        detail.update(weight=int(weight), style=style or 'normal')
        if family:
            if not re.fullmatch(r'[\w -]+', family):
                raise ValueError('Invalid font family name')
            entry.setdefault('meta', {})['font'] = {'family': family}
    path = inside(library, 'languages', language_id, 'assets', detail['file'])
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if hashlib.sha256(path.read_bytes()).hexdigest() != metadata['sha256']:
            raise ValueError('Asset content hash mismatch')
    else:
        with path.open('xb') as stream:
            stream.write(data)
    entry['variants'][variant] = detail
    save_language(library, language_id, document)
    log.info('asset_promote language=%s asset=%s variant=%s hash=%s', language_id, asset_id, variant, metadata['sha256'])
    return entry


def asset_path(library, language_id, detail):
    if not HASH_FILE.fullmatch(detail.get('file', '')):
        raise ValueError('Expected content-addressed asset file')
    return inside(library, 'languages', identifier(language_id), 'assets', detail['file'])


def background_binding(document, value):
    """Resolve the background-image asset syntax without touching source originals."""
    parts = value.split(':') if isinstance(value, str) else []
    if len(parts) != 3 or parts[0] != 'asset' or not all(parts[1:]):
        raise ValueError('Expected asset:<asset-id>:<variant>')
    asset, variant = parts[1:]
    entry = document.get('assets', {}).get(asset)
    if entry is None:
        raise KeyError('Missing background image asset: ' + asset)
    if not isinstance(entry, dict) or entry.get('kind') != 'image':
        raise ValueError('Background binding must name an image asset')
    variants = entry.get('variants', {})
    if not isinstance(variants, dict):
        raise ValueError('Asset variants must be an object')
    if variant not in variants:
        raise KeyError('Missing background image variant: ' + variant)
    detail = variants[variant]
    if not isinstance(detail, dict) or detail.get('format') not in ('svg','png','jpg','webp'):
        raise ValueError('Background image needs a supported image format')
    return asset, variant, detail


def package_files(library, language_id, document):
    """One binding-name/file mapping for previews, exports and hand-offs."""
    return {f'assets/{asset}-{variant}.{detail["format"]}': asset_path(library, language_id, detail).read_bytes()
            for asset,entry in sorted(document.get('assets', {}).items())
            for variant,detail in sorted(entry['variants'].items())}
