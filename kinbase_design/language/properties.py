"""Closed property grammar shared by validation and resolution."""
TOKEN_PROPERTIES = {
    **dict.fromkeys(('color', 'background-color', 'border-color', 'outline-color', 'surface'), {'color'}),
    'background-image': {'gradient'},
    'font-family': {'fontFamily'}, 'font-weight': {'fontWeight'},
    **dict.fromkeys(('font-size', 'letter-spacing', 'border-width', 'border-radius', 'width', 'max-width',
                     'padding', 'padding-block', 'padding-inline', 'margin-block', 'gap'), {'dimension'}),
    'line-height': {'number', 'dimension'},
}
SPACE_PROPERTIES = {'padding', 'padding-block', 'padding-inline', 'margin-block', 'gap'}
CONTROL_BOX_PROPERTIES = {'outline-color', 'background-color', 'border-color', 'border-width', 'border-style',
                          'border-radius', 'padding', 'padding-block', 'padding-inline', 'width', 'max-width'}
CONTROL_TEXT_PROPERTIES = {'color', 'font-family', 'font-size', 'font-weight', 'font-style',
                           'line-height', 'letter-spacing', 'text-align', 'text-transform',
                           'text-decoration-line', 'text-overflow'}
KEYWORDS = {
    'border-style': {'none','solid','dashed','dotted','double'},
    'overflow': {'visible','hidden','clip','auto','scroll'},
    'text-overflow': {'clip','ellipsis'},
    'white-space': {'normal','nowrap','pre-wrap'},
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


def property_value(document, tokens, name, value):
    """Single value-computation path for root, slot, role, override and part CSS."""
    if name in {'width','max-width'} and document.get('vocabulary')!='v1' and isinstance(value,str) and value.startswith('calc('):
        return fluid_width(tokens,value)
    if name in KEYWORDS:
        return value
    if name in OPTIONAL_KEYWORDS and isinstance(value,str) and value in OPTIONAL_KEYWORDS[name]:
        return value
    if name in LAYOUT_PROPERTIES:
        return layout_value(tokens,name,value)
    if name == 'background-image' and isinstance(value, str) and value.startswith('asset:'):
        from ..assets import background_binding
        asset, variant, detail = background_binding(document, value)
        return f'url("assets/{asset}-{variant}.{detail["format"]}")'
    return tokens.reference(value)[1]

# The amendment-02 grammar is parsed completely before producing CSS.
import re
from .tokens import ALIAS

LAYOUT_PROPERTIES = {'grid-template-columns','grid-column','grid-row','aspect-ratio'}
IMAGE_PROPERTIES = {'aspect-ratio','object-fit','object-position'}
TOKEN_PROPERTIES.update({'column-gap':{'dimension'},'row-gap':{'dimension'},
                         'margin-block-start':{'dimension'},'margin-block-end':{'dimension'},
                         'margin-inline':{'dimension'},'box-shadow':{'shadow'}})
SPACE_PROPERTIES.update({'column-gap','row-gap','margin-inline','margin-block-start','margin-block-end'})
KEYWORDS.update({
    'object-fit': {'contain','cover','fill','none','scale-down'},
    'object-position': {'center','top','bottom','left','right'},
    'align-self': {'auto','start','end','center','stretch'},
    'justify-self': {'auto','start','end','center','stretch'},
})
OPTIONAL_KEYWORDS = {'margin-inline':{'auto'},'max-width':{'100%'},'box-shadow':{'none'}}


class LayoutValueError(ValueError):
    def __init__(self, message, parts=()):
        self.parts = parts
        super().__init__(message)


def fluid_width(tokens,value):
    """One closed relative-width form; arbitrary CSS arithmetic is not accepted."""
    match=re.fullmatch(r'calc\(100% ([+-]) (\{[a-zA-Z0-9_-]+(?:\.[a-zA-Z0-9_-]+)*\})\)',value)
    if not match:raise LayoutValueError('calc(100% +/- {nonnegative-dimension-token})')
    kind,amount=tokens.reference(match[2])
    if kind!='dimension' or amount.startswith('-'):raise LayoutValueError('a nonnegative dimension token')
    return 'calc(100% '+match[1]+' '+amount+')'


def layout_value(tokens, name, value):
    if not isinstance(value,str):raise LayoutValueError('a closed layout string')
    if name in {'grid-column','grid-row'}:
        if value=='auto' or name=='grid-column' and value=='1 / -1':return value
        match = re.fullmatch(r'span ([1-9][0-9]?)',value)
        if match and int(match[1]) <= (12 if name=='grid-column' else 6):return value
        raise LayoutValueError('auto, a bounded span, or full-column placement')
    if name=='aspect-ratio':
        if value=='auto':return value
        match = re.fullmatch(r'([1-9][0-9]?) / ([1-9][0-9]?)',value)
        if match and max(int(match[1]),int(match[2]))<=32:return value
        raise LayoutValueError('auto or integer width / height from 1 to 32')
    alias_pattern = r'\{[a-zA-Z0-9_-]+(?:\.[a-zA-Z0-9_-]+)*\}'
    def dimension(raw):
        kind, result = tokens.reference(raw)
        if kind!='dimension' or result.startswith('-'):raise LayoutValueError('a nonnegative dimension token')
        return result
    def track(raw):
        if raw=='auto':return raw
        match = re.fullmatch(r'([1-9]|1[0-2])fr',raw)
        if match:return raw
        if ALIAS.fullmatch(raw):return dimension(raw)
        match = re.fullmatch(r'minmax\(('+alias_pattern+r'),\s*([1-9]|1[0-2])fr\)',raw)
        if match:return 'minmax('+dimension(match[1])+','+match[2]+'fr)'
        raise LayoutValueError('a fraction, auto, dimension token or bounded minmax track')
    repeated = re.fullmatch(r'repeat\((auto-fit|auto-fill|[1-9]|1[0-2]),\s*(.+)\)',value)
    if repeated:
        count, raw = repeated.groups()
        if count in {'auto-fit','auto-fill'} and not re.fullmatch(r'minmax\('+alias_pattern+r',\s*1fr\)',raw):
            raise LayoutValueError('automatic repeat requires minmax(dimension token, 1fr)')
        return 'repeat('+count+','+track(raw)+')'
    # Split only at top-level whitespace; reject trailing text or nested syntax.
    tracks=[];depth=0;start=0
    for i,c in enumerate(value):
        if c=='(':depth+=1
        elif c==')':depth-=1
        if depth<0:raise LayoutValueError('balanced track functions')
        if c.isspace() and depth==0:
            if value[start:i]:tracks.append(value[start:i])
            start=i+1
    if value[start:]:tracks.append(value[start:])
    if depth or not 1<=len(tracks)<=12:raise LayoutValueError('one to twelve complete grid tracks')
    return ' '.join(track(t) for t in tracks)
