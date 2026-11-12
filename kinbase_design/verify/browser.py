"""Render a site's own pages and judge them against a language. Bounded worker only."""
from pathlib import Path
from ..checks.browser import BrowserUnavailable, axe_contrast, decode_backgrounds, keyboard, observe, prepare
from ..checks.evaluate import Evaluation, breakpoint_at
from ..checks.grouping import group_rendered
from ..config import CHECK_TIMEOUT_MS, CHECK_VIEWPORT_HEIGHT
from . import structure
from .membership import ClosedSet, RULES, declared_properties, observations, token_pointer


class AnyPage(dict):
    """A declared truncation is satisfied when its full text is on any verified page."""

    def get(self, key, default=''):
        return ' '.join(self.values()) or default


def membership(evaluation, closed, document, vocabulary, page, width, snapshot):
    breakpoint = breakpoint_at(document, width)
    for node in snapshot['nodes']:
        declared = declared_properties(document, vocabulary, node, breakpoint)
        for prop, (observed, path, nearest, distance) in observations(node, closed, declared):
            hint = (f'; nearest is {path} {nearest}' + (f' (ΔE {distance})' if distance is not None else '')) if path else ''
            finding = evaluation.add(RULES[prop], page, width, node['target'],
                                     measured={'property': prop, 'value': observed, 'element': node['path']}, threshold=nearest,
                                     expected='a value the language holds',
                                     message=f'{prop} {observed} is not in the language{hint}',
                                     pointer=token_pointer(path), context={'property': prop, 'value': observed})
            if path is None:
                finding['observed'] = None  # The language holds no value of this kind at all.


def inspect(document, vocabulary, pages, output, widths, javascript=True, preview=None):
    from playwright.sync_api import sync_playwright, Error, TimeoutError
    evaluation = Evaluation(document, vocabulary)
    closed = ClosedSet(document)
    contract, summary = [], {'text_elements': 0, 'hooked_text_elements': 0, 'constructs': {}}
    try:
        engine = sync_playwright().start()
        executable = Path(engine.chromium.executable_path)
        if not executable.is_file():
            raise BrowserUnavailable('Chromium executable is not installed: ' + str(executable))
        browser = engine.chromium.launch(headless=True, timeout=CHECK_TIMEOUT_MS)
    except Exception as exc:
        if 'engine' in locals():
            engine.stop()
        raise BrowserUnavailable('Chromium is unavailable or cannot start: ' + str(exc)[:1000]) from exc
    try:
        if preview:
            # The language's own preview is the reference rendering for its closed set.
            for width in widths:
                context = browser.new_context(java_script_enabled=False, device_scale_factor=1,
                                              viewport={'width': width, 'height': CHECK_VIEWPORT_HEIGHT})
                context.set_default_timeout(CHECK_TIMEOUT_MS)
                try:
                    for filename in vocabulary['context']['pages']:
                        page = context.new_page()
                        prepare(page, Path(preview) / filename)
                        for node in observe(page, vocabulary)['nodes']:
                            closed.learn(node)
                        page.close()
                finally:
                    context.close()
        for width in widths:
            # A fresh context holds no cookies, storage or credentials for any site.
            context = browser.new_context(java_script_enabled=javascript, service_workers='block', device_scale_factor=1,
                                          viewport={'width': width, 'height': CHECK_VIEWPORT_HEIGHT})
            context.set_default_timeout(CHECK_TIMEOUT_MS)
            try:
                snapshots = {}
                for item in pages:
                    page = context.new_page()
                    name = item['id']
                    try:
                        prepare(page, item['target'])
                        if javascript:
                            decode_backgrounds(page)
                        seen = page.evaluate(Path(__file__).with_name('structure.js').read_text())
                        for finding in structure.check(vocabulary, name, seen):
                            if finding not in contract:
                                contract.append(finding)
                        snapshot = observe(page, vocabulary)
                        for node in snapshot['nodes']:
                            if node['slot'] and not structure.resolvable(vocabulary, node):
                                node['slot'] = None  # Reported as a contract finding; nothing to resolve.
                        snapshots[name] = (page, snapshot)
                        if width == widths[0]:
                            texts = [node for node in snapshot['nodes'] if node['visible'] and node['directText'].strip()]
                            summary['text_elements'] += len(texts)
                            summary['hooked_text_elements'] += sum('.' in node['target'] for node in texts)
                            for found in seen['constructs']:
                                summary['constructs'][found['construct']] = summary['constructs'].get(found['construct'], 0) + 1
                        page.screenshot(path=str(Path(output) / f'{name}@{width}.png'), full_page=True, animations='disabled',
                                        timeout=CHECK_TIMEOUT_MS)
                    except (Error, TimeoutError) as exc:
                        evaluation.context = None
                        evaluation.add('render', name, width, measured=str(exc)[:1000], threshold=f'{CHECK_TIMEOUT_MS}ms',
                                       expected='the page loads and can be inspected within the configured bounds')
                        page.close()
                full_text = AnyPage({name: ' '.join(' '.join(n['directText'] for n in snapshot['nodes'] if n['visible'] and not n['clipped']).split())
                                     for name, (_, snapshot) in snapshots.items()})
                for name, (page, snapshot) in snapshots.items():
                    try:
                        evaluation.snapshot(name, width, snapshot, full_text)
                        membership(evaluation, closed, document, vocabulary, name, width, snapshot)
                        if javascript:
                            axe_contrast(page, evaluation, name, width, snapshot)
                            keyboard(page, snapshot, evaluation, name, width, output)
                    except (Error, TimeoutError) as exc:
                        evaluation.context = None
                        evaluation.add('render', name, width, measured=str(exc)[:1000], threshold=f'{CHECK_TIMEOUT_MS}ms',
                                       expected='the page loads and can be inspected within the configured bounds')
                    finally:
                        page.close()
            finally:
                context.close()
    finally:
        browser.close()
        engine.stop()
    rendered = group_rendered(evaluation.findings)
    for finding in rendered:
        finding['source'] = 'site'
    return contract + rendered, summary
