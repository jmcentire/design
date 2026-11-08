"""Private draft staging lets validation, rendering, checks and promotion stay shared."""
from contextlib import contextmanager
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory
from ..storage import identifier,inside,read_json,save_working,save_language


def folder(workspace,draft_id):return inside(workspace,'drafts',identifier(draft_id))

def load_draft(workspace,draft_id):return read_json(inside(folder(workspace,draft_id),'working.json'))

def write_draft(workspace,draft_id,document):save_working(inside(folder(workspace,draft_id),'working.json'),draft_id,document)


@contextmanager
def stage(library,workspace,draft_id,document=None):
    document=document or load_draft(workspace,draft_id)
    with TemporaryDirectory(prefix='kinbase-draft-') as temporary:
        root=Path(temporary)
        shutil.copytree(inside(library,'vocabulary'),root/'vocabulary')
        save_language(root,draft_id,document)
        assets=inside(folder(workspace,draft_id),'assets')
        if assets.exists():shutil.copytree(assets,root/'languages'/draft_id/'assets')
        yield root
