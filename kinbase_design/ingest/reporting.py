"""Public measured summaries, derived from the same extraction/comparison facts."""
from ..config import INGEST_FULL_RADIUS_PX
from ..language.tokens import Tokens
from .quantize import delta_e


def type_ratio(sizes):
    sizes=sorted({size for size in sizes if size>0})
    return round((sizes[-1]/sizes[0])**(1/(len(sizes)-1)),6) if len(sizes)>1 else 1.0


def measured(document,facts):
    tokens=Tokens(document['style']);colors=[]
    for name in tokens.nodes:
        try:kind,value=tokens.evaluate(name)
        except (ValueError,KeyError):continue  # Shared validation reports defective source tokens.
        if kind=='color':colors.append((name,value))
    palette=[]
    for entry in facts['palette']:
        nearest=min(colors,key=lambda pair:delta_e(entry['value'],pair[1]),default=None)
        if nearest is None:continue
        sources=[member['value'] for member in entry['members']]
        palette.append({'token':nearest[0],'value':nearest[1],'sources':sources,
                        'max_delta_e':round(max(delta_e(value,nearest[1]) for value in sources),6)})
    sizes=facts['type_scale']
    return {'palette':palette,'font_families':facts['font_families'],
            'type_scale':{'base_px':facts.get('type_base_px',sizes[0] if sizes else None),'ratio':type_ratio(sizes),'sizes_px':sizes},
            'spacing':{'base_px':facts['spacing_base'],'steps_px':facts['spacing']},
            'radii_px':[INGEST_FULL_RADIUS_PX if r=='full' else r for r in facts['radii']],
            'breakpoints_px':facts['breakpoints']}


def fidelity_facts(pairs):
    facts=[pair['facts'] for pair in pairs if pair.get('facts')]
    palette=[];families=[];source_sizes=set();actual_sizes=set()
    for fact in facts:
        for entry in fact['palette']:
            item={'captured':entry['source'],'draft':entry['reconstruction'],'delta_e':entry['delta_e']}
            if item not in palette:palette.append(item)
        families.extend(fact['font_family_match'])
        source_sizes.update(fact['source']['type_scale']);actual_sizes.update(fact['reconstruction']['type_scale'])
    family=next((item for item in families if not item['match']),families[0] if families else {})
    spacing=facts[0]['spacing_base'] if facts else {}
    return {'palette':palette,
            'font_family':{'captured':family.get('source'),'draft':family.get('reconstruction'),'match':family.get('match',False)},
            'type_scale':{'captured_ratio':type_ratio(source_sizes),'draft_ratio':type_ratio(actual_sizes)},
            'spacing_base':{'captured_px':spacing.get('source'),'draft_px':spacing.get('reconstruction')}}
