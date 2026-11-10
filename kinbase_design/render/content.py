"""Escaped rich slot values for content compositions; no language decisions."""
from html import escape


def inline(value):
    from .html import element
    if isinstance(value, str):return escape(value)
    chunks = []
    for run in value:
        if isinstance(run,str):chunks.append(escape(run));continue
        text = escape(run['text'])
        if run.get('em'):text = element('em',{},text)
        if run.get('strong'):text = element('strong',{},text)
        if 'href' in run:text = element('a',{'href':run['href']},text)
        chunks.append(text)
    return ''.join(chunks)


def media(value, attrs=None):
    from .html import element
    image = element('img', {'src':value['src'],'alt':value['alt'],'loading':'eager'})
    notes = [escape(value[key]) for key in ('caption','credit') if value.get(key)]
    if notes:image += element('figcaption',{},' · '.join(notes))
    return element('figure',attrs or {},image)


def links(values, listed=False):
    from .html import element
    chunks = [element('a',{'href':item['href'],'data-kd-part':'link' if listed else None},escape(item['text'])) for item in values]
    if listed:return element('ul',{},''.join(element('li',{},chunk) for chunk in chunks))
    return ''.join(chunks)


def prose(values):
    from .html import element
    chunks = []
    for entry in values:
        if 'paragraph' in entry:chunks.append(element('p',{},inline(entry['paragraph'])))
        elif 'list' in entry:
            value = entry['list']
            chunks.append(element('ol' if value.get('ordered') else 'ul',{},''.join(element('li',{},inline(i)) for i in value['items'])))
        elif 'media' in entry:chunks.append(media(entry['media']))
        else:
            value = entry['quote']
            text = element('p',{},inline(value['text']))
            if value.get('cite'):text += element('cite',{},escape(value['cite']))
            chunks.append(element('blockquote',{},text))
    return ''.join(chunks)


def slot(definition, attrs, value, heading=None):
    from .html import element
    tag = definition.get('content-element', definition['element'])
    if heading is not None:tag = 'h' + str(heading)
    kind, data = value['kind'], value['value']
    if kind == 'media':return media(data,attrs)
    if kind == 'inline':text = inline(data)
    elif kind == 'prose':text = prose(data)
    elif kind == 'links':text = links(data, listed=True)
    elif kind == 'actions':
        if tag=='a':return ''.join(element('a',{**attrs,'href':item['href']},escape(item['text'])) for item in data)
        text = links(data)
    elif kind == 'link':
        attrs['href'] = data['href'];text = escape(data['text'])
    elif kind == 'brand':
        attrs['href'] = 'index.html'
        text = (media(data['logo']) if data.get('logo') else '') + element('span',{},escape(data['name']))
    elif kind == 'facts':text = ''.join(element('div',{'data-kd-part':definition.get('fact-part')},element('dt',{},escape(i['label']))+element('dd',{},escape(i['value']))) for i in data)
    elif kind == 'notices':text = ''.join(element('p',{},escape(i)) for i in data)
    elif kind == 'children':text = data  # Only renderer-generated construct bytes, never input HTML.
    else:raise ValueError('Unknown content slot kind: ' + kind)
    return element(tag,attrs,text)
