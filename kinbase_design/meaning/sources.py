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
        # Hex shorthand and letter case are notation; any other syntax is a conversion.
        return 'color', color, not re.fullmatch(r'#[0-9a-fA-F]{3,8}', text)
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


THEME_SCOPE = re.compile(r'[.\[][\w="\'-]*(?:dark|light|theme)[\w="\'-]*\]?')


def token_scope(selectors):
    """Whether a rule declares tokens: a document root, or a bare theme switch.

    A utility class or a component that sets a custom property is an override in its
    own scope, not a definition of the token.
    """
    for selector in selectors.split(','):
        selector = selector.strip()
        if selector in {':root', ':host', 'html', 'body'} or THEME_SCOPE.fullmatch(selector):
            return True
    return selectors.strip().startswith('@theme')


def css_tokens(text):
    """Custom property declarations in cascade order: (name, value, context, line).

    A scope naming dark or light supplies that context. Returns the declarations
    and how many were set outside a token scope and therefore not read.
    """
    def spaces(match):
        return '\n' * match[0].count('\n')
    text = re.sub(r'/\*.*?\*/', spaces, text, flags=re.S)
    found, ignored, stack, buffer, line, start = [], 0, [], '', 1, 1
    def flush():
        nonlocal ignored
        match = re.fullmatch(r'\s*--([A-Za-z0-9_-]+)\s*:\s*(.+?)\s*', buffer, flags=re.S)
        if not match or not stack:
            return
        rules = [prelude for prelude in stack if not prelude.startswith('@') or prelude.startswith('@theme')]
        if len(rules) != 1 or not token_scope(rules[0]):
            ignored += 1
            return
        if VAR.fullmatch(match[2]) and VAR.fullmatch(match[2])[1] == match[1]:
            return  # A theme layer re-exporting the property under its own name.
        # The theme may be named by the rule or by a prefers-color-scheme query around it.
        scope = ' '.join([rules[0]] + [prelude for prelude in stack if prelude.startswith('@media')]).lower()
        found.append((match[1], match[2], 'dark' if 'dark' in scope else 'light' if 'light' in scope else BASE, start))
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
    return found, ignored


def token(table, path, artifact):
    return table.setdefault(path, {'path': path, 'type': None, 'artifact': artifact, 'contexts': {}})


def read_css(table, problems, artifact, text, only=()):
    declarations, ignored = css_tokens(text)
    if only:
        declarations = [item for item in declarations if item[0].startswith(tuple(only))]
    if ignored:
        problems.append({'artifact': artifact, 'message':
                         f'{ignored} custom property declarations outside a root or theme scope were not read as tokens'})
    names = {name for name, *_ in declarations}
    for name, value, context, line in declarations:
        entry = token(table, 'css.' + name, artifact)
        kind, parsed, converted = css_value(name, value)
        if kind == 'alias' and parsed not in names:
            kind, parsed = None, 'The referenced custom property is not declared in this source'
        record = {'location': f'css:--{name}@{context}; line {line}', 'raw': value}
        if kind is None:
            record['unsupported'] = parsed
        else:
            record.update(value='{css.' + parsed + '}' if kind == 'alias' else parsed, kind=kind)
            if converted:
                record['converted'] = True
        earlier = entry['contexts'].get(context)
        # The cascade's last declaration wins. When the schema cannot hold it exactly,
        # the source's own earlier value is kept and the override is recorded.
        if earlier and 'value' in earlier and not earlier.get('converted') and (kind is None or converted):
            earlier['overridden_by'] = value
            continue
        entry['contexts'][context] = record
    for entry in table.values():
        kinds = {record.get('kind') for record in entry['contexts'].values() if record.get('kind') not in {None, 'alias'}}
        if len(kinds) > 1:
            problems.append({'artifact': artifact, 'message': f'--{entry["path"].removeprefix("css.")} changes type between contexts'})
            for record in entry['contexts'].values():
                record['unsupported'] = 'The value changes token type between contexts'
                record.pop('value', None)
        elif kinds:
            entry['type'] = kinds.pop()
        for record in entry['contexts'].values():
            record.pop('kind', None)
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


MODES = ('light', 'dark')


def read_dtcg(table, problems, artifact, data):
    tree = json.loads(data)
    if not isinstance(tree, dict):
        raise ValueError('DTCG import must be an object')
    tokens = Tokens(tree)
    # A group whose only members are tokens named light and dark is one themed token.
    members = {}
    for path in tokens.nodes:
        members.setdefault(path.rpartition('.')[0], set()).add(path.rpartition('.')[2])
    themed = {group for group, names in members.items() if group and names <= set(MODES)
              and not any(other.startswith(group + '.') and other.count('.') > group.count('.') + 1 for other in tokens.nodes)}
    def unthemed(value):
        alias = ALIAS.fullmatch(value) if isinstance(value, str) else None
        if alias and alias[1].rpartition('.')[0] in themed:
            return '{' + alias[1].rpartition('.')[0] + '}'
        return value
    for path, node in tokens.nodes.items():
        group, _, leaf = path.rpartition('.')
        folded = group in themed
        entry = token(table, group if folded else path, artifact)
        record = {'location': 'json:' + pointer(*path.split('.'), '$value'), 'value': unthemed(node['$value'])}
        try:
            entry['type'], _ = tokens.evaluate(path)
        except (ValueError, KeyError) as exc:
            entry['type'] = entry['type'] or (node.get('$type') if isinstance(node.get('$type'), str) else None)
            record['unsupported'] = str(exc)
        entry['contexts'][leaf if folded else BASE] = record


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


def read(workspace, artifact_ids, only=()):
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
                read_css(table, problems, artifact, data.decode('utf-8'), only)
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


def holdable(path):
    """Whether the language schema can name this token (R4 constrains breakpoint ids)."""
    return not path.startswith('breakpoint.') or bool(re.fullmatch(r'breakpoint\.[a-z][a-z0-9]*(?:-[a-z0-9]+)*', path))


def context_value(entry, context):
    """The record a context resolves to; a named context falls back to the base one."""
    return entry['contexts'].get(context) or entry['contexts'].get(BASE)


def tree(table, context):
    """A DTCG tree of the tokens one context can express; dangling aliases are left out."""
    nodes = {}
    for path, entry in table.items():
        record = context_value(entry, context)
        if not record or 'value' not in record or entry['type'] is None or not holdable(path):
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
