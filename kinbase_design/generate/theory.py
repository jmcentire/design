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
    'rounded': (['ui-rounded','Trebuchet MS','sans-serif'], ['ui-rounded','Trebuchet MS','sans-serif']),
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
        if dimension:owners[path]=dimension
        if dimension in preferences:
            provenance[path]={'kind':'chosen','choice':preferences[dimension]['choices'][-1]}
        return '{'+group+'.'+name+'}'
    hue=values['hue-family'];sat=.25+.7*values['saturation']
    primary=put('color','primary','color',hsl(hue,sat,.22),'hue-family')
    attention=put('color','attention','color',hsl(hue+140*values['whimsy'],sat,.22),'whimsy')
    wash=put('color','wash','color',hsl(hue,sat*.25,.97),'hue-family')
    ink=round(80-64*values['value-contrast'])
    foreground=put('color','ink','color','#'+f'{ink:02x}'*3,'value-contrast')
    paper=put('color','paper','color','#ffffff')
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
        provenance[pointer('style',group)]=source(item['artifact'],'json:')
        tokens=Tokens(tree)
        for name in tokens.nodes:
            kind,value=tokens.evaluate(name)
            if kind=='color':
                # Namespace aliases cannot be rewritten without changing source values;
                # routed tokens preserve their original literal/evaluated colour separately.
                node=tokens.nodes[name]
                ref=put('palette','p'+str(len(palette_refs)),'color',node['$value'] if not isinstance(node['$value'],str) or not node['$value'].startswith('{') else value)
                provenance[pointer('style','palette','p'+str(len(palette_refs)))]=source(item['artifact'],'json:/'+name.replace('.','/'))
                palette_refs.append(ref)
    families=PAIRINGS[values['type-pairing']]
    title_family=put('font','title','fontFamily',families[0],'type-pairing')
    body_family=put('font','body','fontFamily',families[1],'type-pairing')
    supplied_font=resources.get('font')
    if supplied_font:
        body_family=put('font','supplied','fontFamily',[supplied_font['family'],'sans-serif'])
        doc['style']['font']['supplied']['$extensions']={'kinbase-design':{'asset':supplied_font['asset']}}
        provenance['/style/font/supplied']=source(supplied_font['artifact'],'json:')
    regular=put('font','regular','fontWeight',supplied_font['weight'] if supplied_font else 400)
    strong=put('font','strong','fontWeight',600)
    ratio=values['type-scale'];sizes={}
    for role,power in [('title',2),('subtitle',1),('body',0),('subtext',-.5),('label',0),('caption',-1),('action',0),('control',0),('media',0)]:
        sizes[role]=put('type',role,'dimension',f'{16*ratio**power:.5f}px','type-scale')
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
        if construct in {'page-shell','listing-card','nav'}:treatment['properties']['background-color']=paper
        if construct=='hero':treatment['properties'].update({'padding-block':spacing['quad'],'background-color':wash})
        if construct=='nav':treatment['properties'].update({'display':'flex','flex-wrap':'wrap','align-items':'center','justify-content':'space-between'})
        if construct in {'form','search-bar'}:treatment['properties']['display']='grid'
        if construct=='listing-card':treatment['properties'].update({'border-radius':radius,'border-color':border,'border-width':line_width,'border-style':'solid'})
        for slot in spec['slots']:
            props={}
            if slot['kind']=='action' and slot['element']!='div':
                props={'padding':spacing['base'],'border-radius':radius}
                if slot['element']=='button':props.update({'background-color':primary,'color':paper,'border-style':'solid','border-color':primary,'border-width':line_width})
            if slot['kind']=='control' and slot['element']=='label':
                props={'border-radius':radius,'border-style':'solid','border-color':border,'border-width':line_width,
                       'background-color':paper,'padding':spacing['base']}
            if slot.get('asset_kind'):
                asset=resources.get('bindings',{}).get(slot['asset_kind'])
                if asset:treatment.setdefault('assets',{})[slot['id']]=asset
                if slot['asset_kind']=='logo':props={'width':logo_width}
            if props:treatment['slots'][slot['id']]={'properties':props}
        doc['components'][construct]=treatment
    # Make the attention and formality decisions visible on the common A/B screen.
    doc['components']['hero']['slots']['eyebrow']={'role':'label','emphasis':'attention'}
    doc['components']['hero']['slots'].setdefault('action',{})['emphasis']='primary'
    doc['components']['listing-card']['slots'].setdefault('rating',{})['emphasis']='attention'
    if palette_refs:
        # Visible fixed source swatches on existing constructs; no invented structural variant.
        for i,construct in enumerate(('hero','content-section','footer')):
            ref=palette_refs[i%len(palette_refs)];bg=Tokens(doc['style']).reference(ref)[1]
            fg='#000000' if contrast(color('#000000'),color(bg))>=contrast(color('#ffffff'),color(bg)) else '#ffffff'
            foreground_ref=put('color','source-text-'+str(i),'color',fg)
            comp=doc['components'][construct];comp['properties']['background-color']=ref
            for slot in vocabulary['constructs'][construct]['slots']:
                comp['slots'].setdefault(slot['id'],{}).setdefault('properties',{}).update(color=foreground_ref)
    for asset,artifact in resources.get('origins',{}).items():provenance[pointer('assets',asset)]=source(artifact,'json:')
    return doc,complete(doc,provenance,[]),owners
