"""Closed preference domains, deterministic priors and pair distances."""
import math
import re

DOMAINS = {
    'hue-family': (0, 360), 'value-contrast': (0, 1), 'saturation': (0, 1),
    'type-pairing': ('geometric-sans', 'humanist-sans', 'rounded', 'serif', 'slab'),
    'type-scale': (1.067, 1.618), 'density': (2, 16), 'shape': (0, 32),
    'formality': (0, 1), 'whimsy': (0, 1),
}
DEFAULTS = {'hue-family':195, 'value-contrast':.8, 'saturation':.6,
            'type-pairing':'humanist-sans', 'type-scale':1.25, 'density':8,
            'shape':12, 'formality':.3, 'whimsy':.3}


def validate_values(values):
    if not isinstance(values,dict):raise ValueError('Dimension values must be a JSON object')
    for key,value in values.items():
        if key not in DOMAINS:raise ValueError('Unknown dimension: '+key)
        domain=DOMAINS[key]
        if key=='type-pairing':
            if value not in domain:raise ValueError('Unknown type pairing')
        elif type(value) not in {int,float} or not math.isfinite(value) or not domain[0]<=value<=domain[1] or key=='hue-family' and value==360:
            raise ValueError('Value outside dimension domain: '+key)
    return dict(values)


def seeds(brief):
    words=set(re.findall(r'[a-z]+',brief.lower()));values=dict(DEFAULTS)
    hues=[v for names,v in [(('blue','blues','ocean'),215),(('green','greens'),145),(('turquoise','teal'),175),
                           (('red','reds'),5),(('orange','sunset'),25),(('purple','violet'),275),(('pink',),325)] if words.intersection(names)]
    if hues:values['hue-family']=round(math.degrees(math.atan2(sum(math.sin(math.radians(h)) for h in hues),sum(math.cos(math.radians(h)) for h in hues)))%360)
    if words.intersection({'beach','relaxing','calm'}):values.update(density=10,saturation=.75,formality=.2)
    if words.intersection({'family','families','young','casual'}):values.update(shape=24,formality=.2,**{'type-pairing':'rounded','type-scale':1.5})
    if words.intersection({'whimsical','playful','whimsy','engaging'}):values['whimsy']=.75
    if words.intersection({'formal','corporate'}):values.update(formality=.85,shape=2)
    return values


def distance(d,a,b):
    if d=='type-pairing':return int(a!=b)
    if d=='hue-family':return min(abs(a-b),360-abs(a-b))
    return abs(a-b)


def alternatives(d,center,rejected=()):
    """Grow rejected intervals, then offer the full domain without cycling forever."""
    if d=='type-pairing':
        used={v for pair in rejected for v in pair};available=[v for v in DOMAINS[d] if v not in used]
        if len(available)<2:
            # With an odd-sized domain, pair its final unseen value with an
            # earlier value, avoiding the immediately rejected pair if possible.
            last=set(rejected[-1]) if rejected else set()
            available += [v for v in DOMAINS[d] if v not in available and v not in last]
            available += [v for v in DOMAINS[d] if v not in available]
        if not rejected:available=[center]+[v for v in available if v!=center]
        return available[:2]
    lo,hi=DOMAINS[d];maximum=180 if d=='hue-family' else hi-lo
    prior=max((distance(d,*pair) for pair in rejected),default=0)
    initial=50 if d=='hue-family' else maximum*(.3 if d=='saturation' else .6)
    spread=min(maximum,max(initial,prior*1.8))
    if maximum-spread<1e-8:spread=maximum
    if d=='hue-family':
        if not rejected:return [center%360,(center+spread)%360]
        return [(center-spread/2)%360,(center+spread/2)%360]
    a=max(lo,min(hi-spread,center-spread/2))
    return [round(a,8),round(a+spread,8)]


def exhausted(d,rejected):
    if not rejected:return False
    if d=='type-pairing':return len({v for pair in rejected for v in pair})>=len(DOMAINS[d])
    maximum=180 if d=='hue-family' else DOMAINS[d][1]-DOMAINS[d][0]
    return any(distance(d,*pair)>=maximum-1e-7 for pair in rejected)
