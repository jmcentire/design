"""Guided generate application operations shared by CLI and workbench."""
from dataclasses import asdict
from ..config import generate_config
from ..storage import inside,write_json
from . import sessions
from .sessions import interview,choose,settled
from .dimensions import DOMAINS,seeds,alternatives
from .resources import prepare
from .candidates import materialize
from .planning import pair,baseline


def start(library,workspace,brief,artifacts=(),settings=None):
    if not isinstance(brief,str) or not brief.strip() or len(brief)>16000:raise ValueError('Brief must contain 1–16000 characters')
    settings=settings or generate_config();session=sessions.new_id('session');values=seeds(brief)
    state={'id':session,'brief':brief,'seeds':values,'interview':{},'artifacts':list(artifacts),'moodboard':[],
           'pairs':{},'settings':asdict(settings),'created':sessions.now(),'mapping':'heuristic','standards':'unknown (Kinbase unconnected)'}
    state['resources']=prepare(library,workspace,session,artifacts)
    imported_briefs=' '.join(item['text'] for item in state['resources']['briefs'])
    if imported_briefs:values.update(seeds(brief+' '+imported_briefs))
    # Palette/image evidence is a starting point; its original values/bytes stay fixed.
    if state['resources']['colors']:
        import colorsys
        from ..checks.math import color
        colors=[rgba for raw in state['resources']['colors'] if (rgba:=color(raw)) and max(rgba[:3])-min(rgba[:3])>.1]
        if colors:
            hue,lightness,saturation=colorsys.rgb_to_hls(*colors[0][:3])
            values['hue-family']=round(hue*360,6)%360
            values['saturation']=round(saturation,6)
    for d in DOMAINS:
        av,bv=alternatives(d,values[d])
        for n,v in enumerate((av,bv)):
            state['moodboard'].append({'id':d+'-'+str(n+1),'kind':'type pairing' if d=='type-pairing' else 'palette' if d in {'hue-family','saturation','value-contrast'} else 'shape / rhythm / mood',
                                      'values':{d:v},'pinned':False,'removed':False})
    for asset,entry in state['resources']['assets'].items():
        state['moodboard'].append({'id':asset,'kind':entry['kind'],'asset':asset,'pinned':False,'removed':False})
    sessions.write(workspace,state)
    inside(sessions.folder(workspace,session),'choices.jsonl').touch(exist_ok=False)
    return {'session':session,'seeds':values}


def moodboard(library,workspace,session,pin=None,remove=None):
    state=sessions.read(workspace,session)
    for value,action in ((pin,'pinned'),(remove,'removed')):
        if value:
            item=next((i for i in state['moodboard'] if i['id']==value),None)
            if item is None:raise ValueError('Unknown mood board item')
            item[action]=True
            if action=='pinned':item['removed']=False
    base=baseline(workspace,session)
    for item in state['moodboard']:
        if 'values' in item and not item.get('preview'):
            candidate=materialize(library,workspace,state,{**base,**item['values']})
            item['preview']=candidate['preview'];item['hash']=candidate['hash']
        elif 'asset' in item:
            detail=state['resources']['assets'][item['asset']]['variants']['primary']
            item['file']=detail['file'];item['format']=detail['format']
    sessions.write(workspace,state)
    return state['moodboard']


def interview_samples(library,workspace,session):
    state=sessions.read(workspace,session);base=baseline(workspace,session);result=[]
    count=state['settings']['candidates_per_question']
    for d in DOMAINS:
        a,b=alternatives(d,base[d]);domain=DOMAINS[d]
        values=list(domain[:count]) if d=='type-pairing' else [a+(b-a)*i/(count-1) for i in range(count)]
        if d=='hue-family':values=[v%360 for v in values]
        result.append({'dimension':d,'candidates':[materialize(library,workspace,state,{**base,d:v}) for v in values]})
    return result


from .derive import derive
