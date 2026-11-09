"""Pure interpretation of browser observations, with source-backed findings."""
from ..config import (CHECK_NON_TEXT_CONTRAST, CHECK_TARGET_SIZE, CHECK_PIXEL_TOLERANCE)
from ..findings import Finding, location
from ..language.resolver import resolve, property_pointer
from ..language.tokens import Tokens, ALIAS, number_text
from ..language.behaviors import matching, property_exception
from ..language.properties import CONTROL_BOX_PROPERTIES, IMAGE_PROPERTIES
from .math import color, contrast, effective_background, text_threshold, spacing_exception, css_equal
from .grouping import observation_context


def breakpoint_at(document, width):
    tokens = Tokens(document['style'])
    eligible = [(tokens.breakpoint(p.removeprefix('breakpoint.')),p.removeprefix('breakpoint.')) for p in tokens.nodes if p.startswith('breakpoint.')]
    return max((item for item in eligible if item[0]<=width),default=(0,None))[1]


class Evaluation:
    def __init__(self, document, vocabulary):
        self.document, self.vocabulary = document, vocabulary
        self.findings = []
        self.covered = set()
        self.context = None

    def add(self, rule, page, width, target='page', *, type='violation', criterion=None,
            measured=None, threshold=None, expected='', message='', exception=None, pointer=None, context=None):
        if pointer is None:
            construct = target.split('.')[0]
            pointer = '/components/' + construct if construct in self.vocabulary['constructs'] else ''
        pointer, observed = location(self.document,pointer)
        finding = Finding(type,rule,f'languages/{self.document["id"]}/working.json',pointer,
                          observed,expected,message or expected).to_dict()
        finding.update(page=page,width=width,target=target,criterion=criterion or rule,measured=measured,
                       threshold=threshold,exception=exception,screenshot=page.removesuffix('.html')+f'@{width}.png')
        finding['_context'] = context if context is not None else self.context
        if exception and exception.startswith('/behaviors/'):
            self.covered.add(exception)
        self.findings.append(finding)
        return finding

    def snapshot(self, page, width, snapshot, full_text):
        from .composition import evaluate
        if self.vocabulary.get('composition_rules'):
            evaluate(self,page,width,snapshot.get('composition',{}))
        for item in snapshot.get('preservation',[]):
            self.add(item['kind'],page,width,item['target'],measured=item['text'],
                     expected='content text, media and controls remain visible in accessible reading order')
        bp = breakpoint_at(self.document,width)
        tokens = Tokens(self.document['style'])
        for node in snapshot['nodes']:
            self.context = observation_context(node)
            target = node['target']
            if not node['visible']:
                if node['image'] or node.get('backgroundAsset'):
                    self.add('asset-load',page,width,target,measured={'decoded':node['decoded'],'box':node['box']},threshold='decoded and visible',expected='bound image has a visible box')
                continue
            if node['slot'] or node.get('part'):
                scope=node['slot'] or node['part']
                if node.get('heading') and node['slot']:scope+='.h'+str(node['heading'])
                props = resolve(self.document,self.vocabulary,scope,node['state'],bp)['properties']
                for prop, treatment in props.items():
                    observations = node.get('controlStyles') if prop in CONTROL_BOX_PROPERTIES and node.get('controlStyles') is not None else [node]
                    if prop in IMAGE_PROPERTIES and node.get('imageStyles') is not None:
                        observations = node['imageStyles']
                        if not observations:continue  # A missing-media placeholder has no image treatment.
                    for observation in observations or [{'css':{},'fontSize':node['fontSize']}]:
                        actual = observation['css'].get(prop,'')
                        equal = css_equal(prop,treatment['value'],actual,observation['fontSize'],snapshot['rootSize'],blockified=observation.get('blockified',False))
                        if not equal:
                            self.add('role-conformance',page,width,target,measured={'property':prop,'value':actual},threshold=treatment['value'],
                                     type='needs-review' if equal is None else 'violation',
                                     expected=f'{prop} = {treatment["value"]}',message=f'{prop}: computed {actual}; resolved {treatment["value"]}',
                                     exception=property_exception(self.document,target,prop),
                                     pointer=property_pointer(self.document,self.vocabulary,prop,treatment))
                family = props.get('font-family')
                if family and node['text'].strip():
                    raw_path = property_pointer(self.document,self.vocabulary,'font-family',family)
                    _,raw = location(self.document,raw_path)
                    asset = tokens.font_asset(ALIAS.fullmatch(raw)[1])
                    if asset:
                        first = family['value'].split(',')[0].strip().strip('"')
                        weight = number_text(props.get('font-weight',{}).get('value',400))
                        style = props.get('font-style',{}).get('value','normal')
                        loaded = any(f['family'].strip('"')==first and f['status']=='loaded' and f['weight']==weight and f['style']==style for f in snapshot['fonts'])
                        if not loaded or not node['fontReady'] or node['css']['font-family'].split(',')[0].strip().strip('"')!=first:
                            self.add('asset-load',page,width,target,measured={'family':first,'loaded':loaded,'ready':node['fontReady']},threshold='loaded and used',expected='bound font loaded and used by its text',pointer=raw_path,context={'asset':asset})
            if node['directText'].strip() and not node['disabled']:
                background = effective_background(node['backgrounds'])
                foreground = color(node['css']['color'])
                threshold = text_threshold(node['fontSize'],node['fontWeight'])
                if background is None or foreground is None or node['overImage']:
                    self.add('contrast',page,width,target,type='needs-review',criterion='WCAG 1.4.3',threshold=threshold,
                             expected='review text over imagery or unresolved background',message='The effective text background cannot be measured reliably')
                else:
                    ratio = contrast(foreground,background)
                    if ratio < threshold:
                        self.add('contrast',page,width,target,criterion='WCAG 1.4.3',measured=round(ratio,2),threshold=threshold,expected=f'text contrast at least {threshold}:1')
            if node['clipped'] and node['text'].strip():
                exception = None
                for pointer,behavior in matching(self.document,'truncate',target):
                    complete = ' '.join(node['text'].split())
                    destination = full_text.get(behavior['full-content'],'')
                    if complete and complete in destination and node['lineClamp']==behavior['lines']:
                        exception=pointer
                        break
                self.add('clipping',page,width,target,criterion='text clipping',measured={'scroll':node['scroll'],'box':node['box'],'lines':node['lineClamp']},threshold='full text available',exception=exception,expected='unclipped text or a declared truncation with accessible full content')
            if node['image']:
                if not node['decoded'] or node['box'][2]<=0 or node['box'][3]<=0:
                    self.add('asset-load',page,width,target,measured={'decoded':node['decoded'],'box':node['box']},threshold='decoded and visible',expected='bound image decodes into a visible box')
                elif node['meaningfulImage']:
                    self.add('non-text-contrast',page,width,target,type='needs-review',criterion='WCAG 1.4.11',threshold=CHECK_NON_TEXT_CONTRAST,expected='review image/logo legibility on this surface',message='Image colors and meaningful regions require visual review')
            if node.get('backgroundAsset') and not node.get('backgroundDecoded'):
                self.add('asset-load',page,width,target,measured={'backgroundDecoded':False,'box':node['box']},threshold='decoded and visible',expected='bound background image decodes into a visible box')
            if node['control'] and not node['disabled'] and not node.get('nativeControl', False):
                external = effective_background(node['backgrounds'][1:])
                boundaries = [parsed for value in node.get('boundaries',[node['boundary']]) if (parsed:=color(value)) is not None and parsed[3]>0]
                if not boundaries or external is None:
                    self.add('non-text-contrast',page,width,target,type='needs-review',criterion='WCAG 1.4.11',threshold=CHECK_NON_TEXT_CONTRAST,expected='review the control boundary/state')
                else:
                    ratio = max(contrast(boundary,external) for boundary in boundaries)
                    if ratio < CHECK_NON_TEXT_CONTRAST:
                        self.add('non-text-contrast',page,width,target,criterion='WCAG 1.4.11',measured=round(ratio,2),threshold=CHECK_NON_TEXT_CONTRAST,expected='control boundary contrast at least 3:1')
        targets = [n for n in snapshot['nodes'] if n['interactive'] and n['visible'] and not n['disabled']]
        for node in targets:
            self.context = observation_context(node)
            if node['box'][2]>=CHECK_TARGET_SIZE and node['box'][3]>=CHECK_TARGET_SIZE:
                continue
            declarations = matching(self.document,'target-exception',node['target'])
            exception = declarations[0][0] if declarations else ('inline' if node['inline'] else 'user-agent' if node['userAgent'] else None)
            if not exception and spacing_exception(node['box'],[n['box'] for n in targets if n['index']!=node['index']]):
                exception='spacing'
            if not exception and node['equivalent']:
                exception='equivalent'
            self.add('target-size',page,width,node['target'],criterion='WCAG 2.5.8',measured={'width':round(node['box'][2],2),'height':round(node['box'][3],2)},threshold=CHECK_TARGET_SIZE,exception=exception,expected='24×24 CSS px target or a named WCAG exception')
        self.context = None
        if width==320:
            if snapshot['pageWidth']>width+CHECK_PIXEL_TOLERANCE:
                self.add('reflow',page,width,criterion='WCAG 1.4.10',measured=snapshot['pageWidth'],threshold=width,expected='no horizontal page scrolling at 320 CSS px')
            for node in snapshot['nodes']:
                if node['visible'] and node['scroll'][0]>node['box'][2]+CHECK_PIXEL_TOLERANCE and node['scrollContainer']:
                    declarations = matching(self.document,'horizontal-scroll',node['target'])
                    exception = declarations[0][0] if declarations else None
                    self.add('reflow',page,width,node['target'],criterion='WCAG 1.4.10',measured={'scrollWidth':node['scroll'][0],'width':node['box'][2]},threshold=width,exception=exception,expected='horizontal content scrolling declared intentionally',context=observation_context(node))

    def coverage(self, pages, widths):
        for index,behavior in enumerate(self.document.get('behaviors',[])):
            pointer=f'/behaviors/{index}'
            if pointer not in self.covered:
                self.add('behavior-coverage',pages[0],widths[0],behavior['scope'],type='coverage',pointer=pointer,
                         expected='a rendered finding covered by this behavior',message='This behavior covered no rendered finding')
