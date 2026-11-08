"""Chromium boundary. This module runs only in the bounded check worker."""
from pathlib import Path
import logging
import time
from ..config import (CHECK_TIMEOUT_MS, CHECK_VIEWPORT_HEIGHT, CHECK_PIXEL_TOLERANCE,
                      CHECK_TARGET_SIZE, CHECK_MAX_TAB_STEPS)
from ..language.properties import TOKEN_PROPERTIES, KEYWORDS, LAYOUT_PROPERTIES
from .evaluate import Evaluation
from .math import color, contrast, effective_background
from .grouping import group_rendered, observation_context
from .native import unmodified_native
from ..config import CHECK_NON_TEXT_CONTRAST

log = logging.getLogger(__name__)


class BrowserUnavailable(RuntimeError):
    pass


def prepare(page, file, timeout_ms=CHECK_TIMEOUT_MS):
    page.goto(file.as_uri(),wait_until='load',timeout=timeout_ms)
    # DevTools can inspect a no-JS document. Poll native readiness from Python,
    # rather than relying on page timers in the JavaScript-disabled context.
    page.evaluate("() => {for(const image of document.images) image.loading='eager';}")
    deadline=time.monotonic()+timeout_ms/1000
    while not page.evaluate("() => document.fonts.status!=='loading' && [...document.images].every(image=>image.complete)"):
        if time.monotonic()>=deadline:
            from playwright.sync_api import TimeoutError
            raise TimeoutError('Asset readiness timed out')
        time.sleep(.05)


def decode_backgrounds(page):
    page.evaluate("""async timeout => {
      const urls=new Set();
      for(const element of document.querySelectorAll('*')) {
        const value=getComputedStyle(element).backgroundImage;
        if(value.startsWith('url('))urls.add(value.slice(4,-1).trim().replace(/^['"]|['"]$/g,''));
      }
      const load=async()=>Object.fromEntries(await Promise.all([...urls].map(async url=>{
        const image=new Image();image.src=url;
        try {await image.decode();return [url,image.naturalWidth>0&&image.naturalHeight>0];}
        catch {return [url,false];}
      })));
      window.__kdBackgroundImages=await Promise.race([load(),new Promise((_,reject)=>setTimeout(()=>reject(new Error('Background image decoding timed out')),timeout))]);
    }""",CHECK_TIMEOUT_MS)


def observe(page, vocabulary=None):
    source = Path(__file__).with_name('observe.js').read_text().replace(
        '__NATIVE_CONTROL__', Path(__file__).with_name('native-control.js').read_text())
    snapshot = page.evaluate(source,{
        'properties':sorted((TOKEN_PROPERTIES.keys() | KEYWORDS.keys() | LAYOUT_PROPERTIES)-{'surface'}),
        'controlSlots':[construct+'.'+slot['id'] for construct,contract in (vocabulary or {}).get('constructs',{}).items()
                        for slot in contract['slots'] if slot['kind']=='control'],
        'mediaSlots':[construct+'.'+slot['id'] for construct,contract in (vocabulary or {}).get('constructs',{}).items()
                      for slot in contract['slots'] if slot['kind']=='media'],
        'tolerance':CHECK_PIXEL_TOLERANCE,'targetSize':CHECK_TARGET_SIZE})
    for node in snapshot['nodes']:
        node['nativeControl'] = unmodified_native(node.pop('nativeAppearance'))
    return snapshot


def focus_style(locator):
    result = locator.evaluate('''e=>{const nativeControl=__NATIVE_CONTROL__;const s=getComputedStyle(e);return {
      nativeAppearance:nativeControl(e),
      outline:s.outline,outlineWidth:parseFloat(s.outlineWidth),outlineStyle:s.outlineStyle,
      outlineColor:s.outlineColor,shadow:s.boxShadow,border:s.border,borderColor:s.borderTopColor,background:s.backgroundColor,
      backgrounds:(()=>{const layers=[];for(let p=e.parentElement;p;p=p.parentElement){const c=getComputedStyle(p);layers.push({color:c.backgroundColor,image:c.backgroundImage,uncertain:parseFloat(c.opacity)<1});}return layers;})()
    }}'''.replace('__NATIVE_CONTROL__', Path(__file__).with_name('native-control.js').read_text()))
    result['nativeControl'] = unmodified_native(result.pop('nativeAppearance'))
    return result


def keyboard(page, snapshot, evaluation, filename, width, output):
    candidates=[n for n in snapshot['nodes'] if n['interactive'] and n['visible'] and not n['disabled']]
    if len(candidates)>CHECK_MAX_TAB_STEPS:
        evaluation.add('keyboard',filename,width,expected='keyboard audit within configured bound',measured=len(candidates),threshold=CHECK_MAX_TAB_STEPS)
        return
    before={n['index']:focus_style(page.locator(f'[data-kd-check="{n["index"]}"]')) for n in candidates}
    page.evaluate("() => {document.body.tabIndex=-1;document.body.focus();document.body.removeAttribute('tabindex');}")
    visited=[]
    for expected in candidates:
        evaluation.context=observation_context(expected)
        page.keyboard.press('Tab')
        actual=page.evaluate("() => document.activeElement?.getAttribute('data-kd-check')")
        index=int(actual) if actual is not None else None
        visited.append(index)
        if index!=expected['index']:
            evaluation.add('keyboard',filename,width,expected['target'],criterion='keyboard reading order',
                           measured=index,threshold=expected['index'],expected='Tab reaches each interactive element in reading order')
        if index not in before:
            continue
        locator=page.locator(f'[data-kd-check="{index}"]')
        after=focus_style(locator)
        prior=before[index]
        indicator=(after['outlineWidth']>0 and after['outlineStyle'] not in {'none','hidden'} and after['outlineColor']!='rgba(0, 0, 0, 0)' and after['outline']!=prior['outline']) or any(after[k]!=prior[k] for k in ('shadow','border','background'))
        if indicator and not after['nativeControl']:
            evaluation.context=observation_context({'backgrounds':after['backgrounds']})
            foreground=color(after['outlineColor'] if after['outline']!=prior['outline'] and after['outlineWidth']>0 else after['background'] if after['background']!=prior['background'] else after['borderColor'] if after['border']!=prior['border'] else '')
            background=effective_background(after['backgrounds'])
            if foreground is None or background is None:
                finding=evaluation.add('non-text-contrast',filename,width,expected['target'],type='needs-review',criterion='WCAG 1.4.11',threshold=CHECK_NON_TEXT_CONTRAST,expected='review the focused indicator contrast')
            elif contrast(foreground,background)<CHECK_NON_TEXT_CONTRAST:
                finding=evaluation.add('non-text-contrast',filename,width,expected['target'],criterion='WCAG 1.4.11',measured=round(contrast(foreground,background),2),threshold=CHECK_NON_TEXT_CONTRAST,expected='focus indicator contrast at least 3:1')
            else:
                finding=None
            if finding:
                finding['screenshot']=filename.removesuffix('.html')+f'@{width}-focus-{index}.png'
                page.screenshot(path=str(Path(output)/finding['screenshot']),timeout=CHECK_TIMEOUT_MS)
        if not indicator:
            evaluation.add('focus-visible',filename,width,expected['target'],criterion='WCAG 2.4.7',measured=after,threshold='visible change',expected='a measurable outline, shadow, border or background focus indicator')
    for node in candidates:
        if node['index'] not in visited:
            evaluation.add('keyboard',filename,width,node['target'],measured='unreachable',threshold='reachable',expected='target reachable by Tab',context=observation_context(node))
    evaluation.context=None


def axe_contrast(page, evaluation, filename, width, snapshot):
    page.add_script_tag(path=str(Path(__file__).parent/'vendor/axe.min.js'))
    result=page.evaluate('''async timeout => Promise.race([
      axe.run(document,{runOnly:{type:'rule',values:['color-contrast']}}),
      new Promise((_,reject)=>setTimeout(()=>reject(new Error('axe contrast timed out')),timeout))
    ])''',CHECK_TIMEOUT_MS)
    # Equivalent computed alpha-composition supplies ratios. Axe additionally catches
    # layered/rendering cases our simple evaluator cannot safely classify.
    for item in result.get('incomplete',[]):
        for node in item.get('nodes',[]):
            locator=page.locator(node['target'][0])
            index=locator.get_attribute('data-kd-check') if locator.count() else None
            evaluation.context=observation_context(snapshot['nodes'][int(index)]) if index is not None else None
            target=locator.evaluate("e=>e.closest('[data-kd-slot]')?.dataset.kdSlot||e.closest('[data-kd-construct]')?.dataset.kdConstruct||'page'") if locator.count() else 'page'
            if not any(f['rule']=='contrast' and f['type']=='needs-review' and f['page']==filename and f['width']==width and f['target']==target for f in evaluation.findings):
                evaluation.add('contrast',filename,width,target,type='needs-review',criterion='WCAG 1.4.3',expected='review unresolved rendered contrast',message=node.get('failureSummary','Axe could not determine contrast'))
    for item in result.get('violations',[]):
        for node in item.get('nodes',[]):
            locator=page.locator(node['target'][0])
            index=locator.get_attribute('data-kd-check') if locator.count() else None
            evaluation.context=observation_context(snapshot['nodes'][int(index)]) if index is not None else None
            target=locator.evaluate("e=>e.closest('[data-kd-slot]')?.dataset.kdSlot||e.closest('[data-kd-construct]')?.dataset.kdConstruct||'page'") if locator.count() else 'page'
            if any(f['rule']=='contrast' and f['page']==filename and f['width']==width and f['target']==target for f in evaluation.findings):
                continue
            checks=node.get('any',[])+node.get('all',[])+node.get('none',[])
            data=next((c.get('data') for c in checks if isinstance(c.get('data'),dict) and c['data'].get('contrastRatio') is not None),{})
            ratio=data.get('contrastRatio')
            threshold=data.get('expectedContrastRatio')
            try: threshold=float(str(threshold).split(':')[0])
            except (ValueError,TypeError): threshold=None
            evaluation.add('contrast',filename,width,target,criterion='WCAG 1.4.3',measured=round(float(ratio),2) if ratio is not None else None,threshold=threshold,
                           expected='rendered text contrast meets WCAG',message=node.get('failureSummary','Axe detected insufficient contrast'))
    evaluation.context=None


def inspect(document, vocabulary, preview, output, widths):
    from playwright.sync_api import sync_playwright, Error, TimeoutError
    pages=list(vocabulary['context']['pages'])
    evaluation=Evaluation(document,vocabulary)
    try:
        engine=sync_playwright().start()
        executable=Path(engine.chromium.executable_path)
        if not executable.is_file():
            raise BrowserUnavailable('Chromium executable is not installed: '+str(executable))
        browser=engine.chromium.launch(headless=True,timeout=CHECK_TIMEOUT_MS)
    except Exception as exc:
        if 'engine' in locals(): engine.stop()
        raise BrowserUnavailable('Chromium is unavailable or cannot start: '+str(exc)[:1000]) from exc
    try:
        for width in widths:
            snapshots={}
            for js in (False,True):
                context=browser.new_context(java_script_enabled=js,viewport={'width':width,'height':CHECK_VIEWPORT_HEIGHT},device_scale_factor=1)
                context.set_default_timeout(CHECK_TIMEOUT_MS)
                try:
                    for filename in pages:
                        evaluation.context=None
                        page=context.new_page()
                        try:
                            prepare(page,Path(preview)/filename)
                            if js: decode_backgrounds(page)
                            snapshot=observe(page,vocabulary)
                            if not js:
                                snapshots[filename]=snapshot
                                page.screenshot(path=str(Path(output)/(filename.removesuffix('.html')+f'@{width}.png')),full_page=True,animations='disabled',timeout=CHECK_TIMEOUT_MS)
                                linked={l['href'].split('#')[0].split('?')[0] for l in snapshot['links'] if l['visible']}
                                if not snapshot['text'].strip() or not snapshot.get('contentPage') and not set(pages)<=linked:
                                    evaluation.add('no-js',filename,width,measured={'text':bool(snapshot['text'].strip()),'links':sorted(linked)},threshold=pages,expected='page renders and links to every preview page without JavaScript')
                                if filename=='states.html':
                                    expected={(c,s) for c,contract in vocabulary['constructs'].items() for s in contract['states']}
                                    absent=expected-{tuple(s) for s in snapshot['states']}
                                    if absent: evaluation.add('no-js',filename,width,measured=sorted(absent),threshold='all declared states',expected='all declared states depicted without JavaScript')
                            else:
                                full_text={name:' '.join(' '.join(n['directText'] for n in s['nodes'] if n['visible'] and not n['clipped']).split()) for name,s in snapshots.items()}
                                evaluation.snapshot(filename,width,snapshot,full_text)
                                axe_contrast(page,evaluation,filename,width,snapshot)
                                keyboard(page,snapshot,evaluation,filename,width,output)
                        except (Error,TimeoutError) as exc:
                            page.screenshot(path=str(Path(output)/(filename.removesuffix('.html')+f'@{width}.png')),full_page=True,timeout=CHECK_TIMEOUT_MS)
                            evaluation.add('render',filename,width,measured=str(exc)[:1000],threshold=f'{CHECK_TIMEOUT_MS}ms',expected='page and audit operations complete within configured bounds')
                        finally:
                            page.close()
                        log.info('check_page language=%s page=%s width=%d js=%s',document['id'],filename,width,js)
                finally:
                    context.close()
    finally:
        browser.close()
        engine.stop()
    evaluation.coverage(pages,widths)
    return group_rendered(evaluation.findings)
