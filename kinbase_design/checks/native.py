"""Compare native control appearance without treating unpainted styles as changes."""


def _painted(style, prefix):
    return (style.get(prefix + '-style', 'none') not in {'none', 'hidden'}
            and style.get(prefix + '-width', '0px') not in {'0', '0px'})


def unmodified_native(observation):
    if not observation:
        return False
    authored, native = observation['authored'], observation['native']
    if authored.get('appearance') == 'none':
        return False
    properties = {'appearance', 'accent-color', 'background-color', 'background-image',
                  'box-shadow', 'filter', 'opacity',
                  'padding-top', 'padding-right', 'padding-bottom', 'padding-left'}
    if not observation['checkable']:
        # Checkboxes/radios paint a native glyph, not text. Their inherited font
        # and currentColor do not change that glyph when accent-color is auto.
        properties.update({'color', 'font-family', 'font-size', 'font-weight',
                           'font-style', 'line-height'})
    painted_border = False
    for side in ('top', 'right', 'bottom', 'left'):
        prefix = 'border-' + side
        if _painted(authored, prefix) or _painted(native, prefix):
            painted_border = True
            properties.update(prefix + '-' + prop for prop in ('color', 'style', 'width'))
    if not observation['checkable'] or painted_border:
        properties.update('border-' + corner + '-radius' for corner in
                          ('top-left', 'top-right', 'bottom-left', 'bottom-right'))
    if _painted(authored, 'outline') or _painted(native, 'outline'):
        properties.update({'outline-color', 'outline-style', 'outline-width', 'outline-offset'})
    return all(authored.get(prop) == native.get(prop) for prop in properties)
