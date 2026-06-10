"""
leathercraft_dsl — DSL compiler for the leathercraft_svg library.

Usage:
    python leathercraft_dsl.py build pattern.lcraft

Supported constructs: pattern, size, layer, symmetry, rectangle,
rounded_rectangle, circle, triangle, rounded_triangle, outer,
stitches, holes, hole, export.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Union

from leathercraft_svg import (
    Arc,
    Circle,
    Ellipse,
    Point,
    Polygon,
    Rectangle,
    RoundedRectangle,
    RoundedTriangle,
    Stadium,
    StrokeStyle,
    SvgDocument,
    Triangle,
    mirror_polyline,
    offset_polyline,
)

# ---------------------------------------------------------------------------
# Named-colour table (DSL colour → hex)
# ---------------------------------------------------------------------------

_NAMED_COLORS: dict[str, str] = {
    "red": "#ff0000",
    "blue": "#0000ff",
    "green": "#00aa00",
    "gray": "#777777",
    "grey": "#777777",
    "black": "#000000",
    "white": "#ffffff",
}

# ---------------------------------------------------------------------------
# Edge aliases (rectangle-centric; triangle edges use numeric indices)
# ---------------------------------------------------------------------------

_RECT_EDGE_NAMES: dict[str, int] = {
    "top": 0,
    "right": 1,
    "bottom": 2,
    "left": 3,
}

_EDGE_ALIASES: dict[str, list[str]] = {
    "all": ["top", "right", "bottom", "left"],
    "except_top": ["right", "bottom", "left"],
    "sides": ["left", "right"],
    "horizontal": ["top", "bottom"],
    "vertical": ["left", "right"],
}

# ---------------------------------------------------------------------------
# DSL model dataclasses
# ---------------------------------------------------------------------------


@dataclass
class LayerStyle:
    color: str
    stroke_width: float
    dashed: bool = False


@dataclass
class RectangleDefinition:
    id: str
    x: float
    y: float
    width: float
    height: float
    layer: str = "cut"


@dataclass
class RoundedRectangleDefinition:
    id: str
    x: float
    y: float
    width: float
    height: float
    radius: float
    layer: str = "cut"
    radius_tl: float | None = None
    radius_tr: float | None = None
    radius_br: float | None = None
    radius_bl: float | None = None


@dataclass
class StadiumDefinition:
    id: str
    x: float
    y: float
    width: float
    height: float
    layer: str = "cut"


@dataclass
class CircleDefinition:
    id: str
    cx: float
    cy: float
    radius: float
    layer: str = "cut"


@dataclass
class ArcDefinition:
    id: str
    cx: float
    cy: float
    radius: float
    start_angle: float
    end_angle: float
    inner_radius: float = 0.0
    layer: str = "cut"


@dataclass
class EllipseDefinition:
    id: str
    cx: float
    cy: float
    rx: float
    ry: float
    layer: str = "cut"


@dataclass
class TriangleDefinition:
    id: str
    p1: tuple[float, float]
    p2: tuple[float, float]
    p3: tuple[float, float]
    layer: str = "cut"


@dataclass
class RoundedTriangleDefinition:
    id: str
    p1: tuple[float, float]
    p2: tuple[float, float]
    p3: tuple[float, float]
    radius: float
    layer: str = "cut"


@dataclass
class OuterPathDefinition:
    smooth: bool
    mirrored: bool
    points: list[tuple[float, float]]
    layer: str = "cut"
    id: str = "outer"


@dataclass
class StitchesOperation:
    source: str | None          # shape id — None means custom path
    edges: list[str]            # canonical names, numeric strings, or ["all"]
    margin: float
    spacing: float
    length: float
    angle: float
    layer: str
    mirror: bool
    side: str
    path_points: list[tuple[float, float]]  # empty if source-based
    rounded_path: bool = False


@dataclass
class HolesOperation:
    source: str
    edges: list[str]
    margin: float
    spacing: float
    radius: float
    layer: str
    rounded_path: bool = False


@dataclass
class SingleHoleDefinition:
    id: str
    x: float | None             # None when mirror mode
    y: float
    radius: float
    mirror: bool
    x_from_center: float | None
    layer: str = "cut"


@dataclass
class ExportDefinition:
    format: str | None          # None = default (svg + png)
    filename: str


@dataclass
class PatternDocument:
    name: str | None
    width_mm: float | None
    height_mm: float | None
    layers: dict[str, LayerStyle]
    symmetry_axis_x: float | None
    shapes: list
    operations: list
    exports: list[ExportDefinition]


# ---------------------------------------------------------------------------
# DSL parse error
# ---------------------------------------------------------------------------


class DslError(ValueError):
    pass


# ---------------------------------------------------------------------------
# Low-level tokeniser helpers
# ---------------------------------------------------------------------------


def _strip_comments(text: str) -> list[tuple[int, str]]:
    """Return (lineno, stripped_line) for non-empty, non-comment lines.

    Only strips '#' as a comment when preceded by whitespace and NOT followed
    by 3-8 hex digits (preserving hex colour values like #ff0000).
    """
    result = []
    for i, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if line.startswith("#"):
            continue
        line = re.sub(r"\s+#(?![0-9a-fA-F]{3,8}(\s|$)).*$", "", line).strip()
        if line:
            result.append((i, line))
    return result


def _check_no_unit_suffix(token: str, lineno: int) -> None:
    if re.search(r"\d(mm|cm|in|pt|px)$", token, re.IGNORECASE):
        raise DslError(
            f"Line {lineno}: units are not allowed in numeric values. "
            f"Use 'size 150 112', not 'size 150mm 112mm'. All dimensions are millimeters."
        )


def _parse_float(token: str, lineno: int, field_name: str = "value") -> float:
    _check_no_unit_suffix(token, lineno)
    try:
        return float(token)
    except ValueError:
        raise DslError(f"Line {lineno}: expected a number for {field_name}, got '{token}'")


def _resolve_color(token: str) -> str:
    low = token.lower()
    if low in _NAMED_COLORS:
        return _NAMED_COLORS[low]
    if re.fullmatch(r"#[0-9a-fA-F]{3,8}", token):
        return token
    raise DslError(f"Unknown color '{token}'. Use a named color or hex value like #ff0000.")


# ---------------------------------------------------------------------------
# Block splitter
# ---------------------------------------------------------------------------

_BLOCK_STARTERS = {
    "rectangle", "rounded_rectangle", "stadium",
    "circle", "ellipse", "arc",
    "triangle", "rounded_triangle",
    "outer",
    "stitches", "holes", "hole",
    "path", "points",
}


def _split_blocks(lines: list[tuple[int, str]]) -> list[tuple[int, str, list[tuple[int, str]]]]:
    """
    Split the flat line list into:
      - Top-level single-line commands: (lineno, line, [])
      - Blocks: (start_lineno, header_line, body_lines)
    """
    result = []
    i = 0
    while i < len(lines):
        lineno, line = lines[i]
        first_token = line.split()[0]
        if first_token in _BLOCK_STARTERS:
            header_lineno = lineno
            body: list[tuple[int, str]] = []
            i += 1
            depth = 1
            while i < len(lines):
                blineno, bline = lines[i]
                btok = bline.split()[0]
                if btok in _BLOCK_STARTERS:
                    depth += 1
                    body.append((blineno, bline))
                elif btok == "end":
                    depth -= 1
                    if depth == 0:
                        break
                    body.append((blineno, bline))
                else:
                    body.append((blineno, bline))
                i += 1
            else:
                raise DslError(f"Line {header_lineno}: missing 'end' for block '{line}'")
            result.append((header_lineno, line, body))
        else:
            result.append((lineno, line, []))
        i += 1
    return result


# ---------------------------------------------------------------------------
# Parser helpers
# ---------------------------------------------------------------------------


def _resolve_edges(edge_tokens: list[str], lineno: int) -> list[str]:
    """Expand aliases; accept named rect edges, numeric indices, or 'all'."""
    result: list[str] = []
    for tok in edge_tokens:
        if tok in _EDGE_ALIASES:
            result.extend(_EDGE_ALIASES[tok])
        elif tok in _RECT_EDGE_NAMES:
            result.append(tok)
        elif re.fullmatch(r"\d+", tok):
            result.append(tok)          # numeric index — kept as string
        else:
            raise DslError(
                f"Line {lineno}: unknown edge '{tok}'. "
                f"Use: top, right, bottom, left, all, except_top, sides, "
                f"horizontal, vertical, or a numeric index (0, 1, 2, ...)."
            )
    # deduplicate preserving order
    seen: set[str] = set()
    deduped = []
    for e in result:
        if e not in seen:
            seen.add(e)
            deduped.append(e)
    return deduped


def _parse_block_body(body: list[tuple[int, str]]) -> dict:
    """Flatten block body lines into key→value dict; preserve path/points sub-blocks."""
    data: dict = {}
    i = 0
    while i < len(body):
        lineno, line = body[i]
        tokens = line.split()
        key = tokens[0]
        if key in ("path", "points"):
            sub: list[tuple[int, str]] = []
            i += 1
            while i < len(body):
                blineno, bline = body[i]
                if bline.strip() == "end":
                    i += 1
                    break
                sub.append((blineno, bline))
                i += 1
            data[key] = sub
            continue
        if len(tokens) > 1:
            data[key] = (lineno, tokens[1:])
        else:
            data[key] = (lineno, [])
        i += 1
    return data


def _parse_xy_list(lines: list[tuple[int, str]]) -> list[tuple[float, float]]:
    pts = []
    for lineno, line in lines:
        tokens = line.split()
        if len(tokens) != 2:
            raise DslError(f"Line {lineno}: expected 'x y' point, got '{line}'")
        x = _parse_float(tokens[0], lineno, "x")
        y = _parse_float(tokens[1], lineno, "y")
        pts.append((x, y))
    return pts


def _parse_triangle_points(
    data: dict,
    shape_id: str,
    lineno: int,
) -> tuple[tuple[float, float], tuple[float, float], tuple[float, float]]:
    """Extract p1/p2/p3 from block body; support both point form and at+size box form."""
    if "p1" in data and "p2" in data and "p3" in data:
        p1_ln, p1v = data["p1"]
        p2_ln, p2v = data["p2"]
        p3_ln, p3v = data["p3"]
        p1 = (_parse_float(p1v[0], p1_ln, "p1 x"), _parse_float(p1v[1], p1_ln, "p1 y"))
        p2 = (_parse_float(p2v[0], p2_ln, "p2 x"), _parse_float(p2v[1], p2_ln, "p2 y"))
        p3 = (_parse_float(p3v[0], p3_ln, "p3 x"), _parse_float(p3v[1], p3_ln, "p3 y"))
    elif "at" in data and "size" in data:
        at_ln, at_v = data["at"]
        sz_ln, sz_v = data["size"]
        x = _parse_float(at_v[0], at_ln, "at x")
        y = _parse_float(at_v[1], at_ln, "at y")
        w = _parse_float(sz_v[0], sz_ln, "size width")
        h = _parse_float(sz_v[1], sz_ln, "size height")
        # Triangle.from_box layout: top-center, bottom-right, bottom-left
        p1 = (x + w / 2, y)
        p2 = (x + w, y + h)
        p3 = (x, y + h)
    else:
        raise DslError(
            f"Line {lineno}: '{shape_id}' needs either "
            f"'p1/p2/p3' coordinates or 'at + size' (box form)."
        )
    return p1, p2, p3


# ---------------------------------------------------------------------------
# Main parser
# ---------------------------------------------------------------------------


def parse(text: str) -> PatternDocument:
    """Parse DSL text and return a PatternDocument."""
    raw_lines = _strip_comments(text)
    blocks = _split_blocks(raw_lines)

    name: str | None = None
    width_mm: float | None = None
    height_mm: float | None = None
    layers: dict[str, LayerStyle] = {}
    symmetry_axis_x: float | None = None
    shapes: list = []
    operations: list = []
    exports: list[ExportDefinition] = []

    shape_ids: set[str] = set()

    for lineno, line, body in blocks:
        tokens = line.split()
        keyword = tokens[0]

        # ------------------------------------------------------------------
        if keyword == "pattern":
            if len(tokens) < 2:
                raise DslError(f"Line {lineno}: 'pattern' requires a name")
            name = tokens[1]

        # ------------------------------------------------------------------
        elif keyword == "size":
            if len(tokens) < 3:
                raise DslError(f"Line {lineno}: 'size' requires width and height")
            width_mm = _parse_float(tokens[1], lineno, "width")
            height_mm = _parse_float(tokens[2], lineno, "height")

        # ------------------------------------------------------------------
        elif keyword == "layer":
            if len(tokens) < 4:
                raise DslError(f"Line {lineno}: 'layer' requires name, color, stroke_width")
            lname = tokens[1]
            color = _resolve_color(tokens[2])
            sw = _parse_float(tokens[3], lineno, "stroke_width")
            dashed = len(tokens) > 4 and tokens[4] == "dashed"
            layers[lname] = LayerStyle(color=color, stroke_width=sw, dashed=dashed)

        # ------------------------------------------------------------------
        elif keyword == "symmetry":
            rest = tokens[1:]
            if not rest:
                raise DslError(f"Line {lineno}: 'symmetry' requires a value")
            if rest[0] == "vertical":
                xpart = rest[1] if len(rest) > 1 else ""
                if xpart.startswith("x="):
                    symmetry_axis_x = _parse_float(xpart[2:], lineno, "symmetry x")
                else:
                    raise DslError(f"Line {lineno}: expected 'x=<value>' after 'symmetry vertical'")
            else:
                symmetry_axis_x = _parse_float(rest[0], lineno, "symmetry x")

        # ------------------------------------------------------------------
        elif keyword == "rectangle":
            if len(tokens) < 2:
                raise DslError(f"Line {lineno}: 'rectangle' requires an id")
            shape_id = tokens[1]
            data = _parse_block_body(body)

            def _req(k: str, sid=shape_id, ln=lineno) -> tuple[int, list[str]]:
                if k not in data:
                    raise DslError(f"Line {ln}: rectangle '{sid}' is missing '{k}'")
                return data[k]

            at_lineno, at_vals = _req("at")
            sz_lineno, sz_vals = _req("size")
            x = _parse_float(at_vals[0], at_lineno, "at x")
            y = _parse_float(at_vals[1], at_lineno, "at y")
            w = _parse_float(sz_vals[0], sz_lineno, "size width")
            h = _parse_float(sz_vals[1], sz_lineno, "size height")
            layer_name = "cut"
            if "layer" in data:
                layer_name = data["layer"][1][0]
            shapes.append(RectangleDefinition(id=shape_id, x=x, y=y, width=w, height=h, layer=layer_name))
            shape_ids.add(shape_id)

        # ------------------------------------------------------------------
        elif keyword == "rounded_rectangle":
            if len(tokens) < 2:
                raise DslError(f"Line {lineno}: 'rounded_rectangle' requires an id")
            shape_id = tokens[1]
            data = _parse_block_body(body)

            def _req(k: str, sid=shape_id, ln=lineno) -> tuple[int, list[str]]:
                if k not in data:
                    raise DslError(f"Line {ln}: rounded_rectangle '{sid}' is missing '{k}'")
                return data[k]

            at_lineno, at_vals = _req("at")
            sz_lineno, sz_vals = _req("size")
            x = _parse_float(at_vals[0], at_lineno, "at x")
            y = _parse_float(at_vals[1], at_lineno, "at y")
            w = _parse_float(sz_vals[0], sz_lineno, "size width")
            h = _parse_float(sz_vals[1], sz_lineno, "size height")

            corner_keys = ("radius_tl", "radius_tr", "radius_br", "radius_bl")
            corners: dict[str, float | None] = {k: None for k in corner_keys}
            for k in corner_keys:
                if k in data:
                    c_ln, c_vals = data[k]
                    val = _parse_float(c_vals[0], c_ln, k)
                    if val < 0:
                        raise DslError(f"Line {c_ln}: {k} must be >= 0")
                    corners[k] = val

            has_corner = any(v is not None for v in corners.values())
            if "radius" in data:
                r_lineno, r_vals = data["radius"]
                r = _parse_float(r_vals[0], r_lineno, "radius")
                if r <= 0:
                    raise DslError(f"Line {r_lineno}: radius must be greater than 0")
            elif has_corner:
                # Per-corner only: unspecified corners default to sharp (0)
                r = 0.0
                corners = {k: (v if v is not None else 0.0) for k, v in corners.items()}
            else:
                raise DslError(
                    f"Line {lineno}: rounded_rectangle '{shape_id}' is missing 'radius' "
                    f"(or per-corner radius_tl/radius_tr/radius_br/radius_bl)"
                )

            layer_name = "cut"
            if "layer" in data:
                layer_name = data["layer"][1][0]
            shapes.append(RoundedRectangleDefinition(
                id=shape_id, x=x, y=y, width=w, height=h, radius=r, layer=layer_name,
                radius_tl=corners["radius_tl"], radius_tr=corners["radius_tr"],
                radius_br=corners["radius_br"], radius_bl=corners["radius_bl"],
            ))
            shape_ids.add(shape_id)

        # ------------------------------------------------------------------
        elif keyword == "stadium":
            if len(tokens) < 2:
                raise DslError(f"Line {lineno}: 'stadium' requires an id")
            shape_id = tokens[1]
            data = _parse_block_body(body)

            def _req(k: str, sid=shape_id, ln=lineno) -> tuple[int, list[str]]:
                if k not in data:
                    raise DslError(f"Line {ln}: stadium '{sid}' is missing '{k}'")
                return data[k]

            at_lineno, at_vals = _req("at")
            sz_lineno, sz_vals = _req("size")
            x = _parse_float(at_vals[0], at_lineno, "at x")
            y = _parse_float(at_vals[1], at_lineno, "at y")
            w = _parse_float(sz_vals[0], sz_lineno, "size width")
            h = _parse_float(sz_vals[1], sz_lineno, "size height")
            if w <= 0 or h <= 0:
                raise DslError(f"Line {sz_lineno}: stadium size must be greater than 0")
            layer_name = "cut"
            if "layer" in data:
                layer_name = data["layer"][1][0]
            shapes.append(StadiumDefinition(id=shape_id, x=x, y=y, width=w, height=h, layer=layer_name))
            shape_ids.add(shape_id)

        # ------------------------------------------------------------------
        elif keyword == "circle":
            if len(tokens) < 2:
                raise DslError(f"Line {lineno}: 'circle' requires an id")
            shape_id = tokens[1]
            data = _parse_block_body(body)

            def _req(k: str, sid=shape_id, ln=lineno) -> tuple[int, list[str]]:
                if k not in data:
                    raise DslError(f"Line {ln}: circle '{sid}' is missing '{k}'")
                return data[k]

            at_lineno, at_vals = _req("at")
            r_lineno, r_vals = _req("radius")
            cx = _parse_float(at_vals[0], at_lineno, "at cx")
            cy = _parse_float(at_vals[1], at_lineno, "at cy")
            r = _parse_float(r_vals[0], r_lineno, "radius")
            if r <= 0:
                raise DslError(f"Line {r_lineno}: radius must be greater than 0")
            layer_name = "cut"
            if "layer" in data:
                layer_name = data["layer"][1][0]
            shapes.append(CircleDefinition(id=shape_id, cx=cx, cy=cy, radius=r, layer=layer_name))
            shape_ids.add(shape_id)

        # ------------------------------------------------------------------
        elif keyword == "arc":
            if len(tokens) < 2:
                raise DslError(f"Line {lineno}: 'arc' requires an id")
            shape_id = tokens[1]
            data = _parse_block_body(body)

            def _req(k: str, sid=shape_id, ln=lineno) -> tuple[int, list[str]]:
                if k not in data:
                    raise DslError(f"Line {ln}: arc '{sid}' is missing '{k}'")
                return data[k]

            at_lineno, at_vals = _req("at")
            r_lineno, r_vals = _req("radius")
            fa_lineno, fa_vals = _req("from_angle")
            ta_lineno, ta_vals = _req("to_angle")
            cx = _parse_float(at_vals[0], at_lineno, "at cx")
            cy = _parse_float(at_vals[1], at_lineno, "at cy")
            r = _parse_float(r_vals[0], r_lineno, "radius")
            if r <= 0:
                raise DslError(f"Line {r_lineno}: radius must be greater than 0")
            start_a = _parse_float(fa_vals[0], fa_lineno, "from_angle")
            end_a = _parse_float(ta_vals[0], ta_lineno, "to_angle")
            inner_r = 0.0
            if "inner_radius" in data:
                ir_lineno, ir_vals = data["inner_radius"]
                inner_r = _parse_float(ir_vals[0], ir_lineno, "inner_radius")
                if inner_r < 0:
                    raise DslError(f"Line {ir_lineno}: inner_radius must be >= 0")
                if inner_r >= r:
                    raise DslError(f"Line {ir_lineno}: inner_radius must be smaller than radius")
            layer_name = "cut"
            if "layer" in data:
                layer_name = data["layer"][1][0]
            shapes.append(ArcDefinition(
                id=shape_id, cx=cx, cy=cy, radius=r,
                start_angle=start_a, end_angle=end_a,
                inner_radius=inner_r, layer=layer_name,
            ))
            shape_ids.add(shape_id)

        # ------------------------------------------------------------------
        elif keyword == "ellipse":
            if len(tokens) < 2:
                raise DslError(f"Line {lineno}: 'ellipse' requires an id")
            shape_id = tokens[1]
            data = _parse_block_body(body)

            def _req(k: str, sid=shape_id, ln=lineno) -> tuple[int, list[str]]:
                if k not in data:
                    raise DslError(f"Line {ln}: ellipse '{sid}' is missing '{k}'")
                return data[k]

            at_lineno, at_vals = _req("at")
            cx = _parse_float(at_vals[0], at_lineno, "at cx")
            cy = _parse_float(at_vals[1], at_lineno, "at cy")
            if "rx" in data and "ry" in data:
                rx_lineno, rx_vals = data["rx"]
                ry_lineno, ry_vals = data["ry"]
                rx = _parse_float(rx_vals[0], rx_lineno, "rx")
                ry = _parse_float(ry_vals[0], ry_lineno, "ry")
            elif "size" in data:
                sz_lineno, sz_vals = data["size"]
                rx = _parse_float(sz_vals[0], sz_lineno, "size width") / 2
                ry = _parse_float(sz_vals[1], sz_lineno, "size height") / 2
            else:
                raise DslError(
                    f"Line {lineno}: ellipse '{shape_id}' needs either 'rx' + 'ry' or 'size'"
                )
            if rx <= 0 or ry <= 0:
                raise DslError(f"Line {lineno}: ellipse radii must be greater than 0")
            layer_name = "cut"
            if "layer" in data:
                layer_name = data["layer"][1][0]
            shapes.append(EllipseDefinition(id=shape_id, cx=cx, cy=cy, rx=rx, ry=ry, layer=layer_name))
            shape_ids.add(shape_id)

        # ------------------------------------------------------------------
        elif keyword == "triangle":
            if len(tokens) < 2:
                raise DslError(f"Line {lineno}: 'triangle' requires an id")
            shape_id = tokens[1]
            data = _parse_block_body(body)
            p1, p2, p3 = _parse_triangle_points(data, shape_id, lineno)
            layer_name = "cut"
            if "layer" in data:
                layer_name = data["layer"][1][0]
            shapes.append(TriangleDefinition(id=shape_id, p1=p1, p2=p2, p3=p3, layer=layer_name))
            shape_ids.add(shape_id)

        # ------------------------------------------------------------------
        elif keyword == "rounded_triangle":
            if len(tokens) < 2:
                raise DslError(f"Line {lineno}: 'rounded_triangle' requires an id")
            shape_id = tokens[1]
            data = _parse_block_body(body)
            p1, p2, p3 = _parse_triangle_points(data, shape_id, lineno)
            if "radius" not in data:
                raise DslError(f"Line {lineno}: rounded_triangle '{shape_id}' is missing 'radius'")
            r_lineno, r_vals = data["radius"]
            r = _parse_float(r_vals[0], r_lineno, "radius")
            if r <= 0:
                raise DslError(f"Line {r_lineno}: radius must be greater than 0")
            layer_name = "cut"
            if "layer" in data:
                layer_name = data["layer"][1][0]
            shapes.append(RoundedTriangleDefinition(
                id=shape_id, p1=p1, p2=p2, p3=p3, radius=r, layer=layer_name
            ))
            shape_ids.add(shape_id)

        # ------------------------------------------------------------------
        elif keyword == "outer":
            rest = tokens[1:]
            smooth = False
            mirrored = False
            for tok in rest:
                if tok == "smooth":
                    smooth = True
                elif tok == "straight":
                    smooth = False
                elif tok == "mirrored":
                    mirrored = True
            pts = _parse_xy_list(body)
            if not pts:
                raise DslError(f"Line {lineno}: 'outer' block has no points")
            shapes.append(OuterPathDefinition(smooth=smooth, mirrored=mirrored, points=pts))
            shape_ids.add("outer")

        # ------------------------------------------------------------------
        elif keyword == "stitches":
            data = _parse_block_body(body)

            _KNOWN_STITCH_KEYS = {
                "source", "edges", "margin", "spacing", "length", "angle",
                "layer", "mirror", "side", "path", "rounded_path",
            }
            for _k in data:
                if _k not in _KNOWN_STITCH_KEYS:
                    _kln = data[_k][0] if isinstance(data[_k], tuple) else lineno
                    raise DslError(
                        f"Line {_kln}: unknown key '{_k}' in stitches block "
                        f"(did you mean one of: {', '.join(sorted(_KNOWN_STITCH_KEYS))}?)"
                    )

            source = None
            edges_raw: list[str] = ["all"]
            margin = 4.0
            spacing = 5.0
            length = 3.0
            angle = 0.0
            layer_name = "stitch"
            mirror_flag = False
            side = "right"
            path_pts: list[tuple[float, float]] = []
            rounded_path = False

            if "source" in data:
                src_ln, src_vals = data["source"]
                source = src_vals[0]
                if source not in shape_ids:
                    raise DslError(
                        f"Line {src_ln}: stitches block references unknown source '{source}'"
                    )
            if "edges" in data:
                e_ln, e_vals = data["edges"]
                edges_raw = _resolve_edges(e_vals, e_ln)
            if "margin" in data:
                ln, vals = data["margin"]
                margin = _parse_float(vals[0], ln, "margin")
            if "spacing" in data:
                ln, vals = data["spacing"]
                spacing = _parse_float(vals[0], ln, "spacing")
            if "length" in data:
                ln, vals = data["length"]
                length = _parse_float(vals[0], ln, "length")
            if "angle" in data:
                ln, vals = data["angle"]
                angle = _parse_float(vals[0], ln, "angle")
            if "layer" in data:
                layer_name = data["layer"][1][0]
            if "mirror" in data:
                mirror_flag = True
            if "side" in data:
                side = data["side"][1][0]
            if "path" in data:
                path_pts = _parse_xy_list(data["path"])
            if "rounded_path" in data:
                rounded_path = True

            operations.append(StitchesOperation(
                source=source,
                edges=edges_raw,
                margin=margin,
                spacing=spacing,
                length=length,
                angle=angle,
                layer=layer_name,
                mirror=mirror_flag,
                side=side,
                path_points=path_pts,
                rounded_path=rounded_path,
            ))

        # ------------------------------------------------------------------
        elif keyword == "holes":
            data = _parse_block_body(body)

            _KNOWN_HOLES_KEYS = {
                "source", "edges", "margin", "spacing", "radius",
                "layer", "rounded_path",
            }
            for _k in data:
                if _k not in _KNOWN_HOLES_KEYS:
                    _kln = data[_k][0] if isinstance(data[_k], tuple) else lineno
                    raise DslError(
                        f"Line {_kln}: unknown key '{_k}' in holes block "
                        f"(did you mean one of: {', '.join(sorted(_KNOWN_HOLES_KEYS))}?)"
                    )

            def _req(k: str, ln=lineno) -> tuple[int, list[str]]:
                if k not in data:
                    raise DslError(f"Line {ln}: 'holes' block is missing '{k}'")
                return data[k]

            src_ln, src_vals = _req("source")
            source = src_vals[0]
            if source not in shape_ids:
                raise DslError(
                    f"Line {src_ln}: holes block references unknown source '{source}'"
                )

            edges_raw = ["all"]
            margin = 4.0
            spacing = 6.0
            radius = 1.2
            layer_name = "cut"
            rounded_path = False

            if "edges" in data:
                e_ln, e_vals = data["edges"]
                edges_raw = _resolve_edges(e_vals, e_ln)
            if "margin" in data:
                ln, vals = data["margin"]
                margin = _parse_float(vals[0], ln, "margin")
            if "spacing" in data:
                ln, vals = data["spacing"]
                spacing = _parse_float(vals[0], ln, "spacing")
            if "radius" in data:
                ln, vals = data["radius"]
                radius = _parse_float(vals[0], ln, "radius")
                if radius <= 0:
                    raise DslError(f"Line {ln}: radius must be greater than 0")
            if "layer" in data:
                layer_name = data["layer"][1][0]
            if "rounded_path" in data:
                rounded_path = True

            operations.append(HolesOperation(
                source=source,
                edges=edges_raw,
                margin=margin,
                spacing=spacing,
                radius=radius,
                layer=layer_name,
                rounded_path=rounded_path,
            ))

        # ------------------------------------------------------------------
        elif keyword == "hole":
            if len(tokens) < 2:
                raise DslError(f"Line {lineno}: 'hole' requires an id")
            hole_id = tokens[1]
            data = _parse_block_body(body)

            mirror_flag = "mirror" in data
            layer_name = "cut"
            if "layer" in data:
                layer_name = data["layer"][1][0]

            if mirror_flag:
                def _req_field(k: str, hid=hole_id, ln=lineno) -> tuple[int, list[str]]:
                    if k not in data:
                        raise DslError(f"Line {ln}: mirrored hole '{hid}' is missing '{k}'")
                    return data[k]

                xfc_ln, xfc_vals = _req_field("x_from_center")
                y_ln, y_vals = _req_field("y")
                r_ln, r_vals = _req_field("radius")

                xfc = _parse_float(xfc_vals[0], xfc_ln, "x_from_center")
                hole_y = _parse_float(y_vals[0], y_ln, "y")
                r = _parse_float(r_vals[0], r_ln, "radius")
                if r <= 0:
                    raise DslError(f"Line {r_ln}: radius must be greater than 0")

                operations.append(SingleHoleDefinition(
                    id=hole_id, x=None, y=hole_y, radius=r,
                    mirror=True, x_from_center=xfc, layer=layer_name,
                ))
            else:
                def _req_field(k: str, hid=hole_id, ln=lineno) -> tuple[int, list[str]]:
                    if k not in data:
                        raise DslError(f"Line {ln}: hole '{hid}' is missing '{k}'")
                    return data[k]

                at_ln, at_vals = _req_field("at")
                r_ln, r_vals = _req_field("radius")

                hole_x = _parse_float(at_vals[0], at_ln, "at x")
                hole_y = _parse_float(at_vals[1], at_ln, "at y")
                r = _parse_float(r_vals[0], r_ln, "radius")
                if r <= 0:
                    raise DslError(f"Line {r_ln}: radius must be greater than 0")

                operations.append(SingleHoleDefinition(
                    id=hole_id, x=hole_x, y=hole_y, radius=r,
                    mirror=False, x_from_center=None, layer=layer_name,
                ))

        # ------------------------------------------------------------------
        elif keyword == "export":
            rest = tokens[1:]
            if not rest:
                raise DslError(f"Line {lineno}: 'export' requires at least a name")
            if len(rest) == 1:
                exports.append(ExportDefinition(format=None, filename=rest[0]))
            else:
                fmt = rest[0].lower()
                if fmt not in ("svg", "png", "pdf"):
                    raise DslError(
                        f"Line {lineno}: unknown export format '{fmt}'. Use: svg, png, pdf."
                    )
                exports.append(ExportDefinition(format=fmt, filename=rest[1]))

        else:
            raise DslError(f"Line {lineno}: unknown keyword '{keyword}'")

    return PatternDocument(
        name=name,
        width_mm=width_mm,
        height_mm=height_mm,
        layers=layers,
        symmetry_axis_x=symmetry_axis_x,
        shapes=shapes,
        operations=operations,
        exports=exports,
    )


# ---------------------------------------------------------------------------
# Compiler — PatternDocument → SvgDocument
# ---------------------------------------------------------------------------


def _default_layers() -> dict[str, StrokeStyle]:
    return {
        "cut":    StrokeStyle("#ff0000", 0.2),
        "stitch": StrokeStyle("#0000ff", 0.2),
        "crease": StrokeStyle("#00aa00", 0.2, "3 2"),
        "guide":  StrokeStyle("#777777", 0.2, "2 2"),
    }


def _layer_style(ls: LayerStyle) -> StrokeStyle:
    dasharray = "3 2" if ls.dashed else ""
    return StrokeStyle(ls.color, ls.stroke_width, dasharray)


def _edges_to_indices(edges: list[str]) -> str | list[int]:
    """Convert stored edge tokens to the format the library expects.

    Accepts:
    - Named rect edges (top/right/bottom/left) and their aliases
    - Numeric strings ("0", "1", "2", ...)
    - The alias "all" (or its expansion)

    Returns "all" when all four rectangle named edges are present,
    otherwise a list of ints.
    """
    # Expand any named aliases first (leaves numeric strings unchanged)
    expanded: list[str] = []
    for e in edges:
        if e in _EDGE_ALIASES:
            expanded.extend(_EDGE_ALIASES[e])
        else:
            expanded.append(e)

    # All four rect named edges → "all"
    if set(expanded) == {"top", "right", "bottom", "left"}:
        return "all"

    # All numeric strings → list of ints (triangle / polygon / circle edges)
    if all(re.fullmatch(r"\d+", e) for e in expanded):
        return [int(e) for e in expanded]

    # Mixed named rect edges → indices
    return [_RECT_EDGE_NAMES[e] for e in expanded]


def compile_document(doc: PatternDocument) -> SvgDocument:
    """Convert a PatternDocument into a fully rendered SvgDocument."""

    if doc.width_mm is None or doc.height_mm is None:
        raise DslError("missing required command 'size'")

    if doc.layers:
        merged = _default_layers()
        merged.update({name: _layer_style(ls) for name, ls in doc.layers.items()})
        styles = merged
    else:
        styles = _default_layers()

    svg = SvgDocument(width_mm=doc.width_mm, height_mm=doc.height_mm, styles=styles)

    # --- build shape registry ----------------------------------------
    shape_objects: dict[str, object] = {}

    for shape_def in doc.shapes:
        if isinstance(shape_def, RectangleDefinition):
            s = Rectangle(shape_def.x, shape_def.y, shape_def.width, shape_def.height)
            svg.add_shape(s, layer=shape_def.layer)
            shape_objects[shape_def.id] = s

        elif isinstance(shape_def, RoundedRectangleDefinition):
            s = RoundedRectangle(
                shape_def.x, shape_def.y,
                shape_def.width, shape_def.height,
                radius=shape_def.radius,
                radius_tl=shape_def.radius_tl,
                radius_tr=shape_def.radius_tr,
                radius_br=shape_def.radius_br,
                radius_bl=shape_def.radius_bl,
            )
            svg.add_shape(s, layer=shape_def.layer)
            shape_objects[shape_def.id] = s

        elif isinstance(shape_def, StadiumDefinition):
            s = Stadium(shape_def.x, shape_def.y, shape_def.width, shape_def.height)
            svg.add_shape(s, layer=shape_def.layer)
            shape_objects[shape_def.id] = s

        elif isinstance(shape_def, CircleDefinition):
            s = Circle(shape_def.cx, shape_def.cy, shape_def.radius)
            svg.add_shape(s, layer=shape_def.layer)
            shape_objects[shape_def.id] = s

        elif isinstance(shape_def, ArcDefinition):
            s = Arc(
                shape_def.cx, shape_def.cy, shape_def.radius,
                start_angle=shape_def.start_angle,
                end_angle=shape_def.end_angle,
                inner_radius=shape_def.inner_radius,
            )
            svg.add_shape(s, layer=shape_def.layer)
            shape_objects[shape_def.id] = s

        elif isinstance(shape_def, EllipseDefinition):
            s = Ellipse(shape_def.cx, shape_def.cy, shape_def.rx, shape_def.ry)
            svg.add_shape(s, layer=shape_def.layer)
            shape_objects[shape_def.id] = s

        elif isinstance(shape_def, TriangleDefinition):
            s = Triangle(
                Point(*shape_def.p1),
                Point(*shape_def.p2),
                Point(*shape_def.p3),
            )
            svg.add_shape(s, layer=shape_def.layer)
            shape_objects[shape_def.id] = s

        elif isinstance(shape_def, RoundedTriangleDefinition):
            s = RoundedTriangle(
                Point(*shape_def.p1),
                Point(*shape_def.p2),
                Point(*shape_def.p3),
                radius=shape_def.radius,
            )
            svg.add_shape(s, layer=shape_def.layer)
            shape_objects[shape_def.id] = s

        elif isinstance(shape_def, OuterPathDefinition):
            if shape_def.mirrored:
                if doc.symmetry_axis_x is None:
                    raise DslError(
                        "'outer mirrored' requires a global symmetry axis. Add 'symmetry <x>'."
                    )
                s = Polygon.from_mirror(
                    shape_def.points,
                    center_x=doc.symmetry_axis_x,
                    smooth=shape_def.smooth,
                )
            else:
                s = Polygon(points=shape_def.points, smooth=shape_def.smooth)
            svg.add_shape(s, layer=shape_def.layer)
            shape_objects["outer"] = s

    # --- operations --------------------------------------------------
    for op in doc.operations:

        if isinstance(op, StitchesOperation):
            if op.source is not None:
                shape = shape_objects[op.source]
                edges_arg = _edges_to_indices(op.edges)
                svg.add_stitch_pattern(
                    shape,
                    edges=edges_arg,
                    spacing=op.spacing,
                    stitch_length=op.length,
                    inset=op.margin,
                    layer=op.layer,
                    stitch_angle_deg=op.angle,
                    rounded_path=op.rounded_path,
                )
            else:
                if not op.path_points:
                    raise DslError("stitches block with no 'source' must have a 'path' sub-block")
                seam = offset_polyline(op.path_points, distance=op.margin, side=op.side)
                svg.add_stitch_on_polyline(
                    seam,
                    spacing=op.spacing,
                    stitch_length=op.length,
                    stitch_angle_deg=op.angle,
                    layer=op.layer,
                )
                if op.mirror:
                    if doc.symmetry_axis_x is None:
                        raise DslError(
                            "stitches 'mirror' requires a global symmetry axis. Add 'symmetry <x>'."
                        )
                    mirrored_seam = mirror_polyline(seam, doc.symmetry_axis_x)
                    svg.add_stitch_on_polyline(
                        mirrored_seam,
                        spacing=op.spacing,
                        stitch_length=op.length,
                        stitch_angle_deg=op.angle,
                        layer=op.layer,
                    )

        elif isinstance(op, HolesOperation):
            shape = shape_objects[op.source]
            edges_arg = _edges_to_indices(op.edges)
            svg.add_holes(
                shape,
                edges=edges_arg,
                spacing=op.spacing,
                hole_radius=op.radius,
                inset=op.margin,
                layer=op.layer,
                rounded_path=op.rounded_path,
            )

        elif isinstance(op, SingleHoleDefinition):
            if op.mirror:
                if doc.symmetry_axis_x is None:
                    raise DslError(
                        f"hole '{op.id}' uses mirror but no symmetry axis is defined"
                    )
                cx = doc.symmetry_axis_x
                assert op.x_from_center is not None
                svg.add_circle(cx - op.x_from_center, op.y, op.radius, layer=op.layer)
                svg.add_circle(cx + op.x_from_center, op.y, op.radius, layer=op.layer)
            else:
                assert op.x is not None
                svg.add_circle(op.x, op.y, op.radius, layer=op.layer)

    return svg


# ---------------------------------------------------------------------------
# Export helpers
# ---------------------------------------------------------------------------


def _export(svg: SvgDocument, exp: ExportDefinition, default_name: str) -> None:
    if exp.format is None:
        stem = exp.filename
        svg.save(f"{stem}.svg")
        try:
            svg.save_png(f"{stem}.png", background_color="white")
        except Exception as exc:
            print(f"  PNG skipped: {exc}", file=sys.stderr)
    elif exp.format == "svg":
        svg.save(exp.filename)
    elif exp.format == "png":
        svg.save_png(exp.filename, background_color="white")
    elif exp.format == "pdf":
        try:
            import cairosvg
            cairosvg.svg2pdf(bytestring=svg.to_svg().encode(), write_to=exp.filename)
        except Exception as exc:
            raise DslError(f"PDF export failed: {exc}") from exc


def build_file(path: str | Path) -> SvgDocument:
    """Parse, compile, and export a .lcraft file. Returns the SvgDocument."""
    path = Path(path)
    text = path.read_text(encoding="utf-8")
    doc = parse(text)
    svg = compile_document(doc)

    default_name = doc.name or path.stem
    if not doc.exports:
        stem = path.parent / default_name
        svg.save(str(stem) + ".svg")
        try:
            svg.save_png(str(stem) + ".png", background_color="white")
        except Exception as exc:
            print(f"PNG skipped: {exc}", file=sys.stderr)
    else:
        for exp in doc.exports:
            _export(svg, exp, default_name)

    return svg


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]

    if len(argv) < 2 or argv[0] != "build":
        print("Usage: python leathercraft_dsl.py build <file.lcraft>", file=sys.stderr)
        return 1

    lcraft_file = argv[1]
    try:
        build_file(lcraft_file)
        print(f"Built {lcraft_file}")
        return 0
    except DslError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except FileNotFoundError:
        print(f"Error: file not found: {lcraft_file}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
