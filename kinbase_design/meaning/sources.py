"""Read immutable private artifacts into one token table. Nothing is fetched or executed."""
import colorsys
import json
from pathlib import Path
import re
from ..artifacts import read_artifact
from ..artifacts.bundle import metadata
from ..config import MEANING_MAX_TOKENS, MEANING_MAX_USAGE, MEANING_USAGE_TEXT
from ..findings import pointer
from ..ingest.quantize import hex_color
from ..language.tokens import Tokens, ALIAS, normalize

BASE = 'base'
VAR = re.compile(r'var\(\s*--([A-Za-z0-9_-]+)\s*(?:,[^()]*)?\)')
NUMBER = r'-?(?:\d+(?:\.\d+)?|\.\d+)'


def css_color(value):
    text = value.strip().lower()
    if re.fullmatch(r'#[0-9a-f]{3,4}', text):
        text = '#' + ''.join(c * 2 for c in text[1:])
    match = re.fullmatch(r'hsla?\(([^)]+)\)', text)
    if match:
        parts = [p for p in re.split(r'[,\s/]+', match[1].strip()) if p]
        try:
            hue = float(parts[0].removesuffix('deg')) % 360 / 360
            saturation, light = (float(p.rstrip('%')) / 100 for p in parts[1:3])
            alpha = (float(parts[3].rstrip('%')) / (100 if parts[3].endswith('%') else 1)) if len(parts) == 4 else 1
        except (ValueError, IndexError):
            return None
        if len(parts) not in {3, 4}:
            return None
        red, green, blue = colorsys.hls_to_rgb(hue, light, saturation)
        channels = [red, green, blue] + ([alpha] if alpha < 1 else [])
        return '#' + ''.join(f'{round(max(0, min(1, c)) * 255):02x}' for c in channels)
    return hex_color(text)


def css_value(name, value):
    """Return (type, DTCG value, converted) or (None, reason, False)."""
    text = value.strip()
    alias = VAR.fullmatch(text)
    if alias:
        return 'alias', alias[1], False
    color = css_color(text)
    if color:
        return 'color', color, text.lower() != color
    if re.fullmatch(NUMBER + r'(px|rem)', text):
        return 'dimension', text, False
    words = set(re.split(r'[-_]+', name.lower()))
    if re.fullmatch(NUMBER, text):
        number = float(text)
        if words & {'weight', 'bold', 'medium', 'regular', 'semibold'} and 1 <= number <= 1000:
            return 'fontWeight', int(number) if number.is_integer() else number, False
        return 'number', int(number) if number.is_integer() else number, False
    if words & {'font', 'family'} and not re.search(r'[()\d]', text):
        families = [part.strip().strip('"\'') for part in text.split(',')]
        if all(re.fullmatch(r'[\w -]+', family) and family.strip() for family in families):
            return 'fontFamily', families, False
    return None, 'The value is outside the supported token types', False


def css_tokens(text):
    """Custom properties by context. A selector naming dark or light chooses the context."""
    def spaces(match):
        return '\n' * match[0].count('\n')
    text = re.sub(r'/\*.*?\*/', spaces, text, flags=re.S)
    found, stack, buffer, line, start = [], [], '', 1, 1
    def flush():
        match = re.fullmatch(r'\s*--([A-Za-z0-9_-]+)\s*:\s*(.+?)\s*', buffer, flags=re.S)
        if match and stack:
            scope = ' '.join(stack).lower()
            context = 'dark' if 'dark' in scope else 'light' if 'light' in scope else BASE
            found.append((match[1], match[2], context, start))
    for char in text:
        if char == '\n':
            line += 1
        if char == '{':
            stack.append(buffer.strip())
            buffer, start = '', line
        elif char == '}':
            flush()
            if stack:
                stack.pop()
            buffer, start = '', line
        elif char == ';':
            flush()
            buffer, start = '', line
        else:
            if not buffer.strip():
                start = line
            buffer += char
    return found


def token(table, path, artifact):
    return table.setdefault(path, {'path': path, 'type': None, 'artifact': artifact, 'contexts': {}})


def read_css(table, problems, artifact, text):
    names = {name for name, *_ in css_tokens(text)}
    for name, value, context, line in css_tokens(text):
        path = 'css.' + name
        entry = token(table, path, artifact)
        kind, parsed, converted = css_value(name, value)
        record = {'location': f'css:--{name}@{context}; line {line}', 'raw': value}
        if kind == 'alias':
            if parsed not in names:
                kind, parsed = None, 'The referenced custom property is not declared in this source'
            else:
                record['value'] = '{css.' + parsed + '}'
        elif kind:
            record['value'] = parsed
            if converted:
                record['converted'] = True
        if kind is None:
            record['unsupported'] = parsed
        elif kind != 'alias':
            if entry['type'] not in {None, kind}:
                problems.append({'artifact': artifact, 'message': f'--{name} changes type between contexts'})
                record['unsupported'] = 'The value changes token type between contexts'
                record.pop('value', None)
            else:
                entry['type'] = kind
        entry['contexts'][context] = record
    # An alias takes its type from its target once every declaration is read.
    for _ in range(len(table)):
        changed = False
        for entry in table.values():
            if entry['type'] is None:
                for record in entry['contexts'].values():
                    alias = ALIAS.fullmatch(record.get('value', '')) if isinstance(record.get('value'), str) else None
                    if alias and table.get(alias[1], {}).get('type'):
                        entry['type'] = table[alias[1]]['type']
                        changed = True
        if not changed:
            break


def read_dtcg(table, problems, artifact, data):
    tree = json.loads(data)
    if not isinstance(tree, dict):
        raise ValueError('DTCG import must be an object')
    tokens = Tokens(tree)
    for path, node in tokens.nodes.items():
        entry = token(table, path, artifact)
        record = {'location': 'json:' + pointer(*path.split('.'), '$value'), 'value': node['$value']}
        try:
            entry['type'], _ = tokens.evaluate(path)
        except (ValueError, KeyError) as exc:
            entry['type'] = node.get('$type') if isinstance(node.get('$type'), str) else None
            record['unsupported'] = str(exc)
        entry['contexts'][BASE] = record


def usage(table, artifact, text):
    """Lines of prose that name a token. Evidence only: prose is data, never a rule."""
    names = {}
    for path in table:
        name = path.removeprefix('css.')
        for spelling in ({'--' + name, name} if path.startswith('css.') else {path}):
            if spelling.startswith('--') or '-' in spelling or '.' in spelling:
                names[spelling] = path
    if not names:
        return []
    pattern = re.compile(r'(?<![\w.-])(' + '|'.join(sorted(map(re.escape, names), key=len, reverse=True)) + r')(?![\w-])')
    found = []
    for number, line in enumerate(text.splitlines(), 1):
        mentioned = list(dict.fromkeys(names[m] for m in pattern.findall(line)))
        if mentioned:
            found.append({'artifact': artifact, 'location': f'line {number}', 'tokens': mentioned,
                          'text': line.strip()[:MEANING_USAGE_TEXT]})
        if len(found) >= MEANING_MAX_USAGE:
            break
    return found


def read(workspace, artifact_ids):
    table, problems, documents = {}, [], []
    for artifact in artifact_ids:
        kind = metadata(workspace, artifact).get('kind', 'asset')
        if kind in {'capture', 'figma-export'}:
            problems.append({'artifact': artifact, 'message': f'{kind} artifacts enter through ingest; import their token files directly'})
            continue
        data, meta = read_artifact(workspace, artifact)
        suffix = Path(meta['filename']).suffix.lower()
        try:
            if kind == 'css' or suffix == '.css':
                read_css(table, problems, artifact, data.decode('utf-8'))
            elif kind == 'dtcg' or suffix == '.json':
                read_dtcg(table, problems, artifact, data)
            elif kind in {'doc', 'brief'} or suffix in {'.md', '.mdx', '.txt'}:
                documents.append((artifact, data.decode('utf-8')))
            else:
                problems.append({'artifact': artifact, 'message': 'Not a token source or a document'})
        except (ValueError, UnicodeError) as exc:
            problems.append({'artifact': artifact, 'message': str(exc)})
        if len(table) > MEANING_MAX_TOKENS:
            raise ValueError('Corpus exceeds the configured token bound')
    evidence = [item for artifact, text in documents for item in usage(table, artifact, text)][:MEANING_MAX_USAGE]
    return table, evidence, problems


def context_value(entry, context):
    """The record a context resolves to; a named context falls back to the base one."""
    return entry['contexts'].get(context) or entry['contexts'].get(BASE)


def tree(table, context):
    """A DTCG tree of the tokens one context can express; dangling aliases are left out."""
    nodes = {}
    for path, entry in table.items():
        record = context_value(entry, context)
        if not record or 'value' not in record or entry['type'] is None:
            continue
        value = record['value']
        try:
            if not (isinstance(value, str) and ALIAS.fullmatch(value)):
                normalize(entry['type'], value)
        except ValueError:
            continue
        nodes[path] = {'$type': entry['type'], '$value': value}
    while True:
        dangling = [path for path, node in nodes.items() if isinstance(node['$value'], str)
                    and (alias := ALIAS.fullmatch(node['$value'])) and alias[1] not in nodes]
        if not dangling:
            break
        for path in dangling:
            del nodes[path]
    result = {}
    for path in sorted(nodes):
        node = result
        parts = path.split('.')
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        node[parts[-1]] = nodes[path]
    return result
