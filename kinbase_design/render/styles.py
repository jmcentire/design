"""CSS is derived from the resolver; identity stays out of sample HTML."""
import json
from pathlib import Path
from ..language.resolver import resolve
from ..language.tokens import Tokens
from ..language.properties import KEYWORDS
from ..language.versions import digest
from ..vocabulary import slot_map

FONT_FORMAT_HINTS = {'woff2': 'woff2', 'woff': 'woff', 'ttf': 'truetype', 'otf': 'opentype'}

PSEUDOS = {'hover': ':hover', 'focus-visible': ':focus-visible', 'active': ':active',
           'disabled': ':disabled', 'selected': '[aria-selected="true"]',
           'expanded': '[aria-expanded="true"]', 'loading': '[aria-busy="true"]',
           'error': '[aria-invalid="true"]'}


def declaration(properties):
    return ';'.join(f'{key}:{value["value"]}' for key, value in sorted(properties.items()) if key != 'surface')


def selector(construct, slot=None, state=None):
    root = f'[data-kd-construct="{construct}"]'
    child = f' [data-kd-slot="{construct}.{slot}"]' if slot else ''
    if state and state != 'default':
        static = root + f'[data-kd-state="{state}"]' + child
        pseudo = PSEUDOS.get(state)
        interaction = ',' + root + child + pseudo if pseudo else ''
        if state in {'focus-visible', 'disabled'}:
            interaction += ',' + root + child + ':has(' + pseudo + ')'
        return static + interaction
    return root + child


def stylesheet(document, vocabulary):
    tokens = Tokens(document.get('style', {}))
    # JSON escapes user text, and escaping comment terminators keeps this inert.
    identity = json.dumps({'id':document['id'], 'name':document['name'], 'hash':digest(document)}, ensure_ascii=True).replace('*/', '*\\/')
    rules = ['/* Kinbase Design ' + identity + ' */', Path(__file__).with_name('base.css').read_text()]
    for asset, entry in document.get('assets', {}).items():
        if entry['kind'] != 'font':
            continue
        families = set()
        for name, node in tokens.nodes.items():
            if node['$type'] == 'fontFamily' and tokens.font_asset(name) == asset:
                # The asset applies to the first family; the rest are fallbacks.
                families.add(tokens.evaluate(name)[1].split(', ')[0])
        for family in sorted(families):
            for variant, detail in sorted(entry['variants'].items()):
                format_hint = FONT_FORMAT_HINTS.get(detail['format'], detail['format'])
                rules.append('@font-face{' + f'font-family:{family};src:url("assets/{asset}-{variant}.{detail["format"]}") format("{format_hint}");font-weight:{detail["weight"]};font-style:{detail["style"]};font-display:swap' + '}')
    breakpoints = sorted((tokens.breakpoint(name.removeprefix('breakpoint.')), name.removeprefix('breakpoint.')) for name in tokens.nodes if name.startswith('breakpoint.'))
    emitted = {}
    for bp in [None] + [name for _, name in breakpoints]:
        block = []
        for construct, contract in vocabulary['constructs'].items():
            for slot in [None] + list(slot_map(contract)):
                scope = construct + ('.' + slot if slot else '')
                base = declaration(resolve(document, vocabulary, scope, 'default', bp)['properties'])
                for state in contract['states']:
                    props = declaration(resolve(document, vocabulary, scope, state, bp)['properties'])
                    key = (construct, slot, state)
                    if state != 'default' and props == base and key not in emitted:
                        continue
                    if props and emitted.get(key) != props:
                        block.append(selector(construct, slot, state) + '{' + props + '}')
                        emitted[key] = props
        if bp and block:
            rules.append(f'@media (min-width:{tokens.breakpoint(bp):g}px)' + '{\n' + '\n'.join(block) + '\n}')
        elif not bp:
            rules.extend(block)
    for construct, component in document.get('components', {}).items():
        for part, props in component.get('parts', {}).items():
            values = {key:{'value':value if key in KEYWORDS else tokens.reference(value)[1]} for key,value in props.items()}
            rules.append(f'[data-kd-construct="{construct}"] [data-kd-part="{part}"]' + '{' + declaration(values) + '}')
    return '\n'.join(rules) + '\n'
