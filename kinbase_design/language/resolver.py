"""Compute effective treatment, preserving the source of every property."""
from ..vocabulary import slot_map
from dataclasses import dataclass
from .tokens import Tokens
from ..findings import pointer
from .properties import property_value


@dataclass(frozen=True)
class Scope:
    construct: str
    slot: str | None = None
    state: str | None = None
    breakpoint: str | None = None
    part: str | None = None


def parse_scope(value, vocabulary, tokens=None):
    if not isinstance(value, str) or value.count('@') > 1:
        raise ValueError('Malformed scope')
    base, _, bp = value.partition('@')
    if '~' in base:
        from ..storage import ID
        if base.count('~')!=1:raise ValueError('Malformed part scope')
        construct, part = base.split('~')
        if construct not in vocabulary['constructs'] or not ID.fullmatch(part):raise ValueError('Unknown construct or malformed part')
        if '@' in value and not bp:raise ValueError('Missing breakpoint')
        if bp and tokens:tokens.breakpoint(bp)
        return Scope(construct,breakpoint=bp or None,part=part)
    parts = base.split('.')
    construct = parts.pop(0)
    contract = vocabulary['constructs'].get(construct)
    if not contract:
        raise ValueError('Unknown construct in scope')
    slot = state = None
    if parts and parts[0] in slot_map(contract):
        slot = parts.pop(0)
    if parts and parts[0] in contract['states']:
        state = parts.pop(0)
    if parts or ('@' in value and not bp):
        raise ValueError('Malformed scope or unknown slot/state')
    if bp and tokens:
        tokens.breakpoint(bp)
    return Scope(construct, slot, state, bp or None)


def resolve(document, vocabulary, scope, state='default', breakpoint=None):
    tokens = Tokens(document.get('style', {}))
    target = parse_scope(scope, vocabulary)
    if target.state or target.breakpoint:
        raise ValueError('Use --state and --breakpoint separately')
    contract = vocabulary['constructs'][target.construct]
    if state not in contract['states']:
        raise ValueError('State is not declared for this construct')
    width = tokens.breakpoint(breakpoint) if breakpoint else None
    component = document.get('components', {}).get(target.construct, {})
    treatment = component.get('slots', {}).get(target.slot, {}) if target.slot else component
    if target.part:
        treatment = {'properties':component.get('parts',{}).get(target.part,{})}
    values = {}

    def apply(props, source):
        for key, raw in props.items():
            if key == 'surface':
                continue
            value = property_value(document, tokens, key, raw)
            values[key] = {'value': value, 'source': source}

    if target.slot:
        defaults = slot_map(contract)[target.slot]
        role = treatment.get('role', defaults['role'])
        emphasis = treatment.get('emphasis', defaults['emphasis'])
        apply(document.get('roles', {}).get(role, {}).get(emphasis, {}), f'role:{role}.{emphasis}')
    component_source = f'component:{scope}'
    apply(treatment.get('properties', {}), component_source)
    apply(treatment.get('states', {}).get('default', {}), component_source + '.default')
    if state != 'default':
        apply(treatment.get('states', {}).get(state, {}), component_source + '.' + state)
    matches = []
    for override in document.get('overrides', []):
        candidate = parse_scope(override['scope'], vocabulary, tokens)
        if (candidate.construct, candidate.slot, candidate.part) != (target.construct, target.slot, target.part):
            continue
        if candidate.state and candidate.state != state:
            continue
        bp_width = tokens.breakpoint(candidate.breakpoint) if candidate.breakpoint else -1
        if candidate.breakpoint and (width is None or width < bp_width):
            continue
        # Qualified state+breakpoint beats both; largest threshold breaks bp ties.
        rank = (2 * bool(candidate.breakpoint) + bool(candidate.state), bp_width)
        matches.append((rank, override))
    for _, override in sorted(matches, key=lambda pair: pair[0]):
        apply(override['properties'], 'override:' + override['scope'])
    # Emit only effective, nonoverlapping axes when a shorthand and its logical
    # longhands coexist. The renderer and checker consume this same result.
    for shorthand,axes in (('padding',('padding-block','padding-inline')),('gap',('row-gap','column-gap'))):
        if vocabulary.get('content_pages') and shorthand in values and any(axis in values for axis in axes):
            detail=values.pop(shorthand)
            for axis in axes:
                values.setdefault(axis,{**detail,'source_property':shorthand})
    return {'language': document['id'], 'scope': scope, 'state': state,
            'breakpoint': breakpoint, 'properties': values}


def property_pointer(document, vocabulary, property_name, resolved_property):
    """Locate the source member of a resolved property without copying its value."""
    property_name = resolved_property.get('source_property',property_name)
    kind, source = resolved_property['source'].split(':', 1)
    if kind == 'role':
        role, emphasis = source.split('.')
        return pointer('roles', role, emphasis, property_name)
    if kind == 'override':
        index = next(i for i, entry in enumerate(document['overrides']) if entry['scope'] == source)
        return pointer('overrides', index, 'properties', property_name)
    scope = parse_scope(source, vocabulary)
    parts = ['components', scope.construct]
    if scope.part:
        return pointer(*parts,'parts',scope.part,property_name)
    if scope.slot:
        parts.extend(['slots', scope.slot])
    if scope.state:
        parts.extend(['states', scope.state])
    else:
        parts.append('properties')
    return pointer(*parts, property_name)
