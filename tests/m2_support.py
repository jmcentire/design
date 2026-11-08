"""Independent M2 measurement/provenance oracles and public artifact readers."""

import json
import math
from pathlib import Path
import re
import shutil

from PIL import Image

from tests.support import LibraryCase, pointer_value


def read_json(path):
    return json.loads(path.read_text())


def confined(root, relative):
    path = Path(relative)
    assert not path.is_absolute(), relative
    target = root / path
    assert target.resolve().is_relative_to(root.resolve()), relative
    assert target.is_file(), target
    return target


def png(path):
    with Image.open(path) as picture:
        assert picture.format == "PNG" and picture.width > 0 and picture.height > 0
        picture.load()


def capture(library, urls):
    args = [arg for url in urls for arg in ("--url", url)]
    output = library.json("capture", *args, cwd=library.project, timeout=90)
    return captured_artifact(library, urls, output)


def captured_artifact(library, urls, output):
    """Inspect the public result independently of how the real CLI was supervised."""
    artifact = output["artifact"]
    root = library.workspace / "artifacts" / artifact
    assert root.resolve().is_relative_to(library.workspace.resolve())
    document = read_json(root / "capture.json")
    assert document["kind"] == "capture"
    assert set(output["pages"]) == {p["name"] for p in document["pages"]}
    assert output["problems"] == document["problems"]
    assert {p["url"] for p in document["pages"]} == set(urls)
    for page in document["pages"]:
        for width, files in page["widths"].items():
            assert int(width) > 0
            assert files["screenshot"] == f'pages/{page["name"]}@{width}.png'
            assert files["dom"] == f'pages/{page["name"]}@{width}.html'
            assert files["styles"] == f'pages/{page["name"]}@{width}.styles.json'
            png(confined(root, files["screenshot"]))
            assert confined(root, files["dom"]).read_text().strip()
            assert read_json(confined(root, files["styles"])), "Empty computed-style capture"
    return artifact, root, document


def draft(library, artifacts, name):
    args = [arg for artifact in artifacts for arg in ("--from", artifact)]
    summary = library.json("draft", *args, "--language", name, cwd=library.project, timeout=90)
    root = library.workspace / "drafts" / name
    assert summary == read_json(root / "summary.json")
    assert summary["draft"] == name and summary["mapping"] == "heuristic"
    document = read_json(root / "working.json")
    assert document["id"] == name
    assert_valid_draft(library, document, root)
    return root, document, summary


def assert_valid_draft(library, document, root):
    """Run the same public validator against an isolated copy, without saving the draft."""
    validation_root = library.project / "draft-validation" / document["id"]
    shutil.copytree(library.library / "vocabulary", validation_root / "vocabulary", dirs_exist_ok=True)
    case = LibraryCase(library.project, validation_root, library.workspace)
    case.write(document)
    if (root / "assets").is_dir():
        shutil.copytree(root / "assets", case.path(document["id"]).parent / "assets", dirs_exist_ok=True)
    case.validate(document["id"], accepted=True)


def token_values(style, prefix=(), inherited=None):
    """Read DTCG values without adopting candidate naming or quantization decisions."""
    if "$value" in style:
        yield ".".join(prefix), style.get("$type", inherited), style["$value"]
    else:
        inherited = style.get("$type", inherited)
        for key, child in style.items():
            if not key.startswith("$") and isinstance(child, dict):
                yield from token_values(child, (*prefix, key), inherited)


def dereference(style, value, seen=()):
    if isinstance(value, str) and value.startswith("{") and value.endswith("}"):
        name = value[1:-1]
        assert name not in seen
        node = style
        for key in name.split("."):
            node = node[key]
        return dereference(style, node["$value"], (*seen, name))
    return value


def dimension_px(value):
    if isinstance(value, dict):
        assert value["unit"] in {"px", "rem"}
        return value["value"] * (16 if value["unit"] == "rem" else 1)
    if value.endswith("rem"):
        return float(value[:-3]) * 16
    assert value.endswith("px"), value
    return float(value[:-2])


def scalar_leaves(value, pointer=""):
    if isinstance(value, dict):
        for key, child in value.items():
            yield from scalar_leaves(child, pointer + "/" + key.replace("~", "~0").replace("/", "~1"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from scalar_leaves(child, pointer + f"/{index}")
    else:
        yield pointer, value


def provenance_at(records, pointer):
    """Amendment 09: an exact record wins, otherwise use the nearest ancestor."""
    while pointer not in records:
        assert pointer, "Design value has no provenance"
        pointer = pointer.rsplit("/", 1)[0]
    return records[pointer]


def design_pointers(document):
    for name, _, value in token_values(document.get("style", {})):
        pointer = "/style/" + "/".join(part.replace("~", "~0").replace("/", "~1") for part in name.split(".")) + "/$value"
        for leaf, _ in scalar_leaves(value, pointer):
            yield leaf
    for section in ("roles", "layout", "components", "overrides", "behaviors", "assets"):
        for pointer, _ in scalar_leaves(document.get(section, {}), "/" + section):
            segments = pointer.split("/")
            if any(part in {"$type", "$description", "$extensions", "description"} for part in segments):
                continue
            if section in {"overrides", "behaviors"} and segments[-1] == "reason":
                continue
            yield pointer


def assert_provenance(document, records, shared=False):
    assert isinstance(records, dict)
    for pointer, record in records.items():
        pointer_value(document, pointer)
        assert record["kind"] in {"source", "inferred", "chosen"}
        if shared:
            assert set(record) <= {"kind", "artifact", "location", "method"}, record
        if record["kind"] == "source":
            assert isinstance(record["artifact"], str) and record["artifact"]
            assert isinstance(record["location"], str) and record["location"]
        elif record["kind"] == "inferred":
            assert isinstance(record["method"], str) and record["method"]
            if not shared:
                assert isinstance(record["inputs"], list)
        elif not shared:
            assert isinstance(record["choice"], str) and record["choice"]
    pointers = list(design_pointers(document))
    assert pointers
    for pointer in pointers:
        assert provenance_at(records, pointer)["kind"] in {"source", "inferred", "chosen"}


def assert_shared_privacy(library):
    """Inspect shared metadata; supplied package assets retain their original bytes."""
    private = (str(library.workspace), str(library.project), str(library.workspace.parent))
    for path in library.library.rglob("*"):
        if not path.is_file():
            continue
        # B8 governs metadata/provenance, while B6 preserves supplied assets.
        # SVG namespace URIs (and other original asset content) are not leaks
        # introduced by shared provenance. Do not exempt any other library text.
        if path.parent.name == "sha256" and path.parent.parent.name == "assets":
            continue
        data = path.read_bytes()
        assert not any(value.encode() in data for value in private), path
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            continue
        assert not re.search(r"(?:https?|file)://", text, re.I), path
        if path.suffix != ".json":
            continue
        document = json.loads(text)
        records = path.parent.name == "provenance"
        if records:
            working = read_json(path.parent.parent / "working.json")
            for pointer in document:
                pointer_value(working, pointer)  # These keys are not filesystem paths.
        for pointer, value in scalar_leaves(document):
            if not isinstance(value, str):
                continue
            assert not re.search(r"(?:^|\s)[A-Za-z]:[\\/]", value), (path, value)
            if not value.startswith("/"):
                continue
            # Only provenance locations may legitimately look absolute: the
            # contract permits selectors and JSON pointers. Concrete private
            # source/workspace paths are checked above, including inside strings.
            assert records and pointer.endswith("/location"), (path, value)
            assert not re.match(r"/(?:Users|home|private|tmp|var|etc|opt|usr|Volumes)/", value), (path, value)


def lab(hex_color):
    """sRGB -> CIE Lab, D65 white; arithmetic independent of the extractor."""
    rgb = [int(hex_color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    rgb = [v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in rgb]
    matrix = ((0.4124564, 0.3575761, 0.1804375),
              (0.2126729, 0.7151522, 0.0721750), (0.0193339, 0.1191920, 0.9503041))
    xyz = [sum(a * b for a, b in zip(row, rgb)) / white for row, white in zip(matrix, (0.95047, 1, 1.08883))]
    f = [v ** (1 / 3) if v > (6 / 29) ** 3 else v / (3 * (6 / 29) ** 2) + 4 / 29 for v in xyz]
    return 116 * f[1] - 16, 500 * (f[0] - f[1]), 200 * (f[1] - f[2])


def delta_e_2000(first, second):
    """CIEDE2000 with unit parametric factors, using the standard hue-wrap formula."""
    l1, a1, b1 = first
    l2, a2, b2 = second
    cbar = (math.hypot(a1, b1) + math.hypot(a2, b2)) / 2
    g = (1 - math.sqrt(cbar ** 7 / (cbar ** 7 + 25 ** 7))) / 2
    a1, a2 = (1 + g) * a1, (1 + g) * a2
    c1, c2 = math.hypot(a1, b1), math.hypot(a2, b2)
    h1, h2 = math.degrees(math.atan2(b1, a1)) % 360, math.degrees(math.atan2(b2, a2)) % 360
    dh = h2 - h1
    if c1 * c2 == 0:
        dh = 0
    elif dh > 180:
        dh -= 360
    elif dh < -180:
        dh += 360
    dl, dc = l2 - l1, c2 - c1
    d_h = 2 * math.sqrt(c1 * c2) * math.sin(math.radians(dh / 2))
    lbar, cpbar = (l1 + l2) / 2, (c1 + c2) / 2
    if c1 * c2 == 0:
        hbar = h1 + h2
    elif abs(h1 - h2) <= 180:
        hbar = (h1 + h2) / 2
    elif h1 + h2 < 360:
        hbar = (h1 + h2 + 360) / 2
    else:
        hbar = (h1 + h2 - 360) / 2
    cos = lambda angle: math.cos(math.radians(angle))
    t = 1 - 0.17 * cos(hbar - 30) + 0.24 * cos(2 * hbar) + 0.32 * cos(3 * hbar + 6) - 0.20 * cos(4 * hbar - 63)
    sl = 1 + 0.015 * (lbar - 50) ** 2 / math.sqrt(20 + (lbar - 50) ** 2)
    sc, sh = 1 + 0.045 * cpbar, 1 + 0.015 * cpbar * t
    rt = -2 * math.sqrt(cpbar ** 7 / (cpbar ** 7 + 25 ** 7)) * math.sin(math.radians(60 * math.exp(-((hbar - 275) / 25) ** 2)))
    return math.sqrt((dl / sl) ** 2 + (dc / sc) ** 2 + (d_h / sh) ** 2 + rt * (dc / sc) * (d_h / sh))


def color_distance(first, second):
    return delta_e_2000(lab(first), lab(second))
