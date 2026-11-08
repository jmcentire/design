"""Private observation handoff for an explicit Company publisher, never a ruling."""
from datetime import datetime, timezone
import hashlib
import json
import re
from pathlib import Path
from .artifacts.bundle import metadata, read_member


def publisher_error(record):
    """The publisher's admission bounds, checked before any export is written."""
    fields = {'schema','id','source','statement','author_kind','updated_at','evidence_refs'}
    if not isinstance(record,dict) or set(record)!=fields:return 'record must have exactly the publisher fields'
    if record['schema']!='design-evidence/1':return 'unsupported schema'
    if not isinstance(record['id'],str) or not re.fullmatch(r'[0-9a-f]{64}',record['id']):return 'id must be 64 lowercase hex characters'
    if record['author_kind']!='agent':return 'exported observations require agent authorship'
    source = record['source']
    required = {'kind','file_key','version','digest','evidence_kind','time_basis'}
    if not isinstance(source,dict) or not required<=source.keys() or source.keys()-required-{'node_id','comment_id'}:return 'invalid source fields'
    if source['kind']!='figma':return 'source.kind must be figma'
    if source['time_basis'] not in ('source-modified','observed','capture-fallback'):return 'invalid source.time_basis'
    for key,value in source.items():
        if key=='version' and value is None:continue
        if not isinstance(value,str) or not value.strip() or len(value)>256:return 'source.'+key+' must be a nonempty string of at most 256 characters (version may be null)'
    refs = record['evidence_refs']
    if not isinstance(refs,list) or not 1<=len(refs)<=16 or any(not isinstance(ref,str) or not ref.strip() or len(ref)>2048 for ref in refs):return 'evidence_refs must contain 1–16 nonempty strings of at most 2048 characters'
    statement = record['statement']
    if not isinstance(statement,str) or not statement.strip():return 'statement must be nonempty text'
    publisher_text = 'Machine design evidence (not approved direction), source ' + json.dumps(source,sort_keys=True,ensure_ascii=False) + ': ' + statement
    if len(' '.join(publisher_text.split()).encode('utf-8'))>16*1024:return 'full publisher text exceeds 16 KiB'
    stamp = record['updated_at']
    if not isinstance(stamp,str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})',stamp):return 'updated_at must be a timezone-qualified ISO timestamp'
    try:
        if datetime.fromisoformat(stamp).utcoffset() is None:return 'updated_at needs a timezone'
    except ValueError:return 'updated_at is not a valid ISO timestamp'
    return None


def records(workspace, artifact):
    meta=metadata(workspace,artifact)
    source=meta.get('details',{}).get('source',{})
    if source.get('provider')!='figma':raise ValueError('Expected a Figma snapshot artifact')
    document=json.loads(read_member(workspace,artifact,'figma.json'))
    modified=document.get('lastModified')
    result=[]
    def emit(kind,statement,node=None,version=None,observed=None,comment_id=None):
        origin={'kind':'figma','file_key':source['file_key'],'version':version,'digest':artifact,
                'evidence_kind':kind}
        if node:origin['node_id']=node
        if comment_id:origin['comment_id']=comment_id
        origin['time_basis']='observed' if observed else ('source-modified' if modified else 'capture-fallback')
        # The extractor, not a typed comment author name, owns this observation.
        payload={'source':origin,'statement':statement,'author_kind':'agent'}
        # Identity follows the source observation, not its changing contents.
        # A node's values are one aggregate: replacing it also removes old fields.
        identity={key:origin[key] for key in ('kind','file_key','evidence_kind','node_id','comment_id') if key in origin}
        digest=hashlib.sha256(json.dumps(identity,sort_keys=True).encode()).hexdigest()
        result.append({'schema':'design-evidence/1','id':digest,**payload,
                       'updated_at':observed or modified or meta['created'],
                       'evidence_refs':['figma:'+str(source['file_key'])+':'+str(version or 'live')+('#'+str(node) if node else ''),artifact]})
    tokens=json.loads(read_member(workspace,artifact,'tokens.json'))
    for group in tokens.values():
        identity=group.get('$extensions',{}).get('figma',{})
        values={k:v for k,v in group.items() if not k.startswith('$')}
        if not identity.get('nodeId'):continue
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
                comment_id=comment.get('id')
                if not isinstance(comment_id,str) or not comment_id:continue
                if not isinstance(message,str) or not message.strip():continue
                fact={'comment_id':comment.get('id'),'source_user_id':comment.get('user',{}).get('id'),
                      'message':message[:6000],'excerpt':len(message)>6000}
                emit('comment-observation','Unverified source comment; not a design ruling: '+json.dumps(fact,sort_keys=True),
                     observed=observation.get('observed_at'),comment_id=comment_id)
        else:
            emit(kind+'-reference','Live unversioned '+kind+' evidence retained in private artifact member '+observation['member'],
                 observed=observation.get('observed_at'))
    return result


def export(workspace,artifact,destination):
    destination=Path(destination)
    observations = records(workspace,artifact)
    for index,record in enumerate(observations):
        reason = publisher_error(record)
        if reason:raise ValueError(f'Evidence record {index} rejected by publisher contract: {reason}; no export written')
    data=''.join(json.dumps(record,sort_keys=True,ensure_ascii=False)+'\n' for record in observations)
    # Refuse silent replacement of a different export; repeat runs are idempotent.
    destination.parent.mkdir(parents=True,exist_ok=True)
    if destination.exists():
        if destination.read_text()!=data:raise ValueError('Evidence output exists with different content')
    else:
        with destination.open('x') as stream:stream.write(data)
    return {'path':str(destination),'observations':len(data.splitlines()),
            'status':'prepared-not-submitted','authority':'machine-observation-only'}
