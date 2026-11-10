"""Compile content-owned values into the renderer's existing composition tree."""


def value(kind, data):
    return {'kind':kind,'value':data}


def compile_page(document):
    def instance(construct, values, **extra):
        return {'construct':construct,'values':values,**extra}

    def copy_fields(source, *fields):
        return {field:value('inline',source[field]) for field in fields if field in source}

    hero_seen = False
    has_hero = any(b['type']=='hero' for b in document['blocks'])
    blocks = []
    for block in document['blocks']:
        kind = block['type']
        values = copy_fields(block,'eyebrow','title','body')
        extra = {'id':block.get('id')}
        if kind == 'hero':
            extra['heading_levels'] = {'title':2 if hero_seen else 1}
            hero_seen = True
            if 'media' in block:values['media'] = value('media',block['media'])
        elif kind == 'section':values['body'] = value('prose',block.get('content',[]))
        elif kind == 'collection':
            if 'intro' in block:values['body'] = value('inline',block['intro'])
            cards = []
            for card in block.get('items',[]):
                slots = copy_fields(card,'eyebrow','title','body')
                for key, slot, content_kind in [('media','media','media'),('facts','meta','facts'),('action','action','link')]:
                    if key in card:slots[slot] = value(content_kind,card[key])
                cards.append(instance('card',slots,heading_levels={'title':3 if block.get('title') else 2}))
            extra.update(children=cards,children_slot='items')
        if 'actions' in block:values['action'] = value('actions',block['actions'])
        construct = {'hero':'hero','section':'content-section','collection':'collection','cta':'content-section'}[kind]
        blocks.append(instance(construct,values,**extra))
    site = document['site']; footer = document.get('footer',{})
    navigation = instance('site-header',{},children=[instance('nav',{'logo':value('brand',site),'links':value('links',site.get('nav',[]))})])
    shell = instance('page-shell',{} if has_hero else {'title':value('inline',document['page']['title'])},children=blocks)
    foot = instance('footer',{'body':value('inline',footer.get('text','')),'links':value('links',footer.get('links',[])),
                              'notices':value('notices',footer.get('notices',[]))})
    return {**document['page'],'content_document':True,'instances':[navigation,shell,foot]}
