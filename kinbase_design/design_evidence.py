"""Private observation handoff for an explicit Company publisher, never a ruling."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from .artifacts.bundle import metadata, read_member


def records(workspace, artifact):
    meta=metadata(workspace,artifact)
    source=meta.get('details',{}).get('source',{})
    if source.get('provider')!='figma':raise ValueError('Expected a Figma snapshot artifact')
    result=[]
    def emit(kind,statement,node=None,version=None,observed=None):
        origin={'kind':'figma','file_key':source['file_key'],'version':version,'digest':artifact,
                'evidence_kind':kind}
        if node:origin['node_id']=node
        # The extractor, not a typed comment author name, owns this observation.
        payload={'source':origin,'statement':statement,'author_kind':'agent'}
        digest=hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest()
        result.append({'schema':'design-evidence/1','id':digest,**payload,
                       'updated_at':observed or meta['created'],
                       'evidence_refs':['figma:'+source['file_key']+':'+str(version or 'live')+('#'+node if node else ''),artifact]})
    tokens=json.loads(read_member(workspace,artifact,'tokens.json'))
    for group in tokens.values():
        identity=group.get('$extensions',{}).get('figma',{})
        values={k:v for k,v in group.items() if not k.startswith('$')}
        emit('node-values','Observed Figma node values (not an approved standard): '+json.dumps(values,sort_keys=True),
             identity.get('nodeId'),source['version'])
    for observation in meta['details'].get('observations',[]):
        kind=observation['kind']
        if kind=='render':
            emit('render-reference','Rendered visual reference retained in private artifact member '+observation['member'],
                 observation.get('node_id'),source['version'])
        elif kind=='comments':
            payload=json.loads(read_member(workspace,artifact,observation['member']))
            for comment in payload.get('comments',[]):
                message=comment.get('message','')
                if not isinstance(message,str) or not message.strip():continue
                fact={'comment_id':comment.get('id'),'source_user_id':comment.get('user',{}).get('id'),
                      'message':message[:6000],'excerpt':len(message)>6000}
                emit('comment-observation','Unverified source comment; not a design ruling: '+json.dumps(fact,sort_keys=True),
                     observed=observation.get('observed_at'))
        else:
            emit(kind+'-reference','Live unversioned '+kind+' evidence retained in private artifact member '+observation['member'],
                 observed=observation.get('observed_at'))
    return result


def export(workspace,artifact,destination):
    destination=Path(destination)
    data=''.join(json.dumps(record,sort_keys=True,ensure_ascii=False)+'\n' for record in records(workspace,artifact))
    # Refuse silent replacement of a different export; repeat runs are idempotent.
    destination.parent.mkdir(parents=True,exist_ok=True)
    if destination.exists():
        if destination.read_text()!=data:raise ValueError('Evidence output exists with different content')
    else:
        with destination.open('x') as stream:stream.write(data)
    return {'path':str(destination),'observations':len(data.splitlines()),
            'status':'prepared-not-submitted','authority':'machine-observation-only'}
