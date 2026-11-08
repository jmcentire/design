"""CSS is derived from the resolver; identity stays out of sample HTML."""
import json
from pathlib import Path
from ..language.resolver import resolve, parse_scope, property_pointer
from ..findings import location
from ..language.tokens import ALIAS, Tokens
from ..language.properties import property_value, CONTROL_BOX_PROPERTIES, CONTROL_TEXT_PROPERTIES
from ..language.versions import digest
from ..vocabulary import slot_map

FONT_FORMAT_HINTS = {'woff2': 'woff2', 'woff': 'woff', 'ttf': 'truetype', 'otf': 'opentype'}

PSEUDOS = {'hover': ':hover', 'focus-visible': ':focus-visible', 'active': ':active',
           'disabled': ':disabled', 'selected': '[aria-selected="true"]',
           'expanded': '[aria-expanded="true"]', 'loading': '[aria-busy="true"]',
           'error': '[aria-invalid="true"]'}


def declaration(properties):
    return ';'.join(f'{key}:{value["value"]}' for key, value in sorted(properties.items()) if key != 'surface')


def selector(construct, slot=None, state=None, native=False):
    root = f'[data-kd-construct="{construct}"]'
    child = f' [data-kd-slot="{construct}.{slot}"]' if slot else ''
    control = ' :is(input,select,textarea,button)' if native else ''
    if state and state != 'default':
        static = root + f'[data-kd-state="{state}"]' + child + control
        pseudo = PSEUDOS.get(state)
        interaction = ',' + root + child + control + pseudo if pseudo else ''
        if native and pseudo:
            interaction += ',' + root + child + pseudo + control
        if state in {'focus-visible', 'disabled'}:
            interaction += ',' + root + child + ':has(' + pseudo + ')' + control
        return static + interaction
    return root + child + control


def treatments(properties, control):
    if not control:return (declaration(properties), '')
    return (declaration({k:v for k,v in properties.items() if k not in CONTROL_BOX_PROPERTIES}),
            declaration({k:v for k,v in properties.items() if k in CONTROL_BOX_PROPERTIES}))


def stylesheet(document, vocabulary, variables=None):
    tokens = Tokens(document.get('style', {}))

    def resolved(scope, state='default', breakpoint=None):
        properties = resolve(document, vocabulary, scope, state, breakpoint)['properties']
        if variables is not None:
            for name, detail in properties.items():
                _, raw = location(document, property_pointer(document, vocabulary, name, detail))
                alias = ALIAS.fullmatch(raw) if isinstance(raw, str) else None
                if alias:detail['value'] = 'var(' + variables[alias[1]] + ')'
        return properties
    # JSON escapes user text, and escaping comment terminators keeps this inert.
    identity = json.dumps({'id':document['id'], 'name':document['name'], 'hash':digest(document)}, ensure_ascii=True).replace('*/', '*\\/')
    rules = ['/* Kinbase Design ' + identity + ' */', Path(__file__).with_name('base.css').read_text()]
    body = resolved('page-shell.body')
    inherited = {k:v for k,v in body.items() if k in {'color','font-family','font-size','font-weight','line-height'}}
    background = resolved('page-shell').get('background-color')
    if background: inherited['background-color'] = background
    focus = inherited.get('color', {}).get('value', 'currentColor')
    rules.append('body{--kd-focus-color:' + str(focus) + ';' + declaration(inherited) + '}')
    for construct,contract in vocabulary['constructs'].items():
        for slot in contract['slots']:
            if slot['kind']=='control':
                rules.append(selector(construct,slot['id'],native=True)+'{'+declaration({p:{'value':'inherit'} for p in CONTROL_TEXT_PROPERTIES})+'}')
    for asset, entry in sorted(document.get('assets', {}).items()):
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
                control = slot is not None and slot_map(contract)[slot]['kind']=='control'
                base = treatments(resolved(scope, 'default', bp),control)
                for state in contract['states']:
                    props = treatments(resolved(scope, state, bp),control)
                    key = (construct, slot, state)
                    if state != 'default' and props == base and key not in emitted:
                        continue
                    if any(props) and emitted.get(key) != props:
                        for native,values in enumerate(props):
                            if values:block.append(selector(construct, slot, state, native=bool(native)) + '{' + values + '}')
                        emitted[key] = props
        if bp and block:
            rules.append(f'@media (min-width:{tokens.breakpoint(bp):g}px)' + '{\n' + '\n'.join(block) + '\n}')
        elif not bp:
            rules.extend(block)
    for construct, component in sorted(document.get('components', {}).items()):
        for part, props in sorted(component.get('parts', {}).items()):
            values = {key:{'value':('var(' + variables[ALIAS.fullmatch(value)[1]] + ')'
                                  if variables is not None and isinstance(value,str) and ALIAS.fullmatch(value)
                                  else property_value(document, tokens, key, value))} for key,value in props.items()}
            rules.append(f'[data-kd-construct="{construct}"] [data-kd-part="{part}"]' + '{' + declaration(values) + '}')
    for behavior in document.get('behaviors', []):
        scope = parse_scope(behavior['scope'], vocabulary)
        target = selector(scope.construct, scope.slot)
        if behavior['kind'] == 'truncate':
            rules.append(target + '{display:-webkit-box;-webkit-box-orient:vertical;-webkit-line-clamp:' + str(behavior['lines']) + ';overflow:hidden}')
        elif behavior['kind'] == 'horizontal-scroll':
            rules.append(target + '{overflow-x:auto;overscroll-behavior-x:contain}')
            media = target if scope.slot else target + ' [data-kd-slot$=".media"]'
            rules.append(media + '{display:flex;gap:inherit}')
            rules.append(media + '>img{flex:0 0 100%;max-width:none}')
    return '\n'.join(rules) + '\n'
