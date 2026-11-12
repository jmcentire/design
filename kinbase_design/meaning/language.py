"""Carry mappings into a language draft, and check a language against them.

The draft goes through the ordinary ingest path: same validator, resolver, provenance
map and save operation. A mapping only decides which source token a role treatment names.
"""
from copy import deepcopy
import json
from ..artifacts import import_bytes
from ..findings import Finding, pointer, report, location
from ..ingest import draft as ingest_draft, summary
from ..ingest.documents import read_document, write_document
from ..ingest.provenance import complete, record_at, source
from ..ingest.staging import folder as draft_folder, load_draft, write_draft, stage
from ..language import validate
from ..language.properties import TOKEN_PROPERTIES, SPACE_PROPERTIES
from ..language.tokens import Tokens, ALIAS
from ..storage import inside, load_language
from ..vocabulary import load as load_vocabulary
from .graph import STANDING, certification, effective, load
from .sources import BASE, context_value, tree

TEXT_PROPERTIES = ('color', 'surface', 'font-size', 'font-family')
CONTROL_PROPERTIES = ('background-color', 'border-color')


def provenance_record(item):
    """The provenance of a role value placed by a mapping, by the mapping's standing."""
    shared = {'mapping': item['subject'], 'standing': item['status']}
    if item['status'] == 'certified':
        return {'kind': 'source', 'artifact': item['authority'], 'location': item['certified']['location'], **shared}
    if item['status'] == 'chosen':
        return {'kind': 'chosen', 'choice': 'meaning/' + item['decision'], **shared}
    return {'kind': 'inferred', 'method': 'Heuristic meaning mapping (uncertified candidate)',
            'inputs': [item['source']], **shared}


def assign(document, path, value):
    keys = [part.replace('~1', '/').replace('~0', '~') for part in path.split('/')[1:]]
    owner = document
    for key in keys[:-1]:
        owner = owner.setdefault(key, {})
    owner[keys[-1]] = value


def draft(library, workspace, corpus, language_id, context=None):
    document = load(workspace, corpus)
    context = context or (BASE if BASE in document['contexts'] else document['contexts'][0])
    if context not in document['contexts']:
        raise ValueError('Unknown context; this corpus has: ' + ', '.join(document['contexts']))
    styles = {path: entry for path, entry in document['tokens'].items() if path.startswith('css.')}
    artifacts = list(dict.fromkeys(entry['artifact'] for path, entry in document['tokens'].items() if path not in styles))
    if styles:
        derived = tree(styles, context)
        if derived:
            data = (json.dumps(derived, sort_keys=True, indent=2) + '\n').encode()
            artifacts.append(import_bytes(workspace, data, f'{corpus}-{context}.tokens.json', 'dtcg'))
    if not artifacts:
        raise ValueError('This context has no token the language schema can hold')
    ingest_draft(library, workspace, artifacts, language_id)
    root = draft_folder(workspace, language_id)
    working = load_draft(workspace, language_id)
    provenance = read_document(inside(root, 'provenance.json'))
    for path, entry in styles.items():
        target = pointer('style', *path.split('.'), '$value')
        if location(working, target)[0] != target:
            continue
        record = context_value(entry, context)
        origin = source(entry['artifact'], record['location'])
        for child in [key for key in provenance if key == target or key.startswith(target + '/')]:
            del provenance[child]
        # The derived token file is a transcription; the stylesheet stays the source.
        provenance[target] = ({'kind': 'inferred', 'method': 'CSS colour converted to sRGB hex', 'inputs': [origin]}
                              if record.get('converted') else origin)
    write_document(inside(root, 'provenance.json'), complete(working, provenance, artifacts))
    state = read_document(inside(root, 'state.json'))
    state['meaning'] = {'corpus': corpus, 'context': context, 'baseline': {}}
    write_document(inside(root, 'state.json'), state)
    return apply(library, workspace, corpus, language_id)


def placements(mappings, tokens, vocabulary):
    """Choose one token per role treatment: higher standing first, then fewer doubts."""
    usable = [item for subject, item in mappings.items()
              if item['meaning'] and 'state' not in item['meaning'] and subject in tokens.nodes]
    def rank(item):
        flags = item['candidate']['flags'] if item['status'] == 'candidate' else []
        return STANDING.index(item['status']), len(flags), item['subject']
    def pick(prop, role, emphases):
        pool = [item for item in usable if item['meaning']['property'] == prop]
        for wanted in (role, None):
            for emphasis in emphases:
                found = sorted((item for item in pool if item['meaning'].get('role') == wanted
                                and item['meaning'].get('emphasis') == emphasis), key=rank)
                if found:
                    return found
        return []
    placed, missing, collisions = {}, [], []
    families = [item for item in usable if item['meaning']['property'] == 'font-family']
    for role in vocabulary['roles']:
        for emphasis in vocabulary['emphasis']:
            for prop in TEXT_PROPERTIES + (CONTROL_PROPERTIES if role == 'control' else ()):
                if prop == 'color':
                    found = pick(prop, role, (emphasis,))
                elif prop == 'surface':
                    # One default surface for every emphasis: a ranked background is a
                    # different surface, not the pairing for muted text.
                    found = pick(prop, role, (None, 'neutral'))
                elif prop == 'font-family':
                    found = [item for item in families if item['meaning'].get('role') == role] or (families if len(families) == 1 else [])
                else:
                    found = [item for item in pick(prop, role, (emphasis, None)) if item['meaning'].get('role') == role]
                if found:
                    placed[pointer('roles', role, emphasis, prop)] = found[0]
                    if len(found) > 1 and prop in {'color', 'surface'}:
                        collisions.append((found[0]['subject'], [item['subject'] for item in found[1:]]))
                elif prop == 'color' and role not in {'media'}:
                    missing.append(emphasis)
    return placed, sorted(set(missing), key=vocabulary['emphasis'].index), collisions


def apply(library, workspace, corpus, draft_id):
    """Re-place role treatments from the corpus's current effective mappings."""
    root = draft_folder(workspace, draft_id)
    state = read_document(inside(root, 'state.json'))
    held = state.get('meaning')
    if not held or held['corpus'] != corpus:
        raise ValueError('This draft was not created from corpus ' + corpus)
    working = load_draft(workspace, draft_id)
    vocabulary = load_vocabulary(library, working['vocabulary'])
    provenance = read_document(inside(root, 'provenance.json'))
    # Start from the ingest treatment so a withdrawn mapping leaves nothing behind.
    for path, before in held['baseline'].items():
        if before['value'] is None:
            location(working, path.rsplit('/', 1)[0])[1].pop(path.rsplit('/', 1)[1], None)
        else:
            assign(working, path, deepcopy(before['value']))
        if before['value'] is None or before['provenance'] is None:
            provenance.pop(path, None)
        else:
            provenance[path] = deepcopy(before['provenance'])
    mappings = effective(workspace, vocabulary, corpus)
    placed, missing, collisions = placements(mappings, Tokens(working['style']), vocabulary)
    applied = []
    for path, item in placed.items():
        if (record_at(provenance, path) or {}).get('kind') == 'source':
            continue  # A fixed input (a supplied value or a Kinbase standard) already owns this value.
        found, value = location(working, path)
        held['baseline'].setdefault(path, {'value': value if found == path else None, 'provenance': record_at(provenance, path)})
        assign(working, path, '{' + item['subject'] + '}')
        provenance[path] = provenance_record(item)
        applied.append({'pointer': path, 'subject': item['subject'], 'standing': item['status']})
    with stage(library, workspace, draft_id, working) as staged:
        result = validate(staged, draft_id)
        if not result['accepted']:
            raise ValueError('The draft does not satisfy language validation: ' + '; '.join(
                f['rule'] + ' ' + f['pointer'] + ' ' + f['message'] for f in result['findings'] if f['type'] in {'violation', 'missing'}))
    write_draft(workspace, draft_id, working)
    write_document(inside(root, 'provenance.json'), complete(working, provenance, []))
    counts = {status: sum(item['standing'] == status for item in applied) for status in STANDING[:3]}
    used = {item['subject'] for item in applied}
    unplaced = sorted(subject for subject, item in mappings.items() if item['meaning'] and subject not in used)
    gaps = {}
    for item in mappings.values():
        if item['status'] == 'gap':
            gaps[item['gap']['reason']] = gaps.get(item['gap']['reason'], 0) + 1
    notes = [note for note in state['notes'] if not str(note.get('rule', '')).startswith('meaning-')]
    notes.append({'rule': 'meaning-mapping', 'message':
                  f'{len(applied)} role treatments placed from corpus {corpus} ({held["context"]}): {counts["certified"]} certified, '
                  f'{counts["chosen"]} locally chosen, {counts["candidate"]} heuristic candidates. '
                  'Uncertified mappings are proposals, not standards.'})
    if missing:
        notes.append({'rule': 'meaning-gap', 'message': 'No mapping supplies a text colour for emphasis '
                      + ', '.join(missing) + '; the ingest default is retained'})
    for subject, others in list(dict.fromkeys((s, tuple(o)) for s, o in collisions))[:20]:
        notes.append({'rule': 'meaning-collision', 'message': f'{subject} is placed; same meaning, not placed: {", ".join(others)}'})
    if unplaced:
        notes.append({'rule': 'meaning-unplaced', 'message': f'{len(unplaced)} mapped tokens are held in Style but not placed by role defaults'})
    if gaps:
        notes.append({'rule': 'meaning-gap', 'message': 'Tokens recorded as gaps: ' + ', '.join(f'{count} {reason}' for reason, count in sorted(gaps.items()))})
    others = [name for name in load(workspace, corpus)['contexts'] if name != held['context']]
    if others:
        notes.append({'rule': 'meaning-context', 'message': 'A language holds one context; not expressed here: ' + ', '.join(others)})
    state['notes'] = notes
    write_document(inside(root, 'state.json'), state)
    return {**summary(library, workspace, draft_id),
            'meaning': {'corpus': corpus, 'context': held['context'], 'placed': applied, 'unplaced': unplaced, 'counts': counts}}


def uses(document):
    """Every token reference in a language, with the property and role position using it."""
    def walk(value, path, context):
        if isinstance(value, dict):
            for key, child in value.items():
                if key in TOKEN_PROPERTIES and isinstance(child, str) and ALIAS.fullmatch(child):
                    yield {'pointer': path + pointer(key), 'property': key, 'reference': ALIAS.fullmatch(child)[1], **context}
                elif isinstance(child, (dict, list)):
                    yield from walk(child, path + pointer(key), context)
        elif isinstance(value, list):
            for index, child in enumerate(value):
                yield from walk(child, path + pointer(index), context)
    for role, emphases in document.get('roles', {}).items():
        for emphasis, props in (emphases.items() if isinstance(emphases, dict) else ()):
            yield from walk(props, pointer('roles', role, emphasis), {'role': role, 'emphasis': emphasis})
    for group in ('components', 'overrides'):
        yield from walk(document.get(group, {}), pointer(group), {})


def chain(tokens, path):
    """A token and everything it aliases, nearest first."""
    seen = []
    while path in tokens.nodes and path not in seen:
        seen.append(path)
        value = tokens.nodes[path]['$value']
        alias = ALIAS.fullmatch(value) if isinstance(value, str) else None
        if not alias:
            break
        path = alias[1]
    return seen


def compatible(meaning, use):
    wanted = meaning['property']
    if wanted == 'space':
        return use in SPACE_PROPERTIES
    return use == wanted or {wanted, use} == {'surface', 'background-color'}


def check(library, workspace, language_id, corpus):
    """The meaning gate: a certified contract that is broken is a violation; anything
    of lower standing is advisory coverage, labelled with that standing."""
    document = load_language(library, language_id)
    vocabulary = load_vocabulary(library, document['vocabulary'])
    mappings = effective(workspace, vocabulary, corpus)
    tokens = Tokens(document.get('style', {}))
    file = f'languages/{language_id}/working.json'
    findings, standing = [], {}
    for use in uses(document):
        for subject in chain(tokens, use['reference']):
            item = mappings.get(subject)
            if not item or not item['meaning']:
                continue
            standing[subject] = item['status']
            meaning, problems = item['meaning'], []
            if not compatible(meaning, use['property']):
                problems.append(f'is mapped as {meaning["property"]} and is used as {use["property"]}')
            for member in ('emphasis', 'role'):
                if member in use and member in meaning and meaning[member] != use[member] and use['property'] != 'surface':
                    problems.append(f'is mapped to {member} {meaning[member]} and is used for {member} {use[member]}')
            by = (f'certified by {item["authority"]} for scope {item["scope"]}' if item['status'] == 'certified' else
                  'a local choice, not certified' if item['status'] == 'chosen' else 'a heuristic candidate, not certified')
            for problem in problems:
                findings.append(Finding('violation' if item['status'] == 'certified' else 'coverage', 'meaning-contract', file,
                                        use['pointer'], '{' + use['reference'] + '}',
                                        'a use that honours the mapping of ' + subject,
                                        f'{subject} {problem}; the mapping is {by}').to_dict())
    uncertified = sorted(subject for subject, status in standing.items() if status != 'certified')
    if uncertified:
        findings.append(Finding('coverage', 'meaning-uncertified', file, '/roles', len(uncertified), 'certified mappings',
                                f'{len(uncertified)} of {len(standing)} token meanings in use are uncertified proposals').to_dict())
    certified = certification(workspace, corpus)
    return {**report(language_id, findings), 'corpus': corpus,
            'certification': 'current' if certified['connected'] else 'unknown (Kinbase unavailable: ' + str(certified['reason']) + ')',
            'standing': {status: sum(value == status for value in standing.values()) for status in STANDING[:3]}}
