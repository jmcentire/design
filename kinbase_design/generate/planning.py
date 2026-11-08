"""Pair planning derives state from effective decisions, including neither and revision."""
from copy import deepcopy
import hashlib
import json
from .dimensions import alternatives,distance,widest
from .sessions import read,write,choices,effective,settled,new_id
from .candidates import materialize

PLANNING_REVISION = 2


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


def variation(d,a,b):
    return {'distance':distance(d,a,b),'widest':widest(d,a,b)}


def offered_variation(offered,dimension):
    if offered.get('planning_revision')==PLANNING_REVISION:
        return offered['variation'][dimension]
    # Older sessions used category exploration rather than distance to name
    # their limit. Upgrade that interpretation without rewriting choice history.
    return variation(dimension,offered['a']['values'][dimension],offered['b']['values'][dimension])


def at_limit(state,log,dimension):
    return any(c['choice']=='neither' and dimension in c['dimensions']
               and offered_variation(state['pairs'][c['pair']],dimension)['widest']
               for c in log)


def pair(library,workspace,session):
    state=read(workspace,session);log=effective(choices(workspace,session));preferences=settled(workspace,session)
    answered={c['pair'] for c in log}
    # Repeated GETs/CLI calls do not consume rounds before a decision is made.
    basis=[c['id'] for c in log]
    standards_basis=hashlib.sha256(json.dumps(state['resources'].get('kinbase',{}),sort_keys=True).encode()).hexdigest()
    pending=[p for key,p in state['pairs'].items() if key not in answered and p.get('basis')==basis and p.get('planning_revision')==PLANNING_REVISION and p.get('standards_basis')==standards_basis
             and all(d in preferences['unsettled'] for d in p['dimensions'])]
    if pending:return pending[-1]
    if len(answered)>=state['settings']['round_cap'] or not preferences['unsettled']:return {'done':True}
    remaining=[d for d in preferences['unsettled'] if not at_limit(state,log,d)]
    retry=[]
    if log and log[-1]['choice']=='neither':
        retry=[d for d in log[-1]['dimensions'] if d in remaining]
    dims=retry or remaining[:2]
    if not dims:return {'done':True}
    values=baseline(workspace,session);a=deepcopy(values);b=deepcopy(values)
    for d in dims:a[d],b[d]=alternatives(d,values[d],rejected(state,log,d))
    result={'pair':new_id('pair'),'round':len(answered)+1,'dimensions':dims,
            'basis':basis,'planning_revision':PLANNING_REVISION,'standards_basis':standards_basis,
            'variation':{d:variation(d,a[d],b[d]) for d in dims},
            'exhausted':[d for d in preferences['unsettled'] if at_limit(state,log,d)],
            'a':materialize(library,workspace,state,a),'b':materialize(library,workspace,state,b)}
    state['pairs'][result['pair']]=result;write(workspace,state)
    return result
