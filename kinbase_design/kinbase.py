"""Existing Kinbase commands behind one bounded, explicit adapter boundary."""
from copy import deepcopy
from datetime import datetime,timezone
import fcntl
import json
import logging
import os
import signal
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from uuid import uuid4
from .config import kinbase_config,KINBASE_TIMEOUT_SECONDS,KINBASE_OUTPUT_BYTES,KINBASE_FEEDBACK_LENGTH
from .storage import inside,load_language,write_json
from .language.versions import digest

log=logging.getLogger(__name__)


def command(arguments,cwd=None):
    """Bound runtime and captured diagnostics without a shell or credential lookup."""
    with tempfile.TemporaryFile() as out,tempfile.TemporaryFile() as err:
        process=None
        try:
            process=subprocess.Popen(arguments,cwd=cwd,stdout=out,stderr=err,start_new_session=os.name=='posix')
            process.wait(timeout=KINBASE_TIMEOUT_SECONDS)
        except (OSError,subprocess.TimeoutExpired) as exc:
            return {'ok':False,'error':str(exc),'receipt':None}
        finally:
            if process is not None:
                try:
                    if os.name=='posix':os.killpg(process.pid,signal.SIGKILL)
                    elif process.poll() is None:process.kill()
                except ProcessLookupError:pass
                process.wait(timeout=KINBASE_TIMEOUT_SECONDS)
        for stream in (out,err):
            if stream.tell()>KINBASE_OUTPUT_BYTES:return {'ok':False,'error':'Kinbase response exceeds output bound','receipt':None}
            stream.seek(0)
        stdout=out.read().decode('utf-8',errors='replace');stderr=err.read().decode('utf-8',errors='replace')
    log.info('kinbase_command executable=%s status=%s',Path(arguments[0]).name,process.returncode)
    try:receipt=json.loads(stdout)
    except ValueError:receipt=stdout
    return {'ok':process.returncode==0,'receipt':receipt,'stdout':stdout,'stderr':stderr,
            'error':(stderr or stdout or 'Kinbase command failed') if process.returncode else None}


def unavailable(reason):
    label='unknown (Kinbase unavailable: '+reason+')'
    return {'connected':False,'standards':label,'direction':label,'reason':reason,'facts':[],'unknowns':[]}


def configured_repo(library,settings):
    if settings.repo:return Path(settings.repo).expanduser().resolve()
    root=Path(library or Path.cwd()).resolve()
    return next((p for p in (root,*root.parents) if (p/'.git').exists()),root)


def machine_statement(statement):
    """Amendment18 proposal only; prose is never interpreted as an instruction."""
    if not isinstance(statement,str):return None
    try:value=json.loads(statement,parse_constant=lambda value:(_ for _ in ()).throw(ValueError(value)))
    except ValueError:return None
    if not isinstance(value,dict) or set(value)!={'kinbase-design'}:return None
    design=value['kinbase-design']
    if not isinstance(design,dict) or set(design)-{'values','dimensions','mappings'}:return None
    values=design.get('values',{})
    if not isinstance(values,dict):return None
    # Meaning mappings: corpus id → token path → Vocabulary-grounded meaning. Shape only;
    # the meaning layer grounds each one against the Vocabulary before it certifies anything.
    mappings=design.get('mappings',{})
    if not isinstance(mappings,dict):return None
    for corpus,subjects in mappings.items():
        if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*',corpus) or not isinstance(subjects,dict):return None
        for subject,meaning in subjects.items():
            if not re.fullmatch(r'[a-zA-Z0-9_-]+(?:\.[a-zA-Z0-9_-]+)*',subject) or not isinstance(meaning,dict):return None
            if set(meaning)-{'property','emphasis','role','state'} or any(not isinstance(v,str) for v in meaning.values()):return None
    from .generate.dimensions import validate_values
    try:dimensions=validate_values(design.get('dimensions',{}))
    except ValueError:return None
    for pointer in values:
        if not pointer.startswith('/') or re.search(r'~(?![01])',pointer):return None
        # Identity is owned by the language package, not a presentation standard.
        if pointer.split('/')[1] not in {'style','roles','layout','components','overrides','behaviors','assets'}:return None
    return {'values':deepcopy(values),'dimensions':dimensions,'mappings':deepcopy(mappings)}


def machine_values(statement):
    parsed=machine_statement(statement)
    return parsed['values'] if parsed is not None else None


def explain(settings,repo,scope,key,kind):
    result=command([settings.binary,'explain',key,'--repo',str(repo),'--decision',settings.decision,'--json'],cwd=repo)
    if not result['ok']:return None,result['error']
    receipt=result['receipt']
    if not isinstance(receipt,dict) or receipt.get('state') not in {'current','conflict','unknown'}:
        return None,'Kinbase explain returned an invalid response'
    current=receipt.get('current')
    entry={'kind':kind,'scope':scope,'key':key,'state':receipt['state'],'current':current,
           'trusted':receipt.get('trusted'),'unknowns':receipt.get('unknowns',[]),'receipt':receipt,
           'fixed':False,'values':{},'dimensions':{},'mappings':{},'application':'Unknown'}
    if receipt['state']=='conflict':entry['application']='Conflict — no value applied'
    elif receipt['state']=='current' and isinstance(current,dict):
        authoritative=current.get('standing')=='authoritative'
        in_scope=current.get('scope')==scope
        fact_id=current.get('fact_id')
        parsed=machine_statement(current.get('statement'))
        if receipt.get('trusted') is False:entry['application']='Untrusted projection — no value applied'
        elif not in_scope:entry['application']='Outside configured scope — no value applied'
        elif not authoritative:entry['application']='Suggestion — not a fixed input'
        elif kind=='direction':entry['application']='Current direction'
        elif parsed is None:entry['application']='Authoritative standard: not machine-applicable — apply manually'
        elif not isinstance(fact_id,str) or not re.fullmatch(r'[a-zA-Z0-9_.:-]+',fact_id):
            entry['application']='Authoritative standard: missing usable fact id — apply manually'
        elif kind=='standards':
            entry.update(fixed=True,**parsed,application='Authoritative fixed input')
        else:entry['application']='Current direction'
    return entry,None


def status(library=None,settings=None):
    try:settings=settings or kinbase_config()
    except (ValueError,OSError) as exc:return unavailable(str(exc))
    binary=shutil.which(settings.binary)
    if not binary:return unavailable('binary not found: '+settings.binary)
    repo=configured_repo(library,settings)
    verified=command([settings.binary,'fsck','--repo',str(repo),'--json'],cwd=repo)
    if not verified['ok']:return unavailable('fsck failed (repository not initialized or unavailable): '+str(verified['error']))
    facts=[];unknowns=[]
    for kind,keys in (('standards',settings.standard_keys),('direction',settings.direction_keys)):
        for scope,key in sorted(keys.items()):
            fact,error=explain(settings,repo,scope,key,kind)
            if error:return unavailable(error)
            facts.append(fact)
            if isinstance(fact['unknowns'],list):unknowns.extend(fact['unknowns'])
    result={'connected':True,'reason':None,'facts':facts,'unknowns':unknowns}
    for kind in ('standards','direction'):
        entries=[f for f in facts if f['kind']==kind]
        result[kind]=('conflict' if any(f['state']=='conflict' for f in entries) else
                      'current' if entries and all(f['state']=='current' for f in entries) else 'unknown')
    return result


def fact_provenance(fact,member,name):
    from .findings import pointer
    return {'kind':'source','artifact':'kinbase:'+fact['current']['fact_id'],
            'location':pointer('kinbase-design',member,name)}


def fixed_dimensions(snapshot):
    result={}
    for fact in snapshot.get('facts',[]):
        if not fact.get('fixed'):continue
        for dimension,value in fact.get('dimensions',{}).items():
            if dimension in result and result[dimension]['value']!=value:
                raise ValueError('Conflicting authoritative Kinbase dimension: '+dimension)
            result[dimension]={'value':value,**fact_provenance(fact,'dimensions',dimension)}
    return result


def apply_dimensions(values,snapshot):
    return {**values,**{dimension:entry['value'] for dimension,entry in fixed_dimensions(snapshot).items()}}


def dimension_provenance(provenance,owners,snapshot):
    fixed=fixed_dimensions(snapshot)
    for path,dimensions in owners.items():
        records=[{k:v for k,v in fixed[d].items() if k!='value'} for d in dimensions if d in fixed]
        if records:
            provenance[path]={**records[0],**({'inputs':records[1:]} if len(records)>1 else {})}
    return provenance


def fixed_inputs(snapshot):
    """Retain fact ids at exact pointers; incompatible sources are explicit conflicts."""
    values={};conflicts=[]
    for fact in snapshot.get('facts',[]):
        if not fact.get('fixed'):continue
        for pointer,value in fact['values'].items():
            record={'value':deepcopy(value),**fact_provenance(fact,'values',pointer)}
            previous=values.get(pointer)
            if previous is not None and previous['value']!=value:conflicts.append(pointer)
            else:values[pointer]=record
    from .findings import location
    for pointer,entry in values.items():
        for child,other in values.items():
            if child.startswith(pointer+'/'):
                requested=child[len(pointer):]
                found,value=location(entry['value'],requested)
                if found!=requested or value!=other['value']:conflicts.extend((pointer,child))
    if conflicts:raise ValueError('Conflicting authoritative Kinbase values at '+', '.join(sorted(set(conflicts))))
    return values


def apply_fixed(document,provenance,inputs):
    """Apply pointer values verbatim; ordinary language validation still judges them."""
    from .findings import location
    for pointer,entry in sorted(inputs.items(),key=lambda pair:(pair[0].count('/'),pair[0])):
        old_path,old_value=location(document,pointer)
        overlaps=[p for p,r in provenance.items() if r.get('kind')=='source' and
                  (p==pointer or p.startswith(pointer+'/') or pointer.startswith(p+'/'))]
        if overlaps and (old_path!=pointer or old_value!=entry['value']):
            raise ValueError('Authoritative input conflicts with supplied source at '+pointer)
        current=document;parts=[part.replace('~1','/').replace('~0','~') for part in pointer.split('/')[1:]]
        for part in parts[:-1]:
            if isinstance(current,dict):current=current.setdefault(part,{})
            elif isinstance(current,list) and part.isdecimal() and int(part)<len(current):current=current[int(part)]
            else:raise ValueError('Authoritative pointer has no assignable parent: '+pointer)
        key=parts[-1]
        if isinstance(current,dict):current[key]=deepcopy(entry['value'])
        elif isinstance(current,list) and key.isdecimal() and int(key)<len(current):current[int(key)]=deepcopy(entry['value'])
        else:raise ValueError('Authoritative pointer is not assignable: '+pointer)
        for child in list(provenance):
            if child.startswith(pointer+'/'):del provenance[child]
        provenance[pointer]={key:value for key,value in entry.items() if key!='value'}
    return document,provenance


def submit(library,text,kind,settings=None):
    if kind not in {'concept','question','decision'}:raise ValueError('Unsupported Kinbase submission type')
    try:settings=settings or kinbase_config()
    except (ValueError,OSError) as exc:return {'status':'not sent (Kinbase unavailable)','reason':str(exc),'receipt':None}
    snapshot=status(library,settings)
    if not snapshot['connected']:return {'status':'not sent (Kinbase unavailable)','reason':snapshot['reason'],'receipt':None}
    repo=configured_repo(library,settings)
    result=command(['kin','kinbase','submit','--repo',str(repo),'--type',kind,text,'--json'],cwd=repo)
    return {'status':'received' if result['ok'] else 'not sent (Kinbase command failed)',
            'receipt':result['receipt'],'error':result.get('error'),'stderr':result.get('stderr','')}


def ask(library,question_id,settings=None):
    try:settings=settings or kinbase_config()
    except (ValueError,OSError) as exc:return {'status':'not sent (Kinbase unavailable)','reason':str(exc),'receipt':None}
    snapshot=status(library,settings)
    if not snapshot['connected']:return {'status':'not sent (Kinbase unavailable)','reason':snapshot['reason'],'receipt':None}
    owned=[item for item in snapshot['unknowns'] if isinstance(item,dict) and
           (item.get('question_id')==question_id or item.get('unknown_id')==question_id or item.get('id')==question_id) and
           (item.get('owner_identity') or item.get('owner') or item.get('owner_role'))]
    if not owned:raise ValueError('Only owned Unknowns returned by explain may be routed')
    result=command([settings.binary,'questions','ask',question_id,'--json'],cwd=configured_repo(library,settings))
    return {'status':'received' if result['ok'] else 'not sent (Kinbase command failed)',
            'receipt':result['receipt'],'error':result.get('error'),'stderr':result.get('stderr','')}


def feedback(library,workspace,language_id,author,target,text,flag=False):
    if not isinstance(author,str) or not author.strip() or len(author)>200:raise ValueError('Feedback needs an author')
    if not isinstance(text,str) or not text.strip() or len(text)>KINBASE_FEEDBACK_LENGTH:raise ValueError('Feedback text is empty or too long')
    document=load_language(library,language_id)
    from .vocabulary import load
    vocabulary=load(library,document['vocabulary'])
    if target not in vocabulary['constructs'] and target not in vocabulary['context']['pages']:raise ValueError('Unknown feedback page or construct')
    reference=language_id+'@'+digest(document)+'#'+target
    entry={'id':'feedback-'+uuid4().hex,'author':author,'target':reference,'text':text,
           'ts':datetime.now(timezone.utc).isoformat(),'kind':'question' if flag else 'concept','provenance':'agent'}
    path=inside(workspace,'feedback.jsonl');path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('a',encoding='utf-8') as stream:
        fcntl.flock(stream,fcntl.LOCK_EX);stream.write(json.dumps(entry,ensure_ascii=False)+'\n');stream.flush()
    receipt=submit(library,'Kinbase Design feedback (agent provenance), author '+author+', target '+reference+': '+text,entry['kind'])
    write_json(inside(workspace,'kinbase-receipts',entry['id']+'.json'),receipt)
    return {**entry,'submission':receipt}


def propose(library,workspace,language_id,scope):
    settings=kinbase_config()
    if scope not in settings.direction_keys:raise ValueError('Choose a configured direction scope')
    from .language.versions import mint
    version=mint(library,language_id)
    if 'ref' not in version:raise ValueError('Language has unresolved validation findings; direction proposal was not sent')
    reference=version['ref']
    result=submit(library,'Kinbase Design direction proposal (agent provenance): use '+reference+' for scope '+scope,'decision',settings)
    receipt_id='proposal-'+uuid4().hex
    write_json(inside(workspace,'kinbase-receipts',receipt_id+'.json'),result)
    return {'id':receipt_id,'submission':result}
