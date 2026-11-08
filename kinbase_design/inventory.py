"""Site-owned requirements compared with the canonical resolver and validator."""
import hashlib
import logging
from pathlib import Path
from .assets import asset_path
from .findings import Finding, location, pointer, report
from .language.resolver import resolve, property_pointer
from .language.tokens import Tokens
from .language.validation import Validator
from .storage import load_language, read_json
from .vocabulary import load, slot_map

INVENTORY_FILE = 'kinbase-design.inventory.json'


def justified_exception(exceptions, scope, rule, finding_type=None):
    for index, entry in enumerate(exceptions):
        if not isinstance(entry,dict) or not isinstance(entry.get('reason'),str) or not entry['reason'].strip():continue
        declared = entry.get('scope')
        if (entry.get('rule')!=rule and entry.get('rule')!=finding_type) or not isinstance(declared,str):continue
        if rule == 'inventory-asset':
            page,request=scope.rsplit('/asset/',1)
            # Retain the earlier page/kind spelling for existing inventories.
            prefix=page+'/asset/' if declared.startswith(page+'/asset/') else page+'/'
            if not declared.startswith(prefix):continue
            asset_request=declared[len(prefix):]
            if asset_request==request or (':' not in asset_request and asset_request==request.split(':',1)[0]):
                return pointer('exceptions',index)
        elif scope == declared or scope.startswith(declared + '.'):
            return pointer('exceptions',index)
    return None


class Treatment:
    """Inspect effective properties, without another resolution/validation path."""
    def __init__(self, library, language_id, document, vocabulary):
        self.library,self.id,self.doc,self.vocab = library,language_id,document,vocabulary
        self.tokens = Tokens(document.get('style',{}))
        self.breakpoints = [None] + [name.removeprefix('breakpoint.') for name in sorted(self.tokens.nodes)
                                      if name.startswith('breakpoint.')]

    def properties(self, scope, state='default', breakpoint=None):
        return resolve(self.doc,self.vocab,scope,state,breakpoint)['properties']

    def complete(self, construct, slot=None):
        validator = Validator(self.library,self.id,self.doc,self.vocab)
        validator.tokens = self.tokens
        contract = self.vocab['constructs'][construct]
        slots = [slot] if slot else [s['id'] for s in contract['slots'] if s['required']]
        try:
            for name in slots:
                defaults = slot_map(contract)[name]
                entry = self.doc.get('components',{}).get(construct,{}).get('slots',{}).get(name,{})
                role,emphasis=entry.get('role',defaults['role']),entry.get('emphasis',defaults['emphasis'])
                validator.role_pair(role,emphasis,pointer('components',construct,'slots',name))
                validator.properties(self.doc.get('roles',{}).get(role,{}).get(emphasis,{}),
                                     pointer('roles',role,emphasis),roles=True)
            for scope in ([construct] if slot is None else []) + [construct+'.'+name for name in slots]:
                for bp in self.breakpoints:
                    for prop, detail in self.properties(scope,breakpoint=bp).items():
                        path = property_pointer(self.doc,self.vocab,prop,detail)
                        _, raw = location(self.doc,path)
                        validator.properties({prop:raw},path.rsplit('/',1)[0])
        except (KeyError,ValueError,TypeError,AttributeError):
            return False
        return not any(f['type'] in {'violation','missing'} for f in validator.findings)

    def distinct_state(self, construct, state):
        if state == 'default':return self.complete(construct)
        contract = self.vocab['constructs'][construct]
        if state not in contract['states']:return False
        scopes = [construct] + [construct+'.'+name for name in slot_map(contract)]
        try:
            return any({k:v['value'] for k,v in self.properties(scope,state,bp).items()} !=
                       {k:v['value'] for k,v in self.properties(scope,'default',bp).items()}
                       for bp in self.breakpoints for scope in scopes)
        except (KeyError,ValueError,TypeError,AttributeError):
            return False

    def bound_assets(self):
        bindings = set()
        for component in self.doc.get('components',{}).values():
            for binding in component.get('assets',{}).values():
                if isinstance(binding,str) and binding.count(':')==1:bindings.add(tuple(binding.split(':')))
        for name,node in self.tokens.nodes.items():
            if node['$type']=='fontFamily':
                asset = self.tokens.font_asset(name)
                bindings.update((asset,variant) for variant in self.doc.get('assets',{}).get(asset,{}).get('variants',{}))
        def backgrounds(value):
            if isinstance(value,dict):
                raw=value.get('background-image')
                if isinstance(raw,str) and raw.startswith('asset:') and raw.count(':')==2:
                    bindings.add(tuple(raw.split(':')[1:]))
                for child in value.values():backgrounds(child)
            elif isinstance(value,list):
                for child in value:backgrounds(child)
        backgrounds(self.doc)
        packaged={}
        def present(detail):
            if not isinstance(detail,dict):return False
            key=detail.get('file')
            if not isinstance(key,str):return False
            if key not in packaged:
                try:
                    file=asset_path(self.library,self.id,detail)
                    packaged[key]=hashlib.sha256(file.read_bytes()).hexdigest()==key.split('/')[1]
                except (OSError,ValueError,KeyError,TypeError):packaged[key]=False
            return packaged[key]
        bound={asset for asset,variant in bindings
               if present(self.doc.get('assets',{}).get(asset,{}).get('variants',{}).get(variant))}
        # Binding makes the asset available; the inventory may request any of its
        # packaged variants, without requiring the preview to display that variant.
        return {(self.doc['assets'][asset]['kind'],variant)
                for asset in bound
                for variant,detail in self.doc['assets'][asset].get('variants',{}).items()
                if present(detail)}



def inventory_check(library, language_id, inventory_path):
    path=Path(inventory_path).expanduser().resolve()
    inventory=read_json(path)
    root=next((p for p in path.parents if (p/'.git').exists()),path.parent)
    file=path.relative_to(root).as_posix()
    document=load_language(library,language_id)
    vocabulary=load(library,document['vocabulary'])
    treatment=Treatment(library,language_id,document,vocabulary)
    findings=[]
    exceptions=inventory.get('exceptions',[]) if isinstance(inventory,dict) else []

    def issue(kind, rule, at, expected, message, scope=None):
        existing,observed=location(inventory,at)
        item=Finding(kind,rule,file,existing,observed,expected,message).to_dict()
        item['scope']=scope
        item['exception']=justified_exception(exceptions,scope,rule,kind) if scope else None
        findings.append(item)

    if not isinstance(inventory,dict) or not isinstance(inventory.get('pages'),list):
        issue('violation','schema','/pages','an inventory with a pages array','Inventory needs a pages array')
        return report(language_id,findings)
    if not isinstance(exceptions,list):
        issue('violation','schema','/exceptions','an array','Exceptions must be an array');exceptions=[]
    for index,entry in enumerate(exceptions):
        if not isinstance(entry,dict) or any(not isinstance(entry.get(k),str) or not entry[k].strip() for k in ('scope','rule','reason')):
            issue('violation','schema',pointer('exceptions',index),'scope, rule and nonempty reason','An exception needs a scope, rule and justification')
    assets=treatment.bound_assets()
    kinds={kind for kind,variant in assets}
    for pi,page in enumerate(inventory['pages']):
        base=pointer('pages',pi)
        if not isinstance(page,dict) or not isinstance(page.get('id'),str) or not page['id']:
            issue('violation','schema',base,'a page with an id','Inventory page needs an id');continue
        page_id=page['id']
        for key in ('constructs','assets'):
            if not isinstance(page.get(key,[]),list):
                issue('violation','schema',base+'/'+key,'an array','Page '+key+' must be an array')
        if isinstance(page.get('constructs',[]),list):
            for ci,entry in enumerate(page.get('constructs',[])):
                at=base+pointer('constructs',ci)
                construct=entry.get('construct') if isinstance(entry,dict) else None
                if not isinstance(construct,str):
                    issue('violation','schema',at,'a construct requirement','Requirement needs a construct id');continue
                scope=page_id+'/'+construct
                if construct not in vocabulary['constructs'] or not treatment.complete(construct):
                    issue('missing','inventory-construct',at+'/construct','a complete resolved construct treatment',f'Untreated construct: {construct}',scope)
                for field,rule in (('slots','inventory-slot'),('states','inventory-state')):
                    values=entry.get(field,[])
                    if not isinstance(values,list):
                        issue('violation','schema',at+'/'+field,'an array','Requirement '+field+' must be an array');continue
                    for vi,value in enumerate(values):
                        q=at+pointer(field,vi)
                        if not isinstance(value,str):
                            issue('violation','schema',q,'an identifier','Required '+field+' must be identifiers');continue
                        contract=vocabulary['constructs'].get(construct,{'slots':[]})
                        covered=(value in slot_map(contract) and treatment.complete(construct,value) if field=='slots' else
                                 construct in vocabulary['constructs'] and treatment.distinct_state(construct,value))
                        if not covered:
                            expected='a complete resolved slot treatment' if field=='slots' else 'a declared state with resolved treatment distinct from default'
                            issue('missing',rule,q,expected,f'Untreated {field[:-1]}: {construct}.{value}',scope+'.'+value)
        if isinstance(page.get('assets',[]),list):
            for ai,request in enumerate(page.get('assets',[])):
                covered=False
                if isinstance(request,str):
                    covered=tuple(request.split(':')) in assets if ':' in request else request in kinds
                if not covered:
                    issue('missing','inventory-asset',base+pointer('assets',ai),'a bound asset kind with the requested variant packaged',
                          f'Absent bound asset request: {request}',page_id+'/asset/'+str(request))
    result=report(language_id,findings)
    logging.getLogger(__name__).info('inventory_check language=%s accepted=%s findings=%d',language_id,result['accepted'],len(findings))
    return result
