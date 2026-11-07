"""Local configuration and limits; paths are resolved once at the boundary."""
import os
from pathlib import Path
import tomllib

MAX_UPLOAD_BYTES = 20 * 1024 * 1024
VIEWPORTS = (320, 768, 1280)
DEFAULT_VIEWPORT = 768
REM_PX = 16
MAX_JSON_BYTES = 4 * 1024 * 1024


def roots(library=None, workspace=None):
    file = Path.cwd() / "kinbase-design.toml"
    config = tomllib.loads(file.read_text()) if file.exists() else {}
    library = Path(library or os.environ.get("KINBASE_DESIGN_LIBRARY") or
                   config.get("library", "library")).expanduser().resolve()
    workspace = Path(workspace or os.environ.get("KINBASE_DESIGN_WORKSPACE") or
                     config.get("workspace", Path.home() / ".local/share/kinbase-design")).expanduser().resolve()
    if workspace == library or library in workspace.parents:
        raise ValueError("Private workspace must be outside the shared library")
    return library, workspace
