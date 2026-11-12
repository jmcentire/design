"""The contract a site builder and an independent tester each need, from one language version.

Three artifacts, all derived by the same renderer and resolver the library uses:
- CONTRACT.md and markup/ tell the builder which markup to write and which values exist.
- expected.json is the tester's oracle: resolved treatments and the closed set.
The builder must not receive expected.json; the tester must not receive the build.
"""
import json
from ..language.resolver import resolve
from ..language.tokens import Tokens
from ..render.html import SampleRenderer
from ..verify.membership import ClosedSet
from ..vocabulary import slot_map
from .adapters import custom_property, tailwind_variables

FOLDER = 'kinbase-design'
ORACLE = FOLDER + '/expected.json'


def treatments(document, vocabulary):
    """Resolved properties per scope: every state and breakpoint that differs from the default."""
    tokens = Tokens(document['style'])
    breakpoints = sorted((tokens.breakpoint(path.removeprefix('breakpoint.')), path.removeprefix('breakpoint.'))
                         for path in tokens.nodes if path.startswith('breakpoint.'))
    result = {}
    for construct, contract in vocabulary['constructs'].items():
        for scope in [construct] + [construct + '.' + slot for slot in slot_map(contract)]:
            def values(state, breakpoint=None):
                return {name: entry['value'] for name, entry in resolve(document, vocabulary, scope, state, breakpoint)['properties'].items()}
            base = values('default')
            entry = {'default': base}
            for state in contract['states']:
                if state != 'default' and values(state) != base:
                    entry[state] = values(state)
            for _, name in breakpoints:
                if values('default', name) != base:
                    entry['default@' + name] = values('default', name)
            result[scope] = entry
    return result, {name: width for width, name in breakpoints}


def expected(document, vocabulary, reference):
    resolved, breakpoints = treatments(document, vocabulary)
    closed = ClosedSet(document)
    return {'language': reference, 'vocabulary': vocabulary['version'], 'breakpoints': breakpoints, 'treatments': resolved,
            'closed_set': {'colors': {path: value for value, path in closed.colors.items()},
                           'font_families': {path: family for family, path in closed.families.items()},
                           'font_weights': {path: weight for weight, path in closed.weights.items()},
                           **{scale: {path: number for number, path in values.items()} for scale, values in closed.dimensions.items()}},
            'contracts': {name: {'root': contract['root'], 'states': contract['states'],
                                 'reading_order': contract['contract']['reading-order'],
                                 'slots': [{key: slot[key] for key in ('id', 'element', 'required', 'role', 'emphasis', 'kind')}
                                           for slot in contract['slots']]}
                          for name, contract in vocabulary['constructs'].items()}}


def markup(document, vocabulary, samples):
    renderer = SampleRenderer(document, vocabulary, samples)
    return {name: renderer.construct(name) + '\n' for name in vocabulary['constructs']}


def contract_text(document, vocabulary, reference, adapter, target_dir, export_names, command):
    tokens = Tokens(document['style'])
    variables = tailwind_variables(tokens) if adapter.startswith('dtcg-tailwind') else {name: custom_property(name) for name in tokens.nodes}
    sheets = [name for name in export_names if name.endswith('.css')]
    lines = [f'# Design contract: {reference}', '',
             f'This site renders the Kinbase Design language `{reference}` (export adapter `{adapter}`).',
             'A page fits the design when it uses the language\'s constructs for what they are and takes every',
             'other value from the language. The check at the end decides; nothing here is a matter of taste.', '',
             '## Load the language', '',
             'Load these stylesheets, in this order, on every page:', '']
    lines.extend(f'- `{target_dir}/{name}`' for name in sorted(sheets, key=lambda name: (name != 'tokens.css', name)))
    lines.extend(['', f'Assets are in `{target_dir}/assets/`. The markup files reference them as `assets/...`; serve or rewrite',
                  'that path so each image loads.', '',
                  '## Rules', '',
                  '1. **Use a construct for what it is.** Copy its markup from `' + FOLDER + '/markup/<construct>.html`: the same',
                  '   root element, `data-kd-construct`, and one element per slot carrying `data-kd-slot="<construct>.<slot>"`.',
                  '   The text, links, form action, ids and accessible names are the page\'s own. The elements, the hooks',
                  '   and their order are not.',
                  '2. **Add no styling to a slot.** The exported stylesheet treats it. A state is `data-kd-state` on the root.',
                  '3. **Outside constructs, use only the language\'s values.** Layout wrappers may set spacing, colour, type and',
                  '   radius only through the custom properties below. A raw value is a finding even when it looks close.',
                  '4. **Do not invent constructs or slots.** If the page needs something no construct expresses, stop and say',
                  '   so: that is a Vocabulary decision, not a builder\'s.',
                  '5. **Every task completes with server-rendered HTML alone.** JavaScript may only enhance.', '',
                  '## Constructs', '',
                  '| Construct | Root | Required slots | Optional slots | States |', '| --- | --- | --- | --- | --- |'])
    for name, contract in vocabulary['constructs'].items():
        required = ', '.join(slot['id'] for slot in contract['slots'] if slot['required']) or 'none'
        optional = ', '.join(slot['id'] for slot in contract['slots'] if not slot['required']) or 'none'
        lines.append(f'| `{name}` | `<{contract["root"]}>` | {required} | {optional} | {", ".join(contract["states"])} |')
    lines.extend(['', '## Values', '', '| Custom property | Value | Token |', '| --- | --- | --- |'])
    for name in sorted(tokens.nodes):
        lines.append(f'| `{variables[name]}` | `{tokens.evaluate(name)[1]}` | `{name}` |')
    lines.extend(['', '## The check', '',
                  'Run against the built page. It renders the page in Chromium at 320, 768 and 1280 CSS px and fails on any',
                  'broken construct contract, any computed style that differs from the language\'s resolved treatment, any',
                  'value outside the language, and any contrast, clipping, reflow, target-size or focus failure.', '',
                  '```sh', command, '```', '',
                  'A justified exception belongs in the site\'s `kinbase-design.inventory.json` as',
                  '`{"scope": ..., "rule": ..., "reason": ...}`. It is reported, never hidden.', ''])
    return '\n'.join(lines)


def files(document, vocabulary, samples, reference, adapter, target_dir, export_names, command):
    """The committed contract pack, keyed by path under the target directory."""
    pack = {FOLDER + '/CONTRACT.md': contract_text(document, vocabulary, reference, adapter, target_dir, export_names, command).encode(),
            ORACLE: (json.dumps(expected(document, vocabulary, reference), ensure_ascii=False, indent=2, sort_keys=True) + '\n').encode()}
    for name, html in markup(document, vocabulary, samples).items():
        pack[f'{FOLDER}/markup/{name}.html'] = html.encode()
    return pack
