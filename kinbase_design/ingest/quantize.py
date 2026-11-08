"""Pure perceptual colour and scale measurements over captured values."""
from collections import Counter
import math
from ..checks.math import color
from ..config import (INGEST_COLOR_DELTA_E, INGEST_TYPE_TOLERANCE_PX,
                      INGEST_SPACE_TOLERANCE_PX, INGEST_DEFAULT_SPACE)


def hex_color(value):
    rgba=color(value)
    if rgba is None:return None
    return '#' + ''.join(f'{round(v*255):02x}' for v in (rgba if rgba[3]<1 else rgba[:3]))


def lab(value):
    rgb=color(value)
    if rgb is None:raise ValueError('Expected an sRGB colour')
    channels=[v/12.92 if v<=.04045 else ((v+.055)/1.055)**2.4 for v in rgb[:3]]
    x,y,z=[sum(a*b for a,b in zip(row,channels))/white for row,white in
           [((.4124564,.3575761,.1804375),.95047),((.2126729,.7151522,.0721750),1),((.0193339,.1191920,.9503041),1.08883)]]
    f=lambda t:t**(1/3) if t>(6/29)**3 else t/(3*(6/29)**2)+4/29
    return 116*f(y)-16,500*(f(x)-f(y)),200*(f(y)-f(z))


def delta_e(left,right):
    """CIEDE2000 with unit parametric factors, D65 sRGB inputs or Lab triples."""
    l1,a1,b1=lab(left) if isinstance(left,str) else left
    l2,a2,b2=lab(right) if isinstance(right,str) else right
    c1,c2=math.hypot(a1,b1),math.hypot(a2,b2); c=(c1+c2)/2
    g=.5*(1-math.sqrt(c**7/(c**7+25**7)))
    ap1,ap2=(1+g)*a1,(1+g)*a2
    cp1,cp2=math.hypot(ap1,b1),math.hypot(ap2,b2)
    hp1,hp2=math.degrees(math.atan2(b1,ap1))%360,math.degrees(math.atan2(b2,ap2))%360
    dl,dc=l2-l1,cp2-cp1; dh=hp2-hp1
    if cp1*cp2==0:dh=0
    elif dh>180:dh-=360
    elif dh< -180:dh+=360
    dh=2*math.sqrt(cp1*cp2)*math.sin(math.radians(dh/2))
    lp,cp=(l1+l2)/2,(cp1+cp2)/2
    hp=hp1+hp2 if cp1*cp2==0 else (hp1+hp2)/2 if abs(hp1-hp2)<=180 else (hp1+hp2+360)/2 if hp1+hp2<360 else (hp1+hp2-360)/2
    cos=lambda d:math.cos(math.radians(d))
    t=1-.17*cos(hp-30)+.24*cos(2*hp)+.32*cos(3*hp+6)-.20*cos(4*hp-63)
    sl=1+.015*(lp-50)**2/math.sqrt(20+(lp-50)**2);sc=1+.045*cp;sh=1+.015*cp*t
    rt=-2*math.sqrt(cp**7/(cp**7+25**7))*math.sin(math.radians(60*math.exp(-((hp-275)/25)**2)))
    return math.sqrt((dl/sl)**2+(dc/sc)**2+(dh/sh)**2+rt*(dc/sc)*(dh/sh))


def palette(values,tolerance=INGEST_COLOR_DELTA_E):
    counts=Counter(v for raw in values if (v:=hex_color(raw)) is not None and (len(v)!=9 or v[-2:]!='00'))
    groups=[]
    for value,count in counts.most_common():
        group=next((g for g in groups if len(g['value'])==len(value) and (len(value)!=9 or value[-2:]==g['value'][-2:]) and delta_e(value,g['value'])<=tolerance),None)
        if group is None:group={'value':value,'count':0,'members':[]};groups.append(group)
        group['count']+=count;group['members'].append({'value':value,'delta_e':round(delta_e(value,group['value']),4)})
    return groups


def px(value):
    if isinstance(value,(float,int)):return float(value)
    try:return float(value[:-2]) if value.endswith('px') else None
    except (AttributeError,ValueError):return None


def scale(values,tolerance=INGEST_TYPE_TOLERANCE_PX):
    result=[]
    for value in sorted(v for v in values if v is not None):
        if not result or abs(value-result[-1])>tolerance:result.append(value)
    return result


def spacing_base(values):
    values=[v for v in values if v is not None and v>0]
    if not values:return INGEST_DEFAULT_SPACE
    candidates=[v/4 for v in range(4,65)]
    valid=[base for base in candidates if all(abs(v-round(v/base)*base)<=INGEST_SPACE_TOLERANCE_PX and round(v/base)>0 for v in values)]
    return max(valid,default=min(values))


def measurements(views,extra_colors=()):
    nodes=[n for view in views for n in view.get('nodes',[])]
    styles=[n.get('styles',{}) for n in nodes]
    sizes=scale([px(s.get('font-size')) for s in styles])
    spaces=[px(s.get(p)) for s in styles for p in ('padding-top','padding-right','padding-bottom','padding-left','margin-top','margin-bottom','row-gap','column-gap')]
    return {'palette':palette([s.get(p) for s in styles for p in ('color','background-color','border-top-color')]+list(extra_colors)),
            'type_scale':sizes,'type_scale_ratios':[round(b/a,4) for a,b in zip(sizes,sizes[1:]) if a],
            'font_families':list(dict.fromkeys(s['font-family'] for s in styles if s.get('font-family'))),
            'spacing':scale(spaces,INGEST_SPACE_TOLERANCE_PX),'spacing_base':spacing_base(spaces),
            'radii':scale([px(s.get('border-top-left-radius')) for s in styles]),
            'breakpoints':sorted({w for view in views for w in view.get('breakpoints',[])})}
