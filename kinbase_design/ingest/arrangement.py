"""Private repeated-group geometry, measured independently at each capture width."""
from statistics import median
import re
from ..config import INGEST_ROW_TOLERANCE_PX, INGEST_MAX_COLUMNS
from .quantize import px


def bounds(boxes):
    if not boxes:return None
    x=min(b[0] for b in boxes);y=min(b[1] for b in boxes)
    return [x,y,max(b[0]+b[2] for b in boxes)-x,max(b[1]+b[3] for b in boxes)-y]


def gutters(boxes):
    """Distances beyond the adjacent items' own extent are not item gutters."""
    rows=[]
    for box in sorted(boxes,key=lambda b:(b[1],b[0])):
        row=next((r for r in rows if abs(r[0][1]-box[1])<=INGEST_ROW_TOLERANCE_PX),None)
        if row is None:rows.append([box])
        else:row.append(box)
    horizontal=[b[0]-a[0]-a[2] for row in rows for a,b in zip(sorted(row),sorted(row)[1:])
                if 0<=b[0]-a[0]-a[2]<=max(a[2],b[2])]
    vertical=[]
    for previous,row in zip(rows,rows[1:]):
        gap=min(b[1] for b in row)-max(b[1]+b[3] for b in previous)
        if 0<=gap<=max(b[3] for b in previous+row):vertical.append(gap)
    return {'column-gap':horizontal,'row-gap':vertical}


def measure(parent,items):
    boxes=[item['box'] for item in items if item.get('box')]
    rows=[]
    for box in sorted(boxes,key=lambda b:(b[1],b[0])):
        row=next((r for r in rows if abs(r[0][1]-box[1])<=INGEST_ROW_TOLERANCE_PX),None)
        if row is None:rows.append([box])
        else:row.append(box)
    style=parent.get('styles',{});tracks=style.get('grid-template-columns','').split()
    columns=len(tracks) if style.get('display')=='grid' and tracks and all(re.fullmatch(r'[\d.]+px',t) for t in tracks) else max(map(len,rows),default=1)
    columns=max(1,min(INGEST_MAX_COLUMNS,columns))
    layout={'columns':columns}
    for prop,observed in gutters(boxes).items():
        value=px(style.get(prop))
        extent=max((b[2 if prop=='column-gap' else 3] for b in boxes),default=0)
        if value is not None and value>extent:value=None
        if value is None and observed:value=median(observed)
        if value is not None:layout[prop]=max(0,value)
    return {'selector':parent['selector'],'members':[item['selector'] for item in items],
            'box':bounds(boxes) or parent.get('box'),'layout':layout}


def groups(instances,by):
    siblings={}
    for item in instances:
        if item.get('group'):siblings.setdefault((item['group'],tuple(item.get('group_members',[]))),[]).append(item)
    return [measure(by.get(key,{'selector':key}),items) for (key,_),items in siblings.items() if len(items)>=2]


def compose(instances,groups):
    """Insert layout wrappers without adding Vocabulary content or changing source order."""
    by={item['selector']:item for item in instances if item.get('selector')};top=[]
    for item in instances:
        parent=by.get(item.get('parent'))
        if parent:parent.setdefault('children',[]).append(item)
        else:top.append(item)
    def wrap(items):
        for item in items:
            if item.get('children'):item['children']=wrap(item['children'])
        memberships={}
        for group in groups:
            children=[item for item in items if item.get('selector') in group['members']]
            if len(children)>=2:
                wrapper={key:group[key] for key in ('selector','box','layout')}
                wrapper.update(group=True,children=children)
                for child in children:memberships[id(child)]=wrapper
        result=[];seen=set()
        for item in items:
            wrapper=memberships.get(id(item))
            if wrapper is None:result.append(item)
            elif id(wrapper) not in seen:result.append(wrapper);seen.add(id(wrapper))
        return result
    return wrap(top)
