"""Focused mood/interview compositions, all rendered by the normal preview path."""
from ..language.tokens import Tokens


def filename(dimension):
    if dimension in {'hue-family','saturation','value-contrast'}:return 'palette.html'
    if dimension in {'type-pairing','type-scale'}:return 'type.html'
    if dimension in {'shape','density'}:return 'shape.html'
    if dimension=='formality':return 'formality.html'
    return 'texture.html'


def compositions(document):
    tokens=Tokens(document['style'])
    def page(title,items):return {'title':title,'provided_only':True,'instances':items}
    def card(title,body,background,foreground):
        return {'construct':'card','values':{'title':title,'body':body},'treatment':{
            'properties':{'background-color':background,'padding':'{space.double}','gap':'{space.base}','border-radius':'{shape.radius}'},
            'slots':{slot:{'properties':{'color':foreground,'font-size':'{type.caption}'}} for slot in ('title','body')}}}
    swatches=[]
    for name,foreground in [('primary','{color.paper}'),('wash','{color.ink}'),('attention','{color.paper}')]:
        swatches.append(card(name.title(),tokens.evaluate('color.'+name)[1],'{color.'+name+'}',foreground))
    return {
        'palette.html':page('Palette',[
            {'group':True,'selector':'palette-strip','layout':{'columns':3,'column-gap':0},'children':swatches},
            {'construct':'content-section','values':{'title':'Aa · A new perspective','body':'Text and surface, together.'},
             'treatment':{'properties':{'padding':'{space.double}','background-color':'{color.paper}'}}}]),
        'type.html':page('Type specimen',[
            {'construct':'hero','values':{'eyebrow':'TYPE / 0123456789','title':'Aa Bb Cc','body':'A new perspective. The quick brown fox jumps over the lazy dog.'},
             'treatment':{'properties':{'padding':'{space.double}','background-color':'{color.paper}'}}}]),
        'shape.html':page('Shape and rhythm',[
            {'construct':'card','values':{'title':'Room to explore','highlight':'Featured','body':'A clear shape. A comfortable rhythm.','action':'Discover more'}},
            {'construct':'search-bar','values':{'query':'Search','action':'Go'}}]),
        'formality.html':page('Tone and detail',[
            {'construct':'card','values':{'title':'A new perspective','highlight':'Thoughtfully made','body':'Small details set the tone.','action':'Explore'}}]),
        'texture.html':page('Accent and texture',[
            {'construct':'content-section','values':{'title':'Colour in motion','body':'A rhythm of primary and contrasting accents.'}},
            {'construct':'error-state','values':{'title':'A playful accent','body':'A second colour changes the mood.'}}]),
    }
