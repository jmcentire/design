"""Bounded Chromium fidelity screenshots. All input is local immutable capture data."""
import json
from pathlib import Path
import sys
from ..artifacts.runtime import chromium, watch_parent, read_job
from ..checks.browser import prepare
from ..config import IngestConfig,CHECK_VIEWPORT_HEIGHT,CAPTURE_MAX_NODES,CAPTURE_MAX_TEXT
from ..language.properties import TOKEN_PROPERTIES,KEYWORDS
from ..storage import inside,read_json
from .fidelity import compare
from .documents import read_document
from .sources import image_colors


def render(job):
    settings=IngestConfig(**job.get('settings',{}));timeout_ms=settings.timeout_ms
    pairs=[];issues=[]
    with chromium(timeout_ms=timeout_ms) as browser:
        for pair in job['pairs']:
            context=browser.new_context(java_script_enabled=False,viewport={'width':pair['width'],'height':CHECK_VIEWPORT_HEIGHT})
            context.set_default_timeout(timeout_ms)
            context.route('**/*',lambda route:route.continue_() if route.request.url.startswith(('file:','data:')) else route.abort())
            try:
                page=context.new_page();prepare(page,inside(job['output'],pair['html']),timeout_ms)
                page.screenshot(path=str(inside(job['output'],pair['reconstruction'])),full_page=True,animations='disabled',timeout=timeout_ms)
                properties=sorted((TOKEN_PROPERTIES.keys()|KEYWORDS.keys()|{'padding-top','padding-right','padding-bottom','padding-left','margin-top','margin-bottom','border-top-color','border-top-left-radius','row-gap','column-gap'})-{'surface'})
                actual=page.evaluate((Path(__file__).parents[1]/'artifacts/capture.js').read_text(),{'properties':properties,'maxNodes':CAPTURE_MAX_NODES,'maxText':CAPTURE_MAX_TEXT})
                facts=None
                if pair['source']:
                    source=read_document(inside(job['root'],pair['source']));facts,differences=compare(source,actual,settings,job.get('palette'))
                    issues.extend(f'{pair["page"]}@{pair["width"]}: '+d for d in differences)
                else:
                    colors=image_colors(inside(job['output'],pair['capture']).read_bytes())
                    facts,differences=compare({'nodes':[{'styles':{'color':c}} for c in colors]},actual,settings,job.get('palette'))
                    facts['spacing_base']['source']=None
                    facts['divergences']=[item for item in facts['divergences'] if not item['pointer'].startswith('/spacing_base/')]
                    issues.extend(f'{pair["page"]}@{pair["width"]}: '+d for d in differences if not d.startswith('Spacing'))
                    issues.append(f'{pair["page"]}@{pair["width"]}: image reference lacks DOM type and spacing measurements; review visually')
                pairs.append({k:v for k,v in pair.items() if k!='source'}|{'facts':facts})
            finally:context.close()
    return {'pairs':pairs,'issues':issues}


def main():
    watch_parent()
    try:print(json.dumps(render(read_job(Path(sys.argv[1])))));return 0
    except Exception as exc:print(json.dumps({'error':str(exc)}));return 2


if __name__=='__main__':raise SystemExit(main())
