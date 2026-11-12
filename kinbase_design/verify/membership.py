"""Is a rendered value one the language holds? Pure; no browser, no files.

A language's palette and scales are the closed set a site may use. A value outside
the set is reported with the nearest value inside it, so the fix is one edit away.
"""
import re
from ..checks.math import color
from ..config import CHECK_COLOR_TOLERANCE, CHECK_PIXEL_TOLERANCE, REM_PX
from ..findings import pointer
from ..ingest.quantize import delta_e
from ..language.properties import SPACE_PROPERTIES
from ..language.resolver import resolve
from ..language.tokens import Tokens, ALIAS, DIMENSION
from ..meaning.language import uses

TEXT = ('color', 'font-family', 'font-size', 'font-weight')
RULES = {'color': 'off-language-color', 'background-color': 'off-language-color', 'border-color': 'off-language-color',
         'font-family': 'off-language-type', 'font-size': 'off-language-type', 'font-weight': 'off-language-type',
         'border-radius': 'off-language-shape', 'padding': 'off-language-space', 'gap': 'off-language-space'}


def pixels(value, root=REM_PX):
    match = DIMENSION.fullmatch(value) if isinstance(value, str) else None
    return float(match[1]) * (root if match[2] == 'rem' else 1) if match else None


def first_family(value):
    return value.split(',')[0].strip().strip('"\'').lower()


def hex_color(rgba):
    return '#' + ''.join(f'{round(c * 255):02x}' for c in (rgba if rgba[3] < 1 else rgba[:3]))


class ClosedSet:
    """The values a language allows per property, each with the token that holds it."""

    def __init__(self, document, root=REM_PX):
        tokens = Tokens(document['style'])
        self.colors, self.families, self.weights = {}, {}, {}
        dimensions, purpose = {}, {}
        for use in uses(document):
            trail, path = [], use['reference']
            while path in tokens.nodes and path not in trail:
                trail.append(path)
                value = tokens.nodes[path]['$value']
                alias = ALIAS.fullmatch(value) if isinstance(value, str) else None
                if not alias:
                    break
                path = alias[1]
            for path in trail:
                purpose.setdefault(path, set()).add('space' if use['property'] in SPACE_PROPERTIES else use['property'])
        for path in sorted(tokens.nodes):
            try:
                kind, value = tokens.evaluate(path)
            except (KeyError, ValueError):
                continue
            if kind == 'color':
                self.colors.setdefault(value, path)
            elif kind == 'fontFamily':
                self.families.setdefault(first_family(value), path)
            elif kind == 'fontWeight':
                self.weights.setdefault(float(value), path)
            elif kind == 'dimension' and pixels(value, root) is not None:
                dimensions[path] = pixels(value, root)
        # R4 makes space.* the spacing scale. Any other dimension serves the property a
        # treatment uses it for; one that nothing references may serve type or shape.
        self.dimensions = {'space': {}, 'font-size': {}, 'border-radius': {}}
        for path, number in dimensions.items():
            if path.startswith('breakpoint.'):
                continue
            used = purpose.get(path, set())
            if path.startswith('space.') or 'space' in used:
                self.dimensions['space'].setdefault(number, path)
            for prop in ('font-size', 'border-radius'):
                if prop in used or not used and not path.startswith('space.'):
                    self.dimensions[prop].setdefault(number, path)

        # Values the language's own preview renders. The shared base stylesheet and the
        # browser contribute some (a control's default padding, say); a site that renders
        # the same value is rendering the language.
        self.rendered = {'color': [], 'font-family': set(), 'font-weight': set(), 'font-size': set(),
                         'border-radius': set(), 'space': set()}

    def learn(self, node):
        """Admit what one node of the language's own preview renders."""
        if not node['visible']:
            return
        css = node['css']
        raws = [css.get('color'), css.get('background-color')]
        if node.get('borderWidth', 0) > 0:
            raws.extend(re.findall(r'rgba?\([^)]*\)|#[0-9a-fA-F]{6,8}', css.get('border-color') or ''))
        for raw in raws:
            rgba = color(raw)
            if rgba is not None and rgba[3] > 0 and rgba not in self.rendered['color']:
                self.rendered['color'].append(rgba)
        self.rendered['font-family'].add(first_family(css.get('font-family') or ''))
        for prop, scale in (('font-size', 'font-size'), ('border-radius', 'border-radius'), ('padding', 'space'), ('gap', 'space')):
            self.rendered[scale].update(pixels(part) for part in components(css.get(prop)))
        try:
            self.rendered['font-weight'].add(float(css.get('font-weight')))
        except (TypeError, ValueError):
            pass

    def color(self, raw):
        """None when the colour is in the language, else (observed, nearest path, nearest value, ΔE)."""
        rgba = color(raw)
        if rgba is None or rgba[3] == 0:
            return None
        if any(all(abs(a - b) <= CHECK_COLOR_TOLERANCE for a, b in zip(rgba, seen)) for seen in self.rendered['color']):
            return None
        nearest = None
        for value, path in self.colors.items():
            allowed = color(value)
            if all(abs(a - b) <= CHECK_COLOR_TOLERANCE for a, b in zip(rgba, allowed)):
                return None
            distance = delta_e(hex_color(rgba)[:7], value[:7]) + abs(rgba[3] - allowed[3]) * 100
            if nearest is None or distance < nearest[3]:
                nearest = (hex_color(rgba), path, value, round(distance, 1))
        return nearest or (hex_color(rgba), None, None, None)

    def number(self, scale, raw):
        number = pixels(raw, REM_PX) if isinstance(raw, str) else raw
        if number is None or abs(number) <= CHECK_PIXEL_TOLERANCE:
            return None
        allowed = self.dimensions[scale]
        if any(abs(number - value) <= CHECK_PIXEL_TOLERANCE for value in (*allowed, *self.rendered[scale])):
            return None
        nearest = min(allowed.items(), key=lambda item: abs(item[0] - number), default=(None, None))
        return f'{number:g}px', nearest[1], f'{nearest[0]:g}px' if nearest[0] is not None else None, None

    def family(self, raw):
        family = first_family(raw)
        if not family or family in self.families or family in self.rendered['font-family']:
            return None
        return family, next(iter(self.families.values()), None), next(iter(self.families), None), None

    def weight(self, raw):
        try:
            number = float(raw)
        except (TypeError, ValueError):
            return None
        if number in self.weights or number in self.rendered['font-weight'] or not self.weights:
            return None
        nearest = min(self.weights, key=lambda value: abs(value - number))
        return f'{number:g}', self.weights[nearest], f'{nearest:g}', None


def components(value):
    """The px lengths of a shorthand; keywords, percentages and 'normal' are not scale values."""
    return [part for part in re.split(r'[\s/]+', value or '') if DIMENSION.fullmatch(part)]


def observations(node, closed, declared=()):
    """Yield (property, off-language result) for one visible node.

    Properties a slot's resolved treatment declares are judged exactly elsewhere.
    An unmodified native control is the browser's, not the site's.
    """
    if not node['visible'] or node.get('nativeControl') or node['tag'] in {'img', 'svg', 'video', 'canvas', 'br', 'hr'}:
        return
    css = node['css']
    if node['directText'].strip():
        for prop, judge in (('color', closed.color), ('font-family', closed.family),
                            ('font-size', lambda raw: closed.number('font-size', raw)), ('font-weight', closed.weight)):
            if prop not in declared and (result := judge(css.get(prop))):
                yield prop, result
    if 'background-color' not in declared and (result := closed.color(css.get('background-color'))):
        yield 'background-color', result
    if node.get('borderWidth', 0) > 0 and 'border-color' not in declared:
        for part in re.findall(r'rgba?\([^)]*\)|#[0-9a-fA-F]{6,8}', css.get('border-color') or ''):
            if result := closed.color(part):
                yield 'border-color', result
    if 'border-radius' not in declared:
        for part in components(css.get('border-radius')):
            if result := closed.number('border-radius', part):
                yield 'border-radius', result
    for prop in ('padding', 'gap'):
        if not ({prop, 'padding-block', 'padding-inline'} & set(declared) if prop == 'padding' else prop in declared):
            for part in components(css.get(prop)):
                if result := closed.number('space', part):
                    yield prop, result


def declared_properties(document, vocabulary, node, breakpoint):
    if not node.get('slot'):
        return ()
    return tuple(resolve(document, vocabulary, node['slot'], node['state'], breakpoint)['properties'])


def token_pointer(path):
    return pointer('style', *path.split('.'), '$value') if path else '/style'
