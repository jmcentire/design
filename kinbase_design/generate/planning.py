"""Pair planning derives state from effective decisions, including neither and revision."""
from copy import deepcopy
from .dimensions import DOMAINS,alternatives,exhausted
from .sessions import read,write,choices,effective,settled,new_id
from .candidates import materialize


def baseline(workspace,session):
    state=read(workspace,session)
    values={**state['seeds'],**state['interview']}
    for item in state['moodboard']:
        if item['pinned'] and not item['removed']:values.update(item.get('values',{}))
    values.update({d:v['value'] for d,v in settled(workspace,session)['settled'].items()})
    return values


def rejected(state,log,d):
    return [(state['pairs'][c['pair']]['a']['values'][d],state['pairs'][c['pair']]['b']['values'][d])
            for c in log if c['choice']=='neither' and d in c['dimensions']]


def pair(library,workspace,session):
    state=read(workspace,session);log=effective(choices(workspace,session));preferences=settled(workspace,session)
    answered={c['pair'] for c in log}
    # Repeated GETs/CLI calls do not consume rounds before a decision is made.
    basis=[c['id'] for c in log]
    pending=[p for key,p in state['pairs'].items() if key not in answered and p.get('basis')==basis]
    if pending:return pending[-1]
    if len(state['pairs'])>=state['settings']['round_cap'] or not preferences['unsettled']:return {'done':True}
    remaining=[d for d in preferences['unsettled'] if not exhausted(d,rejected(state,log,d))]
    retry=[]
    if log and log[-1]['choice']=='neither':
        retry=[d for d in log[-1]['dimensions'] if d in remaining]
    dims=retry or remaining[:2]
    if not dims:return {'done':True}
    values=baseline(workspace,session);a=deepcopy(values);b=deepcopy(values)
    for d in dims:a[d],b[d]=alternatives(d,values[d],rejected(state,log,d))
    result={'pair':new_id('pair'),'round':len(state['pairs'])+1,'dimensions':dims,
            'basis':basis,
            'a':materialize(library,workspace,state,a),'b':materialize(library,workspace,state,b)}
    state['pairs'][result['pair']]=result;write(workspace,state)
    return result
