"""Composition rules R1–R5; all consumers use this report."""
from ..vocabulary import slot_map
import hashlib
import logging
from .. import vocabulary as vocabulary_store
from ..assets import KINDS, FORMATS, HASH_FILE, asset_path
from ..findings import Finding, pointer, report, location
from ..storage import ID, load_language
from .tokens import Tokens, ALIAS, is_number
from .properties import TOKEN_PROPERTIES, SPACE_PROPERTIES, KEYWORDS
from .resolver import parse_scope, resolve, property_pointer
from .variants import Template

log = logging.getLogger(__name__)


class Validator:
    def __init__(self, library, language_id, document, vocabulary):
        self.library, self.id, self.doc, self.vocab = library, language_id, document, vocabulary
        self.findings = []
        self.tokens = None

    def issue(self, rule, path, observed, expected, message=None, type='violation'):
        path, observed = location(self.doc, path)
        finding = Finding(type, rule, f'languages/{self.id}/working.json', path,
                          observed, expected, message or expected).to_dict()
        if finding not in self.findings:
            self.findings.append(finding)

    def object(self, value, path):
        if not isinstance(value, dict):
            self.issue('schema', path, value, 'an object')
            return False
        return True

    def known(self, obj, allowed, path):
        for key in obj.keys() - set(allowed):
            self.issue('schema', path + pointer(key), obj[key], 'a declared field')

    def properties(self, props, path, roles=False):
        if not self.object(props, path):
            return
        for key, value in props.items():
            p = path + pointer(key)
            if key in KEYWORDS:
                if not isinstance(value, str) or value not in KEYWORDS[key]:
                    self.issue('R2', p, value, 'a valid CSS keyword for ' + key)
            elif key in TOKEN_PROPERTIES and (roles or key != 'surface'):
                alias = ALIAS.fullmatch(value) if isinstance(value, str) else None
                if not alias:
                    self.issue('R2', p, value, 'a token reference; raw values belong in Style')
                    continue
                if key in SPACE_PROPERTIES and not alias[1].startswith('space.'):
                    self.issue('R4', p, value, 'a dimension token under space.*')
                try:
                    kind, _ = self.tokens.reference(value)
                    if kind not in TOKEN_PROPERTIES[key]:
                        self.issue('R1', p, value, 'a declared ' + '/'.join(sorted(TOKEN_PROPERTIES[key])) + ' token')
                except (KeyError, ValueError) as exc:
                    self.issue('R1', p, value, 'a resolvable, correctly typed token', str(exc))
            else:
                self.issue('schema', p, value, 'a property from the closed property set')

    def states(self, states, path, contract):
        if not self.object(states, path):
            return
        for state, props in states.items():
            if state not in contract['states']:
                self.issue('R1', path + pointer(state), state, 'a state declared by this construct')
            self.properties(props, path + pointer(state))

    def role_pair(self, role, emphasis, path):
        if role not in self.vocab['roles']:
            self.issue('R1', path + '/role', role, 'a vocabulary role')
        if emphasis not in self.vocab['emphasis']:
            self.issue('R1', path + '/emphasis', emphasis, 'a vocabulary emphasis')
        role_values = self.doc.get('roles', {}).get(role, {}) if isinstance(role, str) else {}
        pair = role_values.get(emphasis, {}) if isinstance(role_values, dict) and isinstance(emphasis, str) else {}
        if not isinstance(pair, dict) or not {'color', 'surface'} <= pair.keys():
            self.issue('R3', pointer('roles', role, emphasis), pair, 'both color and surface for the used role × emphasis')

    def run(self):
        d = self.doc
        if not self.object(d, ''):
            return
        for key in ('id', 'name', 'vocabulary', 'style', 'roles', 'components'):
            if key not in d:
                self.issue('schema', pointer(key), None, 'a required field')
        self.known(d, {'id','name','vocabulary','style','roles','layout','components','overrides','behaviors','assets','description','provenance'}, '')
        if d.get('id') != self.id:
            self.issue('schema', '/id', d.get('id'), 'the language directory id')
        if not isinstance(d.get('name'), str) or not d.get('name', '').strip():
            self.issue('schema', '/name', d.get('name'), 'a nonempty name')
        for key in ('style', 'roles', 'layout', 'components', 'assets'):
            if not self.object(d.get(key, {}), pointer(key)):
                return
        for key in ('overrides', 'behaviors'):
            if not isinstance(d.get(key, []), list):
                self.issue('schema', pointer(key), d[key], 'an array')
                return
        try:
            self.tokens = Tokens(d.get('style', {}))
        except ValueError as exc:
            self.issue('schema', '/style', d.get('style'), 'a DTCG token tree', str(exc))
            return
        for name, token in self.tokens.nodes.items():
            p = pointer('style', *name.split('.'), '$value')
            if name.startswith('breakpoint.'):
                try:
                    self.tokens.breakpoint(name.removeprefix('breakpoint.'))
                except (KeyError, ValueError) as exc:
                    self.issue('R4', p, token['$value'], 'a dimension token with a breakpoint id', str(exc))
            try:
                self.tokens.evaluate(name)
            except KeyError as exc:
                self.issue('R1', p, token['$value'], 'a declared token reference', str(exc))
            except ValueError as exc:
                alias = isinstance(token['$value'], str) and ALIAS.fullmatch(token['$value'])
                self.issue('R1' if alias else 'R2', p, token['$value'], 'a value matching its token type', str(exc))
        for role, emphases in d.get('roles', {}).items():
            p = pointer('roles', role)
            if role not in self.vocab['roles']:
                self.issue('R1', p, role, 'a vocabulary role')
            if not self.object(emphases, p):
                continue
            for emphasis, props in emphases.items():
                if emphasis not in self.vocab['emphasis']:
                    self.issue('R1', p + pointer(emphasis), emphasis, 'a vocabulary emphasis')
                self.properties(props, p + pointer(emphasis), roles=True)
        variants = d.get('layout', {}).get('variants', {})
        self.known(d.get('layout', {}), {'variants'}, '/layout')
        valid_templates = {}
        if self.object(variants, '/layout/variants'):
            for construct, entries in variants.items():
                p = pointer('layout', 'variants', construct)
                contract = self.vocab['constructs'].get(construct)
                if not contract:
                    self.issue('R1', p, construct, 'a vocabulary construct')
                    continue
                if not self.object(entries, p):
                    continue
                for name, entry in entries.items():
                    q = p + pointer(name)
                    if not ID.fullmatch(name):
                        self.issue('schema', q, name, 'a kebab-case variant id')
                    if not self.object(entry, q):
                        continue
                    self.known(entry, {'template'}, q)
                    template = entry.get('template')
                    try:
                        if not isinstance(template, str):
                            raise ValueError('A template string is required')
                        valid_templates[construct, name] = Template(template, contract)
                    except ValueError as exc:
                        self.issue('R5', q + '/template', template, 'a contract-preserving template', str(exc))
        for construct, component in d.get('components', {}).items():
            p = pointer('components', construct)
            contract = self.vocab['constructs'].get(construct)
            if not contract:
                self.issue('R1', p, construct, 'a vocabulary construct')
                continue
            if not self.object(component, p):
                continue
            self.known(component, {'variant','properties','states','slots','parts','assets'}, p)
            self.properties(component.get('properties', {}), p + '/properties')
            self.states(component.get('states', {}), p + '/states', contract)
            variant = component.get('variant', 'default')
            if not isinstance(variant, str) or (variant != 'default' and (construct, variant) not in valid_templates):
                self.issue('R1', p + '/variant', variant, 'default or a declared valid variant')
            slots = component.get('slots', {})
            if self.object(slots, p + '/slots'):
                for name, treatment in slots.items():
                    q = p + pointer('slots', name)
                    if name not in slot_map(contract):
                        self.issue('R1', q, name, 'a slot declared by this construct')
                        continue
                    if not self.object(treatment, q):
                        continue
                    self.known(treatment, {'role','emphasis','properties','states'}, q)
                    self.properties(treatment.get('properties', {}), q + '/properties')
                    self.states(treatment.get('states', {}), q + '/states', contract)
                for name, defaults in slot_map(contract).items():
                    treatment = slots.get(name, {})
                    if isinstance(treatment, dict):
                        self.role_pair(treatment.get('role', defaults['role']), treatment.get('emphasis', defaults['emphasis']), p + pointer('slots', name))
            parts = component.get('parts', {})
            if self.object(parts, p + '/parts'):
                declared = valid_templates.get((construct, variant)) if isinstance(variant, str) else None
                for name, props in parts.items():
                    if not declared or name not in declared.parts:
                        self.issue('R1', p + pointer('parts', name), name, 'a part in the selected template')
                    self.properties(props, p + pointer('parts', name))
            bindings = component.get('assets', {})
            if self.object(bindings, p + '/assets'):
                for name, binding in bindings.items():
                    q = p + pointer('assets', name)
                    if name not in slot_map(contract) or slot_map(contract)[name].get('role') != 'media':
                        self.issue('R1', q, name, 'a media slot')
                    elif isinstance(binding, str) and binding.count(':') == 1:
                        asset, variant = binding.split(':')
                        entry = d.get('assets', {}).get(asset)
                        if not isinstance(entry, dict) or not isinstance(entry.get('variants'), dict) or variant not in entry['variants']:
                            self.issue('R1', q, binding, 'a declared asset and variant', type='missing')
                        elif entry.get('kind') != slot_map(contract)[name].get('asset_kind'):
                            self.issue('R1', q, binding, 'an asset of the slot’s declared kind')
                    else:
                        self.issue('R1', q, binding, 'asset-id:variant', type='missing')
        scopes = set()
        for index, override in enumerate(d.get('overrides', [])):
            p = pointer('overrides', index)
            if not self.object(override, p):
                continue
            self.known(override, {'scope','properties','reason'}, p)
            scope = override.get('scope')
            try:
                parsed = parse_scope(scope, self.vocab)
                if scope in scopes:
                    raise ValueError('Duplicate exact override scope')
                scopes.add(scope)
                if parsed.breakpoint:
                    try:
                        self.tokens.breakpoint(parsed.breakpoint)
                    except (KeyError, ValueError):
                        self.issue('R4', p + '/scope', scope, 'a declared breakpoint.* dimension')
            except (ValueError, TypeError) as exc:
                self.issue('override-scope', p + '/scope', scope, 'one well-formed unique scope', str(exc))
            if not isinstance(override.get('reason'), str) or not override.get('reason', '').strip():
                self.issue('override-reason', p + '/reason', override.get('reason'), 'a nonempty reason')
            if 'properties' not in override:
                self.issue('schema', p + '/properties', None, 'a required properties object')
            self.properties(override.get('properties', {}), p + '/properties')
        for index, behavior in enumerate(d.get('behaviors', [])):
            p = pointer('behaviors', index)
            if not self.object(behavior, p):
                continue
            try:
                parsed = parse_scope(behavior.get('scope'), self.vocab)
                if parsed.state or parsed.breakpoint:
                    raise ValueError('Behavior scope must target a construct or slot')
            except (ValueError, TypeError) as exc:
                self.issue('R1', p + '/scope', behavior.get('scope'), 'construct[.slot]', str(exc))
            if not isinstance(behavior.get('kind'), str) or not ID.fullmatch(behavior.get('kind', '')):
                self.issue('schema', p + '/kind', behavior.get('kind'), 'a behavior kind')
        self.assets()
        self.font_gaps()

    def assets(self):
        assets = self.doc.get('assets', {})
        for name, entry in assets.items():
            p = pointer('assets', name)
            if not ID.fullmatch(name):
                self.issue('schema', p, name, 'a kebab-case asset id')
            if not self.object(entry, p):
                continue
            self.known(entry, {'kind','variants','meta'}, p)
            if not isinstance(entry.get('kind'), str) or entry.get('kind') not in KINDS:
                self.issue('schema', p + '/kind', entry.get('kind'), 'logo, font, image or icon')
            variants = entry.get('variants')
            if not self.object(variants, p + '/variants'):
                continue
            if not variants:
                self.issue('schema', p + '/variants', variants, 'at least one variant')
            for variant, detail in variants.items():
                q = p + pointer('variants', variant)
                if not ID.fullmatch(variant):
                    self.issue('schema', q, variant, 'a kebab-case variant id')
                if not self.object(detail, q):
                    continue
                self.known(detail, {'file','format','weight','style'}, q)
                if not isinstance(detail.get('format'), str) or detail.get('format') not in FORMATS:
                    self.issue('schema', q + '/format', detail.get('format'), 'a supported asset format')
                if entry.get('kind') == 'font':
                    if not is_number(detail.get('weight')) or not 1 <= detail['weight'] <= 1000:
                        self.issue('schema', q + '/weight', detail.get('weight'), 'a font weight from 1–1000')
                    if not isinstance(detail.get('style'), str) or detail.get('style') not in {'normal','italic'}:
                        self.issue('schema', q + '/style', detail.get('style'), 'normal or italic')
                try:
                    file = asset_path(self.library, self.id, detail)
                    if hashlib.sha256(file.read_bytes()).hexdigest() != detail['file'].split('/')[1]:
                        self.issue('R1', q + '/file', detail['file'], 'bytes matching their content hash')
                except (OSError, ValueError, TypeError):
                    self.issue('R1', q + '/file', detail.get('file'), 'an existing sha256/<hex> package file', type='missing')
        for path, token in self.tokens.nodes.items():
            if token['$type'] != 'fontFamily':
                continue
            try:
                asset = self.tokens.font_asset(path)
            except (AttributeError, TypeError):
                self.issue('schema', pointer('style', *path.split('.'), '$extensions'), token.get('$extensions'), 'a font asset extension object')
                continue
            if asset:
                entry = assets.get(asset) if isinstance(asset, str) else None
                if not isinstance(entry, dict) or entry.get('kind') != 'font':
                    self.issue('R1', pointer('style', *path.split('.'), '$extensions'), asset, 'a declared font asset', type='missing')

    def font_gaps(self):
        breakpoints = [None]
        for path in self.tokens.nodes:
            if path.startswith('breakpoint.'):
                bp = path.removeprefix('breakpoint.')
                try:
                    self.tokens.breakpoint(bp)
                except (KeyError, ValueError):
                    continue  # The token check already reports this invalid breakpoint.
                breakpoints.append(bp)
        for construct, component in self.doc.get('components', {}).items():
            contract = self.vocab['constructs'].get(construct)
            if not contract or not isinstance(component, dict):
                continue
            # Include implicit vocabulary slots and root treatments, not just authored slots.
            for slot in [None] + list(slot_map(contract)):
                scope = construct + ('.' + slot if slot else '')
                for state in contract['states']:
                    for bp in breakpoints:
                        try:
                            values = resolve(self.doc, self.vocab, scope, state, bp)['properties']
                            family = values.get('font-family')
                            if not family:
                                continue
                            family_pointer = property_pointer(self.doc, self.vocab, 'font-family', family)
                            _, raw_family = location(self.doc, family_pointer)
                            alias = ALIAS.fullmatch(raw_family)
                            asset = self.tokens.font_asset(alias[1])
                            entry = self.doc.get('assets', {}).get(asset)
                            if not isinstance(entry, dict) or not isinstance(entry.get('variants'), dict):
                                continue  # Missing bindings have their own R1 finding.
                            variants = [v for v in entry['variants'].values() if isinstance(v, dict)]
                        except (KeyError, ValueError, TypeError, AttributeError):
                            # Schema/reference checks above already name the invalid inputs.
                            # An unrelated invalid treatment must not hide other face gaps.
                            if not self.findings:
                                raise
                            continue
                        weight = values.get('font-weight', {}).get('value', 400)
                        style = values.get('font-style', {}).get('value', 'normal')
                        if any(v.get('weight') == weight and v.get('style') == style for v in variants):
                            continue
                        requested = 'font-weight' if not any(v.get('weight') == weight for v in variants) else 'font-style'
                        if requested not in values:
                            requested = 'font-style' if 'font-style' in values else 'font-weight'
                        if requested not in values:
                            requested = 'font-family'
                        p = property_pointer(self.doc, self.vocab, requested, values[requested])
                        self.issue('asset-font', p, None, 'a matching font weight/style variant',
                                   f'Font asset {asset} supplies no {weight}/{style} variant', type='missing')


def validate(library, language_id, document=None):
    try:
        document = load_language(library, language_id) if document is None else document
    except FileNotFoundError:
        raise
    except (ValueError, OSError) as exc:
        return report(language_id, [Finding('violation', 'schema', f'languages/{language_id}/working.json', '', None, 'valid JSON', str(exc)).to_dict()])
    if not isinstance(document, dict):
        return report(language_id, [Finding('violation', 'schema', f'languages/{language_id}/working.json', '', document, 'a language object', 'Language must be an object').to_dict()])
    version = document.get('vocabulary')
    try:
        vocab = vocabulary_store.load(library, version)
    except (OSError, ValueError, TypeError) as exc:
        path, observed = location(document, '/vocabulary')
        return report(language_id, [Finding('violation', 'R1', f'languages/{language_id}/working.json', path, observed, 'an existing vocabulary version', str(exc)).to_dict()])
    validator = Validator(library, language_id, document, vocab)
    validator.run()
    result = report(language_id, validator.findings)
    log.info('validate language=%s accepted=%s findings=%d', language_id, result['accepted'], len(result['findings']))
    return result
