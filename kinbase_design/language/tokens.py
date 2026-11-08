"""DTCG token traversal, alias evaluation, and public value normalization."""
import math
import re
from ..config import REM_PX

ALIAS = re.compile(r"^\{([a-zA-Z0-9_-]+(?:\.[a-zA-Z0-9_-]+)*)\}$")
DIMENSION = re.compile(r"^(-?(?:\d+(?:\.\d+)?|\.\d+))(px|rem)$")
TYPES = {"color", "dimension", "fontFamily", "fontWeight", "number", "duration", "gradient"}


class GradientError(ValueError):
    def __init__(self, rule, parts, message):
        self.rule, self.parts = rule, parts
        super().__init__(message)


def is_number(value):
    return isinstance(value, (float, int)) and not isinstance(value, bool) and math.isfinite(value)


def flatten(tree, prefix="", inherited=None):
    result = {}
    if not isinstance(tree, dict):
        raise ValueError("Token groups must be objects")
    inherited = tree.get("$type", inherited)
    for name, node in tree.items():
        if name.startswith("$"):
            continue
        path = f"{prefix}.{name}" if prefix else name
        if not isinstance(node, dict) or not re.fullmatch(r"[a-zA-Z0-9_-]+", name):
            raise ValueError(f"Invalid token or group: {path}")
        if "$value" in node:
            result[path] = {**node, "$type": node.get("$type", inherited)}
        else:
            result.update(flatten(node, path, inherited))
    return result


def number_text(value):
    return format(float(value), ".15g")


def normalize(kind, value):
    if kind == "color":
        if isinstance(value, str) and re.fullmatch(r"#[0-9a-fA-F]{6}(?:[0-9a-fA-F]{2})?", value):
            value = value.lower()
            return value[:7] if len(value) == 9 and value[-2:] == "ff" else value
        if isinstance(value, dict) and value.get("colorSpace") == "srgb":
            rgb = value.get("components")
            alpha = value.get("alpha", 1)
            if (isinstance(rgb, list) and len(rgb) == 3 and
                all(is_number(v) and 0 <= v <= 1 for v in rgb) and is_number(alpha) and 0 <= alpha <= 1):
                channels = rgb + ([alpha] if alpha < 1 else [])
                return "#" + "".join(f"{int(v * 255 + .5):02x}" for v in channels)
    elif kind == "dimension":
        if isinstance(value, str):
            m = DIMENSION.fullmatch(value)
            if m:
                return number_text(float(m[1])) + m[2]
        if isinstance(value, dict) and is_number(value.get("value")) and value.get("unit") in ("px", "rem"):
            return number_text(value["value"]) + value["unit"]
    elif kind == "fontFamily":
        families = [value] if isinstance(value, str) else value
        if isinstance(families, list) and families and all(isinstance(v, str) and re.fullmatch(r"[\w -]+", v) and v.strip() for v in families):
            return ", ".join('"' + v + '"' if " " in v else v for v in families)
    elif kind == "fontWeight":
        if is_number(value) and 1 <= value <= 1000:
            return value
    elif kind == "number":
        if is_number(value):
            return value
    elif kind == "duration":
        if isinstance(value, dict) and is_number(value.get("value")) and value["value"] >= 0 and value.get("unit") in ("ms", "s"):
            return number_text(value["value"]) + value["unit"]
        if isinstance(value, str) and re.fullmatch(r"\d+(?:\.\d+)?(?:ms|s)", value):
            return value
    raise ValueError(f"Invalid {kind} token value")


class Tokens:
    def __init__(self, style):
        self.nodes = flatten(style)

    def evaluate(self, path, trail=()):
        if path in trail:
            raise ValueError("Token alias cycle: " + " → ".join((*trail, path)))
        if path not in self.nodes:
            raise KeyError(path)
        node = self.nodes[path]
        kind = node.get("$type")
        if not isinstance(kind, str) or kind not in TYPES:
            raise ValueError("Token needs a supported $type")
        value = node["$value"]
        alias = ALIAS.fullmatch(value) if isinstance(value, str) else None
        if alias:
            target_kind, result = self.evaluate(alias[1], (*trail, path))
            if target_kind != kind:
                raise ValueError("Alias type differs from target type")
            return kind, result
        if kind == 'gradient':
            return kind, self.gradient(value, (*trail, path))
        return kind, normalize(kind, value)

    def gradient(self, value, trail):
        if not isinstance(value, list) or len(value) < 2:
            raise GradientError('R2', (), 'A gradient needs at least two color stops')
        stops = []
        for index, stop in enumerate(value):
            if not isinstance(stop, dict):
                raise GradientError('R2', (index,), 'A gradient stop must be an object')
            position = stop.get('position')
            if not is_number(position) or not 0 <= position <= 1:
                raise GradientError('R2', (index,'position'), 'Gradient position must be between 0 and 1')
            raw = stop.get('color')
            alias = ALIAS.fullmatch(raw) if isinstance(raw, str) else None
            try:
                if alias:
                    kind, result = self.evaluate(alias[1], trail)
                    if kind != 'color':
                        raise ValueError('Gradient color alias must name a color token')
                else:
                    result = normalize('color', raw)
            except (KeyError, ValueError) as exc:
                raise GradientError('R1' if alias else 'R2', (index,'color'), str(exc)) from exc
            stops.append(result + ' ' + number_text(position * 100) + '%')
        return 'linear-gradient(180deg, ' + ', '.join(stops) + ')'

    def reference(self, value):
        alias = ALIAS.fullmatch(value) if isinstance(value, str) else None
        if not alias:
            raise ValueError("Expected a token reference")
        return self.evaluate(alias[1])

    def font_asset(self, path, trail=()):
        if path in trail or path not in self.nodes:
            return None
        node = self.nodes[path]
        asset = node.get("$extensions", {}).get("kinbase-design", {}).get("asset")
        alias = ALIAS.fullmatch(node["$value"]) if isinstance(node["$value"], str) else None
        return asset or (self.font_asset(alias[1], (*trail, path)) if alias else None)

    def breakpoint(self, name):
        if not isinstance(name, str) or not re.fullmatch(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*", name):
            raise ValueError("Breakpoint must be a declared breakpoint id, such as md")
        path = "breakpoint." + name
        kind, value = self.evaluate(path)
        if kind != "dimension":
            raise ValueError("Breakpoint must be a dimension")
        match = DIMENSION.fullmatch(value)
        return float(match[1]) * (REM_PX if match[2] == "rem" else 1)
