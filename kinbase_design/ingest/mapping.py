"""Deterministic semantic grouping over captured DOM content and measured nodes."""
import re
from urllib.parse import urljoin
from ..artifacts.capture import public_url
from ..vocabulary import slot_map
from ..checks.math import color


def semantic_role(node):
    tag=node['tag'];attrs=node.get('attributes',{})
    if tag in {'img','svg'}:return 'media'
    if tag in {'input','textarea','select'}:return 'control'
    if tag in {'a','button'}:return 'action'
    headings=re.findall(r'(?:^| > )h([1-6])(?=:| > |$)',node.get('selector',''))
    level=int(tag[1]) if re.fullmatch(r'h[1-6]',tag) else int(headings[-1]) if headings else None
    if level:return 'title' if level<=2 else 'subtitle'
    if re.search(r'(?:^| > )(?:a|button):',node.get('selector','')):return 'action'
    if attrs.get('role')=='heading':return 'title'
    if tag=='label':return 'label'
    if tag in {'figcaption','small'}:return 'caption'
    return 'body'


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
    nodes=view.get('structure',view.get('nodes',[]));by={n['selector']:n for n in nodes}
    children={}
    for node in nodes:children.setdefault(node.get('parent'),[]).append(node)
    descendants=lambda root:[n for n in nodes if n['selector'].startswith(root['selector']+' > ')]
    roots={};assignments=[];unmapped=[]
    def add(node,kind):
        roots[node['selector']]={'construct':kind,'selector':node['selector'],'values':{},'media':{},'nodes':{},'root_node':node}
    # A card's media article may be a sibling of its metadata/link. Group their
    # common wrapper, rather than emitting independent image sections.
    for node in nodes:
        if construct_for(node)!='listing-card':continue
        root=node;parent=by.get(node.get('parent'));desc=descendants(node)
        if parent:
            peers=children.get(parent['selector'],[])
            if any(p['tag']=='a' and p.get('text','').strip() for p in peers) and any(n['tag']=='img' for n in desc):root=parent
        if any(root['selector'].startswith(key+' > ') for key in roots):continue
        add(root,'listing-card')
    # Generic repeated sibling cards need no site-specific class names.
    for parent,peers in children.items():
        candidates=[]
        for node in peers:
            if node['tag'] not in {'div','li','a'} or node['selector'] in roots:continue
            desc=descendants(node)
            titled=any(re.fullmatch('h[1-6]',d['tag']) or d['tag']=='p' and len(d.get('text',''))>3 or 'title' in d.get('attributes',{}).get('class','') for d in desc)
            if len(desc)<150 and re.search(r'[$€£]|\b[0-5]\.\d\b',node.get('text','')) and any(d['tag']=='img' for d in desc) and titled:candidates.append(node)
        if len(candidates)>=2:
            for node in candidates:
                if not any(node['selector'].startswith(key+' > ') or key.startswith(node['selector']+' > ') for key in roots):add(node,'listing-card')
    card_roots=list(roots)
    for node in nodes:
        key=node['selector'];tag=node['tag']
        if key in roots or any(key.startswith(c+' > ') for c in card_roots):continue
        kind=construct_for(node)
        if kind is None:continue
        desc=descendants(node)
        headings=[n for n in desc if re.fullmatch('h[1-6]',n['tag'])]
        if tag=='header' and not headings:kind='nav'
        elif tag=='section' and any(n['tag']=='h1' for n in headings):kind='hero'
        if kind=='content-section' and not headings and not node.get('directText','').strip():continue
        # Avoid structural wrapper sections whose only headings belong to nested sections.
        if kind=='content-section' and headings and all(any(h['selector'].startswith(d['selector']+' > ') for d in desc if d['tag']=='section') for h in headings):continue
        add(node,kind)
    # Editorial blocks are often divs rather than section landmarks. A heading
    # and its surrounding copy still establish a Vocabulary content section.
    for node in nodes:
        if not re.fullmatch('h[1-6]',node['tag']):continue
        ancestors=[key for key in roots if node['selector'].startswith(key+' > ')]
        owner_kind=roots[max(ancestors,key=len)]['construct'] if ancestors else None
        if owner_kind in {'listing-card','hero','nav','footer'}:continue
        if ancestors and node['tag'] in {'h1','h2'}:continue
        parent=by.get(node.get('parent'))
        if not parent or parent['tag']=='a':continue
        root=parent
        if not ancestors:
            current=parent
            while current and current['tag'] not in {'body','main'}:
                bg=current.get('normalized_colors',{}).get('background-color','')
                if bg and bg not in {'#00000000','transparent'}:root=current;break
                current=by.get(current.get('parent'))
        if root['selector'] not in roots:add(root,'content-section')
    if not roots:add(next((n for n in nodes if n['tag']=='body'),{'selector':'body','tag':'body'}),'content-section')
    def owner(node):
        matches=[key for key in roots if node['selector']==key or node['selector'].startswith(key+' > ')]
        return roots[max(matches,key=len)] if matches else None
    def use(item,slot,node,text):
        if not text:return
        if slot=='links':
            labels=item['values'].setdefault(slot,[])
            if text not in labels:labels.append(text)
        else:item['values'][slot]=(item['values'].get(slot,'')+' '+text).strip()
        item['nodes'].setdefault(slot,node)
        def chroma(n):
            rgba=color(n.get('normalized_colors',{}).get('color',n.get('styles',{}).get('color','')))
            return max(rgba[:3])-min(rgba[:3]) if rgba else 0
        if slot in {'action','links','price'} and chroma(node)>chroma(item['nodes'][slot]):item['nodes'][slot]=node
        link=node
        while link and link['tag']!='a':link=by.get(link.get('parent'))
        if link and link.get('attributes',{}).get('href'):
            try:href=public_url(urljoin(view.get('url',''),link['attributes']['href']))
            except ValueError:href=None
            if href:
                if slot=='links':item.setdefault('hrefs',{}).setdefault(slot,{})[text]=href
                else:item.setdefault('hrefs',{})[slot]=href
        spec=slot_map(vocabulary['constructs'][item['construct']])[slot]
        assignments.append({'selector':node['selector'],'construct':item['construct'],'slot':slot,'role':spec['role'],'emphasis':spec['emphasis']})
    proposals={p['selector']:p for p in suggestions}
    for node in nodes:
        item=owner(node)
        if item is None:continue
        if 'sr-only' in node.get('attributes',{}).get('class','').split():continue
        tag=node['tag'];slots=slot_map(vocabulary['constructs'][item['construct']]);text=node.get('directText','').strip()
        if tag=='img' and node.get('src'):
            if not node['src'].startswith(('http://','https://')):continue
            slot=next((s for s,d in slots.items() if d['kind']=='media'),None)
            image={'url':node['src'],'alt':node.get('attributes',{}).get('alt',''),'selector':node['selector']}
            if slot:
                # One representative image per card; carousel alternates remain in the artifact.
                if item['construct']!='listing-card' or not item['media'].get(slot):item['media'].setdefault(slot,[]).append(image);item['nodes'].setdefault(slot,node)
            elif item['construct']=='hero':item.setdefault('background_media',image)
            continue
        if tag=='svg':
            box=node.get('box')
            if item['construct']=='nav' and box and box[2]>32 and node.get('src') and 'logo' in slots and not item['media'].get('logo'):
                item['media']['logo']=[{'url':node['src'],'selector':node['selector'],'alt':node.get('attributes',{}).get('aria-label',''),'color':node.get('normalized_colors',{}).get('color')}]
                item['nodes']['logo']=node
            continue
        if not text:continue
        role=semantic_role(node);hint=' '.join(str(v) for v in node.get('attributes',{}).values()).lower()
        slot=None
        if item['construct']=='listing-card':
            if re.search(r'sav(?:e|ing)|booking direct|discount',text,re.I):slot='price'
            elif re.fullmatch(r'[★☆\s]*[0-5]\.\d(?:\s.*)?',text) or 'rating' in hint:slot='rating'
            elif re.search(r'[$€£]|\bbeds?\b|\bnights?\b',text,re.I):slot='location'
            elif 'title' not in item['values'] and (tag in {'p','h1','h2','h3','h4'} or role in {'title','subtitle'}):slot='title'
            elif role=='action':slot='action'
            elif text not in {'•','★','☆',item['values'].get('title')} and 'title' in item['values']:slot='location'
        else:
            if role in {'title','subtitle'} and 'title' in slots:slot='title'
            elif role=='action' and 'links' in slots:slot='links'
            elif role=='body' and 'body' in slots:slot='body'
            else:slot=next((s for s,d in slots.items() if d['role']==role),None)
        proposal=proposals.get(node['selector'])
        if proposal:
            if proposal['construct']!=item['construct']:
                add(node,proposal['construct']);item=roots[node['selector']]
            slot=proposal['slot']
        if slot:use(item,slot,node,text)
        else:unmapped.append(node['selector'])
    # Unsampled leaf text is recovered above. Keep only content-bearing roots and
    # card wrappers that intersect the captured viewport (not hidden carousel pages).
    ordered=[]
    for key,item in roots.items():
        root=item['root_node'];box=root.get('box')
        if not box:
            box=next((n.get('box') for n in descendants(root) if n.get('box')),None)
        edge=box[0]+box[2]/2 if box and item['construct']=='listing-card' else box[0] if box else 0
        if box and (edge>=view.get('width',float('inf')) or box[0]+box[2]<=0 or box[1]+box[3]<=0):continue
        item['box']=box
        if item['construct']=='listing-card' and not item['values'].get('title') and item['media']:
            image=next(iter(item['media'].values()))[0]
            title=re.sub(r'\s+(?:property\s+)?photo\s*\d+.*$','',image['alt'],flags=re.I)
            if title:item['values']['title']=title
        if item['values'] or item['media'] or item.get('background_media'):ordered.append(item)
    order={n['selector']:i for i,n in enumerate(nodes)};ordered.sort(key=lambda i:order.get(i['selector'],0))
    for item in ordered:
        parents=[p for p in ordered if item['selector'].startswith(p['selector']+' > ') and p['construct']!='listing-card']
        item['parent']=max(parents,key=lambda p:len(p['selector']))['selector'] if parents else None
    return {'instances':ordered,'assignments':assignments,'unmapped':unmapped}
