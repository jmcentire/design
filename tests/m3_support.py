"""M3 public-command drivers and amendment 10 dimension/choice oracles."""

import hashlib
import json
import math
from pathlib import Path
import shutil

from tests.m2_support import confined, read_json
from tests.support import LibraryCase

RANGES = {
    "hue-family": (0, 360), "value-contrast": (0, 1), "saturation": (0, 1),
    "type-scale": (1.067, 1.618), "density": (2, 16), "shape": (0, 32),
    "formality": (0, 1), "whimsy": (0, 1),
}
PAIRINGS = {"geometric-sans", "humanist-sans", "rounded", "serif", "slab"}
DIMENSIONS = set(RANGES) | {"type-pairing"}
BEACH = ("A casual site for young families; relaxing but engaging beach vacation; "
         "blues, greens and turquoise; whimsical flair")


def generate(library, *args, timeout=90):
    return library.json("generate", *args, cwd=library.project, timeout=timeout)


def start(library, brief="An inviting reading room", artifacts=()):
    options = [value for artifact in artifacts for value in ("--artifact", artifact)]
    output = generate(library, "start", "--brief", brief, *options)
    session = output["session"]
    root = library.workspace / "sessions" / session
    assert root.resolve().is_relative_to(library.workspace.resolve())
    assert read_json(root / "session.json")["brief"] == brief
    assert isinstance(output["seeds"], dict)
    return session, root, output["seeds"]


def dimension_value(dimension, value):
    if dimension == "type-pairing":
        assert value in PAIRINGS, value
    else:
        assert isinstance(value, (float, int)) and not isinstance(value, bool) and math.isfinite(value)
        low, high = RANGES[dimension]
        assert low <= value <= high, (dimension, value)
        if dimension == "hue-family":
            assert value < high


def distance(dimension, first, second):
    if dimension == "type-pairing":
        return int(first != second)
    difference = abs(first - second)
    return min(difference, 360 - difference) if dimension == "hue-family" else difference


def candidate_directory(library, session, candidate):
    """Amendment 11 makes the preview a materialized workspace directory."""
    relative = Path(candidate["preview"])
    assert not relative.is_absolute()
    expected = Path("sessions") / session / "candidates" / candidate["hash"]
    assert relative == expected, (relative, expected)
    directory = library.workspace / relative
    assert directory.resolve().is_relative_to(library.workspace.resolve())
    for name in ("working.json", "sample.html", "language.css"):
        assert (directory / name).is_file(), ("Incomplete candidate", directory, name)
    assert (directory / "assets").is_dir()
    # Amendment 14: preview URLs alone do not constitute a language package.
    # Every manifest reference must resolve to local, content-addressed bytes.
    document = read_json(directory / "working.json")
    for asset in document.get("assets", {}).values():
        for variant in asset["variants"].values():
            file = confined(directory / "assets", variant["file"])
            digest = hashlib.sha256(file.read_bytes()).hexdigest()
            assert variant["file"] == "sha256/" + digest, ("Missing or altered packaged asset", variant)
    return directory


def candidate_library(library, directory):
    """Copy the complete delivered directory, without repairing its manifest/files."""
    project = library.project / "portable-candidates" / directory.name
    root = project / "design-library"
    document = read_json(directory / "working.json")
    shutil.copytree(library.library / "vocabulary", root / "vocabulary", dirs_exist_ok=True)
    case = LibraryCase(project, root, project / "fresh-workspace")
    destination = case.path(document["id"]).parent
    assert destination.resolve().is_relative_to(root.resolve())
    shutil.copytree(directory, destination, dirs_exist_ok=True)
    assert case.path(document["id"]).read_bytes() == (directory / "working.json").read_bytes()
    return case, document


def pair(library, session, root):
    result = generate(library, "pair", session)
    if result.get("done") is True:
        return result
    dimensions = result["dimensions"]
    assert 1 <= len(dimensions) <= 2 and len(dimensions) == len(set(dimensions))
    assert set(dimensions) <= DIMENSIONS
    assert result["pair"] and isinstance(result["round"], int)
    for side in ("a", "b"):
        candidate = result[side]
        assert candidate["hash"]
        assert set(candidate["values"]) == DIMENSIONS
        for name, value in candidate["values"].items():
            dimension_value(name, value)
        candidate_directory(library, session, candidate)
    changed = {name for name in DIMENSIONS if result["a"]["values"][name] != result["b"]["values"][name]}
    assert changed == set(dimensions), "The pair must isolate exactly its advertised unsettled dimensions"
    assert result["a"]["hash"] != result["b"]["hash"]
    assert set(result["variation"]) == set(dimensions)
    for dimension, variation in result["variation"].items():
        observed = variation["distance"]
        assert isinstance(observed, (int, float)) and not isinstance(observed, bool) and math.isfinite(observed)
        expected = distance(dimension, result["a"]["values"][dimension], result["b"]["values"][dimension])
        assert math.isclose(observed, expected, rel_tol=1e-9, abs_tol=1e-9), (dimension, variation, expected)
        assert type(variation["widest"]) is bool
    return result


def log_bytes(root):
    path = root / "choices.jsonl"
    return path.read_bytes() if path.exists() else b""


def log_records(root):
    return [json.loads(line) for line in log_bytes(root).splitlines()]


def choose(library, session, root, candidate_pair, choice, *, supersedes=None, comment=""):
    before = log_bytes(root)
    options = ["--comment", comment]
    if supersedes is not None:
        options += ["--supersedes", supersedes]
    library.cli("generate", "choose", session, candidate_pair["pair"], choice, *options,
                cwd=library.project, timeout=90)
    after = log_bytes(root)
    assert after.startswith(before), "A choice rewrote or removed earlier history"
    appended = after[len(before):].splitlines()
    assert len(appended) == 1 and after.endswith(b"\n")
    record = json.loads(appended[0])
    expected = {"round": candidate_pair["round"], "pair": candidate_pair["pair"],
                "a": candidate_pair["a"]["hash"], "b": candidate_pair["b"]["hash"],
                "dimensions": candidate_pair["dimensions"], "choice": choice,
                "comment": comment, "supersedes": supersedes}
    for key, value in expected.items():
        assert record[key] == value, (key, record)
    assert record["id"] and record["ts"]
    records = log_records(root)
    assert len({entry["id"] for entry in records}) == len(records)
    return record


def settled(library, session, root):
    output = generate(library, "settled", session)
    assert output["session"] == session
    values, unsettled = output["settled"], output["unsettled"]
    assert set(values) | set(unsettled) == DIMENSIONS
    assert not set(values) & set(unsettled) and len(unsettled) == len(set(unsettled))
    records = log_records(root)
    superseded = {record["supersedes"] for record in records if record["supersedes"]}
    effective = {record["id"]: record for record in records
                 if record["id"] not in superseded and record["choice"] != "neither"}
    for name, result in values.items():
        dimension_value(name, result["value"])
        assert result["choices"] and set(result["choices"]) <= set(effective)
        assert all(name in effective[identity]["dimensions"] for identity in result["choices"])
    return output
