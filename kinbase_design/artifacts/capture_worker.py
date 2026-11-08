"""Isolated, bounded browser capture; no state is published until capture completes."""
import ipaddress
import json
from pathlib import Path
import socket
import sys
from urllib.parse import urlsplit, unquote, urljoin
from ..config import (CAPTURE_TIMEOUT_MS, CAPTURE_MAX_NODES, CAPTURE_MAX_TEXT, CAPTURE_MAX_WIDTHS,
                      CAPTURE_MAX_ASSETS, ARTIFACT_MAX_BYTES, MAX_UPLOAD_BYTES, CHECK_VIEWPORT_HEIGHT)
from ..language.properties import TOKEN_PROPERTIES, KEYWORDS
from ..storage import read_json
from . import import_bytes
from .bundle import import_bundle
from .capture import public_url, media_widths
from .runtime import chromium


def collect(job):
    from playwright.sync_api import Error
    files={}; pages=[]; problems=[]; assets={}; dns={}; asset_bytes=0
    def allowed(url):
        if url.startswith(('data:','blob:')):return True
        public_url(url)
        host=urlsplit(url).hostname
        if host not in dns:
            addresses=socket.getaddrinfo(host,None,type=socket.SOCK_STREAM)
            dns[host]=bool(addresses) and all(ipaddress.ip_address(a[4][0]).is_global for a in addresses)
        if not dns[host]:raise ValueError('Non-public network destination blocked')
        return True
    with chromium() as browser:
        for number,url in enumerate(job['urls'],1):
            page_id=f'page-{number}'; record={'id':page_id,'url':url,'views':[]};pages.append(record)
            pending=list(job['widths']);done=set()
            while pending:
                width=pending.pop(0)
                if width in done:continue
                done.add(width)
                context=browser.new_context(viewport={'width':width,'height':CHECK_VIEWPORT_HEIGHT},service_workers='block',accept_downloads=False)
                context.set_default_timeout(CAPTURE_TIMEOUT_MS)
                def route(request_route):
                    request=request_route.request
                    try:
                        if request.method not in {'GET','HEAD'}:raise ValueError('Non-read request blocked')
                        allowed(request.url)
                        headers={k:v for k,v in request.headers.items() if k.lower() not in {'cookie','authorization','proxy-authorization'}}
                        request_route.continue_(headers=headers)
                    except (ValueError,OSError):request_route.abort()
                context.route('**/*',route)
                page=context.new_page();responses=[]
                page.on('response',lambda response:responses.append(response) if response.request.resource_type in {'font','image','stylesheet'} else None)
                try:
                    response=page.goto(url,wait_until='domcontentloaded',timeout=CAPTURE_TIMEOUT_MS)
                    if response and response.status>=400:problems.append({'page':page_id,'width':width,'message':f'HTTP {response.status}'})
                    page.evaluate('''async timeout=>{for(const image of document.images)image.loading='eager';await Promise.race([Promise.all([document.fonts.ready,...[...document.images].map(i=>i.decode().catch(()=>{}))]),new Promise(resolve=>setTimeout(resolve,timeout))]);}''',CAPTURE_TIMEOUT_MS)
                    properties=sorted((TOKEN_PROPERTIES.keys()|KEYWORDS.keys()|{'padding-top','padding-right','padding-bottom','padding-left','margin-top','margin-bottom','border-top-width','border-top-color','border-top-left-radius','row-gap','column-gap','position','grid-template-columns','box-shadow'})-{'surface'})
                    data=page.evaluate(Path(__file__).with_name('capture.js').read_text(),{'properties':properties,'maxNodes':CAPTURE_MAX_NODES,'maxText':CAPTURE_MAX_TEXT})
                    prefix=f'{page_id}/{width}'
                    dom=page.content().encode()
                    if len(dom)>MAX_UPLOAD_BYTES:
                        problems.append({'page':page_id,'width':width,'message':'DOM exceeds artifact size bound'});dom=dom[:MAX_UPLOAD_BYTES]
                    files[prefix+'.html']=dom
                    files[prefix+'.png']=page.screenshot(full_page=True,animations='disabled',timeout=CAPTURE_TIMEOUT_MS)
                    for response in responses:
                        if len(assets)>=CAPTURE_MAX_ASSETS:break
                        try:
                            if not response.ok:continue
                            body=response.body()
                            if not body or len(body)>MAX_UPLOAD_BYTES:continue
                            if response.request.resource_type=='stylesheet':
                                import re
                                css=body.decode('utf-8',errors='replace')
                                data['media_queries']+=re.findall(r'@media\s+([^{}]+)',css)
                                for block in re.findall(r'@font-face\s*\{([^{}]+)\}',css):
                                    declarations=dict(re.findall(r'([\w-]+)\s*:\s*([^;]+)',block))
                                    data['font_faces'].append({'family':declarations.get('font-family','').strip(),
                                        'weight':declarations.get('font-weight','400').strip(),'style':declarations.get('font-style','normal').strip(),
                                        'src':' '.join(urljoin(response.url,u) for u in re.findall(r'url\([\"\']?([^\"\')]+)',declarations.get('src','')))})
                                continue
                            if response.url in assets:continue
                            if asset_bytes+len(body)>ARTIFACT_MAX_BYTES:
                                problems.append({'page':page_id,'width':width,'message':'Asset byte limit reached'})
                                break
                            kind='font' if response.request.resource_type=='font' else next((a['kind'] for a in data['candidates'] if a['url']==response.url),'image')
                            name=Path(unquote(urlsplit(response.url).path)).name or ('font.woff2' if kind=='font' else 'image.png')
                            name=name.replace('\\','-')[:150]
                            artifact=import_bytes(job['workspace'],body,name,'asset')
                            asset_bytes+=len(body)
                            assets[response.url]={'artifact':artifact,'kind':kind,'url':response.url,'filename':name}
                        except (Error,ValueError,OSError) as exc:
                            problems.append({'page':page_id,'width':width,'message':'Asset capture: '+str(exc)[:200]})
                    for candidate in data['candidates']:
                        if candidate.get('inline') and candidate['url'] not in assets and len(assets)<CAPTURE_MAX_ASSETS:
                            raw=candidate['inline'].encode()
                            if len(raw)<=MAX_UPLOAD_BYTES and asset_bytes+len(raw)<=ARTIFACT_MAX_BYTES:
                                name='inline-'+str(len(assets)+1)+'.svg';asset_bytes+=len(raw)
                                artifact=import_bytes(job['workspace'],raw,name,'asset')
                                assets[candidate['url']]={'artifact':artifact,'kind':candidate['kind'],'url':candidate['url'],'filename':name}
                    if len(assets)>=CAPTURE_MAX_ASSETS:problems.append({'page':page_id,'width':width,'message':'Asset candidate limit reached; uncaptured assets remain in the DOM snapshot'})
                    data['media_queries']=sorted(set(data['media_queries']))
                    for candidate in media_widths(data['media_queries']):
                        if candidate not in done and candidate not in pending:
                            if len(done)+len(pending)<CAPTURE_MAX_WIDTHS:pending.append(candidate)
                            else:problems.append({'page':page_id,'message':f'Breakpoint {candidate}px exceeds capture width bound'})
                    files[prefix+'.json']=json.dumps(data,ensure_ascii=False).encode()
                    record['views'].append({'width':width,'dom':prefix+'.html','data':prefix+'.json','screenshot':prefix+'.png'})
                    problems.extend({'page':page_id,'width':width,'message':p} for p in data['problems'])
                    if sum(map(len,files.values()))>ARTIFACT_MAX_BYTES:raise ValueError('Capture exceeds artifact size bound')
                except Error as exc:
                    problems.append({'page':page_id,'width':width,'message':str(exc)[:500]})
                finally:context.close()
    details={'pages':pages,'problems':problems,'assets':list(assets.values())}
    artifact=import_bundle(job['workspace'],files,'capture',details)
    return {'artifact':artifact,**details}


def main():
    try:print(json.dumps(collect(read_json(Path(sys.argv[1])))));return 0
    except Exception as exc:print(json.dumps({'error':str(exc)}));return 2


if __name__=='__main__':raise SystemExit(main())
