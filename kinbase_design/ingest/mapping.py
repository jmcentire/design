"""Deterministic semantic mapping. Captured text stays data in the private workspace."""
from ..vocabulary import slot_map


def construct_for(node):
    tag=node['tag'];attrs=node.get('attributes',{});hint=(attrs.get('class','')+' '+attrs.get('id','')).lower()
    if tag=='nav' or attrs.get('role')=='navigation':return 'nav'
    if tag=='footer':return 'footer'
    if tag=='form':return 'search-bar' if 'search' in hint or attrs.get('role')=='search' else 'form'
    if tag=='article' or ('card' in hint and tag in {'div','li'}):return 'listing-card'
    if tag=='header' or 'hero' in hint:return 'hero'
    if tag=='section':return 'gallery' if 'gallery' in hint else 'content-section'
    return None


def map_view(view,vocabulary,suggestions=()):
    nodes=view.get('nodes',[]);by_selector={n['selector']:n for n in nodes}
    instances=[];roots={};assignments=[];unmapped=[]
    proposals={item['selector']:item for item in suggestions}
    for node in nodes:
        construct=construct_for(node)
        if construct in vocabulary['constructs']:
            item={'construct':construct,'selector':node['selector'],'values':{},'media':{},'nodes':{}}
            roots[node['selector']]=item;instances.append(item)
    fallback={'construct':'content-section','selector':'body','values':{},'media':{},'nodes':{}}
    def owner(node):
        current=node
        while current:
            if current['selector'] in roots:return roots[current['selector']]
            current=by_selector.get(current.get('parent'))
        if fallback not in instances:instances.append(fallback)
        return fallback
    for node in nodes:
        direct=node.get('directText','').strip()
        if not direct and node['tag'] not in {'img','svg','input','textarea','select'}:continue
        item=owner(node);proposal=proposals.get(node['selector'])
        if proposal and item['construct']!=proposal['construct']:
            item={'construct':proposal['construct'],'selector':node['selector'],'values':{},'media':{},'nodes':{}}
            instances.append(item)
        slots=slot_map(vocabulary['constructs'][item['construct']])
        hint=' '.join(node.get('attributes',{}).values()).lower();tag=node['tag']
        preferred='price' if 'price' in hint else 'rating' if 'rating' in hint else 'location' if 'location' in hint else None
        role='media' if tag in {'img','svg'} else 'title' if tag in {'h1','h2'} else 'subtitle' if tag in {'h3','h4','h5','h6'} else 'action' if tag in {'a','button'} else 'control' if tag in {'input','textarea','select'} else 'body'
        slot=preferred if preferred in slots else next((name for name,s in slots.items() if s['role']==role),None)
        if proposal:slot=proposal['slot']
        if slot is None and role in {'title','subtitle','body'}:
            slot=next((name for name,s in slots.items() if s['kind']=='text' and name not in item['values']),None)
        if slot is None:unmapped.append(node['selector']);continue
        if tag in {'img','svg'}:item['media'].setdefault(slot,[]).append({'url':node.get('src'),'alt':node.get('attributes',{}).get('alt',node.get('attributes',{}).get('aria-label',''))})
        elif slot=='links' and direct:item['values'].setdefault(slot,[]).append(direct)
        elif direct:item['values'][slot]=(item['values'].get(slot,'')+' '+direct).strip()
        item['nodes'].setdefault(slot,node)
        assignments.append({'selector':node['selector'],'construct':item['construct'],'slot':slot,'role':slots[slot]['role'],'emphasis':slots[slot]['emphasis']})
    for item in instances:
        if item['selector'] in by_selector:item['root_node']=by_selector[item['selector']]
    return {'instances':instances,'assignments':assignments,'unmapped':unmapped}
