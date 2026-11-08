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


def css_equal(property, expected, observed, font_size, root_size):
    if property == 'background-image':
        return background_equal(expected, observed)
    if property in {'color','background-color','border-color'}:
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
