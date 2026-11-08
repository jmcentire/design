"""One deterministic design derivation; dimensions own independent presentation values."""
import colorsys
from copy import deepcopy
from ..checks.math import color, contrast
from ..findings import pointer
from ..language.tokens import Tokens
from ..ingest.provenance import complete,source

PAIRINGS = {
    'geometric-sans': (['Arial','sans-serif'], ['Arial','sans-serif']),
    'humanist-sans': (['system-ui','sans-serif'], ['system-ui','sans-serif']),
    'rounded': (['Trebuchet MS','ui-rounded','sans-serif'], ['Trebuchet MS','ui-rounded','sans-serif']),
    'serif': (['Georgia','serif'], ['Georgia','serif']),
    'slab': (['Rockwell','Courier New','serif'], ['Rockwell','Courier New','serif']),
}


def hsl(h,s,l):return '#'+''.join(f'{round(c*255):02x}' for c in colorsys.hls_to_rgb(h%360/360,l,s))
def token(kind,value):return {'$type':kind,'$value':value}


def language(language_id,vocabulary,values,resources,preferences=None):
    """Fixed source tokens/bytes are copied unchanged; generated tokens have their own namespace."""
    preferences=preferences or {};provenance={'':{'kind':'inferred','method':'Colour harmony, modular type scale, spacing rhythm and Vocabulary hierarchy','inputs':[]}}
    doc={'id':language_id,'name':language_id.replace('-',' ').title(),'vocabulary':vocabulary['version'],
         'description':'Generated from visual preferences; standards unknown (Kinbase unconnected).',
         'style':{},'roles':{},'components':{},'layout':{'variants':{}},'overrides':[],'behaviors':[],
         'assets':deepcopy(resources.get('assets',{}))}
    owners={}
    def put(group,name,kind,value,dimension=None):
        doc['style'].setdefault(group,{})[name]=token(kind,value)
        path=pointer('style',group,name)
        dimensions=(dimension,) if isinstance(dimension,str) else dimension or ()
        if dimensions:owners[path]=list(dimensions)
        decisions=list(dict.fromkeys(choice for d in dimensions if d in preferences for choice in preferences[d]['choices']))
        if decisions:
            provenance[path]={'kind':'chosen','choice':decisions[-1],'choices':decisions}
        return '{'+group+'.'+name+'}'
    hue=values['hue-family'];sat=.25+.7*values['saturation']
    primary=put('color','primary','color',hsl(hue,sat,.22),('hue-family','saturation'))
    attention=put('color','attention','color',hsl(hue+140*values['whimsy'],sat,.22),('hue-family','saturation','whimsy'))
    wash=put('color','wash','color',hsl(hue,sat,.88),('hue-family','saturation'))
    accent_wash=put('color','attention-wash','color',hsl(hue+140*values['whimsy'],sat,.88),('hue-family','saturation','whimsy'))
    texture=put('color','texture','gradient',[{'color':wash,'position':0},{'color':wash,'position':.25},{'color':accent_wash,'position':.25},{'color':accent_wash,'position':.5},{'color':wash,'position':.5},{'color':wash,'position':.75},{'color':accent_wash,'position':.75},{'color':accent_wash,'position':1}],('hue-family','saturation','whimsy'))
    ink=round(80-72*values['value-contrast'])
    foreground=put('color','ink','color','#'+f'{ink:02x}'*3,'value-contrast')
    paper=put('color','paper','color',hsl(0,0,.90+.10*values['value-contrast']),'value-contrast')
    muted=put('color','muted','color','#545454')
    border=put('color','boundary','color','#666666')
    # A palette is fixed evidence, including aliases/composite DTCG values.
    palette_refs=[]
    for i,item in enumerate(resources.get('tokens',[])):
        group='source'+str(i);tree=deepcopy(item['tree'])
        def namespace(value):
            if isinstance(value,dict):return {k:namespace(v) for k,v in value.items()}
            if isinstance(value,list):return [namespace(v) for v in value]
            if isinstance(value,str) and value.startswith('{') and value.endswith('}'):return '{'+group+'.'+value[1:]
            return value
        # Rebase references into their source namespace; literal supplied values stay exact.
        doc['style'][group]=namespace(tree)
        source_prefix='member:'+item['location']+'#' if item.get('location') else 'json:'
        provenance[pointer('style',group)]=source(item['artifact'],source_prefix if item.get('location') else 'page:original')
        tokens=Tokens(tree)
        for name in tokens.nodes:
            kind,value=tokens.evaluate(name)
            if kind=='color':
                # Namespace aliases cannot be rewritten without changing source values;
                # routed tokens preserve their original literal/evaluated colour separately.
                node=tokens.nodes[name]
                ref=put('palette','p'+str(len(palette_refs)),'color',node['$value'] if not isinstance(node['$value'],str) or not node['$value'].startswith('{') else value)
                provenance[pointer('style','palette','p'+str(len(palette_refs)))]=source(item['artifact'],source_prefix+pointer(*name.split('.')))
                palette_refs.append(ref)
    families=PAIRINGS[values['type-pairing']]
    title_family=put('font','title','fontFamily',families[0],'type-pairing')
    body_family=put('font','body','fontFamily',families[1],'type-pairing')
    supplied_font=resources.get('font')
    if supplied_font:
        body_family=put('font','supplied','fontFamily',[supplied_font['family'],'sans-serif'])
        doc['style']['font']['supplied']['$extensions']={'kinbase-design':{'asset':supplied_font['asset']}}
        provenance['/style/font/supplied']=source(supplied_font['artifact'],'page:original')
    regular=put('font','regular','fontWeight',supplied_font['weight'] if supplied_font else 400)
    strong=put('font','strong','fontWeight',600)
    ratio=values['type-scale'];sizes={}
    for role,power in [('title',2),('subtitle',1),('body',0),('subtext',-.5),('label',0),('caption',-1),('action',0),('control',0),('media',0)]:
        sizes[role]=put('type',role,'dimension',f'{16*ratio**power:.5f}px','type-scale')
    display_size=put('type','display','dimension',f'{16*ratio**3:.5f}px','type-scale')
    line=put('line','body','number',1.6);heading_line=put('line','heading','number',1.25)
    tracking=put('type','tracking','dimension',f'{values["formality"]*.6:g}px','formality')
    spacing={}
    for name,multiple in [('base',1),('double',2),('triple',3),('quad',4)]:
        spacing[name]=put('space',name,'dimension',f'{values["density"]*multiple:g}px','density')
    radius=put('shape','radius','dimension',f'{values["shape"]:g}px','shape')
    line_width=put('shape','line','dimension','1px')
    logo_width=put('shape','logo','dimension','96px')
    put('breakpoint','md','dimension','768px');put('breakpoint','lg','dimension','1200px')
    for role in vocabulary['roles']:
        doc['roles'][role]={}
        for emphasis in vocabulary['emphasis']:
            props={'color':{'neutral':foreground,'primary':primary,'attention':attention,'muted':muted}[emphasis],
                   'surface':paper,'font-family':title_family if role in {'title','subtitle'} else body_family,
                   'font-size':sizes[role],'font-weight':strong if role in {'title','subtitle'} else regular,
                   'line-height':heading_line if role in {'title','subtitle'} else line}
            if role=='title':props['letter-spacing']=tracking
            if role=='label':
                props['text-transform']='uppercase' if values['formality']>=.5 else 'none'
                if 'formality' in preferences:provenance[pointer('roles',role,emphasis,'text-transform')]={'kind':'chosen','choice':preferences['formality']['choices'][-1]}
            doc['roles'][role][emphasis]=props
    for construct,spec in vocabulary['constructs'].items():
        treatment={'variant':'default','properties':{'padding':spacing['double'],'gap':spacing['base']},'slots':{}}
        if construct in {'page-shell','listing-card','card','nav'}:treatment['properties']['background-color']=paper
        if construct=='hero':treatment['properties'].update({'padding-block':spacing['quad'],'background-color':wash,'border-radius':radius})
        if construct=='error-state':treatment['properties'].update({'background-color':accent_wash,'border-radius':radius})
        if construct=='content-section':
            # Texture is a non-text sibling, never a background ancestor of copy.
            # A declared variant keeps the vocabulary slots in their reading order.
            variant='accent-band'
            content=''.join('{{slot:'+slot['id']+'}}' for slot in spec['slots'])
            template=f'<{spec["root"]}><div data-kd-part="accent-band"></div>'+content+f'</{spec["root"]}>'
            doc['layout']['variants'][construct]={variant:{'template':template}}
            treatment['variant']=variant
            treatment['properties'].update({'background-color':paper,'border-radius':radius})
            treatment['parts']={'accent-band':{'background-image':texture,'padding-block':spacing['base'],
                                             'margin-block':spacing['base'],'border-radius':radius}}

        if construct=='nav':treatment['properties'].update({'display':'flex','flex-wrap':'wrap','align-items':'center','justify-content':'space-between'})
        if construct in {'form','search-bar'}:treatment['properties']['display']='grid'
        if construct in {'listing-card','card'}:treatment['properties'].update({'border-radius':radius,'border-color':border,'border-width':line_width,'border-style':'solid'})
        for slot in spec['slots']:
            props={}
            if slot['kind']=='action' and slot['element']!='div':
                props={'padding':spacing['base'],'border-radius':radius}
                if slot['element']=='button' or slot['id']=='action':props.update({'background-color':primary,'color':paper,'border-style':'solid','border-color':primary,'border-width':line_width})
            if slot['kind']=='control' and slot['element'] in {'label','input','select','textarea','button'}:
                props={'border-radius':radius,'border-style':'solid','border-color':border,'border-width':line_width,
                       'background-color':paper,'padding':spacing['base']}
            if slot.get('asset_kind'):
                asset=resources.get('bindings',{}).get(slot['asset_kind'])
                if asset:treatment.setdefault('assets',{})[slot['id']]=asset
                if slot['asset_kind']=='logo':props={'width':logo_width}
            if props:treatment['slots'][slot['id']]={'properties':props}
        doc['components'][construct]=treatment
    # Make the attention and formality decisions visible on the common A/B screen.
    doc['components']['hero']['slots']['eyebrow']={'role':'label','emphasis':'attention','properties':{'display':'inline-block','padding':spacing['base'],'border-radius':radius,'background-color':accent_wash}}
    doc['components']['hero']['slots']['title']={'properties':{'font-size':display_size,'color':primary,'margin-block':spacing['base']}}
    doc['components']['hero']['slots']['body']={'properties':{'margin-block':spacing['double']}}
    doc['components']['hero']['slots'].setdefault('action',{})['emphasis']='primary'
    doc['components']['listing-card']['slots'].setdefault('rating',{})['emphasis']='attention'
    if palette_refs:
        # Visible fixed source swatches on existing constructs.
        for i,construct in enumerate(('hero','content-section','footer')):
            ref=palette_refs[i%len(palette_refs)]
            comp=doc['components'][construct];comp['properties']['background-color']=ref
            comp['properties'].pop('background-image',None)
            for slot in vocabulary['constructs'][construct]['slots']:
                props=comp['slots'].setdefault(slot['id'],{}).setdefault('properties',{})
                bg=Tokens(doc['style']).reference(props.get('background-color',ref))[1]
                fg=max(('#000000','#ffffff'),key=lambda value:contrast(color(value),color(bg)))
                props['color']=put('color','source-text-'+str(i)+'-'+slot['id'],'color',fg)
    for asset,artifact in resources.get('origins',{}).items():provenance[pointer('assets',asset)]=source(artifact,'page:original')
    return doc,complete(doc,provenance,[]),owners
