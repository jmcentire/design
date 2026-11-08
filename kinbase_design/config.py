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

# Rendered-check bounds (all browser/worker waits terminate).
CHECK_WIDTHS = VIEWPORTS
CHECK_VIEWPORT_HEIGHT = 900
CHECK_TIMEOUT_MS = 15000
CHECK_TOTAL_TIMEOUT_SECONDS = 600
CHECK_TEXT_CONTRAST = 4.5
CHECK_LARGE_TEXT_CONTRAST = 3.0
CHECK_NON_TEXT_CONTRAST = 3.0
CHECK_LARGE_TEXT_PX = 24
CHECK_LARGE_BOLD_PX = 18.6666667
CHECK_BOLD_WEIGHT = 700
CHECK_TARGET_SIZE = 24
CHECK_PIXEL_TOLERANCE = 0.75
CHECK_COLOR_TOLERANCE = 1 / 255
CHECK_MAX_WIDTH = 7680
CHECK_MAX_WIDTHS = 8
CHECK_MAX_TAB_STEPS = 2000
CHECK_NUMBER_TOLERANCE = 1e-6
