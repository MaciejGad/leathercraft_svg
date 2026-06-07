from __future__ import annotations

from dataclasses import dataclass
from math import cos, hypot, pi, sin
from pathlib import Path
from typing import Iterable, Literal, Sequence

LayerName = Literal["cut", "stitch", "crease", "guide"]


@dataclass(frozen=True)
class Point:
    x: float
    y: float


@dataclass
class StrokeStyle:
    color: str
    width: float = 0.1
    dasharray: str | None = None


DEFAULT_STYLES: dict[str, StrokeStyle] = {
    "cut": StrokeStyle("#ff0000", 0.1),
    "stitch": StrokeStyle("#0000ff", 0.1),
    "crease": StrokeStyle("#00aa00", 0.1, "3 2"),
    "guide": StrokeStyle("#777777", 0.1, "2 2"),
}


class SvgDocument:
    def __init__(self, width_mm: float, height_mm: float, styles: dict[str, StrokeStyle] | None = None):
        self.width_mm = width_mm
        self.height_mm = height_mm
        self.styles = styles or DEFAULT_STYLES
        self.elements: list[str] = []

    def add_path(self, d: str, layer: LayerName = "cut") -> None:
        self.elements.append(f'<path {self._style_attributes(layer)} d="{d}" />')

    def add_line(self, x1: float, y1: float, x2: float, y2: float, layer: LayerName = "cut") -> None:
        self.elements.append(
            f'<line {self._style_attributes(layer)} x1="{x1:.3f}" y1="{y1:.3f}" x2="{x2:.3f}" y2="{y2:.3f}" />'
        )

    def add_circle(self, x: float, y: float, radius: float, layer: LayerName = "cut") -> None:
        self.elements.append(
            f'<circle {self._style_attributes(layer)} cx="{x:.3f}" cy="{y:.3f}" r="{radius:.3f}" />'
        )

    def add_shape(self, shape: "Shape", layer: LayerName = "cut") -> None:
        self.add_path(shape.path_d(), layer)

    def add_holes(
        self,
        shape: "Shape",
        edges: Sequence[int] | Literal["all"] = "all",
        spacing: float = 5.0,
        hole_radius: float = 1.2,
        inset: float = 4.0,
        layer: LayerName = "cut",
        include_corners: bool = False,
    ) -> None:
        for p in shape.hole_points(edges=edges, spacing=spacing, inset=inset, include_corners=include_corners):
            self.add_circle(p.x, p.y, hole_radius, layer)

    def add_stitch_holes(
        self,
        shape: "Shape",
        edges: Sequence[int] | Literal["all"] = "all",
        spacing: float = 5.0,
        hole_radius: float = 1.2,
        inset: float = 4.0,
        layer: LayerName = "cut",
        include_corners: bool = False,
    ) -> None:
        self.add_holes(shape, edges, spacing, hole_radius, inset, layer, include_corners)

    def save(self, path: str | Path) -> None:
        Path(path).write_text(self.to_svg(), encoding="utf-8")

    def save_png(self, path: str | Path, background_color: str = "white") -> None:
        import cairosvg

        cairosvg.svg2png(
            bytestring=self.to_svg().encode("utf-8"),
            write_to=str(path),
            background_color=background_color,
        )

    def to_svg(self) -> str:
        body = "\n  ".join(self.elements)
        return (
            '<?xml version="1.0" encoding="UTF-8" standalone="no"?>\n'
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.width_mm}mm" height="{self.height_mm}mm" '
            f'viewBox="0 0 {self.width_mm} {self.height_mm}" version="1.1">\n'
            f'  {body}\n'
            '</svg>\n'
        )

    def _style_attributes(self, layer: LayerName) -> str:
        style = self.styles[layer]
        dash = f' stroke-dasharray="{style.dasharray}"' if style.dasharray else ""
        return (
            f'fill="none" stroke="{style.color}" stroke-width="{style.width}"'
            f'{dash} vector-effect="non-scaling-stroke"'
        )


class Shape:
    def path_d(self) -> str:
        raise NotImplementedError

    def hole_points(
        self,
        edges: Sequence[int] | Literal["all"] = "all",
        spacing: float = 5.0,
        inset: float = 4.0,
        include_corners: bool = False,
    ) -> list[Point]:
        raise NotImplementedError


@dataclass
class Rectangle(Shape):
    x: float
    y: float
    width: float
    height: float

    def path_d(self) -> str:
        x, y, w, h = self.x, self.y, self.width, self.height
        return f"M {x:.3f} {y:.3f} L {x+w:.3f} {y:.3f} L {x+w:.3f} {y+h:.3f} L {x:.3f} {y+h:.3f} Z"

    def hole_points(self, edges="all", spacing=5.0, inset=4.0, include_corners=False) -> list[Point]:
        x = self.x + inset
        y = self.y + inset
        w = self.width - 2 * inset
        h = self.height - 2 * inset
        edge_defs = [
            (Point(x, y), Point(x + w, y)),
            (Point(x + w, y), Point(x + w, y + h)),
            (Point(x + w, y + h), Point(x, y + h)),
            (Point(x, y + h), Point(x, y)),
        ]
        return points_on_selected_edges(edge_defs, edges, spacing, include_corners)


@dataclass
class RoundedRectangle(Rectangle):
    radius: float = 5.0

    def path_d(self) -> str:
        x, y, w, h = self.x, self.y, self.width, self.height
        r = min(self.radius, w / 2, h / 2)
        return (
            f"M {x+r:.3f} {y:.3f} "
            f"L {x+w-r:.3f} {y:.3f} "
            f"Q {x+w:.3f} {y:.3f} {x+w:.3f} {y+r:.3f} "
            f"L {x+w:.3f} {y+h-r:.3f} "
            f"Q {x+w:.3f} {y+h:.3f} {x+w-r:.3f} {y+h:.3f} "
            f"L {x+r:.3f} {y+h:.3f} "
            f"Q {x:.3f} {y+h:.3f} {x:.3f} {y+h-r:.3f} "
            f"L {x:.3f} {y+r:.3f} "
            f"Q {x:.3f} {y:.3f} {x+r:.3f} {y:.3f} Z"
        )


@dataclass
class Circle(Shape):
    cx: float
    cy: float
    radius: float

    def path_d(self) -> str:
        x, y, r = self.cx, self.cy, self.radius
        return f"M {x-r:.3f} {y:.3f} A {r:.3f} {r:.3f} 0 1 0 {x+r:.3f} {y:.3f} A {r:.3f} {r:.3f} 0 1 0 {x-r:.3f} {y:.3f} Z"

    def hole_points(self, edges="all", spacing=5.0, inset=4.0, include_corners=False) -> list[Point]:
        r = max(self.radius - inset, 0.1)
        count = max(3, int((2 * pi * r) // spacing))
        return [
            Point(self.cx + r * cos(2 * pi * i / count), self.cy + r * sin(2 * pi * i / count))
            for i in range(count)
        ]


@dataclass
class Triangle(Shape):
    p1: Point
    p2: Point
    p3: Point

    @classmethod
    def from_box(cls, x: float, y: float, width: float, height: float) -> "Triangle":
        return cls(Point(x + width / 2, y), Point(x + width, y + height), Point(x, y + height))

    def path_d(self) -> str:
        return f"M {self.p1.x:.3f} {self.p1.y:.3f} L {self.p2.x:.3f} {self.p2.y:.3f} L {self.p3.x:.3f} {self.p3.y:.3f} Z"

    def hole_points(self, edges="all", spacing=5.0, inset=4.0, include_corners=False) -> list[Point]:
        centroid = Point((self.p1.x + self.p2.x + self.p3.x) / 3, (self.p1.y + self.p2.y + self.p3.y) / 3)
        p1 = move_towards(self.p1, centroid, inset)
        p2 = move_towards(self.p2, centroid, inset)
        p3 = move_towards(self.p3, centroid, inset)
        edge_defs = [(p1, p2), (p2, p3), (p3, p1)]
        return points_on_selected_edges(edge_defs, edges, spacing, include_corners)


@dataclass
class RoundedTriangle(Triangle):
    radius: float = 5.0

    def path_d(self) -> str:
        points = [self.p1, self.p2, self.p3]
        start_points = []
        end_points = []
        for i in range(3):
            prev_p = points[(i - 1) % 3]
            p = points[i]
            next_p = points[(i + 1) % 3]
            cut = min(self.radius, distance(p, prev_p) / 3, distance(p, next_p) / 3)
            start_points.append(move_towards(p, prev_p, cut))
            end_points.append(move_towards(p, next_p, cut))
        d = f"M {end_points[0].x:.3f} {end_points[0].y:.3f} "
        for i in range(1, 4):
            idx = i % 3
            d += (
                f"L {start_points[idx].x:.3f} {start_points[idx].y:.3f} "
                f"Q {points[idx].x:.3f} {points[idx].y:.3f} "
                f"{end_points[idx].x:.3f} {end_points[idx].y:.3f} "
            )
        return d + "Z"


def points_on_selected_edges(edge_defs, edges, spacing, include_corners) -> list[Point]:
    selected = range(len(edge_defs)) if edges == "all" else edges
    result = []
    for index in selected:
        p1, p2 = edge_defs[index]
        result.extend(points_on_line(p1, p2, spacing, include_corners))
    return deduplicate_points(result)


def points_on_line(p1: Point, p2: Point, spacing: float, include_corners: bool = False) -> list[Point]:
    length = distance(p1, p2)
    if length == 0:
        return []
    start = 0.0 if include_corners else spacing / 2
    end = length if include_corners else length - spacing / 2
    if end < start:
        return []
    dx = (p2.x - p1.x) / length
    dy = (p2.y - p1.y) / length
    points = []
    pos = start
    while pos <= end + 0.001:
        points.append(Point(p1.x + dx * pos, p1.y + dy * pos))
        pos += spacing
    return points


def distance(a: Point, b: Point) -> float:
    return hypot(b.x - a.x, b.y - a.y)


def move_towards(a: Point, b: Point, amount: float) -> Point:
    d = distance(a, b)
    if d == 0:
        return a
    t = min(amount / d, 1.0)
    return Point(a.x + (b.x - a.x) * t, a.y + (b.y - a.y) * t)


def deduplicate_points(points: Iterable[Point], precision: int = 3) -> list[Point]:
    seen = set()
    result = []
    for p in points:
        key = (round(p.x, precision), round(p.y, precision))
        if key not in seen:
            seen.add(key)
            result.append(p)
    return result
