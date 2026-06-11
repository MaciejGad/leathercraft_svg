"""
leathercraft_dsl — DSL compiler for the leathercraft_svg library.

Usage:
    python leathercraft_dsl.py build pattern.lcraft

Supported constructs: pattern, size, layer, symmetry, rectangle,
rounded_rectangle, stadium, circle, ellipse, arc, triangle, rounded_triangle,
regular_polygon, rounded_regular_polygon, outer,
stitches, holes, hole, export.
"""

from __future__ import annotations

import ast as _ast
import math as _math
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
    RegularPolygon,
    Rectangle,
    RoundedRegularPolygon,
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
class RegularPolygonDefinition:
    id: str
    cx: float
    cy: float
    radius: float
    sides: int
    rotation: float = -90.0
    layer: str = "cut"


@dataclass
class RoundedRegularPolygonDefinition:
    id: str
    cx: float
    cy: float
    radius: float
    sides: int
    corner_radius: float = 0.0
    rotation: float = -90.0
    layer: str = "cut"
    corner_overrides: dict[int, float] = field(default_factory=dict)


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
    distribution: str = "fixed_spacing"
    path_mode: str = "continuous"
    first_margin: float | None = None
    last_margin: float | None = None


@dataclass
class HolesOperation:
    source: str
    edges: list[str]
    margin: float
    spacing: float
    radius: float
    layer: str
    rounded_path: bool = False
    distribution: str = "fixed_spacing"
    path_mode: str = "continuous"
    first_margin: float | None = None
    last_margin: float | None = None


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
            f"Use '150', not '150mm'. All dimensions are millimeters."
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
    "triangle", "rounded_triangle", "regular_polygon", "rounded_regular_polygon",
    "outer",
    "stitches", "holes", "hole",
    "path", "points",
}


# ---------------------------------------------------------------------------
# Variables and numeric expressions
# ---------------------------------------------------------------------------
#
# A line of the form ``<identifier> = <expression>`` defines a document-level
# variable. Expressions are numeric only and are evaluated with a strict
# AST whitelist (never Python ``eval``). Variables must be defined before use
# and may not be reassigned. See leathercraft_dsl_variables_expressions.md.

_IDENTIFIER_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")

_SAFE_FUNCTIONS = {
    "min": min,
    "max": max,
    "abs": abs,
    "round": round,
    "floor": _math.floor,
    "ceil": _math.ceil,
}

# Structural keywords that may not be used as variable names. Parameter-like
# names (radius, spacing, margin, length, angle, rx, ry, ...) are intentionally
# allowed because they read naturally in pattern files.
_RESERVED_VAR_NAMES = _BLOCK_STARTERS | {
    "pattern", "size", "layer", "symmetry", "outer", "export", "end",
    "source", "edges", "at", "p1", "p2", "p3",
    "from_angle", "to_angle", "inner_radius",
    "mirror", "mirrored", "smooth", "straight",
    "x_from_center", "y",
}


class ExpressionEvaluator:
    """Evaluate numeric DSL expressions against a global variable scope."""

    def __init__(self) -> None:
        self.variables: dict[str, float] = {}

    # -- variable definition ------------------------------------------------

    def define(self, name: str, expression: str, lineno: int) -> float:
        if not re.fullmatch(_IDENTIFIER_RE, name):
            raise DslError(f"Line {lineno}: invalid variable name '{name}'")
        if name in _RESERVED_VAR_NAMES:
            raise DslError(
                f"Line {lineno}: '{name}' is a reserved keyword and cannot be "
                f"used as a variable name"
            )
        if name in self.variables:
            raise DslError(f"Line {lineno}: variable '{name}' is already defined")
        value = self.eval(expression, lineno)
        self.variables[name] = value
        return value

    # -- expression evaluation ---------------------------------------------

    # Guard against pathological expressions that would otherwise raise
    # uncaught RecursionError/OverflowError instead of a clean DslError.
    _MAX_EXPRESSION_LENGTH = 2000

    def eval(self, expression: str, lineno: int) -> float:
        expr = expression.strip()
        if not expr:
            raise DslError(f"Line {lineno}: invalid expression ''")
        if len(expr) > self._MAX_EXPRESSION_LENGTH:
            raise DslError(
                f"Line {lineno}: expression is too long "
                f"({len(expr)} characters, limit {self._MAX_EXPRESSION_LENGTH})"
            )
        for token in expr.replace("(", " ").replace(")", " ").replace(",", " ").split():
            _check_no_unit_suffix(token, lineno)
        try:
            tree = _ast.parse(expr, mode="eval")
        except SyntaxError:
            raise DslError(f"Line {lineno}: invalid expression '{expr}'")
        except (RecursionError, MemoryError):
            raise DslError(f"Line {lineno}: expression is too complex")
        try:
            value = self._eval_node(tree.body, expr, lineno)
        except RecursionError:
            raise DslError(f"Line {lineno}: expression is too complex")
        except OverflowError:
            raise DslError(
                f"Line {lineno}: expression value is out of range in '{expr}'"
            )
        try:
            result = float(value)
        except (OverflowError, ValueError):
            raise DslError(
                f"Line {lineno}: expression value is out of range in '{expr}'"
            )
        if not _math.isfinite(result):
            raise DslError(
                f"Line {lineno}: expression value is not a finite number in '{expr}'"
            )
        return result

    def _eval_node(self, node, expr: str, lineno: int) -> float:
        if isinstance(node, _ast.Constant):
            if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
                raise DslError(f"Line {lineno}: unsupported expression syntax")
            return node.value
        if isinstance(node, _ast.Name):
            if node.id in self.variables:
                return self.variables[node.id]
            raise DslError(f"Line {lineno}: unknown variable '{node.id}'")
        if isinstance(node, _ast.BinOp):
            left = self._eval_node(node.left, expr, lineno)
            right = self._eval_node(node.right, expr, lineno)
            op = node.op
            if isinstance(op, _ast.Add):
                return left + right
            if isinstance(op, _ast.Sub):
                return left - right
            if isinstance(op, _ast.Mult):
                return left * right
            if isinstance(op, _ast.Div):
                if right == 0:
                    raise DslError(
                        f"Line {lineno}: division by zero in expression '{expr}'"
                    )
                return left / right
            raise DslError(f"Line {lineno}: unsupported expression syntax")
        if isinstance(node, _ast.UnaryOp):
            operand = self._eval_node(node.operand, expr, lineno)
            if isinstance(node.op, _ast.UAdd):
                return +operand
            if isinstance(node.op, _ast.USub):
                return -operand
            raise DslError(f"Line {lineno}: unsupported expression syntax")
        if isinstance(node, _ast.Call):
            if not isinstance(node.func, _ast.Name):
                raise DslError(f"Line {lineno}: unsupported expression syntax")
            fname = node.func.id
            if fname not in _SAFE_FUNCTIONS:
                raise DslError(f"Line {lineno}: unsupported function '{fname}'")
            if node.keywords:
                raise DslError(f"Line {lineno}: unsupported expression syntax")
            args = [self._eval_node(a, expr, lineno) for a in node.args]
            try:
                return _SAFE_FUNCTIONS[fname](*args)
            except TypeError:
                raise DslError(
                    f"Line {lineno}: invalid arguments to function '{fname}'"
                )
        raise DslError(f"Line {lineno}: unsupported expression syntax")


def _split_top_commas(text: str) -> list[str]:
    """Split on commas that are not nested inside parentheses."""
    parts: list[str] = []
    depth = 0
    current: list[str] = []
    for ch in text:
        if ch == "(":
            depth += 1
            current.append(ch)
        elif ch == ")":
            depth -= 1
            current.append(ch)
        elif ch == "," and depth == 0:
            parts.append("".join(current))
            current = []
        else:
            current.append(ch)
    parts.append("".join(current))
    return [p.strip() for p in parts]


def _eval_values(
    tokens: list[str],
    count: int,
    evaluator: ExpressionEvaluator,
    lineno: int,
    command: str,
) -> list[float]:
    """
    Resolve ``count`` numeric values from a command's value tokens.

    Two forms are accepted:
      * simple whitespace form — each value is a single token (number or
        bare variable name): ``size width height``
      * comma form — for complex expressions: ``size width - 2 * margin, height``
    """
    raw = " ".join(tokens).strip()
    parts = _split_top_commas(raw)
    if len(parts) > 1:
        if len(parts) != count:
            raise DslError(
                f"Line {lineno}: command '{command}' expects {count} values, "
                f"got {len(parts)}"
            )
        return [evaluator.eval(p, lineno) for p in parts]
    if count == 1:
        return [evaluator.eval(raw, lineno)]
    whitespace_tokens = raw.split()
    if len(whitespace_tokens) != count:
        raise DslError(
            f"Line {lineno}: command '{command}' expects {count} values. "
            f"Use commas for complex expressions: {command} <expr>, <expr>"
        )
    return [evaluator.eval(t, lineno) for t in whitespace_tokens]


def _eval_value(
    tokens: list[str],
    evaluator: ExpressionEvaluator,
    lineno: int,
    command: str,
) -> float:
    return _eval_values(tokens, 1, evaluator, lineno, command)[0]


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


def _parse_xy_list(
    lines: list[tuple[int, str]],
    evaluator: ExpressionEvaluator,
) -> list[tuple[float, float]]:
    pts = []
    for lineno, line in lines:
        # Supports plain "x y", variables ("axis 14"), and comma-separated
        # expressions ("width - 10, height - 10").
        x, y = _eval_values(line.split(), 2, evaluator, lineno, "point")
        pts.append((x, y))
    return pts


def _parse_triangle_points(
    data: dict,
    shape_id: str,
    lineno: int,
    evaluator: ExpressionEvaluator,
) -> tuple[tuple[float, float], tuple[float, float], tuple[float, float]]:
    """Extract p1/p2/p3 from block body; support both point form and at+size box form."""
    if "p1" in data and "p2" in data and "p3" in data:
        p1_ln, p1v = data["p1"]
        p2_ln, p2v = data["p2"]
        p3_ln, p3v = data["p3"]
        p1 = tuple(_eval_values(p1v, 2, evaluator, p1_ln, "p1"))
        p2 = tuple(_eval_values(p2v, 2, evaluator, p2_ln, "p2"))
        p3 = tuple(_eval_values(p3v, 2, evaluator, p3_ln, "p3"))
    elif "at" in data and "size" in data:
        at_ln, at_v = data["at"]
        sz_ln, sz_v = data["size"]
        x, y = _eval_values(at_v, 2, evaluator, at_ln, "at")
        w, h = _eval_values(sz_v, 2, evaluator, sz_ln, "size")
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
    evaluator = ExpressionEvaluator()

    for lineno, line, body in blocks:
        # ------------------------------------------------------------------
        # Variable assignment: ``<identifier> = <expression>`` (top-level only).
        # Must be checked before keyword dispatch. An assignment is recognised
        # when the text left of the first '=' is a single whitespace-free token;
        # this lets ``symmetry vertical x=75`` (whitespace before '=') stay a
        # normal command, while an invalid name like ``stitch-spacing = 5`` is
        # still routed to define() for a helpful "invalid variable name" error.
        if not body and "=" in line:
            lhs, _, rhs = line.partition("=")
            lhs = lhs.strip()
            if lhs and not re.search(r"\s", lhs):
                evaluator.define(lhs, rhs.strip(), lineno)
                continue

        tokens = line.split()
        keyword = tokens[0]

        # ------------------------------------------------------------------
        if keyword == "pattern":
            if len(tokens) < 2:
                raise DslError(f"Line {lineno}: 'pattern' requires a name")
            name = tokens[1]

        # ------------------------------------------------------------------
        elif keyword == "size":
            if len(tokens) < 2:
                raise DslError(f"Line {lineno}: 'size' requires width and height")
            width_mm, height_mm = _eval_values(tokens[1:], 2, evaluator, lineno, "size")

        # ------------------------------------------------------------------
        elif keyword == "layer":
            if len(tokens) < 4:
                raise DslError(f"Line {lineno}: 'layer' requires name, color, stroke_width")
            lname = tokens[1]
            color = _resolve_color(tokens[2])
            sw = _eval_value([tokens[3]], evaluator, lineno, "stroke_width")
            dashed = len(tokens) > 4 and tokens[4] == "dashed"
            layers[lname] = LayerStyle(color=color, stroke_width=sw, dashed=dashed)

        # ------------------------------------------------------------------
        elif keyword == "symmetry":
            rest = tokens[1:]
            if not rest:
                raise DslError(f"Line {lineno}: 'symmetry' requires a value")
            if rest[0] == "vertical":
                xpart = " ".join(rest[1:])
                if xpart.startswith("x="):
                    symmetry_axis_x = evaluator.eval(xpart[2:], lineno)
                else:
                    raise DslError(f"Line {lineno}: expected 'x=<value>' after 'symmetry vertical'")
            else:
                symmetry_axis_x = _eval_value(rest, evaluator, lineno, "symmetry")

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
            x, y = _eval_values(at_vals, 2, evaluator, at_lineno, "at")
            w, h = _eval_values(sz_vals, 2, evaluator, sz_lineno, "size")
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
            x, y = _eval_values(at_vals, 2, evaluator, at_lineno, "at")
            w, h = _eval_values(sz_vals, 2, evaluator, sz_lineno, "size")

            corner_keys = ("radius_tl", "radius_tr", "radius_br", "radius_bl")
            corners: dict[str, float | None] = {k: None for k in corner_keys}
            for k in corner_keys:
                if k in data:
                    c_ln, c_vals = data[k]
                    val = _eval_value(c_vals, evaluator, c_ln, k)
                    if val < 0:
                        raise DslError(f"Line {c_ln}: {k} must be >= 0")
                    corners[k] = val

            has_corner = any(v is not None for v in corners.values())
            if "radius" in data:
                r_lineno, r_vals = data["radius"]
                r = _eval_value(r_vals, evaluator, r_lineno, "radius")
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
            x, y = _eval_values(at_vals, 2, evaluator, at_lineno, "at")
            w, h = _eval_values(sz_vals, 2, evaluator, sz_lineno, "size")
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
            cx, cy = _eval_values(at_vals, 2, evaluator, at_lineno, "at")
            r = _eval_value(r_vals, evaluator, r_lineno, "radius")
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
            cx, cy = _eval_values(at_vals, 2, evaluator, at_lineno, "at")
            r = _eval_value(r_vals, evaluator, r_lineno, "radius")
            if r <= 0:
                raise DslError(f"Line {r_lineno}: radius must be greater than 0")
            start_a = _eval_value(fa_vals, evaluator, fa_lineno, "from_angle")
            end_a = _eval_value(ta_vals, evaluator, ta_lineno, "to_angle")
            inner_r = 0.0
            if "inner_radius" in data:
                ir_lineno, ir_vals = data["inner_radius"]
                inner_r = _eval_value(ir_vals, evaluator, ir_lineno, "inner_radius")
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
            cx, cy = _eval_values(at_vals, 2, evaluator, at_lineno, "at")
            if "rx" in data and "ry" in data:
                rx_lineno, rx_vals = data["rx"]
                ry_lineno, ry_vals = data["ry"]
                rx = _eval_value(rx_vals, evaluator, rx_lineno, "rx")
                ry = _eval_value(ry_vals, evaluator, ry_lineno, "ry")
            elif "size" in data:
                sz_lineno, sz_vals = data["size"]
                sw, sh = _eval_values(sz_vals, 2, evaluator, sz_lineno, "size")
                rx = sw / 2
                ry = sh / 2
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
            p1, p2, p3 = _parse_triangle_points(data, shape_id, lineno, evaluator)
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
            p1, p2, p3 = _parse_triangle_points(data, shape_id, lineno, evaluator)
            if "radius" not in data:
                raise DslError(f"Line {lineno}: rounded_triangle '{shape_id}' is missing 'radius'")
            r_lineno, r_vals = data["radius"]
            r = _eval_value(r_vals, evaluator, r_lineno, "radius")
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
        elif keyword == "regular_polygon":
            if len(tokens) < 2:
                raise DslError(f"Line {lineno}: 'regular_polygon' requires an id")
            shape_id = tokens[1]
            data = _parse_block_body(body)

            def _req(k: str, sid=shape_id, ln=lineno) -> tuple[int, list[str]]:
                if k not in data:
                    raise DslError(f"Line {ln}: regular_polygon '{sid}' is missing '{k}'")
                return data[k]

            at_lineno, at_vals = _req("at")
            radius_lineno, radius_vals = _req("radius")
            sides_lineno, sides_vals = _req("sides")
            cx, cy = _eval_values(at_vals, 2, evaluator, at_lineno, "at")
            radius = _eval_value(radius_vals, evaluator, radius_lineno, "radius")
            sides_value = _eval_value(sides_vals, evaluator, sides_lineno, "sides")
            sides = int(sides_value)
            if sides != sides_value:
                raise DslError(f"Line {sides_lineno}: sides must be a whole number")
            if radius <= 0:
                raise DslError(f"Line {radius_lineno}: radius must be greater than 0")
            if sides < 3:
                raise DslError(f"Line {sides_lineno}: sides must be at least 3")
            rotation = -90.0
            if "rotation" in data:
                rotation_lineno, rotation_vals = data["rotation"]
                rotation = _eval_value(rotation_vals, evaluator, rotation_lineno, "rotation")
            layer_name = "cut"
            if "layer" in data:
                layer_name = data["layer"][1][0]
            shapes.append(RegularPolygonDefinition(
                id=shape_id,
                cx=cx,
                cy=cy,
                radius=radius,
                sides=sides,
                rotation=rotation,
                layer=layer_name,
            ))
            shape_ids.add(shape_id)

        # ------------------------------------------------------------------
        elif keyword == "rounded_regular_polygon":
            if len(tokens) < 2:
                raise DslError(f"Line {lineno}: 'rounded_regular_polygon' requires an id")
            shape_id = tokens[1]
            data = _parse_block_body(body)

            def _req(k: str, sid=shape_id, ln=lineno) -> tuple[int, list[str]]:
                if k not in data:
                    raise DslError(f"Line {ln}: rounded_regular_polygon '{sid}' is missing '{k}'")
                return data[k]

            at_lineno, at_vals = _req("at")
            radius_lineno, radius_vals = _req("radius")
            sides_lineno, sides_vals = _req("sides")
            cx, cy = _eval_values(at_vals, 2, evaluator, at_lineno, "at")
            radius = _eval_value(radius_vals, evaluator, radius_lineno, "radius")
            sides_value = _eval_value(sides_vals, evaluator, sides_lineno, "sides")
            sides = int(sides_value)
            if sides != sides_value:
                raise DslError(f"Line {sides_lineno}: sides must be a whole number")
            if radius <= 0:
                raise DslError(f"Line {radius_lineno}: radius must be greater than 0")
            if sides < 3:
                raise DslError(f"Line {sides_lineno}: sides must be at least 3")

            rotation = -90.0
            if "rotation" in data:
                rotation_lineno, rotation_vals = data["rotation"]
                rotation = _eval_value(rotation_vals, evaluator, rotation_lineno, "rotation")

            corner_overrides: dict[int, float] = {}
            allowed_keys = {"at", "radius", "corner_radius", "sides", "rotation", "layer"}
            for key, (key_lineno, key_vals) in data.items():
                if key in allowed_keys:
                    continue
                match = re.fullmatch(r"corner_radius_(\d+)", key)
                if match is None:
                    raise DslError(
                        f"Line {key_lineno}: unknown key '{key}' in rounded_regular_polygon block"
                    )
                index = int(match.group(1))
                if index >= sides:
                    raise DslError(
                        f"Line {key_lineno}: {key} is out of range for {sides} sides"
                    )
                value = _eval_value(key_vals, evaluator, key_lineno, key)
                if value < 0:
                    raise DslError(f"Line {key_lineno}: {key} must be >= 0")
                corner_overrides[index] = value

            if "corner_radius" in data:
                corner_radius_lineno, corner_radius_vals = data["corner_radius"]
                corner_radius = _eval_value(corner_radius_vals, evaluator, corner_radius_lineno, "corner_radius")
                if corner_radius < 0:
                    raise DslError(f"Line {corner_radius_lineno}: corner_radius must be >= 0")
            elif corner_overrides:
                corner_radius = 0.0
            else:
                raise DslError(
                    f"Line {lineno}: rounded_regular_polygon '{shape_id}' is missing 'corner_radius' "
                    f"(or per-corner corner_radius_0/corner_radius_1/...)"
                )

            layer_name = "cut"
            if "layer" in data:
                layer_name = data["layer"][1][0]
            shapes.append(RoundedRegularPolygonDefinition(
                id=shape_id,
                cx=cx,
                cy=cy,
                radius=radius,
                sides=sides,
                corner_radius=corner_radius,
                rotation=rotation,
                layer=layer_name,
                corner_overrides=corner_overrides,
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
            pts = _parse_xy_list(body, evaluator)
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
                "distribution", "path_mode", "first_margin", "last_margin",
            }
            for _k in data:
                if _k == "include_corners":
                    _kln = data[_k][0] if isinstance(data[_k], tuple) else lineno
                    raise DslError(
                        f"Line {_kln}: 'include_corners' has been removed; "
                        "use first_margin / last_margin instead"
                    )
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
            distribution = "fixed_spacing"
            path_mode_val = "continuous"
            first_margin_val: float | None = None
            last_margin_val: float | None = None

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
                margin = _eval_value(vals, evaluator, ln, "margin")
            if "spacing" in data:
                ln, vals = data["spacing"]
                spacing = _eval_value(vals, evaluator, ln, "spacing")
                if spacing <= 0:
                    raise DslError(f"Line {ln}: spacing must be greater than 0")
            if "length" in data:
                ln, vals = data["length"]
                length = _eval_value(vals, evaluator, ln, "length")
            if "angle" in data:
                ln, vals = data["angle"]
                angle = _eval_value(vals, evaluator, ln, "angle")
            if "layer" in data:
                layer_name = data["layer"][1][0]
            if "mirror" in data:
                mirror_flag = True
            if "side" in data:
                side = data["side"][1][0]
            if "path" in data:
                path_pts = _parse_xy_list(data["path"], evaluator)
            if "rounded_path" in data:
                rounded_path = True
            if "distribution" in data:
                dist_ln, dist_vals = data["distribution"]
                if len(dist_vals) != 1:
                    raise DslError(f"Line {dist_ln}: distribution requires exactly one value")
                distribution = dist_vals[0]
                if distribution == "fixed_count":
                    raise DslError(
                        f"Line {dist_ln}: distribution 'fixed_count' is not supported yet"
                    )
                if distribution not in ("fixed_spacing", "fit_evenly"):
                    raise DslError(
                        f"Line {dist_ln}: unknown distribution '{distribution}'. "
                        "Use: fixed_spacing, fit_evenly"
                    )
            if "path_mode" in data:
                pm_ln, pm_vals = data["path_mode"]
                if len(pm_vals) != 1:
                    raise DslError(f"Line {pm_ln}: path_mode requires exactly one value")
                path_mode_val = pm_vals[0]
                if path_mode_val not in ("per_edge", "continuous", "continuous_rounded"):
                    raise DslError(
                        f"Line {pm_ln}: unknown path_mode '{path_mode_val}'. "
                        "Use: per_edge, continuous, continuous_rounded"
                    )
            if "first_margin" in data:
                fm_ln, fm_vals = data["first_margin"]
                first_margin_val = _eval_value(fm_vals, evaluator, fm_ln, "first_margin")
            if "last_margin" in data:
                lm_ln, lm_vals = data["last_margin"]
                last_margin_val = _eval_value(lm_vals, evaluator, lm_ln, "last_margin")

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
                distribution=distribution,
                path_mode=path_mode_val,
                first_margin=first_margin_val,
                last_margin=last_margin_val,
            ))

        # ------------------------------------------------------------------
        elif keyword == "holes":
            data = _parse_block_body(body)

            _KNOWN_HOLES_KEYS = {
                "source", "edges", "margin", "spacing", "radius",
                "layer", "rounded_path", "distribution", "path_mode", "first_margin", "last_margin",
            }
            for _k in data:
                if _k == "include_corners":
                    _kln = data[_k][0] if isinstance(data[_k], tuple) else lineno
                    raise DslError(
                        f"Line {_kln}: 'include_corners' has been removed; "
                        "use first_margin / last_margin instead"
                    )
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
            distribution = "fixed_spacing"
            path_mode_val = "continuous"
            first_margin_val: float | None = None
            last_margin_val: float | None = None

            if "edges" in data:
                e_ln, e_vals = data["edges"]
                edges_raw = _resolve_edges(e_vals, e_ln)
            if "margin" in data:
                ln, vals = data["margin"]
                margin = _eval_value(vals, evaluator, ln, "margin")
            if "spacing" in data:
                ln, vals = data["spacing"]
                spacing = _eval_value(vals, evaluator, ln, "spacing")
                if spacing <= 0:
                    raise DslError(f"Line {ln}: spacing must be greater than 0")
            if "radius" in data:
                ln, vals = data["radius"]
                radius = _eval_value(vals, evaluator, ln, "radius")
                if radius <= 0:
                    raise DslError(f"Line {ln}: radius must be greater than 0")
            if "layer" in data:
                layer_name = data["layer"][1][0]
            if "rounded_path" in data:
                rounded_path = True
            if "distribution" in data:
                dist_ln, dist_vals = data["distribution"]
                if len(dist_vals) != 1:
                    raise DslError(f"Line {dist_ln}: distribution requires exactly one value")
                distribution = dist_vals[0]
                if distribution == "fixed_count":
                    raise DslError(
                        f"Line {dist_ln}: distribution 'fixed_count' is not supported yet"
                    )
                if distribution not in ("fixed_spacing", "fit_evenly"):
                    raise DslError(
                        f"Line {dist_ln}: unknown distribution '{distribution}'. "
                        "Use: fixed_spacing, fit_evenly"
                    )
            if "path_mode" in data:
                pm_ln, pm_vals = data["path_mode"]
                if len(pm_vals) != 1:
                    raise DslError(f"Line {pm_ln}: path_mode requires exactly one value")
                path_mode_val = pm_vals[0]
                if path_mode_val not in ("per_edge", "continuous", "continuous_rounded"):
                    raise DslError(
                        f"Line {pm_ln}: unknown path_mode '{path_mode_val}'. "
                        "Use: per_edge, continuous, continuous_rounded"
                    )
            if "first_margin" in data:
                fm_ln, fm_vals = data["first_margin"]
                first_margin_val = _eval_value(fm_vals, evaluator, fm_ln, "first_margin")
            if "last_margin" in data:
                lm_ln, lm_vals = data["last_margin"]
                last_margin_val = _eval_value(lm_vals, evaluator, lm_ln, "last_margin")

            operations.append(HolesOperation(
                source=source,
                edges=edges_raw,
                margin=margin,
                spacing=spacing,
                radius=radius,
                layer=layer_name,
                rounded_path=rounded_path,
                distribution=distribution,
                path_mode=path_mode_val,
                first_margin=first_margin_val,
                last_margin=last_margin_val,
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

                xfc = _eval_value(xfc_vals, evaluator, xfc_ln, "x_from_center")
                hole_y = _eval_value(y_vals, evaluator, y_ln, "y")
                r = _eval_value(r_vals, evaluator, r_ln, "radius")
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

                hole_x, hole_y = _eval_values(at_vals, 2, evaluator, at_ln, "at")
                r = _eval_value(r_vals, evaluator, r_ln, "radius")
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
                if fmt not in ("svg", "png", "pdf", "dxf"):
                    raise DslError(
                        f"Line {lineno}: unknown export format '{fmt}'. Use: svg, png, pdf, dxf."
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

        elif isinstance(shape_def, RegularPolygonDefinition):
            s = RegularPolygon(
                shape_def.cx,
                shape_def.cy,
                shape_def.radius,
                shape_def.sides,
                rotation_deg=shape_def.rotation,
            )
            svg.add_shape(s, layer=shape_def.layer)
            shape_objects[shape_def.id] = s

        elif isinstance(shape_def, RoundedRegularPolygonDefinition):
            s = RoundedRegularPolygon(
                shape_def.cx,
                shape_def.cy,
                shape_def.radius,
                shape_def.sides,
                corner_radius=shape_def.corner_radius,
                rotation_deg=shape_def.rotation,
                corner_overrides=shape_def.corner_overrides,
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
                    distribution=op.distribution,
                    path_mode=op.path_mode,
                    first_margin=op.first_margin,
                    last_margin=op.last_margin,
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
                    distribution=op.distribution,
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
                        distribution=op.distribution,
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
                distribution=op.distribution,
                path_mode=op.path_mode,
                first_margin=op.first_margin,
                last_margin=op.last_margin,
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
    elif exp.format == "dxf":
        try:
            svg.save_dxf(exp.filename)
        except Exception as exc:
            raise DslError(f"DXF export failed: {exc}") from exc


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
