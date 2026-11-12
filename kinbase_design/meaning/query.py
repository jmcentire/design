"""Impact and definition answers over the library, each with the source it rests on.

Language files are the certified structure: an answer points at the JSON member that
makes it true. Corpus mappings are added with their standing and never as rules.
"""
from ..findings import pointer, location
from ..language import validate
from ..language.resolver import resolve, property_pointer
from ..language.tokens import Tokens, ALIAS
from ..storage import identifier, inside, load_language, read_json
from ..vocabulary import load as load_vocabulary, slot_map
from .language import uses

LABELS = {'certified': 'certified', 'chosen': 'local choice — not certified',
          'candidate': 'heuristic candidate — not certified', 'gap': 'gap — no mapping'}


def languages(library, only=None):
    if only:
        return [identifier(only)]
    parent = inside(library, 'languages')
    return sorted(item.name for item in (parent.iterdir() if parent.exists() else [])
                  if item.is_dir() and (item / 'working.json').exists())


def references(node):
    """Token paths a token value names: an alias, or the colour stops of a gradient."""
    value = node['$value']
    values = [value] if isinstance(value, str) else [stop.get('color') for stop in value if isinstance(stop, dict)] if isinstance(value, list) else []
    return [alias[1] for raw in values if isinstance(raw, str) and (alias := ALIAS.fullmatch(raw))]


def dependents(tokens, token):
    affected, grew = {token}, True
    while grew:
        grew = False
        for path, node in tokens.nodes.items():
            if path not in affected and affected & set(references(node)):
                affected.add(path)
                grew = True
    return affected


def mapping_view(item):
    view = {'subject': item['subject'], 'meaning': item['meaning'], 'standing': item['status'], 'label': LABELS[item['status']],
            'source': item['source']}
    for key in ('authority', 'scope', 'decision', 'author', 'gap'):
        if key in item:
            view[key] = item[key]
    if item['candidate']:
        view['candidate'] = item['candidate']
    if item['decisions']:
        view['decisions'] = item['decisions']
    return view


def corpus_mappings(library, workspace, corpus):
    from .graph import effective
    return effective(workspace, load_vocabulary(library), corpus)


def impact(library, token, language=None, workspace=None, corpus=None):
    """What names this token, in which languages, and which resolved treatments move with it."""
    if not isinstance(token, str) or not ALIAS.fullmatch('{' + token + '}'):
        raise ValueError('Expected a token path such as color.primary')
    found, absent = [], []
    for language_id in languages(library, language):
        document = load_language(library, language_id)
        file = f'languages/{language_id}/working.json'
        try:
            tokens = Tokens(document.get('style', {}))
        except (ValueError, AttributeError):
            absent.append(language_id)
            continue
        if token not in tokens.nodes:
            absent.append(language_id)
            continue
        affected = dependents(tokens, token)
        named = [use for use in uses(document) if use['reference'] in affected]
        entry = {'language': language_id, 'file': file,
                 'token': {'pointer': pointer('style', *token.split('.'), '$value'), 'value': tokens.nodes[token]['$value']},
                 'dependents': [{'token': path, 'pointer': pointer('style', *path.split('.'), '$value')} for path in sorted(affected - {token})],
                 'uses': [{'pointer': use['pointer'], 'property': use['property'], 'via': use['reference']} for use in named],
                 'contrast_pairs': sorted({use['role'] + '.' + use['emphasis'] for use in named
                                           if 'role' in use and use['property'] in {'color', 'surface'}})}
        if validate(library, language_id, document)['accepted']:
            vocabulary = load_vocabulary(library, document['vocabulary'])
            breakpoints = [None] + sorted(path.removeprefix('breakpoint.') for path in tokens.nodes if path.startswith('breakpoint.'))
            scopes = {}
            for construct, contract in vocabulary['constructs'].items():
                for scope in [construct] + [construct + '.' + slot for slot in slot_map(contract)]:
                    for state in contract['states']:
                        for breakpoint in breakpoints:
                            resolved = resolve(document, vocabulary, scope, state, breakpoint)['properties']
                            for name, value in resolved.items():
                                origin = property_pointer(document, vocabulary, name, value)
                                raw = location(document, origin)[1]
                                alias = ALIAS.fullmatch(raw) if isinstance(raw, str) else None
                                if alias and alias[1] in affected:
                                    record = scopes.setdefault((scope, name, origin), {'scope': scope, 'property': name, 'source': origin,
                                                                                         'value': value['value'], 'states': []})
                                    if state not in record['states']:
                                        record['states'].append(state)
            entry['resolved'] = list(scopes.values())
        else:
            entry['resolved'] = None
            entry['note'] = 'The language has unresolved validation findings; only its direct references are listed'
        versions = inside(library, 'languages', language_id, 'versions')
        entry['versions'] = sorted(path.stem for path in (versions.glob('*.json') if versions.exists() else [])
                                   if location(read_json(path), pointer('style', *token.split('.')))[0] == pointer('style', *token.split('.')))
        found.append(entry)
    result = {'token': token, 'languages': found, 'not_in': absent,
              'note': 'Minted versions are immutable. A change produces a new version; consumers pinned to a listed '
                      'lang@hash keep their values until they adopt it. Re-run rendered checks for the listed contrast pairs.'}
    if corpus:
        mappings = corpus_mappings(library, workspace, corpus)
        result['mapping'] = mapping_view(mappings[token]) if token in mappings else None
    return result


def define(library, term, workspace=None, corpus=None):
    """What a Vocabulary term or a corpus token means, and where each part is stated."""
    vocabulary = load_vocabulary(library)
    file = f'vocabulary/{vocabulary["version"]}/vocabulary.json'
    mappings = corpus_mappings(library, workspace, corpus) if corpus else {}
    def mapped(member):
        return [mapping_view(item) for item in mappings.values() if item['meaning'] and item['meaning'].get(member) == term]
    def treatments(path):
        found = []
        for language_id in languages(library):
            document = load_language(library, language_id)
            if isinstance(document, dict) and location(document, path)[0] == path:
                found.append({'language': language_id, 'file': f'languages/{language_id}/working.json', 'pointer': path})
        return found
    for member, key in (('role', 'roles'), ('emphasis', 'emphasis'), ('state', 'states')):
        if term in vocabulary[key]:
            result = {'term': term, 'kind': member, 'standing': 'vocabulary',
                      'source': {'file': file, 'pointer': pointer(key, vocabulary[key].index(term))}}
            if member == 'state':
                result['declared_by'] = [{'construct': name, 'pointer': pointer('constructs', name, 'states', contract['states'].index(term))}
                                         for name, contract in vocabulary['constructs'].items() if term in contract['states']]
            else:
                result['slots'] = [{'slot': name + '.' + slot['id'], 'pointer': pointer('constructs', name, 'slots', index)}
                                   for name, contract in vocabulary['constructs'].items()
                                   for index, slot in enumerate(contract['slots']) if slot[member] == term]
            if member == 'role':
                result['treatments'] = treatments(pointer('roles', term))
            if corpus:
                result['mappings'] = mapped(member)
            return result
    construct, _, slot = term.partition('.')
    if construct in vocabulary['constructs']:
        contract = vocabulary['constructs'][construct]
        result = {'term': term, 'standing': 'vocabulary'}
        if slot:
            if slot not in slot_map(contract):
                raise ValueError('Unknown slot: ' + term)
            index = [item['id'] for item in contract['slots']].index(slot)
            resolved = []
            for language_id in languages(library):
                document = load_language(library, language_id)
                if document.get('vocabulary') == vocabulary['version'] and validate(library, language_id, document)['accepted']:
                    properties = resolve(document, vocabulary, term)['properties']
                    resolved.append({'language': language_id, 'file': f'languages/{language_id}/working.json',
                                     'properties': {name: {'value': value['value'], 'pointer': property_pointer(document, vocabulary, name, value)}
                                                    for name, value in properties.items()}})
            result.update(kind='slot', definition=contract['slots'][index],
                          source={'file': file, 'pointer': pointer('constructs', construct, 'slots', index)},
                          treatments=resolved)
        else:
            result.update(kind='construct', definition={'root': contract['root'], 'contract': contract['contract'],
                                                        'slots': [item['id'] for item in contract['slots']], 'states': contract['states']},
                          source={'file': file, 'pointer': pointer('constructs', construct)},
                          treatments=treatments(pointer('components', construct)))
        return result
    if term in mappings:
        from .graph import load
        document = load(workspace, corpus)
        return {'term': term, 'kind': 'token', 'corpus': corpus, **mapping_view(mappings[term]),
                'contexts': {name: {key: record[key] for key in ('value', 'unsupported', 'converted', 'overridden_by') if key in record}
                             for name, record in document['tokens'][term]['contexts'].items()},
                'usage': [{**item, 'label': 'usage evidence — prose, not a rule'} for item in document['usage'] if term in item['tokens']]}
    raise ValueError('Unknown term: not a Vocabulary role, emphasis, state, construct or slot'
                     + (', nor a token of corpus ' + corpus if corpus else ''))
