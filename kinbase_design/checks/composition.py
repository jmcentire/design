"""Composition constraints interpreted from rendered geometry, not token guesses."""
from collections import Counter


def evaluate(evaluation, page, width, observed):
    def add(rule,item,measured,threshold,expected,type='violation'):
        target=item['target'];construct,_,slot=target.partition('.')
        path='/components/'+construct+('/slots/'+slot if slot else '')
        evaluation.add(rule,page,width,target,type=type,pointer=path,measured=measured,threshold=threshold,
                       expected=expected,context={'composition':rule,'state':item.get('state','default')})
    weights=Counter()
    for run in observed.get('paragraphText',[]):weights[run['size']]+=run['characters']
    body=max(weights,key=lambda size:(weights[size],size)) if weights else None
    headings=observed.get('headings',[]);sizes={}
    for item in headings:sizes.setdefault(item['level'],[]).append(item['size'])
    for item in headings:
        ceiling=min(sizes[item['level']-1]) if item['level']-1 in sizes else None
        if (body is not None and item['size']<body) or (ceiling is not None and item['size']>ceiling):
            add('heading-scale',item,{'level':item['level'],'font_size':item['size'],'body_size':body,'parent_minimum':ceiling},
                {'minimum':body,'maximum':ceiling},'headings are at least body size and no larger than headings of the preceding level')
    for item in observed.get('insets',[]):
        if min(item['left'],item['right'])<8-1e-6:
            add('text-inset',item,{'left':item['left'],'right':item['right'],'surface':item['surface']},8,
                'text line boxes keep at least 8px horizontal inset inside a painted surface')
    targets=observed.get('targets',[])
    for i,a in enumerate(targets):
        for b in targets[i+1:]:
            if a.get('key') in b.get('ancestors',[]) or b.get('key') in a.get('ancestors',[]):continue
            if not (a['painted'] or b['painted']):continue
            ax,ay,aw,ah=a['box'];bx,by,bw,bh=b['box']
            horizontal=max(bx-ax-aw,ax-bx-bw);vertical=max(by-ay-ah,ay-by-bh)
            gap=max(horizontal,vertical)
            if gap<4-1e-6:
                add('control-separation',a,{'gap':gap,'horizontal_gap':horizontal,'vertical_gap':vertical,'other':b['target']},4,
                    'distinct interactive targets with a painted boundary are at least 4px apart')
    if width>=1024:
        for item in observed.get('paragraphs',[]):
            if item['characters']>=60 and item['width']>40*item['size']+1e-6:
                add('measure',item,{'width':item['width'],'font_size':item['size'],'em':item['width']/item['size'],'characters':item['characters']},40,
                    'paragraphs of 60 or more characters are at most 40em wide at desktop widths')
    minimum=evaluation.vocabulary.get('measure_minimum_em',0)
    if minimum:
        for item in observed.get('paragraphs',[]):
            if item['characters']<60:continue
            limit=min(minimum*item['size'],2*item['columnWidth']/3)
            if item['width']<limit-1e-6:
                add('measure',item,{'width':item['width'],'font_size':item['size'],'em':item['width']/item['size'],
                    'characters':item['characters'],'column_width':item['columnWidth'],'column':item['column'],
                    'column_kind':item['columnKind']},{'minimum_em':minimum,'minimum_px':limit},
                    'long paragraphs are at least 15em wide or two thirds of their containing column')
    if 'word-break' in evaluation.vocabulary.get('composition_rules',[]):
        if not hasattr(evaluation,'word_reference'):evaluation.word_reference={}
        prior=evaluation.word_reference.get(page)
        if prior is None or width<prior[0]:
            prior=(width,{w['key']:w for w in observed.get('words',[])})
            evaluation.word_reference[page]=prior
        for item in observed.get('words',[]):
            if item['lines']<=1:continue
            smallest=prior[1].get(item['key'],item)
            unavoidable=smallest['wordWidth']>smallest['availableWidth']
            add('word-break',item,{'word':item['word'],'line_boxes':item['lines'],'word_width':item['wordWidth'],
                                  'block_width':item['blockWidth'],'smallest_width':prior[0],
                                  'smallest_word_width':smallest['wordWidth'],'available_width':smallest['availableWidth']},
                'one line per word','words remain intact; an unavoidable word wider than the available layout requires review',
                type='needs-review' if unavoidable else 'violation')
    if 'label-proximity' in evaluation.vocabulary.get('composition_rules',[]):
        for item in observed.get('labelPairs',[]):
            if item['own']['gap']>=item['next']['gap']:
                add('label-proximity',item,{'label':item['label'],'value':item['value'],'next_label':item['nextLabel'],
                                          'own':item['own'],'next':item['next']},
                    'own gap < next gap','a value is closer to its label than to the next label')
    if 'heading-binding' in evaluation.vocabulary.get('composition_rules',[]):
        for item in observed.get('headingBindings',[]):
            if item['after']>=item['before']:
                add('heading-binding',item,{k:item[k] for k in ('before','after','previous','next')},
                    'after < before','a heading is closer to the following visible block than the preceding block')
    if 'gutter' in evaluation.vocabulary.get('composition_rules',[]):
        for item in observed.get('gutters',[]):
            if item['gap']<8-1e-6:
                add('gutter',item,{k:item[k] for k in ('gap','axis','other')},8,
                    'painted repeated items are separated by at least 8px')
