"""Does the page's hooked markup honour each construct's semantic contract? Pure.

The Vocabulary owns these contracts, so every finding points into the Vocabulary file.
"""
import re
from ..findings import Finding, pointer
from ..vocabulary import slot_map

HEADING = re.compile(r'h[1-6]')


def slot_element(definition, observed):
    """Whether a rendered slot element is the contract's element, as the renderer writes it."""
    wanted, tag = definition['element'], observed['tag']
    if wanted in {'input', 'textarea'}:
        return tag == wanted or tag == 'label' and wanted in observed['contains']
    if definition['kind'] == 'media':
        return tag in {'img', 'a', 'span', 'figure', 'picture'}
    if HEADING.fullmatch(wanted):
        return bool(HEADING.fullmatch(tag))  # The level follows the page's own outline.
    return tag == wanted


def check(vocabulary, page, observed):
    """Findings for one page's constructs; also returns hooks that are safe to resolve."""
    file = f'vocabulary/{vocabulary["version"]}/vocabulary.json'
    findings = []
    def add(kind, rule, path, seen, expected, message, target):
        finding = Finding(kind, rule, file, path, seen, expected, message).to_dict()
        finding.update(page=page, target=target, source='site')
        findings.append(finding)
    constructs = vocabulary['constructs']
    for name in observed['orphans']:
        add('violation', 'site-slot', '/constructs', name, 'a slot inside its construct root',
            f'{name} is marked as a slot outside any data-kd-construct root', 'page')
    for item in observed['constructs']:
        name = item['construct']
        contract = constructs.get(name)
        if contract is None:
            add('violation', 'site-construct', '/constructs', name, 'a Vocabulary construct',
                f'{name} is not a Vocabulary construct; new constructs are a Vocabulary decision', 'page')
            continue
        base = pointer('constructs', name)
        if item['tag'] != contract['root']:
            add('violation', 'site-semantics', base + '/root', item['tag'], f'<{contract["root"]}>',
                f'{name} is rooted in <{item["tag"]}>; its contract requires <{contract["root"]}>', name)
        if item['state'] is not None and item['state'] not in contract['states']:
            add('violation', 'site-state', base + '/states', item['state'], 'a state this construct declares',
                f'{name} does not declare state {item["state"]}', name)
        slots, seen = slot_map(contract), {}
        for index, definition in enumerate(contract['slots']):
            seen[definition['id']] = index
        present = []
        for slot in item['slots']:
            owner, _, local = slot['slot'].partition('.')
            if owner != name or local not in slots:
                add('violation', 'site-slot', base + '/slots', slot['slot'], f'a slot of {name}',
                    f'{slot["slot"]} is not a slot of {name}', name)
                continue
            present.append(local)
            if not slot_element(slots[local], slot):
                add('violation', 'site-semantics', base + pointer('slots', seen[local], 'element'), slot['tag'],
                    f'<{slots[local]["element"]}>', f'{slot["slot"]} is a <{slot["tag"]}>; its contract requires <{slots[local]["element"]}>',
                    slot['slot'])
        for local, definition in slots.items():
            if present.count(local) > 1:
                add('violation', 'site-slot', base + pointer('slots', seen[local]), present.count(local), 'each slot at most once',
                    f'{name}.{local} appears {present.count(local)} times in one {name}', name + '.' + local)
            if definition['required'] and local not in present:
                add('missing', 'site-slot', base + pointer('slots', seen[local]), None, 'every required slot',
                    f'{name} is missing its required slot {local}', name + '.' + local)
        reading = [local for local in contract['contract']['reading-order'] if local in present]
        actual = list(dict.fromkeys(local for local in present if local in reading))
        if actual != reading:
            add('violation', 'site-semantics', base + '/contract/reading-order', actual, 'the declared reading order',
                f'{name} reads {", ".join(actual)}; its contract reads {", ".join(reading)}', name)
    return findings


def resolvable(vocabulary, node):
    """Whether a node's slot and state can be resolved; anything else was reported above."""
    owner, _, local = (node.get('slot') or '').partition('.')
    contract = vocabulary['constructs'].get(owner)
    return bool(contract and local in slot_map(contract) and node['state'] in contract['states'])
