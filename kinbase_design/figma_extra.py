"""Optional Figma evidence. Live comments/variables are not historical file state."""
from datetime import datetime, timezone
from io import BytesIO
import json
import re
from urllib.parse import urlparse
from urllib.request import Request
from urllib.error import HTTPError, URLError
from PIL import Image
from .artifacts import import_bytes
from .config import MAX_UPLOAD_BYTES


def download_png(api, url):
    parsed = urlparse(url)
    host = parsed.hostname or ''
    allowed = host == 'figma.com' or host.endswith('.figma.com') or bool(re.fullmatch(
        r'figma-alpha-api\.s3(?:[.-][a-z0-9-]+)?\.amazonaws\.com', host))
    if parsed.scheme != 'https' or not allowed or parsed.username or parsed.password or parsed.port not in (None,443):
        raise ValueError('Unsupported Figma render host; download refused')
    try:
        # No API credential on image-host requests; same no-redirect transport.
        with api.opener.open(Request(url), timeout=30) as response:
            data = response.read(MAX_UPLOAD_BYTES + 1)
    except (HTTPError, URLError, TimeoutError, OSError):
        raise ValueError('Figma rendered image download failed') from None
    if len(data) > MAX_UPLOAD_BYTES:
        raise ValueError('Figma rendered image exceeds upload limit')
    try:
        with Image.open(BytesIO(data)) as image:
            if image.format != 'PNG': raise ValueError('Figma render is not PNG')
            image.verify()
    except (OSError, Image.DecompressionBombError):
        raise ValueError('Invalid or oversized Figma render') from None
    return data


def color_tokens(payload):
    """Preserve mode identity; resolve color aliases only within the same mode."""
    variables = payload.get('meta', {}).get('variables', {})
    result = {}
    for key, variable in variables.items():
        if variable.get('resolvedType') != 'COLOR': continue
        for mode, value in variable.get('valuesByMode', {}).items():
            visited = {key}
            while isinstance(value, dict) and value.get('type') == 'VARIABLE_ALIAS':
                target = value.get('id')
                if target in visited: value = None; break
                visited.add(target)
                value = variables.get(target, {}).get('valuesByMode', {}).get(mode)
            if not isinstance(value, dict) or not all(c in value for c in ('r','g','b')): continue
            channels = [value[c] for c in ('r','g','b')] + [value.get('a',1)]
            name = 'variable_'+str(key).encode().hex()+'_mode_'+str(mode).encode().hex()
            result[name] = {'$type':'color', '$value':'#'+''.join(f'{round(max(0,min(1,v))*255):02x}' for v in channels),
                            '$extensions':{'figma':{'variableId':key,'modeId':mode}}}
    return result


def acquire(api, workspace, file_key, version, document, nodes=(), variables=False, comments=False):
    files, children, observations, gaps = {}, [], [], []
    encode=lambda value:json.dumps(value,sort_keys=True,ensure_ascii=False).encode()
    if len(nodes)>20: raise ValueError('Select at most 20 render nodes per pull')
    known=set();stack=[document]
    while stack:
        node=stack.pop();known.add(node.get('id'));stack.extend(node.get('children',[]))
    if any(node not in known for node in nodes): raise ValueError('Render node is absent from captured version')
    if nodes:
        try:
            response=api.get('images/'+file_key,ids=','.join(dict.fromkeys(nodes)),version=version,format='png',scale=1)
            for node in dict.fromkeys(nodes):
                url=response.get('images',{}).get(node)
                if not url:
                    gaps.append('Render unavailable for node '+node);continue
                try:
                    data=download_png(api,url)
                    name='render-'+node.encode().hex()+'.png'
                    files[name]=data
                    artifact=import_bytes(workspace,data,name,'image')
                    children.append({'artifact':artifact,'location':name})
                    observations.append({'kind':'render','node_id':node,'file_version':version,'member':name})
                except ValueError as exc:gaps.append(str(exc))
        except ValueError as exc:gaps.append(str(exc))
    for enabled, kind, path in ((variables,'variables','files/'+file_key+'/variables/local'),
                                 (comments,'comments','files/'+file_key+'/comments')):
        if not enabled: continue
        try:
            payload=api.get(path)
            observed=datetime.now(timezone.utc).isoformat()
            files[kind+'.json']=encode(payload)
            observations.append({'kind':kind,'observed_at':observed,'file_version':None,
                                 'association':'live-unversioned','member':kind+'.json'})
            if variables and kind=='variables':
                tokens=color_tokens(payload)
                if tokens:
                    data=encode(tokens);files['variable-colors.json']=data
                    children.append({'artifact':import_bytes(workspace,data,'variable-colors.json','dtcg'),
                                     'location':'variable-colors.json'})
                gaps.append('Non-color variables and unresolved aliases retained as raw evidence, not converted')
        except ValueError as exc:gaps.append(kind+': '+str(exc))
    return files, children, observations, gaps
