"""Isolated, bounded browser capture; no state is published until capture completes."""
import json
import asyncio
import html
import re
from pathlib import Path
import sys
from urllib.parse import urlsplit, unquote, urljoin
from ..config import (IngestConfig, CAPTURE_MAX_NODES, CAPTURE_MAX_TEXT, CAPTURE_MAX_WIDTHS, CAPTURE_MAX_REDIRECTS,
                      CAPTURE_MAX_ASSETS, ARTIFACT_MAX_BYTES, MAX_UPLOAD_BYTES, CHECK_VIEWPORT_HEIGHT, CAPTURE_MAX_REQUESTS)
from ..language.properties import TOKEN_PROPERTIES, KEYWORDS
from ..storage import read_json
from . import import_bytes
from .capture import public_url, media_widths, anonymous_headers
from .capture_output import publish_capture
from .media_ready import prepare_media
from .media import selected_responses
from .runtime import async_chromium, watch_parent, read_job


async def collect(job):
    from playwright.async_api import Error
    settings=IngestConfig(**job.get('settings',{}));timeout_ms=settings.timeout_ms
    files={}; pages=[]; problems=[]; assets={}; asset_bytes=0
    async with async_chromium(timeout_ms) as (browser,requests):
        for number,url in enumerate(job['urls'],1):
            page_id=f'page-{number}'; record={'id':page_id,'url':url,'views':[]};pages.append(record)
            pending=list(job['widths']);done=set()
            while pending:
                width=pending.pop(0)
                if width in done:continue
                done.add(width)
                context=await browser.new_context(viewport={'width':width,'height':CHECK_VIEWPORT_HEIGHT},service_workers='block',accept_downloads=False)
                context.set_default_timeout(timeout_ms)
                def problem(message):
                    finding={'page':page_id,'width':width,'message':message}
                    if finding not in problems:problems.append(finding)
                async def route(request_route):
                    request=request_route.request
                    try:
                        if request.method not in {'GET','HEAD'}:raise ValueError('Non-read request blocked')
                        public_url(request.url)
                        original_headers=await request.all_headers()
                        headers=anonymous_headers(original_headers)
                        if len(headers)!=len(original_headers):
                            problem('Credentials refused: cookie and authorization headers were not sent')
                        headers={key:value for key,value in headers.items()
                                 if key.lower() not in {'host','content-length','connection'}}
                        # Cookie is a forbidden override in route.continue_. Fetch in
                        # a separate empty cookie jar instead, and do not follow redirects
                        # until their destination has passed the same URL checks.
                        destination=request.url
                        for hop in range(CAPTURE_MAX_REDIRECTS+1):
                            fetcher=await requests.new_context(timeout=timeout_ms)
                            try:
                                response=await fetcher.fetch(destination,method=request.method,headers=headers,
                                                   timeout=timeout_ms,max_redirects=0,max_retries=0)
                                response_headers=response.headers;status=response.status
                                if status in {301,302,303,307,308} and response_headers.get('location'):
                                    destination=public_url(urljoin(response.url,response_headers['location']))
                                    if hop==CAPTURE_MAX_REDIRECTS:raise ValueError('Capture redirect limit reached')
                                    continue
                                if int(response_headers.get('content-length','0'))>MAX_UPLOAD_BYTES:
                                    raise ValueError('Response exceeds capture byte limit')
                                body=await response.body()
                                if len(body)>MAX_UPLOAD_BYTES:raise ValueError('Response exceeds capture byte limit')
                                break
                            finally:await fetcher.dispose()
                        if destination!=request.url:
                            # Never forward a 3xx: Chromium bypasses the route handler
                            # for that chain. Preserve relative document resources using
                            # the final URL, and expose the remaining location limitation.
                            if request.resource_type=='document' and 'text/html' in response_headers.get('content-type',''):
                                encoding=re.search(r'charset=([^;\s]+)',response_headers.get('content-type',''))
                                markup=body.decode(encoding.group(1).strip('"\'') if encoding else 'utf-8',errors='replace')
                                base=re.search(r'<base\b[^>]*\bhref\s*=\s*(["\'])(.*?)\1',markup,re.I)
                                base_url=urljoin(destination,html.unescape(base.group(2))) if base else destination
                                tag='<base href="'+html.escape(base_url,quote=True)+'">'
                                head=re.search(r'<head\b[^>]*>',markup,re.I)
                                position=head.end() if head else 0
                                body=(markup[:position]+tag+markup[position:]).encode()
                                response_headers['content-type']='text/html; charset=utf-8'
                                problem('Redirect captured at '+destination+'; document resources use that base, while script location retains the requested URL')
                            elif request.resource_type=='stylesheet':
                                problem('Redirected stylesheet may resolve relative resources differently: '+destination)
                        if status in {401,403}:problem('Authentication is unavailable; HTTP '+str(status))
                        await request_route.fulfill(status=status,body=body,headers={
                                key:value for key,value in response_headers.items()
                                if key.lower() not in {'set-cookie','set-cookie2','content-encoding','content-length','transfer-encoding'}})
                    except (ValueError,LookupError,OSError,Error) as exc:
                        problem('Request blocked: '+str(exc)[:300])
                        await request_route.abort()
                pending_routes=set();slots=asyncio.Semaphore(CAPTURE_MAX_REQUESTS);closing=False
                async def bounded_route(request_route):
                    task=asyncio.current_task();pending_routes.add(task)
                    try:
                        async with slots:
                            if closing:await request_route.abort()
                            else:await route(request_route)
                    except Error:
                        if not closing:raise
                    finally:pending_routes.discard(task)
                await context.route('**/*',bounded_route)
                async def websocket(socket_route):
                    problem('WebSocket request refused: capture only permits unauthenticated HTTP(S)')
                    await socket_route.close(code=1008,reason='Capture only permits HTTP(S)')
                await context.route_web_socket('**/*',websocket)
                page=await context.new_page();responses=[]
                page.on('response',lambda response:responses.append(response) if response.request.resource_type in {'font','image','stylesheet'} else None)
                try:
                    response=await page.goto(url,wait_until='domcontentloaded',timeout=timeout_ms)
                    if response and response.status>=400:problems.append({'page':page_id,'width':width,'message':f'HTTP {response.status}'})
                    readiness=await prepare_media(page,timeout_ms)
                    properties=sorted((TOKEN_PROPERTIES.keys()|KEYWORDS.keys()|{'padding-top','padding-right','padding-bottom','padding-left','margin-top','margin-bottom','border-top-width','border-top-color','border-top-left-radius','row-gap','column-gap','position','grid-template-columns','box-shadow'})-{'surface'})
                    data=await page.evaluate(Path(__file__).with_name('capture.js').read_text(),{'properties':properties,'maxNodes':CAPTURE_MAX_NODES,'maxText':CAPTURE_MAX_TEXT})
                    data['stats']['media_readiness']=readiness['stats']
                    data['notes'].extend(readiness['notes']);data['problems'].extend(readiness['problems'])
                    prefix=f'{page_id}/{width}'
                    dom=(await page.content()).encode()
                    if len(dom)>MAX_UPLOAD_BYTES:
                        problems.append({'page':page_id,'width':width,'message':'DOM exceeds artifact size bound'});dom=dom[:MAX_UPLOAD_BYTES]
                    files[prefix+'.html']=dom
                    files[prefix+'.png']=await page.screenshot(full_page=True,animations='disabled',timeout=timeout_ms)
                    for response in selected_responses(responses,data['candidates']):
                        try:
                            if not response.ok:continue
                            body=await response.body()
                            if not body or len(body)>MAX_UPLOAD_BYTES:continue
                            if response.request.resource_type=='stylesheet':
                                css=body.decode('utf-8',errors='replace')
                                data['media_queries']+=re.findall(r'@media\s+([^{}]+)',css)
                                for block in re.findall(r'@font-face\s*\{([^{}]+)\}',css):
                                    declarations=dict(re.findall(r'([\w-]+)\s*:\s*([^;]+)',block))
                                    data['font_faces'].append({'family':declarations.get('font-family','').strip(),
                                        'weight':declarations.get('font-weight','400').strip(),'style':declarations.get('font-style','normal').strip(),
                                        'src':' '.join(urljoin(response.url,u) for u in re.findall(r'url\([\"\']?([^\"\')]+)',declarations.get('src','')))})
                                continue
                            if response.url in assets:continue
                            if len(assets)>=CAPTURE_MAX_ASSETS:continue
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
                    if len(assets)>=CAPTURE_MAX_ASSETS and any(c['url'] not in assets for c in data['candidates']):problems.append({'page':page_id,'width':width,'message':'Asset candidate limit reached; uncaptured assets remain in the DOM snapshot'})
                    data['media_queries']=sorted(set(data['media_queries']))
                    for candidate in media_widths(data['media_queries']):
                        if candidate not in done and candidate not in pending:
                            if len(done)+len(pending)<CAPTURE_MAX_WIDTHS:pending.append(candidate)
                            else:problems.append({'page':page_id,'width':width,'message':f'Breakpoint {candidate}px exceeds capture width bound'})
                    files[prefix+'.json']=json.dumps(data,ensure_ascii=False).encode()
                    view={'width':width,'dom':prefix+'.html','data':prefix+'.json','screenshot':prefix+'.png'}
                    if job.get('injected_css'):
                        await page.add_style_tag(content=job['injected_css'])
                        # CSS and font bytes are inline; no second network/cookie path.
                        await asyncio.wait_for(page.evaluate('document.fonts.ready.then(() => true)'),timeout=timeout_ms/1000)
                        view['injected']=prefix+'-injected.png'
                        files[view['injected']]=await page.screenshot(full_page=True,animations='disabled',timeout=timeout_ms)
                    record['views'].append(view)
                    problems.extend({'page':page_id,'width':width,'message':p} for p in data['problems'])
                    if sum(map(len,files.values()))>ARTIFACT_MAX_BYTES:raise ValueError('Capture exceeds artifact size bound')
                except Error as exc:
                    problems.append({'page':page_id,'width':width,'message':str(exc)[:500]})
                finally:
                    closing=True
                    tasks=list(pending_routes)
                    for task in tasks:task.cancel()
                    if tasks:await asyncio.gather(*tasks,return_exceptions=True)
                    await context.close()
    return publish_capture(job['workspace'],files,pages,problems,list(assets.values()))


def main():
    watch_parent()
    try:print(json.dumps(asyncio.run(collect(read_job(Path(sys.argv[1]))))));return 0
    except Exception as exc:print(json.dumps({'error':str(exc)}));return 2


if __name__=='__main__':raise SystemExit(main())
