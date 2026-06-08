"""
leathercraft_dsl — DSL compiler for the leathercraft_svg library.

Usage:
    python -m leathercraft_dsl build pattern.lcraft

Supported constructs: pattern, size, layer, symmetry, rectangle,
rounded_rectangle, outer, stitches, holes, hole, export.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Union

from leathercraft_svg import (
    Polygon,
    Rectangle,
    RoundedRectangle,
    StrokeStyle,
    SvgDocument,
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
# Edge aliases
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


@dataclass
class OuterPathDefinition:
    smooth: bool
    mirrored: bool
    points: list[tuple[float, float]]
    layer: str = "cut"
    id: str = "outer"


@dataclass
class StitchesOperation:
    source: str | None  # shape id — None means custom path
    edges: list[str]  # resolved edge names or ["all"]
    margin: float
    spacing: float
    length: float
    angle: float
    layer: str
    mirror: bool
    side: str
    path_points: list[tuple[float, float]]  # empty if source-based


@dataclass
class HolesOperation:
    source: str
    edges: list[str]
    margin: float
    spacing: float
    radius: float
    layer: str


@dataclass
class SingleHoleDefinition:
    id: str
    x: float | None  # None when mirror mode
    y: float
    radius: float
    mirror: bool
    x_from_center: float | None
    layer: str = "cut"


@dataclass
class ExportDefinition:
    format: str | None  # None = default (svg + png)
    filename: str


@dataclass
class PatternDocument:
    name: str | None
    width_mm: float | None
    height_mm: float | None
    layers: dict[str, LayerStyle]
    symmetry_axis_x: float | None
    shapes: list[Union[RectangleDefinition, RoundedRectangleDefinition, OuterPathDefinition]]
    operations: list[Union[StitchesOperation, HolesOperation, SingleHoleDefinition]]
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

    Only strips a '#' as a comment when it appears at the start of a token
    (i.e. preceded by whitespace or at the very beginning of the line).
    This avoids stripping '#' inside hex colour values like '#ff0000'.
    """
    result = []
    for i, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if line.startswith("#"):
            continue
        # inline comment: # preceded by whitespace and NOT followed by hex digits
        # This preserves hex colour values like #ff0000 while stripping comments.
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


def _split_blocks(lines: list[tuple[int, str]]) -> list[tuple[int, str, list[tuple[int, str]]]]:
    """
    Split the flat line list into:
      - Top-level single-line commands: (lineno, line, [])
      - Blocks: (start_lineno, header_line, body_lines)

    Block keywords require a matching 'end'.
    """
    _BLOCK_STARTERS = {
        "rectangle", "rounded_rectangle", "outer", "stitches", "holes", "hole",
        "path", "points",
    }
    result = []
    i = 0
    while i < len(lines):
        lineno, line = lines[i]
        first_token = line.split()[0]
        if first_token in _BLOCK_STARTERS:
            # collect until matching 'end'
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
# Parser
# ---------------------------------------------------------------------------


def _resolve_edges(edge_tokens: list[str], lineno: int) -> list[str]:
    """Expand aliases and return a list of canonical edge names."""
    result: list[str] = []
    for tok in edge_tokens:
        if tok in _EDGE_ALIASES:
            result.extend(_EDGE_ALIASES[tok])
        elif tok in _RECT_EDGE_NAMES:
            result.append(tok)
        else:
            raise DslError(
                f"Line {lineno}: unknown edge '{tok}'. "
                f"Use: top, right, bottom, left, all, except_top, sides, horizontal, vertical."
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
    """
    Flatten block body lines into a key→value or key→list_of_lines dict.
    Sub-blocks (path/points) are preserved as lists.
    """
    data: dict = {}
    i = 0
    while i < len(body):
        lineno, line = body[i]
        tokens = line.split()
        key = tokens[0]
        if key in ("path", "points"):
            # collect sub-block
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

    # track shape ids for validation
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
            # layer <name> <color> <stroke_width> [dashed]
            if len(tokens) < 4:
                raise DslError(f"Line {lineno}: 'layer' requires name, color, stroke_width")
            lname = tokens[1]
            color = _resolve_color(tokens[2])
            sw = _parse_float(tokens[3], lineno, "stroke_width")
            dashed = len(tokens) > 4 and tokens[4] == "dashed"
            layers[lname] = LayerStyle(color=color, stroke_width=sw, dashed=dashed)

        # ------------------------------------------------------------------
        elif keyword == "symmetry":
            # symmetry <x>  OR  symmetry vertical x=<x>
            rest = tokens[1:]
            if not rest:
                raise DslError(f"Line {lineno}: 'symmetry' requires a value")
            if rest[0] == "vertical":
                # x=75
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

            def _req(k: str) -> tuple[int, list[str]]:
                if k not in data:
                    raise DslError(f"Line {lineno}: rectangle '{shape_id}' is missing '{k}'")
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

            def _req(k: str) -> tuple[int, list[str]]:
                if k not in data:
                    raise DslError(f"Line {lineno}: rounded_rectangle '{shape_id}' is missing '{k}'")
                return data[k]

            at_lineno, at_vals = _req("at")
            sz_lineno, sz_vals = _req("size")
            r_lineno, r_vals = _req("radius")
            x = _parse_float(at_vals[0], at_lineno, "at x")
            y = _parse_float(at_vals[1], at_lineno, "at y")
            w = _parse_float(sz_vals[0], sz_lineno, "size width")
            h = _parse_float(sz_vals[1], sz_lineno, "size height")
            r = _parse_float(r_vals[0], r_lineno, "radius")
            if r <= 0:
                raise DslError(f"Line {r_lineno}: radius must be greater than 0")
            layer_name = "cut"
            if "layer" in data:
                layer_name = data["layer"][1][0]
            shapes.append(RoundedRectangleDefinition(
                id=shape_id, x=x, y=y, width=w, height=h, radius=r, layer=layer_name
            ))
            shape_ids.add(shape_id)

        # ------------------------------------------------------------------
        elif keyword == "outer":
            # outer [smooth|straight] [mirrored]
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

            # defaults
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
            ))

        # ------------------------------------------------------------------
        elif keyword == "holes":
            data = _parse_block_body(body)

            def _req(k: str) -> tuple[int, list[str]]:
                if k not in data:
                    raise DslError(f"Line {lineno}: 'holes' block is missing '{k}'")
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

            operations.append(HolesOperation(
                source=source,
                edges=edges_raw,
                margin=margin,
                spacing=spacing,
                radius=radius,
                layer=layer_name,
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
                # mirrored hole: x_from_center + y + radius
                def _req_field(k: str) -> tuple[int, list[str]]:
                    if k not in data:
                        raise DslError(f"Line {lineno}: mirrored hole '{hole_id}' is missing '{k}'")
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
                    id=hole_id,
                    x=None,
                    y=hole_y,
                    radius=r,
                    mirror=True,
                    x_from_center=xfc,
                    layer=layer_name,
                ))
            else:
                # single hole: at + radius
                def _req_field(k: str) -> tuple[int, list[str]]:
                    if k not in data:
                        raise DslError(f"Line {lineno}: hole '{hole_id}' is missing '{k}'")
                    return data[k]

                at_ln, at_vals = _req_field("at")
                r_ln, r_vals = _req_field("radius")

                hole_x = _parse_float(at_vals[0], at_ln, "at x")
                hole_y = _parse_float(at_vals[1], at_ln, "at y")
                r = _parse_float(r_vals[0], r_ln, "radius")
                if r <= 0:
                    raise DslError(f"Line {r_ln}: radius must be greater than 0")

                operations.append(SingleHoleDefinition(
                    id=hole_id,
                    x=hole_x,
                    y=hole_y,
                    radius=r,
                    mirror=False,
                    x_from_center=None,
                    layer=layer_name,
                ))

        # ------------------------------------------------------------------
        elif keyword == "export":
            rest = tokens[1:]
            if not rest:
                raise DslError(f"Line {lineno}: 'export' requires at least a name")
            if len(rest) == 1:
                # simple export: export <name>
                exports.append(ExportDefinition(format=None, filename=rest[0]))
            else:
                # explicit: export <format> <filename>
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
    """Convert a list of canonical edge names to the library's format.

    Accepts already-resolved canonical names (top/right/bottom/left) as well
    as the single-token shorthand ``["all"]``.
    """
    # Expand any remaining aliases (e.g. the default ["all"])
    expanded: list[str] = []
    for e in edges:
        if e in _EDGE_ALIASES:
            expanded.extend(_EDGE_ALIASES[e])
        else:
            expanded.append(e)
    if set(expanded) == {"top", "right", "bottom", "left"}:
        return "all"
    return [_RECT_EDGE_NAMES[e] for e in expanded]


def compile_document(doc: PatternDocument) -> SvgDocument:
    """Convert a PatternDocument into a fully rendered SvgDocument."""

    # --- validation --------------------------------------------------
    if doc.width_mm is None or doc.height_mm is None:
        raise DslError("missing required command 'size'")

    # --- styles ------------------------------------------------------
    if doc.layers:
        styles = {name: _layer_style(ls) for name, ls in doc.layers.items()}
        # merge with defaults so any omitted layer still works
        merged = _default_layers()
        merged.update(styles)
        styles = merged
    else:
        styles = _default_layers()

    svg = SvgDocument(
        width_mm=doc.width_mm,
        height_mm=doc.height_mm,
        styles=styles,
    )

    # --- build shape registry ----------------------------------------
    # id → (shape_object, SvgDocument-added)
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
                # stitches on built-in shape
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
                )
            else:
                # stitches along custom path
                if not op.path_points:
                    raise DslError("stitches block with no 'source' must have a 'path' sub-block")
                pts = op.path_points
                # offset by margin on the specified side
                seam = offset_polyline(pts, distance=op.margin, side=op.side)
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
            )

        elif isinstance(op, SingleHoleDefinition):
            if op.mirror:
                if doc.symmetry_axis_x is None:
                    raise DslError(
                        f"hole '{op.id}' uses mirror but no symmetry axis is defined"
                    )
                cx = doc.symmetry_axis_x
                assert op.x_from_center is not None
                x_left = cx - op.x_from_center
                x_right = cx + op.x_from_center
                svg.add_circle(x_left, op.y, op.radius, layer=op.layer)
                svg.add_circle(x_right, op.y, op.radius, layer=op.layer)
            else:
                assert op.x is not None
                svg.add_circle(op.x, op.y, op.radius, layer=op.layer)

    return svg


# ---------------------------------------------------------------------------
# Export helpers
# ---------------------------------------------------------------------------


def _export(svg: SvgDocument, exp: ExportDefinition, default_name: str) -> None:
    """Write one export to disk."""
    if exp.format is None:
        # default: write svg and png
        stem = exp.filename
        svg.save(f"{stem}.svg")
        try:
            svg.save_png(f"{stem}.png", background_color="white")
        except Exception as exc:  # cairosvg not installed
            print(f"  PNG skipped: {exc}", file=sys.stderr)
    elif exp.format == "svg":
        svg.save(exp.filename)
    elif exp.format == "png":
        svg.save_png(exp.filename, background_color="white")
    elif exp.format == "pdf":
        try:
            import cairosvg
            svg_str = svg.to_svg()
            cairosvg.svg2pdf(bytestring=svg_str.encode(), write_to=exp.filename)
        except Exception as exc:
            raise DslError(f"PDF export failed: {exc}") from exc


def build_file(path: str | Path) -> SvgDocument:
    """
    Parse, compile, and export a .lcraft file.
    Returns the compiled SvgDocument.
    """
    path = Path(path)
    text = path.read_text(encoding="utf-8")
    doc = parse(text)
    svg = compile_document(doc)

    default_name = doc.name or path.stem

    if not doc.exports:
        # default: export svg and png next to the source file
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
        print("Usage: python -m leathercraft_dsl build <file.lcraft>", file=sys.stderr)
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
