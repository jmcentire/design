"""Private ingest evidence has the same byte budget on write and read."""
from ..config import INGEST_JSON_MAX_BYTES
from ..storage import read_json, write_json


def read_document(path):return read_json(path,max_bytes=INGEST_JSON_MAX_BYTES)


def write_document(path,value):write_json(path,value,max_bytes=INGEST_JSON_MAX_BYTES)


def stored_view(view):
    # The captured nodes already hold these styles and selectors. Fidelity needs
    # mapped content, not second copies of root/slot nodes embedded per instance.
    return {**view,'instances':[{key:value for key,value in item.items() if key not in {'nodes','root_node'}}
                               for item in view['instances']]}
