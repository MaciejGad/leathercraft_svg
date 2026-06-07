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

    def add_line(
        self,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        layer: LayerName = "cut",
        stroke_width: float | None = None,
    ) -> None:
        self.elements.append(
            f'<line {self._style_attributes(layer, stroke_width=stroke_width)} '
            f'x1="{x1:.3f}" y1="{y1:.3f}" x2="{x2:.3f}" y2="{y2:.3f}" />'
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
        rounded_path: bool = False,
    ) -> None:
        for p in shape.hole_points(
            edges=edges,
            spacing=spacing,
            inset=inset,
            include_corners=include_corners,
            rounded_path=rounded_path,
        ):
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
        rounded_path: bool = False,
    ) -> None:
        self.add_holes(shape, edges, spacing, hole_radius, inset, layer, include_corners, rounded_path)

    def add_stitch_pattern(
        self,
        shape: "Shape",
        edges: Sequence[int] | Literal["all"] = "all",
        spacing: float = 5.0,
        stitch_length: float = 2.0,
        inset: float = 4.0,
        layer: LayerName = "stitch",
        include_corners: bool = False,
        stitch_thickness: float | None = None,
        stitch_angle_deg: float = 0.0,
        rounded_path: bool = False,
    ) -> None:
        for p1, p2 in shape.stitch_segments(
            edges=edges,
            spacing=spacing,
            inset=inset,
            include_corners=include_corners,
            stitch_length=stitch_length,
            stitch_angle_deg=stitch_angle_deg,
            rounded_path=rounded_path,
        ):
            self.add_line(p1.x, p1.y, p2.x, p2.y, layer=layer, stroke_width=stitch_thickness)

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

    def _style_attributes(self, layer: LayerName, stroke_width: float | None = None) -> str:
        style = self.styles[layer]
        dash = f' stroke-dasharray="{style.dasharray}"' if style.dasharray else ""
        width = style.width if stroke_width is None else stroke_width
        return (
            f'fill="none" stroke="{style.color}" stroke-width="{width}"'
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
        rounded_path: bool = False,
    ) -> list[Point]:
        raise NotImplementedError

    def stitch_segments(
        self,
        edges: Sequence[int] | Literal["all"] = "all",
        spacing: float = 5.0,
        inset: float = 4.0,
        include_corners: bool = False,
        stitch_length: float = 2.0,
        stitch_angle_deg: float = 0.0,
        rounded_path: bool = False,
    ) -> list[tuple[Point, Point]]:
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

    def hole_points(self, edges="all", spacing=5.0, inset=4.0, include_corners=False, rounded_path=False) -> list[Point]:
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
        selected = list(range(len(edge_defs))) if edges == "all" else list(edges)
        selected_set = set(selected)
        result: list[Point] = []
        for edge_index, (p1, p2) in enumerate(edge_defs):
            length = distance(p1, p2)
            if length == 0:
                continue
            positions = positions_on_side_center(length, spacing, include_corners)
            positions = adjust_positions_near_corners(
                positions,
                length,
                include_corners,
                spacing,
            )
            for local_pos in positions:
                if edge_index not in selected_set:
                    continue
                result.append(point_on_edge(p1, p2, local_pos))
        return deduplicate_points(result)

    def stitch_segments(
        self,
        edges="all",
        spacing=5.0,
        inset=4.0,
        include_corners=False,
        stitch_length=2.0,
        stitch_angle_deg=0.0,
        rounded_path=False,
    ) -> list[tuple[Point, Point]]:
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
        selected = list(range(len(edge_defs))) if edges == "all" else list(edges)
        selected_set = set(selected)
        result: list[tuple[Point, Point]] = []
        for edge_index, (p1, p2) in enumerate(edge_defs):
            length = distance(p1, p2)
            if length == 0:
                continue
            positions = positions_on_side_center(length, spacing, include_corners)
            adjusted = adjust_stitch_positions_and_lengths(
                positions,
                length,
                include_corners,
                spacing,
                stitch_length,
            )
            for local_pos, local_stitch_length in adjusted:
                if edge_index not in selected_set:
                    continue
                result.append(segment_on_edge(p1, p2, local_pos, local_stitch_length, stitch_angle_deg))
        return result


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

    def stitch_segments(
        self,
        edges="all",
        spacing=5.0,
        inset=4.0,
        include_corners=False,
        stitch_length=2.0,
        stitch_angle_deg=0.0,
        rounded_path=False,
    ) -> list[tuple[Point, Point]]:
        all_rectangle_edges = edges == "all" or sorted(set(edges)) == [0, 1, 2, 3]
        if not all_rectangle_edges:
            return super().stitch_segments(
                edges=edges,
                spacing=spacing,
                inset=inset,
                include_corners=include_corners,
                stitch_length=stitch_length,
                stitch_angle_deg=stitch_angle_deg,
                rounded_path=rounded_path,
            )

        x = self.x + inset
        y = self.y + inset
        w = self.width - 2 * inset
        h = self.height - 2 * inset
        if w <= 0 or h <= 0:
            return []

        r = max(0.0, min(self.radius - inset, w / 2, h / 2))
        contour = rounded_rectangle_contour(x, y, w, h, r)
        if len(contour) < 2:
            return []

        return stitch_segments_on_closed_polyline(
            contour,
            spacing=spacing,
            stitch_length=stitch_length,
            stitch_angle_deg=stitch_angle_deg,
            include_corners=include_corners,
        )


@dataclass
class Circle(Shape):
    cx: float
    cy: float
    radius: float

    def path_d(self) -> str:
        x, y, r = self.cx, self.cy, self.radius
        return f"M {x-r:.3f} {y:.3f} A {r:.3f} {r:.3f} 0 1 0 {x+r:.3f} {y:.3f} A {r:.3f} {r:.3f} 0 1 0 {x-r:.3f} {y:.3f} Z"

    def hole_points(self, edges="all", spacing=5.0, inset=4.0, include_corners=False, rounded_path=False) -> list[Point]:
        r = max(self.radius - inset, 0.1)
        count = max(3, int((2 * pi * r) // spacing))
        return [
            Point(self.cx + r * cos(2 * pi * i / count), self.cy + r * sin(2 * pi * i / count))
            for i in range(count)
        ]

    def stitch_segments(
        self,
        edges="all",
        spacing=5.0,
        inset=4.0,
        include_corners=False,
        stitch_length=2.0,
        stitch_angle_deg=0.0,
        rounded_path=False,
    ) -> list[tuple[Point, Point]]:
        r = max(self.radius - inset, 0.1)
        count = max(3, int((2 * pi * r) // spacing))
        half = stitch_length / 2
        angle_offset = stitch_angle_deg * pi / 180
        segments = []
        for i in range(count):
            angle = 2 * pi * i / count
            cx = self.cx + r * cos(angle)
            cy = self.cy + r * sin(angle)
            tx = -sin(angle)
            ty = cos(angle)
            ox = tx * cos(angle_offset) - ty * sin(angle_offset)
            oy = tx * sin(angle_offset) + ty * cos(angle_offset)
            segments.append(
                (
                    Point(cx - ox * half, cy - oy * half),
                    Point(cx + ox * half, cy + oy * half),
                )
            )
        return segments


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

    def hole_points(self, edges="all", spacing=5.0, inset=4.0, include_corners=False, rounded_path=False) -> list[Point]:
        p1, p2, p3 = inset_triangle_vertices(self.p1, self.p2, self.p3, inset)
        edge_defs = [(p1, p2), (p2, p3), (p3, p1)]
        selected = list(range(len(edge_defs))) if edges == "all" else list(edges)

        if selected == [0, 1, 2]:
            selected_edge_defs = [edge_defs[i] for i in selected]
            return points_on_closed_edges(
                selected_edge_defs,
                spacing,
                include_corners,
            )

        return points_on_selected_edges(edge_defs, edges, spacing, include_corners)

    def stitch_segments(
        self,
        edges="all",
        spacing=5.0,
        inset=4.0,
        include_corners=False,
        stitch_length=2.0,
        stitch_angle_deg=0.0,
        rounded_path=False,
    ) -> list[tuple[Point, Point]]:
        p1, p2, p3 = inset_triangle_vertices(self.p1, self.p2, self.p3, inset)
        edge_defs = [(p1, p2), (p2, p3), (p3, p1)]
        selected = list(range(len(edge_defs))) if edges == "all" else list(edges)

        if selected == [0, 1, 2]:
            selected_edge_defs = [edge_defs[i] for i in selected]
            return segments_on_closed_edges(
                selected_edge_defs,
                spacing,
                stitch_length,
                include_corners,
                stitch_angle_deg,
            )

        return segments_on_selected_edges(
            edge_defs,
            edges,
            spacing,
            stitch_length,
            include_corners,
            stitch_angle_deg,
        )


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

    def hole_points(
        self,
        edges="all",
        spacing=5.0,
        inset=4.0,
        include_corners=False,
        rounded_path=False,
    ) -> list[Point]:
        all_triangle_edges = edges == "all" or sorted(set(edges)) == [0, 1, 2]
        if not rounded_path or not all_triangle_edges:
            return super().hole_points(
                edges=edges,
                spacing=spacing,
                inset=inset,
                include_corners=include_corners,
                rounded_path=rounded_path,
            )

        p1, p2, p3 = inset_triangle_vertices(self.p1, self.p2, self.p3, inset)
        effective_radius = max(0.0, self.radius - inset)
        contour = rounded_triangle_contour([p1, p2, p3], effective_radius)
        if len(contour) < 2:
            return []
        return points_on_closed_polyline(
            contour,
            spacing=spacing,
            include_corners=include_corners,
        )

    def stitch_segments(
        self,
        edges="all",
        spacing=5.0,
        inset=4.0,
        include_corners=False,
        stitch_length=2.0,
        stitch_angle_deg=0.0,
        rounded_path=False,
    ) -> list[tuple[Point, Point]]:
        all_triangle_edges = edges == "all" or sorted(set(edges)) == [0, 1, 2]
        if not rounded_path or not all_triangle_edges:
            return super().stitch_segments(
                edges=edges,
                spacing=spacing,
                inset=inset,
                include_corners=include_corners,
                stitch_length=stitch_length,
                stitch_angle_deg=stitch_angle_deg,
                rounded_path=rounded_path,
            )

        p1, p2, p3 = inset_triangle_vertices(self.p1, self.p2, self.p3, inset)
        effective_radius = max(0.0, self.radius - inset)
        contour = rounded_triangle_contour([p1, p2, p3], effective_radius)
        if len(contour) < 2:
            return []
        return stitch_segments_on_closed_polyline(
            contour,
            spacing=spacing,
            stitch_length=stitch_length,
            stitch_angle_deg=stitch_angle_deg,
            include_corners=include_corners,
        )


def points_on_selected_edges(edge_defs, edges, spacing, include_corners) -> list[Point]:
    selected = list(range(len(edge_defs))) if edges == "all" else list(edges)

    result = []
    for index in selected:
        p1, p2 = edge_defs[index]
        result.extend(points_on_line(p1, p2, spacing, include_corners))
    return deduplicate_points(result)


def segments_on_selected_edges(
    edge_defs,
    edges,
    spacing,
    stitch_length,
    include_corners,
    stitch_angle_deg,
) -> list[tuple[Point, Point]]:
    selected = list(range(len(edge_defs))) if edges == "all" else list(edges)

    result: list[tuple[Point, Point]] = []
    for index in selected:
        p1, p2 = edge_defs[index]
        result.extend(segments_on_line(p1, p2, spacing, stitch_length, include_corners, stitch_angle_deg))
    return result


def positions_on_edge_chain(
    edge_defs,
    selected: list[int],
    spacing: float,
    include_corners: bool,
) -> list[tuple[int, float]]:
    lengths = [distance(edge_defs[index][0], edge_defs[index][1]) for index in selected]
    total_length = sum(lengths)
    if total_length == 0:
        return []

    chain_positions = positions_on_line(total_length, spacing, include_corners)
    mapped: list[tuple[int, float]] = []
    prefix = 0.0
    position_index = 0

    for local_index, edge_index in enumerate(selected):
        edge_length = lengths[local_index]
        edge_end = prefix + edge_length
        is_last = local_index == len(selected) - 1

        while position_index < len(chain_positions):
            pos = chain_positions[position_index]
            if pos < prefix - 0.001:
                position_index += 1
                continue

            if pos < edge_end - 0.001 or (is_last and pos <= edge_end + 0.001):
                mapped.append((edge_index, max(0.0, min(edge_length, pos - prefix))))
                position_index += 1
                continue

            break

        prefix = edge_end

    return mapped


def shared_endpoints_in_selection(edge_defs, selected: list[int], precision: int = 6) -> tuple[dict[int, bool], dict[int, bool]]:
    endpoint_counts: dict[tuple[float, float], int] = {}
    for edge_index in selected:
        p1, p2 = edge_defs[edge_index]
        k1 = (round(p1.x, precision), round(p1.y, precision))
        k2 = (round(p2.x, precision), round(p2.y, precision))
        endpoint_counts[k1] = endpoint_counts.get(k1, 0) + 1
        endpoint_counts[k2] = endpoint_counts.get(k2, 0) + 1

    shared_start: dict[int, bool] = {}
    shared_end: dict[int, bool] = {}
    for edge_index in selected:
        p1, p2 = edge_defs[edge_index]
        k1 = (round(p1.x, precision), round(p1.y, precision))
        k2 = (round(p2.x, precision), round(p2.y, precision))
        shared_start[edge_index] = endpoint_counts.get(k1, 0) > 1
        shared_end[edge_index] = endpoint_counts.get(k2, 0) > 1

    return shared_start, shared_end


def point_on_edge(p1: Point, p2: Point, distance_on_edge: float) -> Point:
    length = distance(p1, p2)
    if length == 0:
        return p1
    ex = (p2.x - p1.x) / length
    ey = (p2.y - p1.y) / length
    return Point(p1.x + ex * distance_on_edge, p1.y + ey * distance_on_edge)


def segment_on_edge(
    p1: Point,
    p2: Point,
    distance_on_edge: float,
    stitch_length: float,
    stitch_angle_deg: float,
) -> tuple[Point, Point]:
    length = distance(p1, p2)
    if length == 0:
        return p1, p2
    ex = (p2.x - p1.x) / length
    ey = (p2.y - p1.y) / length
    center_x = p1.x + ex * distance_on_edge
    center_y = p1.y + ey * distance_on_edge
    angle_rad = stitch_angle_deg * pi / 180
    dx = ex * cos(angle_rad) - ey * sin(angle_rad)
    dy = ex * sin(angle_rad) + ey * cos(angle_rad)
    half = stitch_length / 2
    return (Point(center_x - dx * half, center_y - dy * half), Point(center_x + dx * half, center_y + dy * half))


def segments_on_closed_edges(
    edge_defs: list[tuple[Point, Point]],
    spacing: float,
    stitch_length: float,
    include_corners: bool,
    stitch_angle_deg: float,
) -> list[tuple[Point, Point]]:
    result: list[tuple[Point, Point]] = []
    for a, b in edge_defs:
        length = distance(a, b)
        if length == 0:
            continue
        positions = positions_on_side_center(length, spacing, include_corners)
        adjusted = adjust_stitch_positions_and_lengths(
            positions,
            length,
            include_corners,
            spacing,
            stitch_length,
        )
        for local_pos, local_stitch_length in adjusted:
            result.append(segment_on_edge(a, b, local_pos, local_stitch_length, stitch_angle_deg))
    return result


def points_on_closed_edges(
    edge_defs: list[tuple[Point, Point]],
    spacing: float,
    include_corners: bool,
) -> list[Point]:
    result: list[Point] = []
    for a, b in edge_defs:
        length = distance(a, b)
        if length == 0:
            continue
        positions = positions_on_side_center(length, spacing, include_corners)
        positions = adjust_positions_near_corners(
            positions,
            length,
            include_corners,
            spacing,
        )
        for local_pos in positions:
            result.append(point_on_edge(a, b, local_pos))
    return deduplicate_points(result)


def positions_on_side_center(
    length: float,
    spacing: float,
    include_corners: bool,
) -> list[float]:
    if length <= 0:
        return []

    if include_corners:
        positions: list[float] = []
        pos = 0.0
        while pos <= length + 0.001:
            positions.append(pos)
            pos += spacing
        return positions

    count = max(1, int(length / spacing))

    center = length / 2
    first = center - spacing * (count - 1) / 2
    return [first + i * spacing for i in range(count)]


def adjust_positions_near_corners(
    positions: list[float],
    length: float,
    include_corners: bool,
    spacing: float,
) -> list[float]:
    if include_corners or not positions or length <= 0:
        return positions

    count = len(positions)
    target_clearance = spacing * 0.7
    clearance = min(target_clearance, length / 2)

    start = positions[0]
    end = positions[-1]
    span_original = end - start
    span_target = max(0.0, length - 2 * clearance)

    if count == 1:
        return [length / 2]
    if span_original <= 1e-9:
        return [clearance + (span_target * i / (count - 1)) for i in range(count)]

    scale = span_target / span_original
    return [clearance + (pos - start) * scale for pos in positions]


def adjust_stitch_positions_and_lengths(
    positions: list[float],
    length: float,
    include_corners: bool,
    spacing: float,
    stitch_length: float,
) -> list[tuple[float, float]]:
    if include_corners or not positions or length <= 0:
        return [(pos, stitch_length) for pos in positions]

    # Preserve stitch count, move away from corners, and shorten near-corner stitches if needed.
    count = len(positions)
    target_clearance = max(stitch_length * 0.8, spacing * 0.7)
    clearance = min(target_clearance, length / 2)

    start = positions[0]
    end = positions[-1]
    span_original = end - start
    span_target = max(0.0, length - 2 * clearance)

    if count == 1:
        shifted_positions = [length / 2]
    elif span_original <= 1e-9:
        shifted_positions = [clearance + (span_target * i / (count - 1)) for i in range(count)]
    else:
        scale = span_target / span_original
        shifted_positions = [clearance + (pos - start) * scale for pos in positions]

    adjusted: list[tuple[float, float]] = []
    for pos in shifted_positions:
        dist_to_corner = min(pos, length - pos)
        max_safe_length = max(0.6, 2 * dist_to_corner * 0.9)
        local_stitch_length = min(stitch_length, max_safe_length)
        adjusted.append((pos, local_stitch_length))

    return adjusted


def points_on_line(
    p1: Point,
    p2: Point,
    spacing: float,
    include_corners: bool = False,
) -> list[Point]:
    length = distance(p1, p2)
    if length == 0:
        return []
    dx = (p2.x - p1.x) / length
    dy = (p2.y - p1.y) / length
    points = []
    for pos in positions_on_line(length, spacing, include_corners):
        points.append(Point(p1.x + dx * pos, p1.y + dy * pos))
    return points


def segments_on_line(
    p1: Point,
    p2: Point,
    spacing: float,
    stitch_length: float,
    include_corners: bool = False,
    stitch_angle_deg: float = 0.0,
) -> list[tuple[Point, Point]]:
    if (p2.x < p1.x) or (p2.x == p1.x and p2.y < p1.y):
        p1, p2 = p2, p1

    length = distance(p1, p2)
    if length == 0:
        return []
    ex = (p2.x - p1.x) / length
    ey = (p2.y - p1.y) / length
    angle_rad = stitch_angle_deg * pi / 180
    dx = ex * cos(angle_rad) - ey * sin(angle_rad)
    dy = ex * sin(angle_rad) + ey * cos(angle_rad)
    half = stitch_length / 2
    segments: list[tuple[Point, Point]] = []
    for pos in positions_on_line(length, spacing, include_corners):
        cx = p1.x + ex * pos
        cy = p1.y + ey * pos
        segments.append(
            (
                Point(cx - dx * half, cy - dy * half),
                Point(cx + dx * half, cy + dy * half),
            )
        )
    return segments


def positions_on_line(
    length: float,
    spacing: float,
    include_corners: bool,
) -> list[float]:
    if length <= 0:
        return []

    if include_corners:
        positions: list[float] = []
        pos = 0.0
        while pos <= length + 0.001:
            positions.append(pos)
            pos += spacing
        return positions

    count = max(1, int(length / spacing))
    margin = (length - (count - 1) * spacing) / 2
    return [margin + i * spacing for i in range(count)]


def rounded_triangle_contour(points: list[Point], radius: float, arc_steps: int = 12) -> list[Point]:
    if len(points) != 3:
        return []
    if radius <= 0:
        return points

    start_points: list[Point] = []
    end_points: list[Point] = []
    for i in range(3):
        prev_p = points[(i - 1) % 3]
        p = points[i]
        next_p = points[(i + 1) % 3]
        cut = min(radius, distance(p, prev_p) / 3, distance(p, next_p) / 3)
        start_points.append(move_towards(p, prev_p, cut))
        end_points.append(move_towards(p, next_p, cut))

    contour: list[Point] = [end_points[0]]
    for i in range(1, 4):
        idx = i % 3
        contour.append(start_points[idx])
        control = points[idx]
        a = start_points[idx]
        b = end_points[idx]
        for step in range(1, arc_steps):
            t = step / arc_steps
            contour.append(quadratic_bezier(a, control, b, t))
        contour.append(b)

    return contour


def rounded_rectangle_contour(
    x: float,
    y: float,
    width: float,
    height: float,
    radius: float,
    arc_steps: int = 12,
) -> list[Point]:
    if width <= 0 or height <= 0:
        return []

    r = max(0.0, min(radius, width / 2, height / 2))
    if r == 0.0:
        return [
            Point(x, y),
            Point(x + width, y),
            Point(x + width, y + height),
            Point(x, y + height),
        ]

    contour: list[Point] = []

    def add_arc(cx: float, cy: float, start_angle: float, end_angle: float) -> None:
        for step in range(1, arc_steps + 1):
            t = step / arc_steps
            angle = start_angle + (end_angle - start_angle) * t
            contour.append(Point(cx + r * cos(angle), cy + r * sin(angle)))

    contour.append(Point(x + r, y))
    contour.append(Point(x + width - r, y))
    add_arc(x + width - r, y + r, -pi / 2, 0.0)
    contour.append(Point(x + width, y + height - r))
    add_arc(x + width - r, y + height - r, 0.0, pi / 2)
    contour.append(Point(x + r, y + height))
    add_arc(x + r, y + height - r, pi / 2, pi)
    contour.append(Point(x, y + r))
    add_arc(x + r, y + r, pi, 3 * pi / 2)

    return contour


def stitch_segments_on_closed_polyline(
    polyline: list[Point],
    spacing: float,
    stitch_length: float,
    stitch_angle_deg: float,
    include_corners: bool,
) -> list[tuple[Point, Point]]:
    edges = [(polyline[i], polyline[(i + 1) % len(polyline)]) for i in range(len(polyline))]
    lengths = [distance(a, b) for a, b in edges]
    total = sum(lengths)
    if total <= 0:
        return []

    positions = positions_on_closed_length(total, spacing, include_corners)
    return map_stitch_positions_on_closed_edges(edges, lengths, positions, stitch_length, stitch_angle_deg)


def points_on_closed_polyline(
    polyline: list[Point],
    spacing: float,
    include_corners: bool,
) -> list[Point]:
    edges = [(polyline[i], polyline[(i + 1) % len(polyline)]) for i in range(len(polyline))]
    lengths = [distance(a, b) for a, b in edges]
    total = sum(lengths)
    if total <= 0:
        return []

    positions = positions_on_closed_length(total, spacing, include_corners)
    points: list[Point] = []
    prefixes = [0.0]
    for length in lengths:
        prefixes.append(prefixes[-1] + length)

    for pos in positions:
        for i, edge_len in enumerate(lengths):
            start = prefixes[i]
            end = prefixes[i + 1]
            if pos < end - 0.001 or i == len(lengths) - 1:
                local = max(0.0, min(edge_len, pos - start))
                a, b = edges[i]
                points.append(point_on_edge(a, b, local))
                break

    return deduplicate_points(points)


def positions_on_closed_length(
    total_length: float,
    spacing: float,
    include_corners: bool,
) -> list[float]:
    if total_length <= 0:
        return []

    if include_corners:
        count = max(1, int(total_length / spacing))
        step = total_length / count
        return [i * step for i in range(count)]

    count = max(1, int(total_length / spacing))

    step = total_length / count
    offset = step / 2
    return [offset + i * step for i in range(count)]


def map_stitch_positions_on_closed_edges(
    edges: list[tuple[Point, Point]],
    lengths: list[float],
    positions: list[float],
    stitch_length: float,
    stitch_angle_deg: float,
) -> list[tuple[Point, Point]]:
    prefixes = [0.0]
    for length in lengths:
        prefixes.append(prefixes[-1] + length)

    segments: list[tuple[Point, Point]] = []
    for pos in positions:
        for i, edge_len in enumerate(lengths):
            start = prefixes[i]
            end = prefixes[i + 1]
            if pos < end - 0.001 or i == len(lengths) - 1:
                local = max(0.0, min(edge_len, pos - start))
                a, b = edges[i]
                segments.append(segment_on_edge(a, b, local, stitch_length, stitch_angle_deg))
                break

    return segments


def quadratic_bezier(a: Point, c: Point, b: Point, t: float) -> Point:
    mt = 1 - t
    x = mt * mt * a.x + 2 * mt * t * c.x + t * t * b.x
    y = mt * mt * a.y + 2 * mt * t * c.y + t * t * b.y
    return Point(x, y)


def distance(a: Point, b: Point) -> float:
    return hypot(b.x - a.x, b.y - a.y)


def inset_triangle_vertices(p1: Point, p2: Point, p3: Point, inset: float) -> tuple[Point, Point, Point]:
    if inset <= 0:
        return p1, p2, p3

    points = [p1, p2, p3]
    area2 = signed_double_area(p1, p2, p3)
    if area2 == 0:
        centroid = Point((p1.x + p2.x + p3.x) / 3, (p1.y + p2.y + p3.y) / 3)
        return (
            move_towards(p1, centroid, inset),
            move_towards(p2, centroid, inset),
            move_towards(p3, centroid, inset),
        )

    # For CCW polygons, inward is the left normal. For CW, inward is right normal.
    ccw = area2 > 0
    offset_edges: list[tuple[Point, Point]] = []
    for i in range(3):
        a = points[i]
        b = points[(i + 1) % 3]
        nx, ny = inward_unit_normal(a, b, ccw)
        offset_edges.append((Point(a.x + nx * inset, a.y + ny * inset), Point(b.x + nx * inset, b.y + ny * inset)))

    # New vertex i is intersection of offset edge (i-1)->i and i->(i+1).
    new_points: list[Point] = []
    for i in range(3):
        e_prev = offset_edges[(i - 1) % 3]
        e_curr = offset_edges[i]
        inter = line_intersection(e_prev[0], e_prev[1], e_curr[0], e_curr[1])
        if inter is None:
            centroid = Point((p1.x + p2.x + p3.x) / 3, (p1.y + p2.y + p3.y) / 3)
            new_points.append(move_towards(points[i], centroid, inset))
        else:
            new_points.append(inter)

    return new_points[0], new_points[1], new_points[2]


def inward_unit_normal(a: Point, b: Point, ccw: bool) -> tuple[float, float]:
    dx = b.x - a.x
    dy = b.y - a.y
    length = hypot(dx, dy)
    if length == 0:
        return 0.0, 0.0
    if ccw:
        return -dy / length, dx / length
    return dy / length, -dx / length


def line_intersection(a1: Point, a2: Point, b1: Point, b2: Point) -> Point | None:
    x1, y1 = a1.x, a1.y
    x2, y2 = a2.x, a2.y
    x3, y3 = b1.x, b1.y
    x4, y4 = b2.x, b2.y

    den = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
    if abs(den) < 1e-9:
        return None

    det1 = x1 * y2 - y1 * x2
    det2 = x3 * y4 - y3 * x4
    px = (det1 * (x3 - x4) - (x1 - x2) * det2) / den
    py = (det1 * (y3 - y4) - (y1 - y2) * det2) / den
    return Point(px, py)


def signed_double_area(a: Point, b: Point, c: Point) -> float:
    return (b.x - a.x) * (c.y - a.y) - (b.y - a.y) * (c.x - a.x)


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
