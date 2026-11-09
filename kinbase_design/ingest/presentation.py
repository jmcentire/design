"""Content-independent signals for captured text and repeated content groups."""
import re
from ..checks.math import color,luminance
from .quantize import px


def literal_node(node):
    return node.get('preformatted',False) or node['tag'] in {'pre','code','kbd','samp'} or bool(re.search(r'(?:^| > )(?:pre|code|kbd|samp)(?=:| > |$)',node['selector']))


def visible_text(node):
    if re.search(r'(?:^| > )svg(?=:| > )',node['selector']):return ''
    if node['tag'] in {'input','select','textarea'}:return ''
    if 'sr-only' in node.get('attributes',{}).get('class','').split():return ''
    return node.get('directText','').strip()


def foreground(node):
    return color(node.get('normalized_colors',{}).get('color',node.get('styles',{}).get('color','')))


def chroma(node):
    rgba=foreground(node)
    return max(rgba[:3])-min(rgba[:3]) if rgba else 0


def size(node):return px(node.get('styles',{}).get('font-size','')) or 16


def weight(node):
    value=node.get('styles',{}).get('font-weight','400')
    try:return float(value)
    except (ValueError,TypeError):return 700 if value=='bold' else 400


def heading(node,by):
    current=node
    while current:
        if re.fullmatch(r'h[1-6]',current['tag']) or current.get('attributes',{}).get('role')=='heading':return current['selector']
        current=by.get(current.get('parent'))
    return None


def repeated_candidate(node,desc):
    if node['tag'] not in {'div','li','a','article','section','p','blockquote'} or len(desc)>=150:return False
    text=[n for n in [node,*desc] if visible_text(n)]
    media=any(n['tag'] in {'img','svg'} and n.get('src') for n in desc)
    titled=any(re.fullmatch('h[1-6]',n['tag']) or n.get('attributes',{}).get('role')=='heading' for n in desc)
    text_blocks=sum(n['tag'] in {'p','small','figcaption','dt','dd'} and bool(visible_text(n)) for n in desc)
    hierarchy=len({(size(n),weight(n)) for n in text})>1
    # A bordered prose item need not have a heading. Pure action links, media
    # carousel frames and their SVG accessible names are not cards.
    style=node.get('styles',{})
    bordered=(px(style.get('border-top-width')) or 0)>0 and style.get('border-top-style',style.get('border-style','solid')) not in {'none','hidden'}
    return bool(text) and (media or bordered and (text_blocks or node['tag']!='a' and visible_text(node)) or len(text)>=2 and (titled or hierarchy or text_blocks>=2))


def clipped_media(node,by):
    box=node.get('box')
    if not box:return False
    ancestor=by.get(node.get('parent'))
    while ancestor:
        bounds=ancestor.get('box');overflow=ancestor.get('styles',{}).get('overflow','visible')
        if bounds and overflow in {'hidden','clip','auto','scroll'}:
            if box[0]>=bounds[0]+bounds[2] or box[0]+box[2]<=bounds[0] or box[1]>=bounds[1]+bounds[3] or box[1]+box[3]<=bounds[1]:return True
        ancestor=by.get(ancestor.get('parent'))
    return False


def card_slots(nodes,by):
    """Assign roles using typography, relative position and control structure only."""
    text=[n for n in nodes if visible_text(n)]
    if not text:return {}
    order={n['selector']:i for i,n in enumerate(nodes)}
    def control(node):
        current=node
        while current and current in nodes:
            if current['tag']=='button':return True
            if current['tag']=='a':
                desc=[n for n in nodes if n['selector'].startswith(current['selector']+' > ')]
                # A whole-card link doesn't turn its title/body into action copy.
                if any(n['tag']=='img' or re.fullmatch('h[1-6]',n['tag']) for n in desc):return False
                blocks={n.get('parent') for n in desc if visible_text(n)}
                return len(blocks)<=1
            current=by.get(current.get('parent'))
        return False
    substantive=[n for n in text if not control(n)] or text
    headings=[n for n in substantive if heading(n,by)]
    title=max(headings or substantive,key=lambda n:(size(n),weight(n),n['tag'] in {'p','h1','h2','h3','h4','h5','h6'},-chroma(n),-order[n['selector']]))
    # Typography can identify body/meta relationships, but cannot turn a source
    # paragraph into an invented semantic heading in fidelity reconstruction.
    title_group=heading(title,by) if headings else None
    title_index=order[title['selector']];result={};title_fg=foreground(title)
    for node in text:
        key=node['selector'];copy=visible_text(node)
        if title_group and (key==title_group or key.startswith(title_group+' > ')):slot='title'
        elif control(node):slot='action'
        elif chroma(node)>.12 and len(copy)<=120:slot='highlight'
        else:
            fg=foreground(node)
            muted=bool(fg and title_fg and luminance(fg)>luminance(title_fg)+.04)
            small=size(node)<size(title)-.5 or node['tag'] in {'small','figcaption'}
            short=len(copy)<=100
            if order[key]<title_index and short:slot='eyebrow'
            elif short and (small or muted or weight(node)<weight(title)):slot='meta'
            elif short and weight(node)>weight(title):slot='highlight'
            else:slot='body'
        result[key]=slot
    # Inline emphasis and links stay in their prose block. Their own captured
    # typography is retained by the fragment treatment, without moving the text.
    for node in text:
        parent=by.get(node.get('parent'))
        while parent and parent in nodes:
            if parent['tag'] in {'p','li','blockquote','figcaption'} and parent['selector'] in result:
                result[node['selector']]=result[parent['selector']];break
            parent=by.get(parent.get('parent'))
    return result
