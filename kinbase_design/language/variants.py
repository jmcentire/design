"""Parse the restricted template grammar, never arbitrary Jinja or HTML."""
from ..vocabulary import slot_map
from html.parser import HTMLParser
import re
from ..storage import ID

SLOT = re.compile(r'\{\{slot:([a-z0-9-]+)\}\}')


class Template(HTMLParser):
    def __init__(self, text, contract):
        super().__init__(convert_charrefs=False)
        self.contract = contract
        self.stack = []
        self.roots = 0
        self.slots = []
        self.parts = set()
        self.feed(text)
        self.close()
        if self.stack or self.roots != 1:
            raise ValueError('Template needs one balanced contract root')
        order = list(slot_map(contract))
        for slot, definition in slot_map(contract).items():
            count = self.slots.count(slot)
            if count > 1 or (definition['required'] and count != 1):
                raise ValueError(f'Slot {slot} must appear ' + ('exactly once' if definition['required'] else 'at most once'))
        if self.slots != sorted(self.slots, key=order.index):
            raise ValueError('Slots must follow contract reading order')

    def handle_starttag(self, tag, attrs):
        if not self.stack:
            self.roots += 1
            if tag != self.contract['root'] or attrs:
                raise ValueError('Wrong contract root or forbidden root attributes')
        else:
            if tag not in {'div', 'span'}:
                raise ValueError('Only div/span wrappers are permitted')
            if attrs and (len(attrs) != 1 or attrs[0][0] != 'data-kd-part' or not ID.fullmatch(attrs[0][1] or '')):
                raise ValueError('Wrappers may only have a data-kd-part identifier')
            if attrs:
                self.parts.add(attrs[0][1])
        self.stack.append(tag)

    def handle_endtag(self, tag):
        if not self.stack or self.stack.pop() != tag:
            raise ValueError('Unbalanced template')

    def handle_startendtag(self, tag, attrs):
        raise ValueError('Self-closing elements are not in the template grammar')

    def handle_data(self, data):
        slots = SLOT.findall(data)
        if SLOT.sub('', data).strip():
            raise ValueError('Template may contain only slot placeholders and whitespace')
        if slots and not self.stack:
            raise ValueError('Slots must be inside the root')
        if any(s not in slot_map(self.contract) for s in slots):
            raise ValueError('Unknown slot')
        self.slots.extend(slots)

    def handle_comment(self, data):
        raise ValueError('Comments are not in the template grammar')

    def handle_entityref(self, name):
        raise ValueError('Text entities are not in the template grammar')

    handle_charref = handle_entityref

    def handle_decl(self, decl):
        raise ValueError('Declarations are not in the template grammar')

    def handle_pi(self, data):
        raise ValueError('Processing instructions are not in the template grammar')

    def unknown_decl(self, data):
        raise ValueError('Declarations are not in the template grammar')
