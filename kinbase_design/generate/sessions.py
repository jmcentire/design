"""Private mutable interview state and the single append-only choice write path."""
from datetime import datetime, timezone
import fcntl
import json
import uuid
from ..storage import inside,identifier,read_json,write_json
from ..config import MAX_JSON_BYTES
from .dimensions import DOMAINS,validate_values


def folder(workspace,session):return inside(workspace,'sessions',identifier(session))
def read(workspace,session):return read_json(inside(folder(workspace,session),'session.json'))
def write(workspace,state):write_json(inside(folder(workspace,state['id']),'session.json'),state)
def now():return datetime.now(timezone.utc).isoformat()
def new_id(prefix):return prefix+'-'+uuid.uuid4().hex[:16]


def choices(workspace,session):
    read(workspace,session)
    path=inside(folder(workspace,session),'choices.jsonl')
    if not path.exists():return []
    if path.stat().st_size>MAX_JSON_BYTES:raise ValueError('Choice log exceeds configured JSON limit')
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def effective(log):
    superseded={c['supersedes'] for c in log if c['supersedes']}
    return [c for c in log if c['id'] not in superseded]


def settled(workspace,session):
    state=read(workspace,session);result={}
    for choice in effective(choices(workspace,session)):
        if choice['choice']=='neither':continue
        pair=state['pairs'][choice['pair']];values=pair[choice['choice'].lower()]['values']
        for d in choice['dimensions']:
            prior=result.get(d)
            support=prior['choices'] if prior and prior['value']==values[d] else []
            result[d]={'value':values[d],'choices':support+[choice['id']]}
    from ..kinbase import fixed_dimensions
    for dimension,entry in fixed_dimensions(state['resources'].get('kinbase',{})).items():
        result[dimension]={**entry,'choices':[],'fixed':True}
    return {'session':session,'settled':result,'unsettled':[d for d in DOMAINS if d not in result]}


def interview(workspace,session,answers):
    values=validate_values(answers);state=read(workspace,session)
    fixed=settled(workspace,session)['settled']
    for dimension,value in values.items():
        if fixed.get(dimension,{}).get('fixed') and value!=fixed[dimension]['value']:
            raise ValueError(dimension+' is fixed by Kinbase')
    state['interview'].update(values);write(workspace,state)
    return {'session':session,'answers':state['interview']}


def choose(workspace,session,pair_id,choice,comment='',supersedes=None):
    if choice not in {'A','B','neither'}:raise ValueError('Choice must be A, B or neither')
    if len(comment)>4000:raise ValueError('Choice comment exceeds 4000 characters')
    root=folder(workspace,session)
    # A separate lock guards validation and append together; the log is never rewritten.
    with inside(root,'choices.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        state=read(workspace,session)
        if pair_id not in state['pairs']:raise ValueError('Unknown pair')
        log=choices(workspace,session);active=effective(log)
        if supersedes:
            previous=next((c for c in active if c['id']==supersedes),None)
            if previous is None or previous['pair']!=pair_id:raise ValueError('Supersedes must name an effective choice for this pair')
        elif any(c['pair']==pair_id for c in active):raise ValueError('Pair already chosen; use --supersedes to revise it')
        pair=state['pairs'][pair_id]
        record={'id':new_id('choice'),'round':pair['round'],'pair':pair_id,'a':pair['a']['hash'],'b':pair['b']['hash'],
                'dimensions':pair['dimensions'],'choice':choice,'comment':comment,'supersedes':supersedes,'ts':now()}
        data=json.dumps(record,ensure_ascii=False,allow_nan=False)+'\n';path=inside(root,'choices.jsonl')
        if (path.stat().st_size if path.exists() else 0)+len(data.encode())>MAX_JSON_BYTES:raise ValueError('Choice log exceeds configured JSON limit')
        with path.open('a',encoding='utf-8') as stream:stream.write(data);stream.flush()
    return record
