"""Browser-independent color and geometry math; sRGB colors use 0–1 channels."""
import math
import re
from ..config import (CHECK_TEXT_CONTRAST, CHECK_LARGE_TEXT_CONTRAST,
                      CHECK_LARGE_TEXT_PX, CHECK_LARGE_BOLD_PX, CHECK_BOLD_WEIGHT,
                      CHECK_TARGET_SIZE, CHECK_PIXEL_TOLERANCE, CHECK_COLOR_TOLERANCE)


def color(value):
    if not isinstance(value, str):
        return None
    if value == 'transparent':
        return (0., 0., 0., 0.)
    if re.fullmatch(r'#[0-9a-fA-F]{6}(?:[0-9a-fA-F]{2})?', value):
        values = [int(value[i:i+2],16)/255 for i in range(1,len(value),2)]
        return tuple(values if len(values)==4 else values+[1.])
    match = re.fullmatch(r'rgba?\(([^)]+)\)',value)
    if match:
        parts = re.split(r'[, /]+',match[1].strip())
        if len(parts) not in {3,4}:
            return None
        try:
            rgb = [float(x[:-1])/100 if x.endswith('%') else float(x)/255 for x in parts[:3]]
            alpha = float(parts[3][:-1])/100 if len(parts)==4 and parts[3].endswith('%') else float(parts[3]) if len(parts)==4 else 1.
            return tuple(rgb+[alpha])
        except ValueError:
            return None
    return None


def composite(foreground, background):
    alpha = foreground[3] + background[3]*(1-foreground[3])
    if not alpha:
        return (0.,0.,0.,0.)
    return tuple((foreground[i]*foreground[3]+background[i]*background[3]*(1-foreground[3]))/alpha for i in range(3))+(alpha,)


def luminance(rgb):
    linear = [v/12.92 if v <= .04045 else ((v+.055)/1.055)**2.4 for v in rgb[:3]]
    return sum(a*b for a,b in zip(linear,(.2126,.7152,.0722)))


def contrast(foreground, background):
    fg = composite(foreground, background)
    light,dark = sorted((luminance(fg),luminance(background)),reverse=True)
    return (light+.05)/(dark+.05)


def effective_background(layers):
    """Layers arrive nearest first; canvas white is the browser's default substrate."""
    result = (1.,1.,1.,1.)
    for layer in reversed(layers):
        if layer.get('image', 'none') != 'none' or layer.get('uncertain'):
            return None
        rgba = color(layer['color'])
        if rgba is None:
            return None
        result = composite(rgba,result)
    return result


def text_threshold(size, weight):
    large = size >= CHECK_LARGE_TEXT_PX or (weight >= CHECK_BOLD_WEIGHT and size >= CHECK_LARGE_BOLD_PX)
    return CHECK_LARGE_TEXT_CONTRAST if large else CHECK_TEXT_CONTRAST


def spacing_exception(target, others):
    """WCAG 2.5.8: a 24px circle at an undersized target cannot intersect another target/circle."""
    radius = CHECK_TARGET_SIZE/2
    x,y,w,h = target
    cx,cy = x+w/2,y+h/2
    for other in others:
        ox,oy,ow,oh = other
        if ow < CHECK_TARGET_SIZE or oh < CHECK_TARGET_SIZE:
            if math.hypot(cx-(ox+ow/2),cy-(oy+oh/2)) < CHECK_TARGET_SIZE:
                return False
        else:
            dx = max(ox-cx,0,cx-(ox+ow))
            dy = max(oy-cy,0,cy-(oy+oh))
            if math.hypot(dx,dy) < radius:
                return False
    return True


def css_equal(property, expected, observed, font_size, root_size, *, blockified=False):
    if property=='display' and blockified:
        # CSS computes inline outer display to block for flex/grid items and
        # out-of-flow boxes. This is conditional on the observed layout context.
        expected={'inline':'block','inline-block':'block','inline-flex':'flex','inline-grid':'grid'}.get(expected,expected)
    if property=='box-shadow':
        if expected==observed:return True
        def shadow(value):
            match=re.search(r'rgba?\([^)]*\)|#[0-9a-fA-F]{6,8}',value)
            if not match:return None
            channels=color(match[0]);rest=value[:match.start()]+value[match.end():]
            lengths=re.findall(r'-?[\d.]+(?:px|rem)',rest)
            if len(lengths)!=4:return None
            numbers=[float(n[:-3])*root_size if n.endswith('rem') else float(n[:-2]) for n in lengths]
            return channels,numbers
        a,b=shadow(str(expected)),shadow(str(observed))
        return bool(a and b and a[0] and b[0] and all(abs(x-y)<=CHECK_COLOR_TOLERANCE for x,y in zip(a[0],b[0])) and all(abs(x-y)<=CHECK_PIXEL_TOLERANCE for x,y in zip(a[1],b[1])))
    if property in {'grid-template-columns','grid-template-rows'}:
        if expected==observed:return True
        compact = str(expected).replace(' ','')
        repeat = re.fullmatch(r'repeat\((\d+),(.+)\)',compact)
        if repeat:tracks = [repeat[2]]*int(repeat[1])
        else:tracks = re.findall(r'minmax\([\d.]+(?:px|rem),[\d.]+fr\)|[\d.]+(?:px|rem|fr)|auto',compact)
        pixels = observed.split()
        if not tracks or any(not re.fullmatch(r'[\d.]+px',p) for p in pixels):return None
        if len(tracks)!=len(pixels):return False
        units = []
        for track,actual in zip(tracks,pixels):
            if track=='auto':return None
            fraction = re.fullmatch(r'([\d.]+)fr',track)
            minimum = re.fullmatch(r'minmax\(([\d.]+)(px|rem),([\d.]+)fr\)',track)
            if minimum:
                lower=float(minimum[1])*(root_size if minimum[2]=='rem' else 1)
                if float(actual[:-2])+CHECK_PIXEL_TOLERANCE<lower:return False
                if lower>0:return None
                units.append(float(actual[:-2])/float(minimum[3]))
            elif fraction:units.append(float(actual[:-2])/float(fraction[1]))
            elif not css_equal('width',track,actual,font_size,root_size):return False
        return not units or max(units)-min(units)<=CHECK_PIXEL_TOLERANCE
    if property=='aspect-ratio':
        if expected==observed:return True
        try:
            numerator,_,denominator = str(observed).partition('/')
            a,_,b=str(expected).partition('/')
            return abs(float(a)/float(b or 1)-float(numerator)/float(denominator or 1))<1e-6
        except (ValueError,ZeroDivisionError):return False
    if property=='object-position':
        expected = {'center':'50% 50%','top':'50% 0%','bottom':'50% 100%','left':'0% 50%','right':'100% 50%'}.get(expected,expected)
    if property in {'grid-column','grid-row'}:
        expected = str(expected)
        if re.fullmatch(r'(?:span )?\d+',expected):expected += ' / auto'
        return expected.replace(' ','')==str(observed).replace(' ','') or expected=='auto' and observed=='auto / auto'
    if expected=='auto' and property in {'margin-inline','width','height','min-width'} and observed!='auto':
        return None  # Computed used sizes cannot establish an authored auto value.
    if property=='width' and isinstance(expected,str) and expected.startswith('calc(100% - '):
        if expected==observed:return True
        # A used pixel width alone does not identify its percentage basis or
        # min/max/flex constraints; do not misreport it as a different treatment.
        return None
    if property == 'background-image':
        return background_equal(expected, observed)
    if property in {'color','background-color','border-color','outline-color'}:
        a,b = color(expected),color(observed)
        return a is not None and b is not None and all(abs(x-y)<=CHECK_COLOR_TOLERANCE for x,y in zip(a,b))
    if isinstance(expected,(int,float)) and property=='line-height':
        expected = expected*font_size
    elif isinstance(expected,str) and re.fullmatch(r'-?[\d.]+(?:px|rem)',expected):
        expected = float(expected[:-3])*root_size if expected.endswith('rem') else float(expected[:-2])
    if isinstance(expected,(int,float)):
        parts = str(observed).split()
        try:
            return bool(parts) and all(abs(float(p.removesuffix('px'))-expected)<=CHECK_PIXEL_TOLERANCE for p in parts)
        except ValueError:
            return False
    if property=='font-family':
        clean=lambda v:[x.strip().strip('"\'').lower() for x in v.split(',')]
        return clean(expected)==clean(observed)
    # Computed shorthands can contain the same token once per side.
    return str(expected)==observed or (property in {'padding','padding-block','padding-inline','margin-block'} and all(p==str(expected) for p in observed.split()))


def css_arguments(text):
    """Split a CSS function's arguments, preserving commas inside rgb()/rgba()."""
    result, start, depth = [], 0, 0
    for index, char in enumerate(text):
        if char == '(':
            depth += 1
        elif char == ')':
            depth -= 1
        elif char == ',' and depth == 0:
            result.append(text[start:index].strip())
            start = index + 1
    result.append(text[start:].strip())
    return result


def gradient(value):
    if not value.startswith('linear-gradient(') or not value.endswith(')'):
        return None
    parts = css_arguments(value[len('linear-gradient('):-1])
    angle = 180.
    if parts[0].endswith('deg'):
        try: angle = float(parts.pop(0)[:-3])
        except ValueError: return None
    elif parts[0] == 'to bottom':
        parts.pop(0)
    stops = []
    for part in parts:
        match = re.fullmatch(r'(.+)\s+(-?[\d.]+)%', part)
        rgba = color(match[1] if match else part)
        if rgba is None:
            return None
        stops.append([rgba,float(match[2])/100 if match else None])
    if len(stops) < 2:
        return None
    if stops[0][1] is None: stops[0][1] = 0.
    if stops[-1][1] is None: stops[-1][1] = 1.
    left = 0
    for right in range(1,len(stops)):
        if stops[right][1] is not None:
            for index in range(left+1,right):
                stops[index][1] = stops[left][1] + (stops[right][1]-stops[left][1])*(index-left)/(right-left)
            left = right
    return angle, stops


def background_equal(expected, observed):
    from urllib.parse import unquote, urlsplit
    from ..config import CHECK_NUMBER_TOLERANCE
    if expected.startswith('url(') and observed.startswith('url('):
        a = unquote(urlsplit(expected[4:-1].strip().strip('"\'')).path)
        b = unquote(urlsplit(observed[4:-1].strip().strip('"\'')).path)
        return a == b or (not a.startswith('/') and b.endswith('/'+a))
    a,b = gradient(expected),gradient(observed)
    if a is None or b is None:
        return expected == observed
    return (abs(a[0]-b[0])<=CHECK_NUMBER_TOLERANCE and len(a[1])==len(b[1]) and
            all(abs(pa-pb)<=CHECK_NUMBER_TOLERANCE and all(abs(x-y)<=CHECK_COLOR_TOLERANCE for x,y in zip(ca,cb))
                for (ca,pa),(cb,pb) in zip(a[1],b[1])))
