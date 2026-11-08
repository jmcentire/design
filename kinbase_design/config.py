"""Local configuration and limits; paths are resolved once at the boundary."""
import os
from pathlib import Path
import tomllib
from dataclasses import dataclass, asdict
import math

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

# Capture/ingest bounds and quantization tolerances.
CAPTURE_WIDTHS = VIEWPORTS
CAPTURE_TIMEOUT_MS = 30000
CAPTURE_TOTAL_SECONDS = 600
CAPTURE_MAX_PAGES = 10
CAPTURE_MAX_REDIRECTS = 10
CAPTURE_MAX_REQUESTS = 16
WORKER_CLEANUP_SECONDS = 5
CAPTURE_MAX_WIDTHS = 12
CAPTURE_MAX_NODES = 600
CAPTURE_MAX_TEXT = 4000
CAPTURE_MAX_ASSETS = 80
ARTIFACT_MAX_FILES = 256
ARTIFACT_MAX_BYTES = 100 * 1024 * 1024
INGEST_COLOR_DELTA_E = 2.0
INGEST_TYPE_TOLERANCE_PX = 1.0
INGEST_SPACE_TOLERANCE_PX = 1.0
INGEST_TYPE_RATIO_TOLERANCE = 0.05
INGEST_MAX_COLORS = 128
INGEST_IMAGE_SAMPLE_SIZE = 128
INGEST_LLM_TIMEOUT_SECONDS = 30
INGEST_DEFAULT_SPACE = 8
INGEST_FULL_RADIUS_PX = 9999


@dataclass(frozen=True)
class IngestConfig:
    color_delta_e: float = INGEST_COLOR_DELTA_E
    type_size_px: float = INGEST_TYPE_TOLERANCE_PX
    type_ratio: float = INGEST_TYPE_RATIO_TOLERANCE
    spacing_px: float = INGEST_SPACE_TOLERANCE_PX
    radius_px: float = 1.0
    widths: tuple = CAPTURE_WIDTHS
    capture_timeout_s: float = CAPTURE_TIMEOUT_MS / 1000
    max_pages: int = CAPTURE_MAX_PAGES

    def __post_init__(self):
        for key in ('color_delta_e','type_size_px','type_ratio','spacing_px','radius_px','capture_timeout_s'):
            value=getattr(self,key)
            if type(value) not in {int,float} or not math.isfinite(value) or value<0 or key=='capture_timeout_s' and value==0:
                raise ValueError('ingest.'+key+' must be a finite '+('positive' if key=='capture_timeout_s' else 'nonnegative')+' number')
        if type(self.max_pages)!=int or self.max_pages<1:raise ValueError('ingest.max_pages must be a positive integer')
        if not isinstance(self.widths,(tuple,list)) or not self.widths or len(self.widths)>CAPTURE_MAX_WIDTHS or any(type(w)!=int or not 1<=w<=CHECK_MAX_WIDTH for w in self.widths):
            raise ValueError('ingest.widths must contain bounded positive integer widths')
        object.__setattr__(self,'widths',tuple(sorted(set(self.widths))))

    @property
    def timeout_ms(self):return max(1,round(self.capture_timeout_s*1000))

    def to_dict(self):return {**asdict(self),'widths':list(self.widths)}


def ingest_config(path=None):
    """Read once at an application boundary; pass the immutable settings inward."""
    path=Path(path) if path is not None else Path.cwd()/'kinbase-design.toml'
    values=tomllib.loads(path.read_text()).get('ingest',{}) if path.exists() else {}
    if not isinstance(values,dict):raise ValueError('ingest configuration must be a table')
    unknown=set(values)-set(IngestConfig.__dataclass_fields__)
    if unknown:raise ValueError('Unknown ingest settings: '+', '.join(sorted(unknown)))
    return IngestConfig(**values)
