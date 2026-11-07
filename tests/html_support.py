"""Parse shipped HTML at the public boundary; never inspect implementation markup."""

from dataclasses import dataclass, field
from html.parser import HTMLParser


@dataclass
class Element:
    tag: str
    attrs: dict = field(default_factory=dict)
    children: list = field(default_factory=list)

    def all(self, tag=None, **attrs):
        matches = []
        if (tag is None or self.tag == tag) and all(self.attrs.get(k) == v for k, v in attrs.items()):
            matches.append(self)
        for child in self.children:
            if isinstance(child, Element):
                matches.extend(child.all(tag, **attrs))
        return matches

    def text(self):
        return " ".join(" ".join(c.text() if isinstance(c, Element) else c for c in self.children).split())


class Document(HTMLParser):
    def __init__(self, data):
        super().__init__(convert_charrefs=True)
        self.root = Element("document")
        self.stack = [self.root]
        self.feed(data.decode("utf-8") if isinstance(data, bytes) else data)
        self.close()

    def handle_starttag(self, tag, attrs):
        node = Element(tag, dict(attrs))
        self.stack[-1].children.append(node)
        if tag not in {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.stack[-1].children.append(Element(tag, dict(attrs)))

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag:
                del self.stack[i:]
                break

    def handle_data(self, data):
        self.stack[-1].children.append(data)

    def all(self, tag=None, **attrs):
        return self.root.all(tag, **attrs)

    def text(self):
        return self.root.text()
