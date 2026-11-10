"""Navigation links and their nearest enclosing painted band, without child paint."""
from ..checks.math import color


def evidence(view,item):
    nodes=view.get('structure',view['nodes']);by={n['selector']:n for n in nodes}
    root=item['root_node']
    def within(node,parent):
        return node['selector']==parent['selector'] or node['selector'].startswith(parent['selector']+' > ')
    regions=[n for n in nodes if within(n,root) and (n['tag']=='nav' or n.get('attributes',{}).get('role')=='navigation')]
    links=[n for n in nodes if within(n,root) and n['tag']=='a' and n.get('attributes',{}).get('role')!='button'
           and (not regions or any(within(n,region) for region in regions))]
    if not links:return [],None
    # Start above the link: a filled anchor or button is never the band.
    ancestor=by.get(links[0].get('parent'))
    while ancestor:
        interactive=ancestor['tag'] in {'a','button','input','select','textarea'} or ancestor.get('attributes',{}).get('role') in {'button','link'}
        paint=color(ancestor.get('normalized_colors',{}).get('background-color',ancestor.get('styles',{}).get('background-color','')))
        if not interactive and all(within(link,ancestor) for link in links) and paint and paint[3]>0:
            return links,ancestor
        ancestor=by.get(ancestor.get('parent'))
    return links,None
