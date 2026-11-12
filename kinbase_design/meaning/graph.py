"""The private meaning graph of one corpus: candidates, local decisions, certification.

Standing is ordered, not timed: a Kinbase-certified mapping outranks a local choice,
which outranks a heuristic candidate. Recency only orders choices among themselves.
"""
from datetime import datetime, timezone
import fcntl
import json
import re
from uuid import uuid4
from .. import kinbase
from ..config import MEANING_MAX_NOTE, KINBASE_FEEDBACK_LENGTH
from ..findings import pointer
from ..ingest.documents import read_document, write_document
from ..storage import identifier, inside, write_json
from .lexicon import ground, pressure, propose as propose_meaning, segments, MEMBERS
from .sources import read, BASE

STANDING = ('certified', 'chosen', 'candidate', 'gap')


def folder(workspace, corpus):
    return inside(workspace, 'meaning', identifier(corpus))


def load(workspace, corpus):
    path = inside(folder(workspace, corpus), 'corpus.json')
    if not path.exists():
        raise ValueError('Unknown corpus: ' + corpus)
    return read_document(path)


def corpora(workspace):
    parent = inside(workspace, 'meaning')
    return sorted(item.name for item in (parent.iterdir() if parent.exists() else [])
                  if item.is_dir() and (item / 'corpus.json').exists())


def discover(workspace, vocabulary, corpus, artifact_ids, only=()):
    """Draft candidate mappings for every token; whatever is not mapped is a recorded gap."""
    root = folder(workspace, corpus)
    if root.exists():
        raise ValueError('Corpus already exists; choose a new corpus id')
    if not artifact_ids:
        raise ValueError('At least one source artifact is required')
    if any(not isinstance(prefix, str) or not re.fullmatch(r'[A-Za-z0-9_-]+', prefix) for prefix in only):
        raise ValueError('A name prefix is letters, digits, hyphens and underscores')
    table, evidence, problems = read(workspace, artifact_ids, only)
    if not table:
        raise ValueError('No tokens were found in the source artifacts')
    candidates, gaps = {}, {}
    def family(path):
        # Tokens that are named together: a DTCG group, or a stylesheet's leading family word.
        return table[path]['type'], segments(path)[0] if path.startswith('css.') else path.rpartition('.')[0]
    groups = {}
    for path in table:
        groups.setdefault(family(path), []).append(path)
    for path, entry in sorted(table.items()):
        unsupported = [r['unsupported'] for r in entry['contexts'].values() if 'unsupported' in r]
        if entry['type'] is None or len(unsupported) == len(entry['contexts']):
            # Vocabulary pressure is the more useful record when both apply (a shadow, say).
            gaps[path] = pressure(path) or {'reason': 'unsupported-value', 'message': unsupported[0] if unsupported else 'The token has no supported type'}
            continue
        siblings = [other for other in groups[family(path)] if other != path]
        candidate, gap = propose_meaning(path, entry['type'], siblings)
        problem = ground(candidate['meaning'], entry['type'], vocabulary) if candidate else None
        if problem:
            candidate, gap = None, {'reason': 'vocabulary', 'message': problem}
        if candidate:
            candidates[path] = {**candidate, 'method': 'name-heuristic'}
        else:
            gaps[path] = gap
    seen = {}
    for path, candidate in candidates.items():
        seen.setdefault(json.dumps(candidate['meaning'], sort_keys=True), []).append(path)
    for paths in seen.values():
        if len(paths) > 1:
            for path in paths:
                candidates[path]['flags'].append('collision')
                candidates[path]['collides'] = [other for other in paths if other != path]
    contexts = sorted({context for entry in table.values() for context in entry['contexts']})
    document = {'id': corpus, 'artifacts': list(artifact_ids), 'only': list(only), 'vocabulary': vocabulary['version'], 'contexts': contexts,
                'tokens': table, 'candidates': candidates, 'gaps': gaps, 'usage': evidence, 'problems': problems}
    root.mkdir(parents=True)
    write_document(inside(root, 'corpus.json'), document)
    return show(workspace, vocabulary, corpus)


def decisions(workspace, corpus):
    path = inside(folder(workspace, corpus), 'decisions.jsonl')
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()] if path.exists() else []


def certification(workspace, corpus):
    path = inside(folder(workspace, corpus), 'certified.json')
    if path.exists():
        return read_document(path)
    return {'connected': False, 'reason': 'not synced', 'mappings': {}, 'rejected': [], 'conflicts': []}


def effective(workspace, vocabulary, corpus):
    """Every token's current mapping, labelled with its standing and how it got there."""
    document = load(workspace, corpus)
    certified = certification(workspace, corpus)
    history = {}
    for decision in decisions(workspace, corpus):
        history.setdefault(decision['subject'], []).append(decision)
    result = {}
    for path, entry in document['tokens'].items():
        candidate, record = document['candidates'].get(path), certified['mappings'].get(path) if certified['connected'] else None
        chosen = history.get(path, [])
        item = {'subject': path, 'type': entry['type'], 'candidate': candidate, 'decisions': chosen,
                'source': {'kind': 'source', 'artifact': entry['artifact'],
                           'location': (entry['contexts'].get(BASE) or next(iter(entry['contexts'].values())))['location']}}
        if record:
            item.update(status='certified', meaning=record['meaning'], authority='kinbase:' + record['fact_id'],
                        scope=record['scope'], certified=record)
        elif chosen and chosen[-1].get('meaning'):
            item.update(status='chosen', meaning=chosen[-1]['meaning'], decision=chosen[-1]['id'], author=chosen[-1]['author'])
        elif chosen:
            item.update(status='gap', meaning=None, gap={'reason': 'reviewed', 'message': chosen[-1]['gap']},
                        decision=chosen[-1]['id'], author=chosen[-1]['author'])
        elif candidate:
            item.update(status='candidate', meaning=candidate['meaning'])
        else:
            item.update(status='gap', meaning=None, gap=document['gaps'][path])
        result[path] = item
    return result


def show(workspace, vocabulary, corpus):
    document = load(workspace, corpus)
    mappings = effective(workspace, vocabulary, corpus)
    certified = certification(workspace, corpus)
    counts = {status: sum(item['status'] == status for item in mappings.values()) for status in STANDING}
    label = ('current' if certified['connected'] else
             'unknown (Kinbase unavailable: ' + str(certified['reason']) + ')')
    return {'corpus': corpus, 'vocabulary': document['vocabulary'], 'artifacts': document['artifacts'],
            'contexts': document['contexts'], 'tokens': len(document['tokens']), 'counts': counts,
            'certification': label, 'rejected': certified['rejected'], 'conflicts': certified['conflicts'],
            'mappings': list(mappings.values()), 'usage': document['usage'], 'problems': document['problems']}


def choose(workspace, vocabulary, corpus, subject, author, meaning=None, gap=None, accept=False, note=''):
    """Record one reviewer's local decision. It is a choice, never a certification."""
    document = load(workspace, corpus)
    if subject not in document['tokens']:
        raise ValueError('Unknown token in this corpus: ' + subject)
    if not isinstance(author, str) or not author.strip() or len(author) > 200:
        raise ValueError('A decision needs an author')
    if not isinstance(note, str) or len(note) > MEANING_MAX_NOTE:
        raise ValueError('Decision note is too long')
    if sum(bool(option) for option in (meaning, gap, accept)) != 1:
        raise ValueError('Choose exactly one of: accept the candidate, a corrected meaning, or a gap')
    if accept:
        if subject not in document['candidates']:
            raise ValueError('There is no candidate to accept for ' + subject)
        meaning = document['candidates'][subject]['meaning']
    if meaning is not None:
        meaning = {member: meaning[member] for member in MEMBERS if meaning.get(member)}
        problem = ground(meaning, document['tokens'][subject]['type'], vocabulary)
        if problem:
            raise ValueError(problem)
    elif not isinstance(gap, str) or not gap.strip() or len(gap) > MEANING_MAX_NOTE:
        raise ValueError('A gap needs a reason')
    previous = [d for d in decisions(workspace, corpus) if d['subject'] == subject]
    entry = {'id': 'decision-' + uuid4().hex, 'ts': datetime.now(timezone.utc).isoformat(), 'author': author.strip(),
             'subject': subject, 'meaning': meaning, 'gap': gap if meaning is None else None, 'note': note,
             'supersedes': previous[-1]['id'] if previous else None}
    path = inside(folder(workspace, corpus), 'decisions.jsonl')
    with path.open('a', encoding='utf-8') as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        stream.write(json.dumps(entry, ensure_ascii=False) + '\n')
        stream.flush()
    return {'corpus': corpus, **effective(workspace, vocabulary, corpus)[subject]}


def sync(library, workspace, vocabulary, corpus):
    """Replace the certification snapshot with what Kinbase reports as current now.

    Only an authoritative, trusted, in-scope current fact certifies. Kinbase unavailable
    means unknown: the snapshot then certifies nothing.
    """
    document = load(workspace, corpus)
    snapshot = kinbase.status(library)
    record = {'connected': snapshot['connected'], 'reason': snapshot.get('reason'), 'mappings': {}, 'rejected': [], 'conflicts': []}
    for fact in snapshot.get('facts', []):
        if not fact.get('fixed'):
            continue
        fact_id = fact['current']['fact_id']
        for subject, meaning in sorted(fact.get('mappings', {}).get(corpus, {}).items()):
            entry = document['tokens'].get(subject)
            problem = ('The token is not in this corpus' if entry is None else
                       ground(meaning, entry['type'], vocabulary))
            if problem:
                record['rejected'].append({'subject': subject, 'fact_id': fact_id, 'message': problem})
            elif subject in record['mappings'] and record['mappings'][subject]['meaning'] != meaning:
                record['conflicts'].append(subject)
            else:
                record['mappings'][subject] = {'meaning': meaning, 'fact_id': fact_id, 'scope': fact['scope'], 'key': fact['key'],
                                               'location': pointer('kinbase-design', 'mappings', corpus, subject)}
    for subject in set(record['conflicts']):
        # Authorities that disagree certify nothing for that token.
        record['mappings'].pop(subject, None)
    record['conflicts'] = sorted(set(record['conflicts']))
    write_document(inside(folder(workspace, corpus), 'certified.json'), record)
    return show(workspace, vocabulary, corpus)


def propose(library, workspace, vocabulary, corpus, author, subjects=()):
    """Send locally chosen mappings to Kinbase as evidence. Received never means certified."""
    if not isinstance(author, str) or not author.strip() or len(author) > 200:
        raise ValueError('A proposal needs an author')
    mappings = effective(workspace, vocabulary, corpus)
    unknown = [subject for subject in subjects if subject not in mappings]
    if unknown:
        raise ValueError('Unknown token in this corpus: ' + unknown[0])
    chosen = {subject: item['meaning'] for subject, item in sorted(mappings.items())
              if item['status'] == 'chosen' and (not subjects or subject in subjects)}
    if not chosen:
        raise ValueError('Only locally reviewed mappings are proposed; choose at least one first')
    statement = json.dumps({'kinbase-design': {'mappings': {corpus: chosen}}}, sort_keys=True, ensure_ascii=False)
    text = 'Kinbase Design meaning-mapping proposal (agent provenance), reviewer ' + author.strip() + ': ' + statement
    if len(text) > KINBASE_FEEDBACK_LENGTH:
        raise ValueError('Proposal exceeds the Kinbase submission bound; propose fewer tokens with --subject')
    result = kinbase.submit(library, text, 'decision')
    receipt_id = 'meaning-' + uuid4().hex
    write_json(inside(workspace, 'kinbase-receipts', receipt_id + '.json'), result)
    return {'id': receipt_id, 'corpus': corpus, 'proposed': sorted(chosen), 'submission': result}
