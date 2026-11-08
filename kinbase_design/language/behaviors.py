"""Declared behavior grammar and exact scope matching, shared by checks and renderer."""
from .resolver import parse_scope

KINDS = {'truncate', 'horizontal-scroll', 'target-exception'}
TARGET_EXCEPTIONS = {'inline', 'spacing', 'equivalent', 'user-agent', 'essential'}


def matches(scope, target):
    return scope == target or ('.' not in scope and target.startswith(scope + '.'))


def matching(document, kind, target):
    return [(f'/behaviors/{index}', behavior) for index, behavior in enumerate(document.get('behaviors', []))
            if behavior.get('kind') == kind and matches(behavior.get('scope', ''), target)]


def validate_behaviors(document, vocabulary, issue):
    for index, behavior in enumerate(document.get('behaviors', [])):
        p = f'/behaviors/{index}'
        if not isinstance(behavior, dict):
            issue('schema', p, behavior, 'a behavior object')
            continue
        try:
            scope = parse_scope(behavior.get('scope'), vocabulary)
            if scope.state or scope.breakpoint:
                raise ValueError('Behavior scope must target a construct or slot')
        except (ValueError, TypeError) as exc:
            issue('R1', p + '/scope', behavior.get('scope'), 'construct[.slot]', str(exc))
        kind = behavior.get('kind')
        if not isinstance(kind, str) or kind not in KINDS:
            issue('schema', p + '/kind', kind, 'truncate, horizontal-scroll or target-exception')
        if not isinstance(behavior.get('reason'), str) or not behavior.get('reason', '').strip():
            issue('schema', p + '/reason', behavior.get('reason'), 'a nonempty behavior reason')
        allowed = {'scope','kind','reason'}
        if kind == 'truncate':
            allowed |= {'lines','full-content'}
            if type(behavior.get('lines')) is not int or behavior['lines'] < 1:
                issue('schema', p + '/lines', behavior.get('lines'), 'a positive line count')
            if not isinstance(behavior.get('full-content'), str) or behavior.get('full-content') not in vocabulary['context']['pages']:
                issue('R1', p + '/full-content', behavior.get('full-content'), 'a declared preview page containing the full text')
        elif kind == 'target-exception':
            allowed.add('exception')
            if not isinstance(behavior.get('exception'), str) or behavior['exception'] not in TARGET_EXCEPTIONS:
                issue('schema', p + '/exception', behavior.get('exception'), 'a WCAG target-size exception name')
        for key in behavior.keys() - allowed:
            issue('schema', p + '/' + key.replace('~','~0').replace('/','~1'), behavior[key], 'a declared behavior field')
