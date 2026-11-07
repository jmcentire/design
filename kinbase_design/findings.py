"""Shared validation/rendered-check result shape."""
from dataclasses import asdict, dataclass
from typing import Literal


@dataclass(frozen=True)
class Finding:
    type: Literal["violation", "missing", "needs-review", "coverage"]
    rule: str
    file: str
    pointer: str
    observed: object
    expected: str
    message: str

    def to_dict(self):
        return asdict(self)


def report(language, findings):
    return {"language": language,
            "accepted": not any(f["type"] in {"missing", "violation", "needs-review"} for f in findings),
            "findings": findings}


def pointer(*parts):
    return "".join("/" + str(p).replace("~", "~0").replace("/", "~1") for p in parts)


def location(document, requested_pointer):
    """Return the existing value addressed by a pointer, or its nearest ancestor.

    Missing fields are reported at their owning object. Derive observed from the
    source document so diagnostic summaries can never stand in for source values.
    """
    value = document
    walked = []
    for encoded in requested_pointer.split('/')[1:]:
        key = encoded.replace('~1', '/').replace('~0', '~')
        if isinstance(value, dict) and key in value:
            value = value[key]
        elif isinstance(value, list) and key.isdecimal() and int(key) < len(value):
            value = value[int(key)]
        else:
            break
        walked.append(key)
    return pointer(*walked), value
