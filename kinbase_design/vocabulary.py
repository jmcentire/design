"""Read versioned, presentation-free content contracts from an explicit library."""
from .storage import identifier, inside, read_json


def load(library, version="v1"):
    return read_json(inside(library, "vocabulary", identifier(version), "vocabulary.json"))


def samples(library, version="v1"):
    return read_json(inside(library, "vocabulary", identifier(version), "samples.json"))


def slot_map(contract):
    """Index the public ordered slots without creating a second contract."""
    return {slot['id']: slot for slot in contract['slots']}
