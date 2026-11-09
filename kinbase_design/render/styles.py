"""CSS is derived from the resolver; identity stays out of sample HTML."""
import json
from pathlib import Path
from ..language.resolver import Resolver, parse_scope, property_pointer
from ..findings import location
from ..language.tokens import ALIAS
from ..language.properties import property_value, CONTROL_BOX_PROPERTIES, CONTROL_TEXT_PROPERTIES, IMAGE_PROPERTIES, LAYOUT_PROPERTIES
from ..language.versions import digest
from ..vocabulary import slot_map

FONT_FORMAT_HINTS = {'woff2': 'woff2', 'woff': 'woff', 'ttf': 'truetype', 'otf': 'opentype'}

PSEUDOS = {'hover': ':hover', 'focus-visible': ':focus-visible', 'active': ':active',
           'disabled': ':disabled', 'selected': '[aria-selected="true"]',
           'expanded': '[aria-expanded="true"]', 'loading': '[aria-busy="true"]',
           'error': '[aria-invalid="true"]'}


def declaration(properties):
    result = ';'.join(f'{key}:{value["value"]}' for key, value in sorted(properties.items()) if key != 'surface')
    if 'outline-color' in properties:
        # The safety outline uses this resolved color on focused descendants too.
        result += ';--kd-focus-color:' + str(properties['outline-color']['value'])
    return result


def selector(construct, slot=None, state=None, native=False, child=None):
    root = f'[data-kd-construct="{construct}"]'
    if child is None:child = f' [data-kd-slot="{construct}.{slot}"]' if slot else ''
    control = ' >img' if native == 'image' else ' :is(input,select,textarea,button)' if native else ''
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


def treatments(properties, control, media=False):
    if media:return (declaration({k:v for k,v in properties.items() if k not in IMAGE_PROPERTIES}), '', declaration({k:v for k,v in properties.items() if k in IMAGE_PROPERTIES}))
    if not control:return (declaration(properties), '', '')
    return (declaration({k:v for k,v in properties.items() if k not in CONTROL_BOX_PROPERTIES}),
            declaration({k:v for k,v in properties.items() if k in CONTROL_BOX_PROPERTIES}), '')


def stylesheet(document, vocabulary, variables=None):
    resolver = Resolver(document, vocabulary)
    tokens = resolver.tokens
    def select(construct, slot=None, state=None, native=False):
        target = selector(construct,slot,state,native)
        if native == 'image' and slot:
            # A hook may annotate the image itself or a figure/span containing it.
            target += ',' + selector(construct,slot,state,child=f' img[data-kd-slot="{construct}.{slot}"]')
        return target

    def resolved(scope, state='default', breakpoint=None):
        properties = resolver.resolve(scope, state, breakpoint)['properties']
        if variables is not None:
            for name, detail in properties.items():
                _, raw = location(document, property_pointer(document, vocabulary, name, detail))
                alias = ALIAS.fullmatch(raw) if isinstance(raw, str) else None
                if alias and name not in LAYOUT_PROPERTIES:detail['value'] = 'var(' + variables[alias[1]] + ')'
        return properties
    # JSON escapes user text, and escaping comment terminators keeps this inert.
    identity = json.dumps({'id':document['id'], 'name':document['name'], 'hash':digest(document)}, ensure_ascii=True).replace('*/', '*\\/')
    base = Path(__file__).with_name('base.css').read_text()
    if vocabulary.get('content_pages'):
        # All normal language declarations outrank presentation defaults, even
        # when the default's selector is more specific. Keep v1's cascade intact.
        base += Path(__file__).with_name('content.css').read_text()
        if vocabulary.get('composition_rules'):
            base += Path(__file__).with_name('composition.css').read_text()
        if 'label-proximity' in vocabulary.get('composition_rules',[]):
            base += Path(__file__).with_name('readability.css').read_text()
        base = '@layer kd-defaults {\n' + base + '\n}'
    rules = ['/* Kinbase Design ' + identity + ' */', base]
    body = resolved('page-shell.body')
    inherited = {k:v for k,v in body.items() if k in {'color','font-family','font-size','font-weight','line-height'}}
    background = resolved('page-shell').get('background-color')
    if background: inherited['background-color'] = background
    focus = inherited.get('color', {}).get('value', 'currentColor')
    rules.append('body{--kd-focus-color:' + str(focus) + ';' + declaration(inherited) + '}')
    for construct,contract in vocabulary['constructs'].items():
        for slot in contract['slots']:
            if slot['kind']=='control':
                rules.append(select(construct,slot['id'],native=True)+'{'+declaration({p:{'value':'inherit'} for p in CONTROL_TEXT_PROPERTIES})+'}')
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
    heading_scopes={}
    stateful_slots={(construct,slot) for construct,component in document.get('components',{}).items()
                    for slot,treatment in component.get('slots',{}).items()
                    if any(state!='default' and props for state,props in treatment.get('states',{}).items())}
    for target,override,_ in resolver.overrides:
        if target.slot and target.state:stateful_slots.add((target.construct,target.slot))
        if target.heading:
            keys=heading_scopes.setdefault((target.construct,target.slot),{}).setdefault(target.heading,set())
            keys.update(override['properties'])
            for shorthand,axes in (('padding',('padding-block','padding-inline')),('gap',('row-gap','column-gap')),('margin-block',('margin-block-start','margin-block-end'))):
                if shorthand in keys:keys.update(axes)
    emitted = {}
    for bp in [None] + [name for _, name in breakpoints]:
        block = []
        for construct, contract in vocabulary['constructs'].items():
            for slot in [None] + list(slot_map(contract)):
                scope = construct + ('.' + slot if slot else '')
                control = slot is not None and slot_map(contract)[slot]['kind']=='control'
                media = slot is not None and slot_map(contract)[slot]['kind']=='media'
                base = treatments(resolved(scope, 'default', bp),control,media)
                for state in contract['states']:
                    props = treatments(resolved(scope, state, bp),control,media)
                    key = (construct, slot, state)
                    if state != 'default' and props == base and key not in emitted:
                        continue
                    if any(props) and emitted.get(key) != props:
                        for native,values in enumerate(props):
                            if values:block.append(select(construct, slot, state, native='image' if native==2 else bool(native)) + '{' + values + '}')
                        emitted[key] = props
                for level in sorted(heading_scopes.get((construct,slot),())):
                    # Without slot state treatments, the default heading rule
                    # already covers every state. Keep the full state cascade
                    # when any state treatment exists: generic state selectors
                    # can otherwise override the heading, and later states may
                    # need to reset an earlier state's heading treatment.
                    states=contract['states'] if (construct,slot) in stateful_slots else ['default']
                    for state in states:
                        properties=resolved(scope+'.h'+str(level),state,bp)
                        values=declaration({k:v for k,v in properties.items() if k in heading_scopes[(construct,slot)][level]})
                        key=(construct,slot,state,level)
                        if values and emitted.get(key)!=values:
                            target=','.join(s+':is(h'+str(level)+')' for s in select(construct,slot,state).split(','))
                            block.append(target+'{'+values+'}');emitted[key]=values
            parts = set(contract.get('parts',{})) | set(document.get('components',{}).get(construct,{}).get('parts',{}))
            for target,override,_ in resolver.overrides:
                if target.construct==construct and target.part:parts.add(target.part)
            for part in sorted(parts):
                values = declaration(resolved(construct+'~'+part,breakpoint=bp))
                key = (construct,'~'+part,'default')
                if values and emitted.get(key)!=values:
                    block.append(f'[data-kd-construct="{construct}"] [data-kd-part="{part}"]'+'{'+values+'}')
                    emitted[key] = values
        if bp and block:
            rules.append(f'@media (min-width:{tokens.breakpoint(bp):g}px)' + '{\n' + '\n'.join(block) + '\n}')
        elif not bp:
            rules.extend(block)
    for behavior in document.get('behaviors', []):
        scope = parse_scope(behavior['scope'], vocabulary)
        target = select(scope.construct, scope.slot)
        if behavior['kind'] == 'truncate':
            rules.append(target + '{display:-webkit-box;-webkit-box-orient:vertical;-webkit-line-clamp:' + str(behavior['lines']) + ';overflow:hidden}')
        elif behavior['kind'] == 'horizontal-scroll':
            rules.append(target + '{overflow-x:auto;overscroll-behavior-x:contain}')
            media = target if scope.slot else ','.join(s+' [data-kd-slot$=".media"]' for s in target.split(','))
            rules.append(media + '{display:flex;gap:inherit}')
            rules.append(','.join(s+'>img' for s in media.split(','))+'{flex:0 0 100%;max-width:none}')
    return '\n'.join(rules) + '\n'
