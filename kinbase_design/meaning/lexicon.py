"""Deterministic name heuristics that propose meanings; the Vocabulary disposes.

Every result is a candidate. Nothing here certifies a mapping, and every proposed
meaning is grounded against the Vocabulary enums and the closed property set.
"""
import re
from ..language.properties import TOKEN_PROPERTIES, SPACE_PROPERTIES

# Words are evidence about a foreign naming scheme, never Vocabulary ids.
COLOR_FAMILIES = (
    ('color', {'text', 'fg', 'foreground', 'content', 'ink', 'icon'}),
    ('surface', {'bg', 'background', 'surface', 'canvas', 'page', 'paper', 'backdrop'}),
    ('background-color', {'fill', 'container'}),
    ('border-color', {'stroke', 'border', 'outline', 'divider', 'separator', 'ring', 'line'}),
)
CONTROL_WORDS = {'control', 'input', 'field'}
EMPHASIS_WORDS = {
    'neutral': {'default', 'base', 'neutral', 'strong', 'body', 'main', 'normal'},
    'primary': {'brand', 'accent', 'link', 'interactive', 'info', 'action'},
    'attention': {'danger', 'error', 'critical', 'destructive', 'warning', 'alert', 'attention', 'negative', 'caution'},
    'muted': {'muted', 'subtle', 'weak', 'dim', 'placeholder', 'disabled', 'faint', 'soft'},
}
ORDINALS = ('primary', 'secondary', 'tertiary', 'quaternary')
STATE_WORDS = {
    'hover': {'hover', 'hovered'}, 'active': {'active', 'pressed', 'press'},
    'focus-visible': {'focus', 'focused'}, 'disabled': {'disabled'},
    'selected': {'selected', 'checked', 'current'}, 'error': {'invalid'},
}
ROLE_WORDS = {
    'title': {'title', 'heading', 'display', 'h1', 'hero'},
    'subtitle': {'subtitle', 'subheading', 'h2', 'h3'},
    'body': {'body', 'paragraph'},
    'subtext': {'subtext'},
    'label': {'label'},
    'caption': {'caption'},
}
DIMENSION_FAMILIES = (
    ('breakpoint', {'breakpoint', 'screen'}),
    ('border-radius', {'radius', 'radii', 'rounded', 'corner'}),
    ('space', {'space', 'spacing', 'gap', 'padding', 'margin', 'inset'}),
    ('letter-spacing', {'tracking', 'letter'}),
    ('line-height', {'leading'}),
    ('font-size', {'text', 'font', 'type', 'size', 'title', 'heading', 'display', 'subtitle', 'body',
                   'caption', 'label', 'subtext'}),
)
# Families with no Vocabulary role or closed-set property. Each is a recorded gap,
# and widening the Vocabulary for one is a Vocabulary version decision.
PRESSURE = {
    'shadow': 'elevation', 'elevation': 'elevation', 'overlay': 'overlay', 'scrim': 'overlay',
    'inverse': 'inverse pairing', 'inverted': 'inverse pairing', 'on': 'on-surface pairing',
    'contrast': 'inverse pairing', 'chart': 'data visualisation', 'graph': 'data visualisation',
    'node': 'workflow or node', 'workflow': 'workflow or node', 'syntax': 'code syntax',
}
NAMESPACES = {'css', 'color', 'colors', 'colour', 'palette', 'semantic', 'theme', 'token', 'tokens', 'kd'}


def properties_by_type():
    """Meaning properties per token type, derived from the closed property grammar."""
    result = {}
    for name, kinds in TOKEN_PROPERTIES.items():
        for kind in kinds:
            result.setdefault(kind, set()).add('space' if name in SPACE_PROPERTIES else name)
    result['dimension'].add('breakpoint')
    result.pop('gradient', None)
    return result


PROPERTIES = properties_by_type()
MEMBERS = ('property', 'emphasis', 'role', 'state')


def segments(path):
    words = []
    for part in re.split(r'[.\-_]+', path):
        words.extend(w.lower() for w in re.findall(r'[A-Za-z][a-z]*|\d+', part))
    while len(words) > 1 and words[0] in NAMESPACES:
        words.pop(0)
    return words


def ground(meaning, token_type, vocabulary):
    """Return a reason when a meaning leaves the Vocabulary enums, else None."""
    if not isinstance(meaning, dict) or set(meaning) - set(MEMBERS) or 'property' not in meaning:
        return 'A meaning needs a property and may name an emphasis, role and state'
    if any(not isinstance(value, str) for value in meaning.values()):
        return 'Meaning members must be Vocabulary ids'
    if meaning['property'] not in PROPERTIES.get(token_type, ()):
        return f'{meaning["property"]} is not a closed-set property for a {token_type} token'
    for member, allowed in (('emphasis', vocabulary['emphasis']), ('role', vocabulary['roles']), ('state', vocabulary['states'])):
        if member in meaning and meaning[member] not in allowed:
            return f'{meaning[member]} is not a Vocabulary {member}'
    return None


def first(words, table):
    for word in words:
        for name, known in (table.items() if isinstance(table, dict) else table):
            if word in known:
                return name, word
    return None, None


def pressure(path):
    """A gap when the name asks for meaning the Vocabulary does not have."""
    for word in segments(path):
        if word in PRESSURE:
            return {'reason': 'vocabulary', 'message':
                    f'No Vocabulary role or closed-set property expresses {PRESSURE[word]} ("{word}")'}
    return None


def propose(path, token_type, siblings=()):
    """Propose one meaning or one gap for a token. Pure; siblings are other paths."""
    words = segments(path)
    gap = pressure(path)
    if gap:
        return None, gap
    if token_type not in PROPERTIES:
        return None, {'reason': 'vocabulary', 'message': f'{token_type} tokens have no role treatment in the closed property set'}
    basis, flags, meaning = [], [], {}
    state, word = first(words, STATE_WORDS)
    if state:
        meaning['state'] = state
        basis.append(word)
    if token_type == 'color':
        control = next((w for w in words if w in CONTROL_WORDS), None)
        family, word = first(words, COLOR_FAMILIES)
        if control:
            # A control's own fill is a box property; its page surface is not.
            meaning.update(role='control', property='background-color' if family in {None, 'surface'} else family)
            basis.extend(w for w in (control, word) if w)
        elif family:
            meaning['property'] = family
            basis.append(word)
        emphasis, word = first([w for w in words if w != 'disabled' or not state], EMPHASIS_WORDS)
        ordinal = next((w for w in words if w in ORDINALS), None)
        if emphasis:
            basis.append(word)
        elif ordinal:
            # "primary" beside "secondary" is a rank, not the brand emphasis.
            ranked = any(set(segments(other)) & set(ORDINALS[1:]) for other in siblings)
            if ordinal == 'primary' and not ranked:
                emphasis = 'primary'
            else:
                emphasis = 'neutral' if ordinal == 'primary' else 'muted'
                flags.append('ordinal-scale')
            basis.append(ordinal)
        if 'property' not in meaning:
            if not emphasis:
                return None, {'reason': 'unmapped', 'message': 'The token name carries no role signal'}
            meaning['property'] = 'color'
            flags.append('no-family')
        if emphasis:
            meaning['emphasis'] = emphasis
        elif meaning['property'] == 'color':
            meaning['emphasis'] = 'neutral'
            flags.append('default-emphasis')
    elif token_type in {'dimension', 'number'}:
        family, word = first(words, DIMENSION_FAMILIES)
        if family == 'border-radius' or family is None and {'border', 'stroke'} & set(words) and 'width' in words:
            family = family or 'border-width'
        if family is None or family not in PROPERTIES[token_type]:
            return None, {'reason': 'unmapped', 'message': 'The token name carries no role signal'}
        meaning['property'] = family
        basis.append(word or 'width')
    else:
        meaning['property'] = 'font-family' if token_type == 'fontFamily' else 'font-weight'
        basis.append(token_type)
    if meaning['property'] in {'font-size', 'font-family', 'font-weight', 'line-height', 'letter-spacing'}:
        role, word = first(words, ROLE_WORDS)
        if role:
            meaning['role'] = role
            basis.append(word)
        elif meaning['property'] == 'font-size':
            flags.append('scale-step-without-role')
    return {'meaning': meaning, 'basis': basis, 'flags': flags}, None
