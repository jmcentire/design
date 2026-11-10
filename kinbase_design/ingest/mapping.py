"""Deterministic semantic grouping over captured DOM content and measured nodes."""
import re
from urllib.parse import urljoin
from ..artifacts.capture import public_url
from ..vocabulary import slot_map
from .arrangement import groups
from .flow import long_form,split_flow,block,inline_role,level,structure
from .presentation import visible_text,chroma,repeated_candidate,card_slots,clipped_media,heading


def semantic_role(node):
    tag=node['tag'];attrs=node.get('attributes',{})
    if node.get('preformatted'):return 'body'
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
    tag=node['tag'];attrs=node.get('attributes',{})
    if tag=='nav' or attrs.get('role')=='navigation':return 'nav'
    if tag=='footer':return 'footer'
    if tag=='form':return 'search-bar' if attrs.get('role')=='search' else 'form'
    if tag=='article':return 'card'
    if tag=='header':return 'hero'
    if tag=='section':return 'content-section'
    return None


def map_view(view,vocabulary,suggestions=()):
    nodes=view.get('structure',view.get('nodes',[]));by={n['selector']:n for n in nodes}
    order={n['selector']:i for i,n in enumerate(nodes)}
    children={}
    for node in nodes:children.setdefault(node.get('parent'),[]).append(node)
    descendants=lambda root:[n for n in nodes if n['selector'].startswith(root['selector']+' > ')]
    roots={};assignments=[];unmapped=[]
    def add(node,kind,group=None):
        roots[node['selector']]={'construct':kind,'selector':node['selector'],'values':{},'media':{},'nodes':{},'root_node':node}
        if group:roots[node['selector']]['group']=group
    def landmark_content(node):
        parent=by.get(node.get('parent'))
        while parent:
            # Definition-list wrappers describe one fact, not a repeated card.
            # Keep them inside their owning item before selecting leaf groups.
            if parent['tag'] in {'nav','footer','form','dl'} or parent.get('attributes',{}).get('role') in {'navigation','contentinfo','search'}:return True
            parent=by.get(parent.get('parent'))
        return False
    repeated=[]
    for parent,peers in children.items():
        run=[];pattern=None
        def finish():
            if len(run)>=2:repeated.append((parent,list(run)))
        for node in peers:
            desc=descendants(node)
            eligible=not landmark_content(node) and not long_form(node,desc) and repeated_candidate(node,desc)
            # Comparable adjacent items form a group. A later callout elsewhere
            # in the same article is not a sibling card merely sharing its tag.
            shape=(node['tag'],tuple(n['tag'] for n in desc if n['tag'] in {'img','p','dl','ul','ol','h1','h2','h3','h4','h5','h6'})) if eligible else None
            if shape is None or shape!=pattern:finish();run=[]
            if eligible:run.append(node)
            pattern=shape
        finish()
    # Prefer complete leaf groups over repeated rows/grids that contain them.
    # Media-only carousel frames do not meet the text/grouping criteria.
    for parent,peers in sorted(repeated,key=lambda pair:len(pair[0] or ''),reverse=True):
        for node in peers:
            if not any(node['selector']==key or node['selector'].startswith(key+' > ') or key.startswith(node['selector']+' > ') for key in roots):
                add(node,'card',parent)
                roots[node['selector']]['group_members']=[peer['selector'] for peer in peers]
    for node in nodes:
        if construct_for(node)!='card' or landmark_content(node) or long_form(node,descendants(node)):continue
        if any(node['selector']==key or node['selector'].startswith(key+' > ') or key.startswith(node['selector']+' > ') for key in roots):continue
        root=node;parent=by.get(node.get('parent'));desc=descendants(node)
        if sum(n['tag']=='article' for n in desc)>1:continue
        if parent:
            peers=children.get(parent['selector'],[])
            if any(p['tag']=='a' and p.get('text','').strip() for p in peers) and any(n['tag']=='img' for n in desc):root=parent
        if not any(root['selector']==key or root['selector'].startswith(key+' > ') or key.startswith(root['selector']+' > ') for key in roots):add(root,'card')
    card_roots=list(roots)
    for node in nodes:
        key=node['selector'];tag=node['tag']
        if key in roots or any(key.startswith(c+' > ') for c in card_roots):continue
        kind='content-section' if long_form(node,descendants(node)) else construct_for(node)
        if kind is None or kind=='card':continue
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
        if owner_kind in {'card','hero','nav','footer'}:continue
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
    assigned={}
    def owner(node):
        if node['selector'] in assigned:return roots[assigned[node['selector']]]
        matches=[key for key in roots if node['selector']==key or node['selector'].startswith(key+' > ')]
        return roots[max(matches,key=len)] if matches else None
    assigned,flow_parents=split_flow(nodes,roots,owner)
    def definition(node):
        field=None;current=node
        while current:
            if current['tag'] in {'dt','dd'} and field is None:field=current
            if current['tag']=='dl':
                return {'list':current['selector'],'field':field['selector'],'tag':field['tag']} if field else None
            current=by.get(current.get('parent'))
        return None
    def href_for(node):
        while node and node['tag']!='a':node=by.get(node.get('parent'))
        if node and node.get('attributes',{}).get('href'):
            try:return public_url(urljoin(view.get('url',''),node['attributes']['href']))
            except ValueError:pass
        return None
    def use(item,slot,node,text):
        if not text:return
        if slot=='links':
            labels=item['values'].setdefault(slot,[])
            if text not in labels:labels.append(text)
        else:item['values'][slot]=(item['values'].get(slot,'')+' '+text).strip()
        text_block=by.get(block(node,by),node)
        representative=text_block if slot in {'body','title','meta'} and text_block['tag'] in {'p','pre','blockquote','h1','h2','h3','h4','h5','h6'} else node
        structured=structure(node,by) if item.get('flow') else []
        if structured:representative=by[structured[0]['selector']]
        item['nodes'].setdefault(slot,representative)
        if slot in {'highlight','eyebrow','action'} and chroma(node)>chroma(item['nodes'][slot]):item['nodes'][slot]=node
        if slot_map(vocabulary['constructs'][item['construct']])[slot]['kind']=='action' and slot!='links':
            control=node
            while control and control['tag'] not in {'a','button'}:control=by.get(control.get('parent'))
            if control:
                actions=item.setdefault('action_items',{}).setdefault(slot,[])
                action=next((a for a in actions if a['selector']==control['selector']),None)
                if action is None:
                    action={'selector':control['selector'],'text':'','href':href_for(control),'element':control['tag']};actions.append(action)
                action.setdefault('segments',[]).extend(node.get('text_segments') or [{'text':text,'order':order[node['selector']]}])
        if href:=href_for(node):
            if slot=='links':item.setdefault('hrefs',{}).setdefault(slot,{})[text]=href
            else:item.setdefault('hrefs',{})[slot]=href
        if slot!='links':
            segments=node.get('text_segments') or [{'text':text,'order':order[node['selector']]}]
            for segment in segments:
                fragment={**segment,'block':block(node,by),'href':href_for(node),'node':node,'preformatted':node.get('preformatted',False)}
                if structured:fragment['structure']=structured
                if item['construct']=='card' and (field:=definition(node)):fragment['definition']=field
                item.setdefault('fragments',{}).setdefault(slot,[]).append(fragment)
        spec=slot_map(vocabulary['constructs'][item['construct']])[slot]
        if re.fullmatch('h[1-6]',spec.get('element','')):
            source_heading=heading(node,by)
            if source_heading:item.setdefault('heading_levels',{})[slot]=level(by[source_heading])
        assignments.append({'selector':node['selector'],'construct':item['construct'],'slot':slot,'role':spec['role'],'emphasis':spec['emphasis']})
    owned={key:[] for key,item in roots.items() if item['construct']=='card'}
    for node in nodes:
        item=owner(node)
        if item and item['selector'] in owned:owned[item['selector']].append(node)
    roles={key:card_slots(group,by) for key,group in owned.items()}
    proposals={p['selector']:p for p in suggestions}
    for node in nodes:
        item=owner(node)
        if item is None:continue
        # SVG title/desc are accessible metadata, not visible HTML copy. The SVG
        # itself is retained as an image for an icon action or logo below.
        if re.search(r'(?:^| > )svg(?=:| > )',node['selector']) and node['tag']!='svg':continue
        if 'sr-only' in node.get('attributes',{}).get('class','').split():continue
        tag=node['tag'];slots=slot_map(vocabulary['constructs'][item['construct']]);text=visible_text(node)
        if (tag=='img' or tag=='svg' and item['construct'] not in {'nav'} and not any(n['tag'] in {'a','button'} and node['selector'].startswith(n['selector']+' > ') for n in nodes)) and node.get('src'):
            if not node['src'].startswith(('http://','https://','inline:')):continue
            if clipped_media(node,by):continue
            slot=next((s for s,d in slots.items() if d['kind']=='media'),None)
            image={'url':node['src'],'alt':node.get('attributes',{}).get('alt',''),'selector':node['selector']}
            if node.get('box') and node['box'][3]>0:image['aspect_ratio']=node['box'][2]/node['box'][3]
            if slot:
                # Keep each visible source image once; offscreen carousel frames remain in the capture.
                box=node.get('box');root_box=item['root_node'].get('box')
                if box and root_box and (box[0]>=root_box[0]+root_box[2] or box[0]+box[2]<=root_box[0]):continue
                if item['construct']=='card' and item['media'].get(slot) and not box:
                    unmapped.append(node['selector']);continue  # No evidence this alternate image was visible.
                if image['url'] not in {i['url'] for i in item['media'].get(slot,[])}:item['media'].setdefault(slot,[]).append(image);item['nodes'].setdefault(slot,node)
            elif item['construct']=='hero':item.setdefault('background_media',image)
            continue
        if tag=='svg':
            box=node.get('box')
            if item['construct']=='nav' and box and box[2]>32 and node.get('src') and 'logo' in slots and not item['media'].get('logo'):
                item['media']['logo']=[{'url':node['src'],'selector':node['selector'],'alt':node.get('attributes',{}).get('aria-label',''),'color':node.get('normalized_colors',{}).get('color')}]
                item['nodes']['logo']=node
            elif 'action' in slots and node.get('src'):
                control=by.get(node.get('parent'))
                while control and control['tag'] not in {'a','button'}:control=by.get(control.get('parent'))
                if control and owner(control) is item:
                    label=control.get('attributes',{}).get('aria-label') or node.get('attributes',{}).get('aria-label')
                    if not label:label=next((n.get('text','') for n in descendants(node) if n['tag']=='title'),'')
                    if label:
                        item.setdefault('accessible_names',{})['action']=label
                        item.setdefault('action_icons',{})['action']={'url':node['src'],'selector':node['selector'],'alt':'','color':node.get('normalized_colors',{}).get('color'),'box':box,'element':control['tag']}
                        item['nodes'].setdefault('action',control)
                        if href:=href_for(control):item.setdefault('hrefs',{})['action']=href
            continue
        if not text:continue
        control=node
        while control and control['tag'] not in {'a','button','p','li','pre'}:control=by.get(control.get('parent'))
        style=control.get('styles',{}) if control else {}
        explicit_action=control and (control['tag']=='button' or control['tag']=='a' and (style.get('display') in {'inline-block','inline-flex'} or control.get('attributes',{}).get('role')=='button'))
        if control and control['tag']=='a' and not explicit_action:
            parent=by.get(control.get('parent'))
            if parent and parent['tag'] in {'p','div'}:
                contents=[parent,*descendants(parent)]
                controls=[n for n in contents if n['tag'] in {'a','button'}]
                # Flex/grid can blockify a link's computed display. A group
                # consisting solely of controls still supplies action evidence.
                explicit_action=bool(controls) and all(any(n['selector']==a['selector'] or n['selector'].startswith(a['selector']+' > ') for a in controls)
                    for n in contents if visible_text(n))
        role='action' if explicit_action else inline_role(node,by) or semantic_role(node)
        slot=None
        if item['construct']=='card':
            slot='meta' if definition(node) and 'meta' in slots else roles[item['selector']].get(node['selector'])
        else:
            if role in {'title','subtitle'} and 'title' in slots:slot='title'
            elif role=='action' and 'links' in slots:slot='links'
            elif (role in {'body','caption'} or tag in {'li','dt','dd','th','td','caption'}) and 'body' in slots:slot='body'
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
    # Whitespace-only parents can separate inline child spans. Keep those source
    # separators when a unique slot owns their prose/heading block.
    for node in nodes:
        if visible_text(node):continue
        item=owner(node)
        if not item:continue
        parent_block=block(node,by)
        matches=[fragments for fragments in item.get('fragments',{}).values() if any(f['block']==parent_block for f in fragments)]
        if len(matches)==1:
            for segment in node.get('text_segments',[]):
                if segment['text'].isspace():
                    fragment={**segment,'block':parent_block,'href':None,'node':node}
                    if item.get('flow'):
                        if grouped:=structure(node,by):fragment['structure']=grouped
                    if item['construct']=='card' and (field:=definition(node)):fragment['definition']=field
                    matches[0].append(fragment)
    ordered=[]
    for key,item in roots.items():
        root=item['root_node'];box=root.get('box')
        if not box and not item.get('flow'):
            box=next((n.get('box') for n in descendants(root) if n.get('box')),None)
        edge=box[0]+box[2]/2 if box and item['construct']=='card' else box[0] if box else 0
        if box and (edge>=view.get('width',float('inf')) or box[0]+box[2]<=0 or box[1]+box[3]<=0):continue
        item['box']=box
        if item['values'] or item['media'] or item.get('background_media') or key in flow_parents.values():ordered.append(item)
        for slot,fragments in item.get('fragments',{}).items():
            fragments.sort(key=lambda fragment:fragment['order'])
            # Values retain the ordinary string API; fragments retain inline DOM order.
            if any(f.get('node',{}).get('text_segments') for f in fragments):
                parts=[];prior=None
                for f in fragments:
                    if prior is not None and prior!=f['block']:parts.append(' ')
                    parts.append(f['text']);prior=f['block']
                item['values'][slot]=' '.join(''.join(parts).split())
    for item in ordered:
        for actions in item.get('action_items',{}).values():
            for action in actions:action['text']=''.join(s['text'] for s in sorted(action.pop('segments',[]),key=lambda s:s['order']))
    ordered.sort(key=lambda i:order.get(i['selector'],0))
    available={p['selector'] for p in ordered}
    for item in ordered:
        parents=[p for p in ordered if item['selector'].startswith(p['selector']+' > ') and p['construct']!='card']
        item['parent']=flow_parents.get(item['selector']) or (max(parents,key=lambda p:len(p['selector']))['selector'] if parents else None)
        while item['parent'] and item['parent'] not in available:item['parent']=flow_parents.get(item['parent'])
    return {'instances':ordered,'groups':groups(ordered,by),'assignments':assignments,'unmapped':unmapped}
