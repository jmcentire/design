"""Server-rendered meaning review over the same operations as the CLI."""
from .. import meaning
from ..artifacts.bundle import metadata
from ..kinbase import status as kinbase_status
from ..meaning.graph import corpora
from ..meaning.lexicon import PROPERTIES
from ..storage import identifier, inside, read_json
from ..vocabulary import load
from .ingest import fields

SOURCE_KINDS = {'css', 'dtcg', 'doc', 'brief'}


def handle(library, workspace, environ, segments, query, html):
    from . import RequestError
    method = environ['REQUEST_METHOD']
    tail = segments[1:]
    def page(template, **context):
        return 200, html(template, **context), 'text/html; charset=utf-8', []
    def redirect(path):
        return 303, b'', 'text/html; charset=utf-8', [('Location', path)]
    if not tail and method == 'GET':
        artifacts = []
        parent = inside(workspace, 'artifacts')
        for item in sorted(parent.iterdir() if parent.exists() else []):
            if item.is_dir() and item.name.startswith('artifact-'):
                meta = metadata(workspace, item.name)
                if meta.get('kind') in SOURCE_KINDS:
                    artifacts.append({'id': item.name, 'kind': meta['kind'], 'name': meta.get('filename', meta['kind'])})
        corpus = query.get('corpus', [''])[0] or None
        answer = None
        if query.get('token', [''])[0]:
            answer = meaning.impact(library, query['token'][0], None, workspace, corpus)
        elif query.get('term', [''])[0]:
            answer = meaning.define(library, query['term'][0], workspace, corpus)
        return page('meaning.html', title='Meaning', corpora=corpora(workspace), artifacts=artifacts[-40:], answer=answer,
                    token=query.get('token', [''])[0], term=query.get('term', [''])[0], corpus=corpus or '')
    if tail == ['discover'] and method == 'POST':
        data = fields(environ)
        corpus = identifier(data.get('corpus', [''])[0].strip())
        meaning.discover(library, workspace, corpus, [identifier(a) for a in data.get('artifact', [])])
        return redirect('/meaning/' + corpus)
    if not tail:
        raise RequestError('Unknown route', 404)
    corpus = identifier(tail[0])
    if len(tail) == 1 and method == 'GET':
        vocabulary = load(library)
        receipt = None
        if query.get('receipt'):
            receipt = read_json(inside(workspace, 'kinbase-receipts', identifier(query['receipt'][0]) + '.json'))
        return page('meaning-corpus.html', title='Meaning · ' + corpus, corpus=meaning.show(library, workspace, corpus),
                    vocabulary=vocabulary, properties=sorted(set().union(*PROPERTIES.values())), receipt=receipt,
                    kinbase=kinbase_status(library))
    if len(tail) == 2 and method == 'POST':
        data = {key: values[0].strip() for key, values in fields(environ).items()}
        if tail[1] == 'choose':
            decision = data.get('decision')
            chosen = {m: data[m] for m in ('property', 'emphasis', 'role', 'state') if data.get(m)} if decision == 'correct' else None
            meaning.choose(library, workspace, corpus, data.get('subject', ''), data.get('author', ''), chosen,
                           data.get('gap') if decision == 'gap' else None, decision == 'accept', data.get('note', ''))
            return redirect('/meaning/' + corpus)
        if tail[1] == 'sync':
            meaning.sync(library, workspace, corpus)
            return redirect('/meaning/' + corpus)
        if tail[1] == 'propose':
            result = meaning.propose(library, workspace, corpus, data.get('author', ''))
            return redirect('/meaning/' + corpus + '?receipt=' + result['id'])
        if tail[1] == 'draft':
            language = identifier(data.get('language', ''))
            meaning.draft(library, workspace, corpus, language, data.get('context') or None)
            return redirect('/ingest/drafts/' + language)
        if tail[1] == 'apply':
            draft = identifier(data.get('draft', ''))
            meaning.apply(library, workspace, corpus, draft)
            return redirect('/ingest/drafts/' + draft)
    raise RequestError('Unknown route', 404)
