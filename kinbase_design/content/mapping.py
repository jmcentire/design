"""Amendment-02 declarative section mapping; records are never executable."""
from copy import deepcopy
from pathlib import Path
import re
from ..findings import Finding, location, pointer
from ..storage import read_json, write_json
from .validation import validate_content, content_field_path


def parts(path):
    if not isinstance(path,str) or (path and not path.startswith('/')) or re.search(r'~(?![01])',path):
        raise ValueError('Expected an RFC 6901 source pointer')
    return [p.replace('~1','/').replace('~0','~') for p in path.split('/')[1:]]


def lookup(value, path):
    for key in parts(path):
        if isinstance(value,dict) and key in value:value=value[key]
        elif isinstance(value,list) and re.fullmatch(r'0|[1-9][0-9]*',key) and int(key)<len(value):value=value[int(key)]
        else:raise KeyError(path)
    return value


def assign(root, path, value):
    keys=path.split('/')
    for i,key in enumerate(keys):
        last=i==len(keys)-1
        if isinstance(root,list):
            index=int(key)
            if index>1000:raise ValueError('Output array index exceeds 1000')
            while len(root)<=index:root.append(None)
            if last:root[index]=value;return
            if root[index] is None:root[index]=[] if keys[i+1].isdigit() else {}
            root=root[index]
        elif isinstance(root,dict):
            if last:root[key]=value;return
            root=root.setdefault(key,[] if keys[i+1].isdigit() else {})
        else:raise ValueError('Conflicting content field paths')


def mapped_value_findings(kind, field, value, item=False):
    """Validate one projection with the content validator, before copying it.

    Other fields may be supplied by later projections. Findings outside this
    field (including missing siblings) remain the final document's concern.
    """
    probe={'schema':'kinbase-content/1','page':{'title':'Mapping'},'site':{'name':'Mapping'},'blocks':[]}
    if not item and field.split('/')[0] in {'page','site','footer'}:
        target=probe;prefix=''
    elif item:
        target={};probe['blocks']=[{'type':'collection','items':[target]}];prefix='/blocks/0/items/0'
    else:
        target={'type':kind};probe['blocks']=[target];prefix='/blocks/0'
    assign(target,field,deepcopy(value))
    path=prefix+'/'+field
    checked,_,_=validate_content(probe,Path('mapped-value.json'),check_images=False)
    return [(f['pointer'][len(path):],f['expected']) for f in checked['findings']
            if f['pointer']==path or f['pointer'].startswith(path+'/')]


def map_sections(mapping_file, sections_file, out):
    mapping_file,sections_file,out=map(lambda p:Path(p).resolve(),(mapping_file,sections_file,out))
    if out in (mapping_file,sections_file):raise ValueError('Mapped content must not overwrite its inputs')
    mapping,source=read_json(mapping_file),read_json(sections_file)
    findings=[];unmapped=[];origins={};missing_origins={}
    def issue(document,file,path,expected):
        p,value=location(document,path)
        findings.append(Finding('violation','section-map',str(file),p,value,expected,expected).to_dict())
    def bad(path,message):issue(mapping,mapping_file,path,message)
    def object(value,path,allowed,required=()):
        if not isinstance(value,dict):bad(path,'an object');return False
        for key in value.keys()-set(allowed):bad(path+pointer(key),'a declared mapping field')
        for key in set(required)-value.keys():bad(path,'required field: '+key)
        return True
    def fields(value,path,kind,item=False):
        if not isinstance(value,dict):bad(path,'an object of content paths to source pointers');return
        for target,ref in value.items():
            if not re.fullmatch(r'[a-z][a-z0-9_-]*(?:/(?:[a-z][a-z0-9_-]*|0|[1-9][0-9]*))*',target):bad(path+pointer(target),'a slash-separated content field path')
            if not content_field_path(kind,target,item):bad(path+pointer(target),'a field path declared by the content block or item schema')
            try:parts(ref)
            except ValueError as exc:bad(path+pointer(target),str(exc))
    if object(mapping,'',{'schema','page','site','footer','sections'},{'schema','sections'}):
        if mapping.get('schema')!='kinbase-section-map/1':bad('/schema','kinbase-section-map/1')
        if not isinstance(mapping.get('sections'),list):bad('/sections','an array of section rules')
        else:
            for i,rule in enumerate(mapping['sections']):
                p=pointer('sections',i)
                if not object(rule,p,{'match','block','fields','items'},{'match','block','fields'}):continue
                match=rule.get('match')
                if object(match,p+'/match',{'type','variant'},{'type'}):
                    for key,val in match.items():
                        if not isinstance(val,str):bad(p+'/match/'+key,'a string')
                if rule.get('block') not in ('hero','section','collection','cta'):bad(p+'/block','hero, section, collection or cta')
                fields(rule.get('fields'),p+'/fields',rule.get('block'))
                if 'items' in rule:
                    if rule.get('block')!='collection':bad(p+'/items','items only on collection rules')
                    if object(rule['items'],p+'/items',{'from','fields'},{'from','fields'}):
                        try:parts(rule['items'].get('from'))
                        except ValueError as exc:bad(p+'/items/from',str(exc))
                        fields(rule['items'].get('fields'),p+'/items/fields',rule.get('block'),True)
    if findings:return {'accepted':False,'out':str(out),'blocks':0,'unmapped':unmapped,'findings':findings}
    records=source.get('sections') if isinstance(source,dict) else source
    prefix='/sections' if isinstance(source,dict) else ''
    if not isinstance(records,list):
        issue(source,sections_file,prefix,'an array of section records')
        return {'accepted':False,'out':str(out),'blocks':0,'unmapped':unmapped,'findings':findings}
    document={'schema':'kinbase-content/1','page':deepcopy(mapping.get('page',{})),
              'site':deepcopy(mapping.get('site',{})),'blocks':[]}
    if 'footer' in mapping:document['footer']=deepcopy(mapping['footer'])
    mapping_invalid=False
    for i,record in enumerate(records):
        p=prefix+pointer(i)
        if not isinstance(record,dict) or not isinstance(record.get('type'),str) or ('variant' in record and not isinstance(record['variant'],str)):
            issue(source,sections_file,p,'a record with string type and optional string variant');continue
        candidates=[(j,r) for j,r in enumerate(mapping['sections']) if r['match']['type']==record['type'] and ('variant' not in r['match'] or r['match']['variant']==record.get('variant'))]
        specific=[pair for pair in candidates if 'variant' in pair[1]['match']]
        if not candidates:
            unmapped.append({'pointer':p,'type':record['type'],'variant':record.get('variant'),'reason':'no matching rule'});continue
        index,rule=(specific or candidates)[0]
        block={'type':rule['block']};target_pointer=pointer('blocks',len(document['blocks']))
        origins[target_pointer]=p;consumed=set()
        def project(field_map,record,base,target,target_base,mapping_base,allow_global=False):
            nonlocal mapping_invalid
            for field,ref in field_map.items():
                scope=target;relative=field;dest=target_base+'/'+field
                if allow_global and field.split('/')[0] in {'page','site','footer'} and '/' in field:
                    scope=document;dest='/'+field
                source_pointer=base+ref
                try:value=deepcopy(lookup(record,ref))
                except KeyError:
                    missing_origins[dest]=source_pointer
                    continue
                if base==p:consumed.add(parts(ref)[0] if parts(ref) else '*')
                if rule['block']=='section' and field=='content' and isinstance(value,str):value=[{'paragraph':value}]
                invalid=mapped_value_findings(rule['block'],field,value,item=not allow_global)
                if invalid:
                    for suffix,expected in invalid:
                        issue(source,sections_file,source_pointer+suffix,expected)
                        findings[-1]['message']='Mapped field omitted: '+expected
                    missing_origins[dest]=source_pointer
                    continue
                origins[dest]=source_pointer
                try:assign(scope,relative,value)
                except (ValueError,TypeError) as exc:
                    bad(mapping_base+pointer(field),str(exc));mapping_invalid=True
        project(rule['fields'],record,p,block,target_pointer,pointer('sections',index,'fields'),True)
        if 'items' in rule:
            spec=rule['items'];ref=spec['from'];consumed.add(parts(ref)[0] if parts(ref) else '*')
            try:items=lookup(record,ref)
            except KeyError:items=None
            if items is not None:
                if not isinstance(items,list):issue(source,sections_file,p+ref,'an array of collection items')
                else:
                    block['items']=[]
                    for j,item in enumerate(items):
                        child={};target=target_pointer+pointer('items',j);origins[target]=p+ref+pointer(j)
                        project(spec['fields'],item,p+ref+pointer(j),child,target,pointer('sections',index,'items','fields'))
                        block['items'].append(child)
        document['blocks'].append(block)
        for key,value in record.items():
            if key not in {'type','variant','version','theme'} and key not in consumed and '*' not in consumed and isinstance(value,(str,int,float,list)) and not isinstance(value,bool):
                unmapped.append({'pointer':p+pointer(key),'reason':'field not mapped'})
    checked,_,_=validate_content(document,out,check_images=False)
    for finding in checked['findings']:
        required=finding['expected'].removeprefix('required field: ')
        missing=finding['pointer']+'/'+required
        if finding['expected'].startswith('required field: ') and missing in missing_origins:
            issue(source,sections_file,missing_origins[missing],finding['expected'])
            continue
        candidates=[key for key in origins if finding['pointer']==key or finding['pointer'].startswith(key+'/')]
        if candidates:
            key=max(candidates,key=len)
            issue(source,sections_file,origins[key]+finding['pointer'][len(key):],finding['expected'])
        else:
            bad(finding['pointer'],finding['expected']);mapping_invalid=True
    count=len(document['blocks'])
    if count and not mapping_invalid:write_json(out,document)
    return {'accepted':bool(count) and not mapping_invalid,'out':str(out),'blocks':count,'unmapped':unmapped,'findings':findings}
