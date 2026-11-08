"""Sample HTML belongs to Vocabulary. A language may only select validated templates/assets."""
from html import escape
import re
from urllib.parse import urlsplit
from jinja2 import Environment, select_autoescape
from markupsafe import Markup
from ..vocabulary import slot_map
from ..language.variants import SLOT, Template
from ..language.resolver import resolve
from .styles import declaration

PAGE = '''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>{{ title }} · Sample collection</title><link rel="stylesheet" href="language.css"></head><body><span id="annotations" class="kd-annotation-target" aria-hidden="true"></span>{{ navigation }}{{ content }}{{ footer }}</body></html>
'''


def attributes(values):
    return ''.join(' ' + key + '="' + escape(str(value), quote=True) + '"' for key, value in values.items() if value is not None)


def element(tag, attrs, content=''):
    start = '<' + tag + attributes(attrs) + '>'
    return start if tag in {'img', 'input'} else start + content + '</' + tag + '>'


def captured_href(value):
    if not isinstance(value,str):return None
    try:
        parts=urlsplit(value)
        return value if parts.scheme in {'http','https'} and parts.hostname and parts.username is None and parts.password is None else None
    except ValueError:return None


class SampleRenderer:
    def __init__(self, document, vocabulary, samples):
        self.document, self.vocabulary, self.samples = document, vocabulary, samples
        self.context = vocabulary['context']
        self.sequence = 0

    def links(self):
        return ''.join(element('a', {'href':file}, escape(label)) for file, label in self.context['pages'].items())

    def slot(self, construct, definition, state, values, missing_image, media=None, treatment=None,hrefs=None):
        name, role, emphasis = definition['id'], definition['role'], definition['emphasis']
        attrs = {'data-kd-slot':construct + '.' + name, 'data-kd-role':role, 'data-kd-emphasis':emphasis}
        if treatment is not None:attrs['style']=declaration(resolve(treatment,self.vocabulary,construct+'.'+name)['properties'])
        binding = self.document.get('components', {}).get(construct, {}).get('assets', {}).get(name)
        if binding:
            attrs['data-kd-asset'] = binding
        copy = str(values.get(name, self.context['copy'][role]))
        tag = definition['element']
        if definition['kind'] == 'media':
            image = None
            if media and name in media:
                image = ''.join(element('img', {'src':item['src'],'alt':item.get('alt',''),'loading':'eager'}) for item in media[name])
            elif binding and not missing_image:
                asset, variant = binding.split(':')
                detail = self.document['assets'][asset]['variants'][variant]
                image = element('img', {'src':f'assets/{asset}-{variant}.{detail["format"]}', 'alt':self.context['copy']['media'] if definition.get('asset_kind') != 'logo' else 'Home', 'loading':'lazy'})
            if not image:
                image = element('span', {'class':'kd-placeholder', 'role':'img', 'aria-label':self.context['image-missing']}, escape(self.context['image-missing']))
            if tag == 'a':
                attrs['href'] = definition['href']
                attrs['aria-label'] = 'Home'
                return element('a', attrs, image)
            count = self.context.get('gallery-images',1) if construct == 'gallery' and not media else 1
            return element('span', attrs, image * count)
        if name == 'links':
            if name in values:
                labels=values[name] if isinstance(values[name],list) else [values[name]]
                def link(label):
                    href=captured_href(hrefs.get(name,{}).get(label)) if hrefs is not None else 'index.html'
                    return element('a' if href else 'span',{'href':href},escape(str(label)))
                return element(tag,attrs,''.join(link(label) for label in labels))
            return element(tag, attrs, self.links())
        if name == 'options':
            controls = ''.join(element('label', {}, element('input', {'type':'checkbox','name':'filter','value':str(index),'disabled':'' if state=='disabled' else None}) + escape(label)) for index,label in enumerate(self.context['filter-options']))
            return element(tag, attrs, controls)
        if tag in {'input', 'textarea'}:
            control_id = f'field-{self.sequence}-{name}'
            control = {'id':control_id, 'name':name, 'disabled':'' if state=='disabled' else None,
                       'aria-invalid':'true' if state=='error' else None}
            if tag == 'input':
                control['type'] = definition.get('field','text')
                control['placeholder'] = self.context['field-placeholder']
            content = element(tag, control)
            # The label owns annotation/treatment; native control inherits its type styles.
            return element('label', {**attrs, 'for':control_id}, escape(definition['label']) + content)
        if tag == 'a':
            attrs['href'] = captured_href(hrefs.get(name)) if hrefs is not None else definition['href']
        if tag == 'button':
            attrs['type'] = 'submit'
            if state == 'disabled':
                attrs['disabled'] = ''
            if name not in values:
                copy = self.context['search-submit'] if construct == 'search-bar' else self.context['form-submit']
        if state == 'selected' and definition['kind'] == 'control':
            attrs['aria-selected'] = 'true'
        content=escape(copy)
        if tag!='a' and hrefs is not None and (href:=captured_href(hrefs.get(name))):content=element('a',{'href':href},content)
        return element(tag, attrs, content)

    def construct(self, construct, state=None, values=None, missing_image=False, media=None, captured=False, treatment=None, children='',background=None,box=None,geometry=None,hrefs=None):
        self.sequence += 1
        contract = self.vocabulary['constructs'][construct]
        copy = dict(values or {}) if captured else {**self.context.get('construct-copy', {}).get(construct, {}), **(values or {})}
        slots = {name:self.slot(construct, definition, state, copy, missing_image, media,treatment,(hrefs or {}) if captured else None) if not captured or name in copy or name in (media or {}) else ''
                 for name, definition in slot_map(contract).items()}
        attrs = {'data-kd-construct':construct, 'data-kd-state':state,
                 'aria-label':contract.get('accessible-name')}
        if captured:attrs['data-kd-captured']='true'
        if treatment is not None:attrs['style']=declaration(resolve(treatment,self.vocabulary,construct)['properties'])
        if geometry:
            if geometry.get('overlay'):layout='position:absolute;inset:0 0 auto;z-index:2'
            else:layout=';'.join(f'{prop}:{max(0,float(geometry[key])):g}px' for key,prop in [('inset','margin-inline'),('gap','margin-top'),('height','min-height')] if key in geometry)
            attrs['style']=attrs.get('style','')+';'+layout
        backdrop=''
        if background:
            attrs['data-kd-backdrop']='true'
            if box:attrs['style']=attrs.get('style','')+f';min-height:{max(0,float(box[3])):g}px'
            backdrop=element('img',{'data-kd-background':'','src':background['src'],'alt':background.get('alt','')})
        if state == 'loading':
            attrs['aria-busy'] = 'true'
        if contract.get('focusable'):
            attrs['tabindex'] = '0'
        if contract['root'] == 'form':
            attrs.update(action=contract['action'], method='get')
        component = self.document.get('components', {}).get(construct, {})
        variant = component.get('variant', 'default')
        if variant == 'default':
            return element(contract['root'], attrs, backdrop+''.join(slots.values())+children)
        template = self.document['layout']['variants'][construct][variant]['template']
        Template(template, contract)
        # This is the restricted parser's placeholder syntax, never executable Jinja.
        rendered = SLOT.sub(lambda match:slots[match[1]], template)
        rendered=re.sub(r'<' + contract['root'] + r'\s*>', lambda match:'<' + contract['root'] + attributes(attrs) + '>'+backdrop, rendered, count=1, flags=re.IGNORECASE)
        return re.sub(r'</'+contract['root']+r'\s*>\s*$',lambda match:children+match[0],rendered,flags=re.IGNORECASE)

    def reconstruction(self, page):
        """Private captured compositions use the same semantic constructs and styles."""
        self.sequence=0
        def render(item):
            children=''.join(render(child) for child in item.get('children',[]))
            if children:
                columns=max(1,min(12,int(item.get('columns',1))))
                children=element('div',{'class':'kd-captured-children','style':f'--kd-columns:{columns}'},children)
            return self.construct(item['construct'],state=item.get('state'),values=item.get('values'),media=item.get('media'),captured=page.get('captured',False),treatment=item.get('resolved_context'),children=children,background=item.get('background'),box=item.get('box'),geometry=item.get('geometry'),hrefs=item.get('hrefs'))
        content=''.join(render(item) for item in page['instances'])
        env=Environment(autoescape=select_autoescape(default_for_string=True))
        return env.from_string(PAGE).render(title=page.get('title','Captured page'),navigation='',content=Markup(content),footer='').encode('utf-8')

    def stress(self):
        sections = []
        for sample in self.samples['stress']:
            label = element('h2', {'class':'kd-context-heading'}, escape(sample['name']))
            if 'items' in sample:
                content = ''.join(self.construct('listing-card') for _ in range(sample['items']))
                if not sample['items']:
                    content = self.construct('empty-state')
                content = element('div', {'class':'kd-grid'}, content)
            else:
                values = {sample['slot']:self.context[sample['context']]} if 'slot' in sample else {}
                content = self.construct(sample['construct'], values=values, missing_image=sample.get('missing-image',False))
            sections.append(element('section', {'data-kd-stress':sample['name']}, label + content))
        return ''.join(sections)

    def page(self, filename):
        self.sequence = 0
        navigation = self.construct('nav')
        if filename == 'states.html':
            content = element('h1', {'class':'kd-context-heading'}, escape(self.context['state-gallery-title']))
            for construct in self.samples['pages'][filename]:
                for state in self.vocabulary['constructs'][construct]['states']:
                    heading = element('h2', {}, escape(construct + ' · ' + state))
                    content += element('section', {'class':'kd-state'}, heading + self.construct(construct,state))
            content += self.stress()
        else:
            content = ''
            for construct in self.samples['pages'][filename]:
                if construct == 'listing-card':
                    content += element('div', {'class':'kd-grid'}, ''.join(self.construct(construct) for _ in range(self.samples['collection-size'])))
                else:
                    content += self.construct(construct)
            if 'page-shell' in self.samples['pages'][filename]:
                # Compose remaining page constructs inside the vocabulary's main shell.
                shell_end = content.index('</main>')
                content = content[:shell_end] + content[shell_end + len('</main>'):] + '</main>'
            else:
                content = element('main', {}, content)
        if filename == 'listing.html':
            texts = [self.context['construct-copy']['listing-card']['title']] + [self.context[s['context']] for s in self.samples['stress'] if s.get('construct') == 'listing-card' and s.get('slot') == 'title']
            content += element('section', {'class':'kd-full-content','aria-label':self.context['full-content-label']}, ''.join(element('p',{},escape(text)) for text in texts))
        footer = self.construct('footer')
        env = Environment(autoescape=select_autoescape(default_for_string=True))
        return env.from_string(PAGE).render(title=self.context['pages'][filename], navigation=Markup(navigation), content=Markup(content), footer=Markup(footer)).encode('utf-8')
