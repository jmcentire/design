"""Closed property grammar shared by validation and resolution."""
TOKEN_PROPERTIES = {
    **dict.fromkeys(('color', 'background-color', 'border-color', 'surface'), {'color'}),
    'font-family': {'fontFamily'}, 'font-weight': {'fontWeight'},
    **dict.fromkeys(('font-size', 'letter-spacing', 'border-width', 'border-radius', 'width', 'max-width',
                     'padding', 'padding-block', 'padding-inline', 'margin-block', 'gap'), {'dimension'}),
    'line-height': {'number', 'dimension'},
}
SPACE_PROPERTIES = {'padding', 'padding-block', 'padding-inline', 'margin-block', 'gap'}
KEYWORDS = {
    'display': {'none', 'block', 'inline', 'inline-block', 'flex', 'inline-flex', 'grid', 'inline-grid', 'contents', 'flow-root'},
    'flex-direction': {'row', 'row-reverse', 'column', 'column-reverse'},
    'flex-wrap': {'nowrap', 'wrap', 'wrap-reverse'},
    'align-items': {'normal', 'stretch', 'center', 'start', 'end', 'flex-start', 'flex-end', 'baseline'},
    'justify-content': {'normal', 'start', 'end', 'center', 'flex-start', 'flex-end', 'space-between', 'space-around', 'space-evenly', 'stretch'},
    'text-align': {'start', 'end', 'left', 'right', 'center', 'justify', 'match-parent'},
    'text-transform': {'none', 'capitalize', 'uppercase', 'lowercase', 'full-width', 'full-size-kana'},
    'font-style': {'normal', 'italic', 'oblique'},
    'text-decoration-line': {'none', 'underline', 'overline', 'line-through', 'underline overline'},
}
for choices in KEYWORDS.values():
    choices.update({'inherit', 'initial', 'unset', 'revert', 'revert-layer'})
