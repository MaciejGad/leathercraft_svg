from __future__ import annotations

from dataclasses import dataclass
from math import asin, cos, hypot, pi, sin
from pathlib import Path
from typing import Iterable, Literal, Sequence

LayerName = Literal["cut", "stitch", "crease", "guide"]

SUPPORTED_DISTRIBUTIONS = ("fixed_spacing", "fit_evenly")
SUPPORTED_PATH_MODES = ("per_edge", "continuous", "continuous_rounded")

_REMOVED = object()  # Sentinel for parameters that have been removed from the public API


@dataclass(frozen=True)
class Point:
    x: float
    y: float


@dataclass
class StrokeStyle:
    color: str
    width: float = 0.2
    dasharray: str | None = None


@dataclass(frozen=True)
class DrawRawPath:
    d: str
    layer: str


@dataclass(frozen=True)
class DrawLineEntity:
    start: Point
    end: Point
    layer: str


@dataclass(frozen=True)
class DrawCircleEntity:
    center: Point
    radius: float
    layer: str


@dataclass(frozen=True)
class DrawShapeEntity:
    shape: "Shape"
    layer: str


DEFAULT_STYLES: dict[str, StrokeStyle] = {
    "cut": StrokeStyle("#ff0000", 0.2),
    "stitch": StrokeStyle("#0000ff", 0.2),
    "crease": StrokeStyle("#00aa00", 0.2, "3 2"),
    "guide": StrokeStyle("#777777", 0.2, "2 2"),
}


class SvgDocument:
    def __init__(self, width_mm: float, height_mm: float, styles: dict[str, StrokeStyle] | None = None):
        self.width_mm = width_mm
        self.height_mm = height_mm
        self.styles = styles or DEFAULT_STYLES
        self.elements: list[str] = []
        self._draw_entities: list[DrawRawPath | DrawLineEntity | DrawCircleEntity | DrawShapeEntity] = []

    def add_path(self, d: str, layer: LayerName = "cut") -> None:
        self.elements.append(f'<path {self._style_attributes(layer)} d="{d}" />')
        self._draw_entities.append(DrawRawPath(d=d, layer=layer))

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
        self._draw_entities.append(
            DrawLineEntity(start=Point(x1, y1), end=Point(x2, y2), layer=layer)
        )

    def add_circle(self, x: float, y: float, radius: float, layer: LayerName = "cut") -> None:
        self.elements.append(
            f'<circle {self._style_attributes(layer)} cx="{x:.3f}" cy="{y:.3f}" r="{radius:.3f}" />'
        )
        self._draw_entities.append(
            DrawCircleEntity(center=Point(x, y), radius=radius, layer=layer)
        )

    def add_shape(self, shape: "Shape", layer: LayerName = "cut") -> None:
        self.elements.append(f'<path {self._style_attributes(layer)} d="{shape.path_d()}" />')
        self._draw_entities.append(DrawShapeEntity(shape=shape, layer=layer))

    def add_holes(
        self,
        shape: "Shape",
        edges: Sequence[int] | Literal["all"] = "all",
        spacing: float = 5.0,
        hole_radius: float = 1.2,
        inset: float = 4.0,
        layer: LayerName = "cut",
        include_corners: object = _REMOVED,
        rounded_path: bool = False,
        distribution: str = "fixed_spacing",
        count: int | None = None,
        path_mode: str = "continuous",
        first_margin: float | None = None,
        last_margin: float | None = None,
    ) -> None:
        if include_corners is not _REMOVED:
            raise ValueError(
                "include_corners has been removed; use first_margin / last_margin instead"
            )
        validate_distribution(spacing, distribution, count)
        for p in shape.hole_points(
            edges=edges,
            spacing=spacing,
            inset=inset,
            rounded_path=rounded_path,
            distribution=distribution,
            count=count,
            path_mode=path_mode,
            first_margin=first_margin,
            last_margin=last_margin,
        ):
            self.add_circle(p.x, p.y, hole_radius, layer)

    def add_stitch_on_polyline(
        self,
        points: "list[tuple[float, float]]",
        spacing: float = 5.0,
        stitch_length: float = 2.0,
        stitch_angle_deg: float = 0.0,
        layer: LayerName = "stitch",
        stitch_thickness: float | None = None,
        distribution: str = "fixed_spacing",
        count: int | None = None,
    ) -> None:
        """Add stitch marks distributed along an open polyline."""
        validate_distribution(spacing, distribution, count)
        for p1, p2 in stitch_segments_on_open_polyline(
            points,
            spacing,
            stitch_length,
            stitch_angle_deg,
            distribution=distribution,
            count=count,
        ):
            self.add_line(p1.x, p1.y, p2.x, p2.y, layer=layer, stroke_width=stitch_thickness)

    def add_stitch_holes(
        self,
        shape: "Shape",
        edges: Sequence[int] | Literal["all"] = "all",
        spacing: float = 5.0,
        hole_radius: float = 1.2,
        inset: float = 4.0,
        layer: LayerName = "cut",
        include_corners: object = _REMOVED,
        rounded_path: bool = False,
        distribution: str = "fixed_spacing",
        count: int | None = None,
        path_mode: str = "continuous",
        first_margin: float | None = None,
        last_margin: float | None = None,
    ) -> None:
        self.add_holes(
            shape, edges, spacing, hole_radius, inset, layer,
            rounded_path=rounded_path, distribution=distribution, count=count,
            path_mode=path_mode, first_margin=first_margin, last_margin=last_margin,
        )

    def add_stitch_pattern(
        self,
        shape: "Shape",
        edges: Sequence[int] | Literal["all"] = "all",
        spacing: float = 5.0,
        stitch_length: float = 2.0,
        inset: float = 4.0,
        layer: LayerName = "stitch",
        include_corners: object = _REMOVED,
        stitch_thickness: float | None = None,
        stitch_angle_deg: float = 0.0,
        rounded_path: bool = False,
        distribution: str = "fixed_spacing",
        count: int | None = None,
        path_mode: str = "continuous",
        first_margin: float | None = None,
        last_margin: float | None = None,
    ) -> None:
        if include_corners is not _REMOVED:
            raise ValueError(
                "include_corners has been removed; use first_margin / last_margin instead"
            )
        validate_distribution(spacing, distribution, count)
        for p1, p2 in shape.stitch_segments(
            edges=edges,
            spacing=spacing,
            inset=inset,
            stitch_length=stitch_length,
            stitch_angle_deg=stitch_angle_deg,
            rounded_path=rounded_path,
            distribution=distribution,
            count=count,
            path_mode=path_mode,
            first_margin=first_margin,
            last_margin=last_margin,
        ):
            self.add_line(p1.x, p1.y, p2.x, p2.y, layer=layer, stroke_width=stitch_thickness)

    def save(self, path: str | Path) -> None:
        Path(path).write_text(self.to_svg(), encoding="utf-8")

    def save_dxf(
        self,
        path: str | Path,
        *,
        version: str = "R2010",
        units: str = "mm",
        preserve_curves: bool = True,
        curve_tolerance: float = 0.1,
        flip_y: bool = False,
    ) -> None:
        if version != "R2010":
            raise ValueError(f"unsupported DXF version '{version}'. Use: R2010")
        if units != "mm":
            raise ValueError(f"unsupported DXF units '{units}'. Use: mm")
        if curve_tolerance <= 0:
            raise ValueError("curve_tolerance must be greater than 0")

        try:
            import ezdxf
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "save_dxf requires the optional dependency 'ezdxf'. Install it with: pip install ezdxf"
            ) from exc

        dxf_doc = ezdxf.new(version)
        dxf_doc.units = ezdxf.units.MM
        dxf_doc.header["$INSUNITS"] = 4

        _create_dxf_layers(dxf_doc, self.styles)

        modelspace = dxf_doc.modelspace()
        context = DxfExportContext(
            document_height=self.height_mm,
            flip_y=flip_y,
            preserve_curves=preserve_curves,
            curve_tolerance=curve_tolerance,
        )

        for entity in self._draw_entities:
            _add_draw_entity_to_dxf(modelspace, entity, context)

        dxf_doc.saveas(str(path))

    def to_png_bytes(self, background_color: str = "white") -> bytes:
        import cairosvg

        return cairosvg.svg2png(
            bytestring=self.to_svg().encode("utf-8"),
            background_color=background_color,
        )

    def save_png(self, path: str | Path, background_color: str = "white") -> None:
        Path(path).write_bytes(self.to_png_bytes(background_color))

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
        include_corners: object = _REMOVED,
        rounded_path: bool = False,
        distribution: str = "fixed_spacing",
        count: int | None = None,
        path_mode: str = "continuous",
        first_margin: float | None = None,
        last_margin: float | None = None,
    ) -> list[Point]:
        raise NotImplementedError

    def stitch_segments(
        self,
        edges: Sequence[int] | Literal["all"] = "all",
        spacing: float = 5.0,
        inset: float = 4.0,
        include_corners: object = _REMOVED,
        stitch_length: float = 2.0,
        stitch_angle_deg: float = 0.0,
        rounded_path: bool = False,
        distribution: str = "fixed_spacing",
        count: int | None = None,
        path_mode: str = "continuous",
        first_margin: float | None = None,
        last_margin: float | None = None,
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

    def _edge_defs(self, inset: float) -> list[tuple[Point, Point]]:
        x = self.x + inset
        y = self.y + inset
        w = self.width - 2 * inset
        h = self.height - 2 * inset
        return [
            (Point(x, y), Point(x + w, y)),
            (Point(x + w, y), Point(x + w, y + h)),
            (Point(x + w, y + h), Point(x, y + h)),
            (Point(x, y + h), Point(x, y)),
        ]

    @staticmethod
    def _chain_waypoints(
        edge_defs: list[tuple[Point, Point]], chain: list[int]
    ) -> list[Point]:
        return [edge_defs[chain[0]][0]] + [edge_defs[i][1] for i in chain]

    def hole_points(
        self,
        edges="all",
        spacing=5.0,
        inset=4.0,
        include_corners=_REMOVED,
        rounded_path=False,
        distribution="fixed_spacing",
        count=None,
        path_mode="continuous",
        first_margin=None,
        last_margin=None,
    ) -> list[Point]:
        if include_corners is not _REMOVED:
            raise ValueError(
                "include_corners has been removed; use first_margin / last_margin instead"
            )
        validate_distribution(spacing, distribution, count)
        edge_defs = self._edge_defs(inset)
        if edge_defs[0][0].x >= edge_defs[0][1].x or edge_defs[1][0].y >= edge_defs[1][1].y:
            return []

        if edges == "all":
            return points_on_closed_edges(edge_defs, spacing, False, distribution, count)

        selected = list(edges)
        if path_mode == "per_edge":
            result: list[Point] = []
            for ei in selected:
                p1, p2 = edge_defs[ei]
                length = distance(p1, p2)
                if length == 0:
                    continue
                if distribution == "fixed_spacing":
                    positions = positions_on_side_center(length, spacing, False)
                    positions = adjust_positions_near_corners(positions, length, False, spacing)
                else:
                    positions = distribute_distances(length, spacing, distribution=distribution)
                for pos in positions:
                    result.append(point_on_edge(p1, p2, pos))
            return deduplicate_points(result)

        chains = _connected_chains(len(edge_defs), selected)
        result = []
        for chain in chains:
            waypoints = self._chain_waypoints(edge_defs, chain)
            result.extend(
                points_on_polyline_chain(
                    waypoints, spacing, distribution,
                    first_margin=first_margin, last_margin=last_margin,
                )
            )
        return deduplicate_points(result)

    def stitch_segments(
        self,
        edges="all",
        spacing=5.0,
        inset=4.0,
        include_corners=_REMOVED,
        stitch_length=2.0,
        stitch_angle_deg=0.0,
        rounded_path=False,
        distribution="fixed_spacing",
        count=None,
        path_mode="continuous",
        first_margin=None,
        last_margin=None,
    ) -> list[tuple[Point, Point]]:
        if include_corners is not _REMOVED:
            raise ValueError(
                "include_corners has been removed; use first_margin / last_margin instead"
            )
        validate_distribution(spacing, distribution, count)
        edge_defs = self._edge_defs(inset)
        if edge_defs[0][0].x >= edge_defs[0][1].x or edge_defs[1][0].y >= edge_defs[1][1].y:
            return []

        if edges == "all":
            return segments_on_closed_edges(
                edge_defs, spacing, stitch_length, False, stitch_angle_deg, distribution, count
            )

        selected = list(edges)
        if path_mode == "per_edge":
            result: list[tuple[Point, Point]] = []
            for ei in selected:
                p1, p2 = edge_defs[ei]
                length = distance(p1, p2)
                if length == 0:
                    continue
                if distribution == "fixed_spacing":
                    positions = positions_on_side_center(length, spacing, False)
                    adjusted = adjust_stitch_positions_and_lengths(
                        positions, length, False, spacing, stitch_length
                    )
                else:
                    positions = distribute_distances(length, spacing, distribution=distribution)
                    validate_stitch_length(stitch_length, fitted_spacing(length, spacing))
                    adjusted = [(p, stitch_length) for p in positions]
                for pos, slen in adjusted:
                    result.append(segment_on_edge(p1, p2, pos, slen, stitch_angle_deg))
            return result

        chains = _connected_chains(len(edge_defs), selected)
        result = []
        for chain in chains:
            waypoints = self._chain_waypoints(edge_defs, chain)
            result.extend(
                segments_on_polyline_chain(
                    waypoints, spacing, stitch_length, stitch_angle_deg, distribution,
                    first_margin=first_margin, last_margin=last_margin,
                )
            )
        return result


@dataclass
class RoundedRectangle(Rectangle):
    """
    Rectangle with rounded corners.

    A single uniform ``radius`` applies to all four corners. Each corner can
    be overridden individually with ``radius_tl`` / ``radius_tr`` /
    ``radius_br`` / ``radius_bl`` (top-left, top-right, bottom-right,
    bottom-left). A per-corner value of 0 produces a sharp corner.
    """

    radius: float = 5.0
    radius_tl: float | None = None
    radius_tr: float | None = None
    radius_br: float | None = None
    radius_bl: float | None = None

    def corner_radii(self) -> tuple[float, float, float, float]:
        """Effective (tl, tr, br, bl) radii, clamped so adjacent corners never overlap."""
        w, h = self.width, self.height
        tl = self.radius if self.radius_tl is None else self.radius_tl
        tr = self.radius if self.radius_tr is None else self.radius_tr
        br = self.radius if self.radius_br is None else self.radius_br
        bl = self.radius if self.radius_bl is None else self.radius_bl
        radii = [max(0.0, r) for r in (tl, tr, br, bl)]
        # Scale all radii down if two corners on a shared edge would overlap
        scale = 1.0
        for pair_sum, edge_len in (
            (radii[0] + radii[1], w),  # top
            (radii[2] + radii[3], w),  # bottom
            (radii[1] + radii[2], h),  # right
            (radii[3] + radii[0], h),  # left
        ):
            if pair_sum > edge_len > 0:
                scale = min(scale, edge_len / pair_sum)
        return tuple(r * scale for r in radii)

    def path_d(self) -> str:
        x, y, w, h = self.x, self.y, self.width, self.height
        tl, tr, br, bl = self.corner_radii()
        parts = [f"M {x+tl:.3f} {y:.3f}", f"L {x+w-tr:.3f} {y:.3f}"]
        if tr > 0:
            parts.append(f"Q {x+w:.3f} {y:.3f} {x+w:.3f} {y+tr:.3f}")
        parts.append(f"L {x+w:.3f} {y+h-br:.3f}")
        if br > 0:
            parts.append(f"Q {x+w:.3f} {y+h:.3f} {x+w-br:.3f} {y+h:.3f}")
        parts.append(f"L {x+bl:.3f} {y+h:.3f}")
        if bl > 0:
            parts.append(f"Q {x:.3f} {y+h:.3f} {x:.3f} {y+h-bl:.3f}")
        parts.append(f"L {x:.3f} {y+tl:.3f}")
        if tl > 0:
            parts.append(f"Q {x:.3f} {y:.3f} {x+tl:.3f} {y:.3f}")
        return " ".join(parts) + " Z"

    def _inner_params(self, inset: float) -> tuple[float, float, float, float, tuple]:
        x = self.x + inset
        y = self.y + inset
        w = self.width - 2 * inset
        h = self.height - 2 * inset
        radii = tuple(max(0.0, min(r - inset, w / 2, h / 2)) for r in self.corner_radii())
        return x, y, w, h, radii

    def hole_points(
        self,
        edges="all",
        spacing=5.0,
        inset=4.0,
        include_corners=_REMOVED,
        rounded_path=False,
        distribution="fixed_spacing",
        count=None,
        path_mode="continuous",
        first_margin=None,
        last_margin=None,
    ) -> list[Point]:
        if include_corners is not _REMOVED:
            raise ValueError(
                "include_corners has been removed; use first_margin / last_margin instead"
            )
        validate_distribution(spacing, distribution, count)
        all_rectangle_edges = edges == "all" or sorted(set(edges)) == [0, 1, 2, 3]
        x, y, w, h, radii = self._inner_params(inset)
        if w <= 0 or h <= 0:
            return []

        if all_rectangle_edges:
            contour = rounded_rectangle_contour(x, y, w, h, 0.0, radii=radii)
            if len(contour) < 2:
                return []
            return points_on_closed_polyline(contour, spacing=spacing, include_corners=False,
                                             distribution=distribution, count=count)

        if path_mode != "continuous_rounded":
            return super().hole_points(
                edges=edges, spacing=spacing, inset=inset,
                distribution=distribution, count=count,
                path_mode=path_mode, first_margin=first_margin, last_margin=last_margin,
            )

        selected = list(edges)
        chains = _connected_chains(4, selected)
        result: list[Point] = []
        for chain in chains:
            waypoints = _rounded_rect_chain_waypoints(x, y, w, h, radii, chain)
            result.extend(
                points_on_polyline_chain(
                    waypoints, spacing, distribution,
                    first_margin=first_margin, last_margin=last_margin,
                )
            )
        return result

    def stitch_segments(
        self,
        edges="all",
        spacing=5.0,
        inset=4.0,
        include_corners=_REMOVED,
        stitch_length=2.0,
        stitch_angle_deg=0.0,
        rounded_path=False,
        distribution="fixed_spacing",
        count=None,
        path_mode="continuous",
        first_margin=None,
        last_margin=None,
    ) -> list[tuple[Point, Point]]:
        if include_corners is not _REMOVED:
            raise ValueError(
                "include_corners has been removed; use first_margin / last_margin instead"
            )
        validate_distribution(spacing, distribution, count)
        all_rectangle_edges = edges == "all" or sorted(set(edges)) == [0, 1, 2, 3]
        x, y, w, h, radii = self._inner_params(inset)
        if w <= 0 or h <= 0:
            return []

        if all_rectangle_edges:
            contour = rounded_rectangle_contour(x, y, w, h, 0.0, radii=radii)
            if len(contour) < 2:
                return []
            return stitch_segments_on_closed_polyline(
                contour,
                spacing=spacing,
                stitch_length=stitch_length,
                stitch_angle_deg=stitch_angle_deg,
                include_corners=False,
                distribution=distribution,
                count=count,
            )

        if path_mode != "continuous_rounded":
            return super().stitch_segments(
                edges=edges, spacing=spacing, inset=inset,
                stitch_length=stitch_length, stitch_angle_deg=stitch_angle_deg,
                distribution=distribution, count=count,
                path_mode=path_mode, first_margin=first_margin, last_margin=last_margin,
            )

        # continuous_rounded: follow corner arcs for partial edge chains
        selected = list(edges)
        chains = _connected_chains(4, selected)
        result: list[tuple[Point, Point]] = []
        for chain in chains:
            waypoints = _rounded_rect_chain_waypoints(x, y, w, h, radii, chain)
            result.extend(
                segments_on_polyline_chain(
                    waypoints, spacing, stitch_length, stitch_angle_deg, distribution,
                    first_margin=first_margin, last_margin=last_margin,
                )
            )
        return result


@dataclass
class Stadium(Rectangle):
    """
    Capsule / oblong: a rectangle whose two short ends are replaced by
    semicircles.  The cap radius is always min(width, height) / 2, so the
    orientation follows from the bounding box (wide box -> caps on the left
    and right, tall box -> caps on the top and bottom).
    """

    @property
    def radius(self) -> float:
        return min(self.width, self.height) / 2

    def path_d(self) -> str:
        x, y, w, h = self.x, self.y, self.width, self.height
        r = self.radius
        return (
            f"M {x+r:.3f} {y:.3f} "
            f"L {x+w-r:.3f} {y:.3f} "
            f"A {r:.3f} {r:.3f} 0 0 1 {x+w:.3f} {y+r:.3f} "
            f"L {x+w:.3f} {y+h-r:.3f} "
            f"A {r:.3f} {r:.3f} 0 0 1 {x+w-r:.3f} {y+h:.3f} "
            f"L {x+r:.3f} {y+h:.3f} "
            f"A {r:.3f} {r:.3f} 0 0 1 {x:.3f} {y+h-r:.3f} "
            f"L {x:.3f} {y+r:.3f} "
            f"A {r:.3f} {r:.3f} 0 0 1 {x+r:.3f} {y:.3f} Z"
        )

    def _inner_contour(self, inset: float) -> list[Point]:
        x = self.x + inset
        y = self.y + inset
        w = self.width - 2 * inset
        h = self.height - 2 * inset
        if w <= 0 or h <= 0:
            return []
        r = max(0.0, min(self.radius - inset, w / 2, h / 2))
        return rounded_rectangle_contour(x, y, w, h, r)

    def hole_points(
        self,
        edges="all",
        spacing=5.0,
        inset=4.0,
        include_corners=_REMOVED,
        rounded_path=False,
        distribution="fixed_spacing",
        count=None,
        path_mode="continuous",
        first_margin=None,
        last_margin=None,
    ) -> list[Point]:
        if include_corners is not _REMOVED:
            raise ValueError(
                "include_corners has been removed; use first_margin / last_margin instead"
            )
        validate_distribution(spacing, distribution, count)
        all_edges = edges == "all" or sorted(set(edges)) == [0, 1, 2, 3]
        if not all_edges:
            return super().hole_points(
                edges=edges, spacing=spacing, inset=inset,
                distribution=distribution, count=count,
                path_mode=path_mode, first_margin=first_margin, last_margin=last_margin,
            )
        contour = self._inner_contour(inset)
        if len(contour) < 2:
            return []
        return points_on_closed_polyline(
            contour, spacing=spacing, include_corners=False,
            distribution=distribution, count=count,
        )

    def stitch_segments(
        self,
        edges="all",
        spacing=5.0,
        inset=4.0,
        include_corners=_REMOVED,
        stitch_length=2.0,
        stitch_angle_deg=0.0,
        rounded_path=False,
        distribution="fixed_spacing",
        count=None,
        path_mode="continuous",
        first_margin=None,
        last_margin=None,
    ) -> list[tuple[Point, Point]]:
        if include_corners is not _REMOVED:
            raise ValueError(
                "include_corners has been removed; use first_margin / last_margin instead"
            )
        validate_distribution(spacing, distribution, count)
        all_edges = edges == "all" or sorted(set(edges)) == [0, 1, 2, 3]
        if not all_edges:
            return super().stitch_segments(
                edges=edges, spacing=spacing, inset=inset,
                stitch_length=stitch_length, stitch_angle_deg=stitch_angle_deg,
                distribution=distribution, count=count,
                path_mode=path_mode, first_margin=first_margin, last_margin=last_margin,
            )
        contour = self._inner_contour(inset)
        if len(contour) < 2:
            return []
        return stitch_segments_on_closed_polyline(
            contour,
            spacing=spacing,
            stitch_length=stitch_length,
            stitch_angle_deg=stitch_angle_deg,
            include_corners=False,
            distribution=distribution,
            count=count,
        )


@dataclass
class Circle(Shape):
    cx: float
    cy: float
    radius: float

    def path_d(self) -> str:
        x, y, r = self.cx, self.cy, self.radius
        return f"M {x-r:.3f} {y:.3f} A {r:.3f} {r:.3f} 0 1 0 {x+r:.3f} {y:.3f} A {r:.3f} {r:.3f} 0 1 0 {x-r:.3f} {y:.3f} Z"

    def hole_points(
        self,
        edges="all",
        spacing=5.0,
        inset=4.0,
        include_corners=_REMOVED,
        rounded_path=False,
        distribution="fixed_spacing",
        count=None,
        path_mode="continuous",
        first_margin=None,
        last_margin=None,
    ) -> list[Point]:
        if include_corners is not _REMOVED:
            raise ValueError(
                "include_corners has been removed; use first_margin / last_margin instead"
            )
        validate_distribution(spacing, distribution, count)
        r = max(self.radius - inset, 0.1)
        if distribution == "fixed_spacing":
            point_count = max(3, int((2 * pi * r) // spacing))
        else:
            point_count = max(1, round((2 * pi * r) / spacing))
        return [
            Point(
                self.cx + r * cos(2 * pi * i / point_count),
                self.cy + r * sin(2 * pi * i / point_count),
            )
            for i in range(point_count)
        ]

    def stitch_segments(
        self,
        edges="all",
        spacing=5.0,
        inset=4.0,
        include_corners=_REMOVED,
        stitch_length=2.0,
        stitch_angle_deg=0.0,
        rounded_path=False,
        distribution="fixed_spacing",
        count=None,
        path_mode="continuous",
        first_margin=None,
        last_margin=None,
    ) -> list[tuple[Point, Point]]:
        if include_corners is not _REMOVED:
            raise ValueError(
                "include_corners has been removed; use first_margin / last_margin instead"
            )
        validate_distribution(spacing, distribution, count)
        r = max(self.radius - inset, 0.1)
        circumference = 2 * pi * r
        if distribution == "fixed_spacing":
            point_count = max(3, int(circumference // spacing))
        else:
            point_count = max(1, round(circumference / spacing))
            validate_stitch_length(stitch_length, circumference / point_count)
        half = stitch_length / 2
        angle_offset = stitch_angle_deg * pi / 180
        segments = []
        for i in range(point_count):
            angle = 2 * pi * i / point_count
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
class Ellipse(Shape):
    """
    Ellipse (oval) defined by a centre point and two independent radii.
    When rx == ry it is identical to a Circle.
    """

    cx: float
    cy: float
    rx: float
    ry: float

    def path_d(self) -> str:
        x, y, rx, ry = self.cx, self.cy, self.rx, self.ry
        return (
            f"M {x-rx:.3f} {y:.3f} "
            f"A {rx:.3f} {ry:.3f} 0 1 0 {x+rx:.3f} {y:.3f} "
            f"A {rx:.3f} {ry:.3f} 0 1 0 {x-rx:.3f} {y:.3f} Z"
        )

    def _inner_contour(self, inset: float, steps: int = 96) -> list[Point]:
        rx = self.rx - inset
        ry = self.ry - inset
        if rx <= 0 or ry <= 0:
            return []
        return [
            Point(self.cx + rx * cos(2 * pi * i / steps), self.cy + ry * sin(2 * pi * i / steps))
            for i in range(steps)
        ]

    def hole_points(
        self,
        edges="all",
        spacing=5.0,
        inset=4.0,
        include_corners=_REMOVED,
        rounded_path=False,
        distribution="fixed_spacing",
        count=None,
        path_mode="continuous",
        first_margin=None,
        last_margin=None,
    ) -> list[Point]:
        if include_corners is not _REMOVED:
            raise ValueError(
                "include_corners has been removed; use first_margin / last_margin instead"
            )
        validate_distribution(spacing, distribution, count)
        contour = self._inner_contour(inset)
        if len(contour) < 2:
            return []
        return points_on_closed_polyline(
            contour, spacing=spacing, include_corners=False,
            distribution=distribution, count=count,
        )

    def stitch_segments(
        self,
        edges="all",
        spacing=5.0,
        inset=4.0,
        include_corners=_REMOVED,
        stitch_length=2.0,
        stitch_angle_deg=0.0,
        rounded_path=False,
        distribution="fixed_spacing",
        count=None,
        path_mode="continuous",
        first_margin=None,
        last_margin=None,
    ) -> list[tuple[Point, Point]]:
        if include_corners is not _REMOVED:
            raise ValueError(
                "include_corners has been removed; use first_margin / last_margin instead"
            )
        validate_distribution(spacing, distribution, count)
        contour = self._inner_contour(inset)
        if len(contour) < 2:
            return []
        return stitch_segments_on_closed_polyline(
            contour, spacing=spacing, stitch_length=stitch_length,
            stitch_angle_deg=stitch_angle_deg, include_corners=False,
            distribution=distribution, count=count,
        )


@dataclass
class Arc(Shape):
    """
    Circular sector (pie wedge) or ring segment (annulus slice).

    Angles are in degrees: 0 = right (3 o'clock), increasing clockwise on
    screen (SVG Y axis points down). The shape spans from ``start_angle`` to
    ``end_angle``; if ``end_angle <= start_angle`` a full turn is added, so
    e.g. ``start=300, end=60`` gives a 120-degree wedge across 3 o'clock.

    With ``inner_radius == 0`` the shape is a wedge from the centre point.
    With ``inner_radius > 0`` the centre is cut out, producing a ring segment.
    """

    cx: float
    cy: float
    radius: float
    start_angle: float
    end_angle: float
    inner_radius: float = 0.0

    def _span_rad(self) -> tuple[float, float]:
        start = self.start_angle * pi / 180
        span = (self.end_angle - self.start_angle) % 360 * pi / 180
        if span == 0:
            span = 2 * pi
        return start, span

    def path_d(self) -> str:
        start, span = self._span_rad()
        end = start + span
        large = 1 if span > pi else 0
        r = self.radius
        x0 = self.cx + r * cos(start)
        y0 = self.cy + r * sin(start)
        x1 = self.cx + r * cos(end)
        y1 = self.cy + r * sin(end)
        if self.inner_radius <= 0:
            return (
                f"M {self.cx:.3f} {self.cy:.3f} "
                f"L {x0:.3f} {y0:.3f} "
                f"A {r:.3f} {r:.3f} 0 {large} 1 {x1:.3f} {y1:.3f} Z"
            )
        ri = self.inner_radius
        xi0 = self.cx + ri * cos(end)
        yi0 = self.cy + ri * sin(end)
        xi1 = self.cx + ri * cos(start)
        yi1 = self.cy + ri * sin(start)
        return (
            f"M {x0:.3f} {y0:.3f} "
            f"A {r:.3f} {r:.3f} 0 {large} 1 {x1:.3f} {y1:.3f} "
            f"L {xi0:.3f} {yi0:.3f} "
            f"A {ri:.3f} {ri:.3f} 0 {large} 0 {xi1:.3f} {yi1:.3f} Z"
        )

    def _contour(self, arc_steps: int = 48) -> list[tuple[float, float]]:
        start, span = self._span_rad()
        steps = max(8, int(arc_steps * span / (2 * pi)) * 4)
        outer = [
            (self.cx + self.radius * cos(start + span * i / steps),
             self.cy + self.radius * sin(start + span * i / steps))
            for i in range(steps + 1)
        ]
        if self.inner_radius <= 0:
            return [(self.cx, self.cy)] + outer
        inner = [
            (self.cx + self.inner_radius * cos(start + span * i / steps),
             self.cy + self.inner_radius * sin(start + span * i / steps))
            for i in range(steps, -1, -1)
        ]
        return outer + inner

    def _inset_contour(self, inset: float, arc_steps: int = 48) -> list[tuple[float, float]]:
        """
        Exact inward inset of the arc contour.

        Built analytically (inset radii + angular trim of asin(inset / r))
        rather than via generic polygon offsetting, so every point keeps the
        full ``inset`` distance from the straight cap edges as well as from
        the arcs — a naive edge offset produces corner spikes that dip back
        towards the cut line.
        """
        if inset <= 0:
            return self._contour(arc_steps)

        start, span = self._span_rad()
        ro = self.radius - inset
        if ro <= 0 or inset / ro > 1:
            return []
        d_out = asin(inset / ro)
        a0 = start + d_out
        a1 = start + span - d_out
        if a1 <= a0:
            return []

        steps = max(8, int(arc_steps * (a1 - a0) / (2 * pi)) * 4)
        outer = [
            (self.cx + ro * cos(a0 + (a1 - a0) * i / steps),
             self.cy + ro * sin(a0 + (a1 - a0) * i / steps))
            for i in range(steps + 1)
        ]

        if self.inner_radius > 0:
            ri = self.inner_radius + inset
            if ri >= ro or inset / ri > 1:
                return []
            d_in = asin(inset / ri)
            b0 = start + d_in
            b1 = start + span - d_in
            if b1 <= b0:
                return []
            inner = [
                (self.cx + ri * cos(b1 + (b0 - b1) * i / steps),
                 self.cy + ri * sin(b1 + (b0 - b1) * i / steps))
                for i in range(steps + 1)
            ]
            return outer + inner

        # Wedge: close the contour near the centre.
        end = start + span
        # Inward normals of the two radial cap edges
        ns = (-sin(start), cos(start))
        ne = (sin(end), -cos(end))
        if span < pi - 1e-9:
            # Caps converge: corner = intersection of the two inset cap lines
            p1 = Point(self.cx + inset * ns[0], self.cy + inset * ns[1])
            p2 = Point(p1.x + cos(start), p1.y + sin(start))
            p3 = Point(self.cx + inset * ne[0], self.cy + inset * ne[1])
            p4 = Point(p3.x + cos(end), p3.y + sin(end))
            corner = line_intersection(p1, p2, p3, p4)
            if corner is None:
                return []
            return [(corner.x, corner.y)] + outer
        if abs(span - pi) <= 1e-9:
            # Caps are parallel (half disc): the chord between the arc
            # endpoints already lies on the inset line.
            return outer
        # Reflex wedge (span > 180°): the centre corner insets to an arc of
        # radius ``inset`` around the centre, between the two cap normals.
        phi1 = end - pi / 2
        phi0 = start + pi / 2
        centre_steps = max(4, int(8 * (phi1 - phi0) / (2 * pi)) * 4)
        centre_arc = [
            (self.cx + inset * cos(phi1 + (phi0 - phi1) * i / centre_steps),
             self.cy + inset * sin(phi1 + (phi0 - phi1) * i / centre_steps))
            for i in range(centre_steps + 1)
        ]
        return outer + centre_arc

    def hole_points(
        self,
        edges="all",
        spacing=5.0,
        inset=4.0,
        include_corners=_REMOVED,
        rounded_path=False,
        distribution="fixed_spacing",
        count=None,
        path_mode="continuous",
        first_margin=None,
        last_margin=None,
    ) -> list[Point]:
        if include_corners is not _REMOVED:
            raise ValueError(
                "include_corners has been removed; use first_margin / last_margin instead"
            )
        validate_distribution(spacing, distribution, count)
        pts = self._inset_contour(inset)
        if len(pts) < 3:
            return []
        polyline = [Point(x, y) for x, y in pts]
        return points_on_closed_polyline(
            polyline, spacing=spacing, include_corners=False,
            distribution=distribution, count=count,
        )

    def stitch_segments(
        self,
        edges="all",
        spacing=5.0,
        inset=4.0,
        include_corners=_REMOVED,
        stitch_length=2.0,
        stitch_angle_deg=0.0,
        rounded_path=False,
        distribution="fixed_spacing",
        count=None,
        path_mode="continuous",
        first_margin=None,
        last_margin=None,
    ) -> list[tuple[Point, Point]]:
        if include_corners is not _REMOVED:
            raise ValueError(
                "include_corners has been removed; use first_margin / last_margin instead"
            )
        validate_distribution(spacing, distribution, count)
        pts = self._inset_contour(inset)
        if len(pts) < 3:
            return []
        polyline = [Point(x, y) for x, y in pts]
        return stitch_segments_on_closed_polyline(
            polyline, spacing=spacing, stitch_length=stitch_length,
            stitch_angle_deg=stitch_angle_deg, include_corners=False,
            distribution=distribution, count=count,
        )


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

    def hole_points(
        self,
        edges="all",
        spacing=5.0,
        inset=4.0,
        include_corners=_REMOVED,
        rounded_path=False,
        distribution="fixed_spacing",
        count=None,
        path_mode="continuous",
        first_margin=None,
        last_margin=None,
    ) -> list[Point]:
        if include_corners is not _REMOVED:
            raise ValueError(
                "include_corners has been removed; use first_margin / last_margin instead"
            )
        validate_distribution(spacing, distribution, count)
        p1, p2, p3 = inset_triangle_vertices(self.p1, self.p2, self.p3, inset)
        edge_defs = [(p1, p2), (p2, p3), (p3, p1)]
        if edges == "all":
            return points_on_closed_edges(edge_defs, spacing, False, distribution, count)
        return points_on_selected_edges(
            edge_defs, edges, spacing, distribution=distribution, count=count,
            path_mode=path_mode, first_margin=first_margin, last_margin=last_margin,
        )

    def stitch_segments(
        self,
        edges="all",
        spacing=5.0,
        inset=4.0,
        include_corners=_REMOVED,
        stitch_length=2.0,
        stitch_angle_deg=0.0,
        rounded_path=False,
        distribution="fixed_spacing",
        count=None,
        path_mode="continuous",
        first_margin=None,
        last_margin=None,
    ) -> list[tuple[Point, Point]]:
        if include_corners is not _REMOVED:
            raise ValueError(
                "include_corners has been removed; use first_margin / last_margin instead"
            )
        validate_distribution(spacing, distribution, count)
        p1, p2, p3 = inset_triangle_vertices(self.p1, self.p2, self.p3, inset)
        edge_defs = [(p1, p2), (p2, p3), (p3, p1)]
        if edges == "all":
            return segments_on_closed_edges(
                edge_defs, spacing, stitch_length, False, stitch_angle_deg, distribution, count
            )
        return segments_on_selected_edges(
            edge_defs, edges, spacing, stitch_length, stitch_angle_deg=stitch_angle_deg,
            distribution=distribution, count=count,
            path_mode=path_mode, first_margin=first_margin, last_margin=last_margin,
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
        include_corners=_REMOVED,
        rounded_path=False,
        distribution="fixed_spacing",
        count=None,
        path_mode="continuous",
        first_margin=None,
        last_margin=None,
    ) -> list[Point]:
        if include_corners is not _REMOVED:
            raise ValueError(
                "include_corners has been removed; use first_margin / last_margin instead"
            )
        validate_distribution(spacing, distribution, count)
        all_triangle_edges = edges == "all" or sorted(set(edges)) == [0, 1, 2]
        if path_mode != "continuous_rounded" or not all_triangle_edges:
            return super().hole_points(
                edges=edges, spacing=spacing, inset=inset,
                distribution=distribution, count=count,
                path_mode=path_mode, first_margin=first_margin, last_margin=last_margin,
            )

        p1, p2, p3 = inset_triangle_vertices(self.p1, self.p2, self.p3, inset)
        effective_radius = max(0.0, self.radius - inset)
        contour = rounded_triangle_contour([p1, p2, p3], effective_radius)
        if len(contour) < 2:
            return []
        return points_on_closed_polyline(
            contour, spacing=spacing, include_corners=False,
            distribution=distribution, count=count,
        )

    def stitch_segments(
        self,
        edges="all",
        spacing=5.0,
        inset=4.0,
        include_corners=_REMOVED,
        stitch_length=2.0,
        stitch_angle_deg=0.0,
        rounded_path=False,
        distribution="fixed_spacing",
        count=None,
        path_mode="continuous",
        first_margin=None,
        last_margin=None,
    ) -> list[tuple[Point, Point]]:
        if include_corners is not _REMOVED:
            raise ValueError(
                "include_corners has been removed; use first_margin / last_margin instead"
            )
        validate_distribution(spacing, distribution, count)
        all_triangle_edges = edges == "all" or sorted(set(edges)) == [0, 1, 2]
        if path_mode != "continuous_rounded" or not all_triangle_edges:
            return super().stitch_segments(
                edges=edges, spacing=spacing, inset=inset,
                stitch_length=stitch_length, stitch_angle_deg=stitch_angle_deg,
                distribution=distribution, count=count,
                path_mode=path_mode, first_margin=first_margin, last_margin=last_margin,
            )

        p1, p2, p3 = inset_triangle_vertices(self.p1, self.p2, self.p3, inset)
        effective_radius = max(0.0, self.radius - inset)
        contour = rounded_triangle_contour([p1, p2, p3], effective_radius)
        if len(contour) < 2:
            return []
        return stitch_segments_on_closed_polyline(
            contour, spacing=spacing, stitch_length=stitch_length,
            stitch_angle_deg=stitch_angle_deg, include_corners=False,
            distribution=distribution, count=count,
        )


@dataclass
class Polygon(Shape):
    """
    Shape defined by an explicit list of (x, y) points.

    Use ``Polygon.from_mirror`` to build a symmetric shape from one half
    of the outline — the right side is generated automatically as a
    horizontal mirror around ``center_x``.

    Parameters:
        points  - ordered list of (x, y) tuples forming a closed polygon.
        smooth  - if True, the outline is drawn with quadratic Bézier curves
                  instead of straight lines.
    """

    points: list[tuple[float, float]]
    smooth: bool = False

    @classmethod
    def from_mirror(
        cls,
        half_points: "list[tuple[float, float]]",
        center_x: float,
        smooth: bool = False,
    ) -> "Polygon":
        """
        Build a symmetric closed polygon from one half.

        ``half_points`` should start and end on the mirror axis (x == center_x).
        The mirrored right side is appended in reverse, so the outline forms
        one continuous closed loop.
        """
        mirrored = [(2 * center_x - x, y) for x, y in half_points]
        full = list(half_points) + list(reversed(mirrored[1:-1]))
        return cls(points=full, smooth=smooth)

    def path_d(self) -> str:
        if self.smooth:
            return _smooth_path_d(self.points)
        return _straight_path_d(self.points)

    def hole_points(
        self,
        edges: "Sequence[int] | Literal['all']" = "all",
        spacing: float = 5.0,
        inset: float = 4.0,
        include_corners: object = _REMOVED,
        rounded_path: bool = False,
        distribution: str = "fixed_spacing",
        count: int | None = None,
        path_mode: str = "continuous",
        first_margin: float | None = None,
        last_margin: float | None = None,
    ) -> list[Point]:
        if include_corners is not _REMOVED:
            raise ValueError(
                "include_corners has been removed; use first_margin / last_margin instead"
            )
        validate_distribution(spacing, distribution, count)
        pts = _offset_closed_polygon(self.points, inset) if inset > 0 else self.points
        polyline = [Point(x, y) for x, y in pts]
        return points_on_closed_polyline(
            polyline, spacing=spacing, include_corners=False,
            distribution=distribution, count=count,
        )

    def stitch_segments(
        self,
        edges: "Sequence[int] | Literal['all']" = "all",
        spacing: float = 5.0,
        inset: float = 4.0,
        include_corners: object = _REMOVED,
        stitch_length: float = 2.0,
        stitch_angle_deg: float = 0.0,
        rounded_path: bool = False,
        distribution: str = "fixed_spacing",
        count: int | None = None,
        path_mode: str = "continuous",
        first_margin: float | None = None,
        last_margin: float | None = None,
    ) -> "list[tuple[Point, Point]]":
        if include_corners is not _REMOVED:
            raise ValueError(
                "include_corners has been removed; use first_margin / last_margin instead"
            )
        validate_distribution(spacing, distribution, count)
        pts = _offset_closed_polygon(self.points, inset) if inset > 0 else self.points
        polyline = [Point(x, y) for x, y in pts]
        return stitch_segments_on_closed_polyline(
            polyline, spacing=spacing, stitch_length=stitch_length,
            stitch_angle_deg=stitch_angle_deg, include_corners=False,
            distribution=distribution, count=count,
        )


@dataclass
class RegularPolygon(Shape):
    """
    Regular polygon defined by centre point, circumscribed radius, and side count.

    ``rotation_deg`` rotates the whole polygon; the default ``-90`` puts the
    first vertex at the top.
    """

    cx: float
    cy: float
    radius: float
    sides: int
    rotation_deg: float = -90.0

    def vertices(self) -> list[tuple[float, float]]:
        if self.sides < 3 or self.radius <= 0:
            return []
        offset = self.rotation_deg * pi / 180
        return [
            (
                self.cx + self.radius * cos(2 * pi * i / self.sides + offset),
                self.cy + self.radius * sin(2 * pi * i / self.sides + offset),
            )
            for i in range(self.sides)
        ]

    def _inner_vertices(self, inset: float) -> list[tuple[float, float]]:
        if self.sides < 3:
            return []
        if inset <= 0:
            return self.vertices()
        apothem = self.radius * cos(pi / self.sides)
        inner_apothem = apothem - inset
        if inner_apothem <= 0:
            return []
        inner_radius = inner_apothem / cos(pi / self.sides)
        offset = self.rotation_deg * pi / 180
        return [
            (
                self.cx + inner_radius * cos(2 * pi * i / self.sides + offset),
                self.cy + inner_radius * sin(2 * pi * i / self.sides + offset),
            )
            for i in range(self.sides)
        ]

    def path_d(self) -> str:
        return _straight_path_d(self.vertices())

    def hole_points(
        self,
        edges="all",
        spacing=5.0,
        inset=4.0,
        include_corners=_REMOVED,
        rounded_path=False,
        distribution="fixed_spacing",
        count=None,
        path_mode="continuous",
        first_margin=None,
        last_margin=None,
    ) -> list[Point]:
        if include_corners is not _REMOVED:
            raise ValueError(
                "include_corners has been removed; use first_margin / last_margin instead"
            )
        validate_distribution(spacing, distribution, count)
        vertices = self._inner_vertices(inset)
        if len(vertices) < 3:
            return []
        edge_defs = [
            (Point(*vertices[i]), Point(*vertices[(i + 1) % len(vertices)]))
            for i in range(len(vertices))
        ]
        if edges == "all":
            return points_on_closed_edges(edge_defs, spacing, False, distribution, count)
        return points_on_selected_edges(
            edge_defs, list(edges), spacing, distribution=distribution, count=count,
            path_mode=path_mode, first_margin=first_margin, last_margin=last_margin,
        )

    def stitch_segments(
        self,
        edges="all",
        spacing=5.0,
        inset=4.0,
        include_corners=_REMOVED,
        stitch_length=2.0,
        stitch_angle_deg=0.0,
        rounded_path=False,
        distribution="fixed_spacing",
        count=None,
        path_mode="continuous",
        first_margin=None,
        last_margin=None,
    ) -> list[tuple[Point, Point]]:
        if include_corners is not _REMOVED:
            raise ValueError(
                "include_corners has been removed; use first_margin / last_margin instead"
            )
        validate_distribution(spacing, distribution, count)
        vertices = self._inner_vertices(inset)
        if len(vertices) < 3:
            return []
        edge_defs = [
            (Point(*vertices[i]), Point(*vertices[(i + 1) % len(vertices)]))
            for i in range(len(vertices))
        ]
        if edges == "all":
            return segments_on_closed_edges(
                edge_defs, spacing, stitch_length, False, stitch_angle_deg, distribution, count
            )
        return segments_on_selected_edges(
            edge_defs, list(edges), spacing, stitch_length, stitch_angle_deg=stitch_angle_deg,
            distribution=distribution, count=count,
            path_mode=path_mode, first_margin=first_margin, last_margin=last_margin,
        )


@dataclass
class RoundedRegularPolygon(Shape):
    """
    Regular polygon with rounded corners.

    ``corner_radius`` applies the same corner rounding to every vertex. Individual
    vertices can be overridden through ``corner_overrides`` where the key is
    the vertex index (0-based, following the polygon winding order).
    """

    cx: float
    cy: float
    radius: float
    sides: int
    corner_radius: float = 5.0
    rotation_deg: float = -90.0
    corner_overrides: dict[int, float] | None = None

    def vertices(self) -> list[tuple[float, float]]:
        if self.sides < 3 or self.radius <= 0:
            return []
        offset = self.rotation_deg * pi / 180
        return [
            (
                self.cx + self.radius * cos(2 * pi * i / self.sides + offset),
                self.cy + self.radius * sin(2 * pi * i / self.sides + offset),
            )
            for i in range(self.sides)
        ]

    def _inner_vertices(self, inset: float) -> list[tuple[float, float]]:
        if self.sides < 3:
            return []
        if inset <= 0:
            return self.vertices()
        apothem = self.radius * cos(pi / self.sides)
        inner_apothem = apothem - inset
        if inner_apothem <= 0:
            return []
        inner_radius = inner_apothem / cos(pi / self.sides)
        offset = self.rotation_deg * pi / 180
        return [
            (
                self.cx + inner_radius * cos(2 * pi * i / self.sides + offset),
                self.cy + inner_radius * sin(2 * pi * i / self.sides + offset),
            )
            for i in range(self.sides)
        ]

    def corner_radii(self) -> list[float]:
        if self.sides < 3:
            return []
        overrides = self.corner_overrides or {}
        radii = [max(0.0, overrides.get(i, self.corner_radius)) for i in range(self.sides)]
        verts = [Point(x, y) for x, y in self.vertices()]
        if len(verts) < 3:
            return radii

        scale = 1.0
        for i in range(self.sides):
            edge_len = distance(verts[i], verts[(i + 1) % self.sides])
            pair_sum = radii[i] + radii[(i + 1) % self.sides]
            if pair_sum > edge_len > 0:
                scale = min(scale, edge_len / pair_sum)
        return [r * scale for r in radii]

    def path_d(self) -> str:
        vertices = [Point(x, y) for x, y in self.vertices()]
        radii = self.corner_radii()
        if len(vertices) < 3:
            return ""
        if not any(radii):
            return _straight_path_d(self.vertices())
        return rounded_polygon_path_d(vertices, radii)

    def hole_points(
        self,
        edges="all",
        spacing=5.0,
        inset=4.0,
        include_corners=_REMOVED,
        rounded_path=False,
        distribution="fixed_spacing",
        count=None,
        path_mode="continuous",
        first_margin=None,
        last_margin=None,
    ) -> list[Point]:
        if include_corners is not _REMOVED:
            raise ValueError(
                "include_corners has been removed; use first_margin / last_margin instead"
            )
        validate_distribution(spacing, distribution, count)
        all_edges = edges == "all" or sorted(set(edges)) == list(range(self.sides))
        radii = self.corner_radii()
        if not all_edges or not any(radii):
            vertices = self._inner_vertices(inset)
            if len(vertices) < 3:
                return []
            edge_defs = [
                (Point(*vertices[i]), Point(*vertices[(i + 1) % len(vertices)]))
                for i in range(len(vertices))
            ]
            if edges == "all":
                return points_on_closed_edges(edge_defs, spacing, False, distribution, count)
            return points_on_selected_edges(
                edge_defs, list(edges), spacing, distribution=distribution, count=count,
                path_mode=path_mode, first_margin=first_margin, last_margin=last_margin,
            )

        inner_vertices = [Point(x, y) for x, y in self._inner_vertices(inset)]
        if len(inner_vertices) < 3:
            return []
        inner_radii = [max(0.0, r - inset) for r in radii]
        contour = rounded_polygon_contour(inner_vertices, inner_radii)
        if len(contour) < 2:
            return []
        return points_on_closed_polyline(
            contour, spacing=spacing, include_corners=False,
            distribution=distribution, count=count,
        )

    def stitch_segments(
        self,
        edges="all",
        spacing=5.0,
        inset=4.0,
        include_corners=_REMOVED,
        stitch_length=2.0,
        stitch_angle_deg=0.0,
        rounded_path=False,
        distribution="fixed_spacing",
        count=None,
        path_mode="continuous",
        first_margin=None,
        last_margin=None,
    ) -> list[tuple[Point, Point]]:
        if include_corners is not _REMOVED:
            raise ValueError(
                "include_corners has been removed; use first_margin / last_margin instead"
            )
        validate_distribution(spacing, distribution, count)
        all_edges = edges == "all" or sorted(set(edges)) == list(range(self.sides))
        radii = self.corner_radii()
        if not all_edges or not any(radii):
            vertices = self._inner_vertices(inset)
            if len(vertices) < 3:
                return []
            edge_defs = [
                (Point(*vertices[i]), Point(*vertices[(i + 1) % len(vertices)]))
                for i in range(len(vertices))
            ]
            if edges == "all":
                return segments_on_closed_edges(
                    edge_defs, spacing, stitch_length, False, stitch_angle_deg, distribution, count
                )
            return segments_on_selected_edges(
                edge_defs, list(edges), spacing, stitch_length, stitch_angle_deg=stitch_angle_deg,
                distribution=distribution, count=count,
                path_mode=path_mode, first_margin=first_margin, last_margin=last_margin,
            )

        inner_vertices = [Point(x, y) for x, y in self._inner_vertices(inset)]
        if len(inner_vertices) < 3:
            return []
        inner_radii = [max(0.0, r - inset) for r in radii]
        contour = rounded_polygon_contour(inner_vertices, inner_radii)
        if len(contour) < 2:
            return []
        return stitch_segments_on_closed_polyline(
            contour, spacing=spacing, stitch_length=stitch_length,
            stitch_angle_deg=stitch_angle_deg, include_corners=False,
            distribution=distribution, count=count,
        )


DXF_LAYER_COLORS = {
    "cut": 1,
    "stitch": 5,
    "crease": 3,
    "guide": 8,
}


@dataclass(frozen=True)
class DxfExportContext:
    document_height: float
    flip_y: bool
    preserve_curves: bool
    curve_tolerance: float


def _style_to_aci_color(layer: str, style: StrokeStyle) -> int:
    if layer in DXF_LAYER_COLORS:
        return DXF_LAYER_COLORS[layer]
    normalized = style.color.lower()
    return {
        "#ff0000": 1,
        "#00aa00": 3,
        "#0000ff": 5,
        "#777777": 8,
    }.get(normalized, 7)


def _create_dxf_layers(dxf_doc, styles: dict[str, StrokeStyle]) -> None:
    for name, style in styles.items():
        if name in dxf_doc.layers:
            dxf_doc.layers.get(name).color = _style_to_aci_color(name, style)
        else:
            dxf_doc.layers.add(name, color=_style_to_aci_color(name, style))


def _transform_point_for_dxf(point: Point, context: DxfExportContext) -> tuple[float, float]:
    if context.flip_y:
        return (point.x, context.document_height - point.y)
    return (point.x, point.y)


def _transform_points_for_dxf(points: list[Point], context: DxfExportContext) -> list[tuple[float, float]]:
    return [_transform_point_for_dxf(point, context) for point in points]


def _arc_angles_for_dxf(start_angle: float, end_angle: float, context: DxfExportContext) -> tuple[float, float]:
    if not context.flip_y:
        return (start_angle, end_angle)
    return ((360.0 - end_angle) % 360.0, (360.0 - start_angle) % 360.0)


def _add_draw_entity_to_dxf(modelspace, entity, context: DxfExportContext) -> None:
    if isinstance(entity, DrawRawPath):
        raise ValueError(
            "DXF export does not support raw SVG paths yet. "
            "Use structured shapes or add a path-to-geometry converter."
        )
    if isinstance(entity, DrawLineEntity):
        modelspace.add_line(
            _transform_point_for_dxf(entity.start, context),
            _transform_point_for_dxf(entity.end, context),
            dxfattribs={"layer": entity.layer},
        )
        return
    if isinstance(entity, DrawCircleEntity):
        modelspace.add_circle(
            _transform_point_for_dxf(entity.center, context),
            entity.radius,
            dxfattribs={"layer": entity.layer},
        )
        return
    if isinstance(entity, DrawShapeEntity):
        _add_shape_to_dxf(modelspace, entity.shape, entity.layer, context)
        return
    raise TypeError(f"unsupported draw entity type: {type(entity)!r}")


def _add_shape_to_dxf(modelspace, shape: Shape, layer: str, context: DxfExportContext) -> None:
    if isinstance(shape, Rectangle) and not isinstance(shape, (RoundedRectangle, Stadium)):
        _add_closed_lwpolyline(modelspace, _rectangle_points(shape), layer, context)
        return
    if isinstance(shape, Circle):
        modelspace.add_circle(
            _transform_point_for_dxf(Point(shape.cx, shape.cy), context),
            shape.radius,
            dxfattribs={"layer": layer},
        )
        return
    if isinstance(shape, Triangle) and not isinstance(shape, RoundedTriangle):
        _add_closed_lwpolyline(modelspace, [shape.p1, shape.p2, shape.p3], layer, context)
        return
    if isinstance(shape, Polygon):
        if shape.smooth:
            _add_closed_lwpolyline(
                modelspace,
                _smooth_polygon_contour(shape.points, context.curve_tolerance),
                layer,
                context,
            )
        else:
            _add_closed_lwpolyline(modelspace, [Point(x, y) for x, y in shape.points], layer, context)
        return
    if isinstance(shape, Arc):
        _add_arc_shape_to_dxf(modelspace, shape, layer, context)
        return
    if isinstance(shape, RoundedRectangle):
        _add_closed_lwpolyline(
            modelspace,
            rounded_rectangle_contour(
                shape.x,
                shape.y,
                shape.width,
                shape.height,
                0.0,
                arc_steps=_curve_steps_for_tolerance(max(shape.width, shape.height), context.curve_tolerance),
                radii=shape.corner_radii(),
            ),
            layer,
            context,
        )
        return
    if isinstance(shape, Stadium):
        _add_closed_lwpolyline(
            modelspace,
            shape._inner_contour(0.0),
            layer,
            context,
        )
        return
    if isinstance(shape, Ellipse):
        _add_closed_lwpolyline(
            modelspace,
            shape._inner_contour(0.0, steps=_curve_steps_for_tolerance(max(shape.rx, shape.ry), context.curve_tolerance)),
            layer,
            context,
        )
        return
    if isinstance(shape, RoundedTriangle):
        _add_closed_lwpolyline(
            modelspace,
            rounded_triangle_contour(
                [shape.p1, shape.p2, shape.p3],
                shape.radius,
                arc_steps=_curve_steps_for_tolerance(shape.radius or 1.0, context.curve_tolerance),
            ),
            layer,
            context,
        )
        return
    if isinstance(shape, RegularPolygon) and not isinstance(shape, RoundedRegularPolygon):
        _add_closed_lwpolyline(modelspace, [Point(x, y) for x, y in shape.vertices()], layer, context)
        return
    if isinstance(shape, RoundedRegularPolygon):
        radii = shape.corner_radii()
        if any(radii) and context.preserve_curves:
            contour = rounded_polygon_contour(
                [Point(x, y) for x, y in shape.vertices()],
                radii,
                arc_steps=_curve_steps_for_tolerance(max(radii) or 1.0, context.curve_tolerance),
            )
            _add_closed_lwpolyline(modelspace, contour, layer, context)
        else:
            _add_closed_lwpolyline(modelspace, [Point(x, y) for x, y in shape.vertices()], layer, context)
        return
    raise TypeError(f"DXF export does not support shape type {type(shape).__name__}")


def _add_closed_lwpolyline(modelspace, points: list[Point], layer: str, context: DxfExportContext) -> None:
    transformed = _transform_points_for_dxf(deduplicate_points(points), context)
    if len(transformed) < 2:
        return
    modelspace.add_lwpolyline(transformed, close=True, dxfattribs={"layer": layer})


def _rectangle_points(shape: Rectangle) -> list[Point]:
    return [
        Point(shape.x, shape.y),
        Point(shape.x + shape.width, shape.y),
        Point(shape.x + shape.width, shape.y + shape.height),
        Point(shape.x, shape.y + shape.height),
    ]


def _curve_steps_for_tolerance(radius_like: float, tolerance: float, minimum: int = 24) -> int:
    effective = max(radius_like, tolerance)
    steps = int(max(minimum, (2 * pi * effective) / max(tolerance, 1e-6)))
    return min(256, steps)


def _smooth_polygon_contour(points: list[tuple[float, float]], tolerance: float) -> list[Point]:
    if len(points) < 3:
        return [Point(x, y) for x, y in points]

    point_objs = [Point(x, y) for x, y in points]
    contour: list[Point] = [point_objs[0]]
    steps = _curve_steps_for_tolerance(
        max(max(abs(x) for x, _ in points), max(abs(y) for _, y in points), default=1.0),
        tolerance,
        minimum=8,
    )
    for index in range(1, len(point_objs) - 1):
        control = point_objs[index]
        next_point = point_objs[index + 1]
        anchor = Point((control.x + next_point.x) / 2, (control.y + next_point.y) / 2)
        start = contour[-1]
        for step in range(1, steps + 1):
            contour.append(quadratic_bezier(start, control, anchor, step / steps))
    last = point_objs[-1]
    first = point_objs[0]
    start = contour[-1]
    for step in range(1, steps + 1):
        contour.append(quadratic_bezier(start, last, first, step / steps))
    return deduplicate_points(contour)


def _add_arc_shape_to_dxf(modelspace, shape: Arc, layer: str, context: DxfExportContext) -> None:
    center = _transform_point_for_dxf(Point(shape.cx, shape.cy), context)
    outer_start, outer_end = _arc_angles_for_dxf(shape.start_angle, shape.end_angle, context)
    modelspace.add_arc(
        center,
        shape.radius,
        outer_start,
        outer_end,
        dxfattribs={"layer": layer},
    )

    start_rad, span = shape._span_rad()
    end_rad = start_rad + span
    outer_start_point = Point(shape.cx + shape.radius * cos(start_rad), shape.cy + shape.radius * sin(start_rad))
    outer_end_point = Point(shape.cx + shape.radius * cos(end_rad), shape.cy + shape.radius * sin(end_rad))

    if shape.inner_radius <= 0:
        center_point = Point(shape.cx, shape.cy)
        modelspace.add_line(
            _transform_point_for_dxf(center_point, context),
            _transform_point_for_dxf(outer_start_point, context),
            dxfattribs={"layer": layer},
        )
        modelspace.add_line(
            _transform_point_for_dxf(outer_end_point, context),
            _transform_point_for_dxf(center_point, context),
            dxfattribs={"layer": layer},
        )
        return

    inner_start_point = Point(shape.cx + shape.inner_radius * cos(start_rad), shape.cy + shape.inner_radius * sin(start_rad))
    inner_end_point = Point(shape.cx + shape.inner_radius * cos(end_rad), shape.cy + shape.inner_radius * sin(end_rad))
    inner_start_angle, inner_end_angle = _arc_angles_for_dxf(shape.start_angle, shape.end_angle, context)
    modelspace.add_arc(
        center,
        shape.inner_radius,
        inner_start_angle,
        inner_end_angle,
        dxfattribs={"layer": layer},
    )
    modelspace.add_line(
        _transform_point_for_dxf(outer_start_point, context),
        _transform_point_for_dxf(inner_start_point, context),
        dxfattribs={"layer": layer},
    )
    modelspace.add_line(
        _transform_point_for_dxf(inner_end_point, context),
        _transform_point_for_dxf(outer_end_point, context),
        dxfattribs={"layer": layer},
    )


def validate_distribution(
    spacing: float,
    distribution: str,
    count: int | None = None,
) -> None:
    if distribution == "fixed_count":
        raise ValueError("distribution 'fixed_count' is not supported yet")
    if distribution not in SUPPORTED_DISTRIBUTIONS:
        choices = ", ".join(SUPPORTED_DISTRIBUTIONS)
        raise ValueError(f"unknown distribution '{distribution}'. Use: {choices}")
    if spacing <= 0:
        raise ValueError("spacing must be greater than 0")


def fitted_spacing(length: float, target_spacing: float) -> float:
    interval_count = max(1, round(length / target_spacing))
    return length / interval_count


def validate_stitch_length(stitch_length: float, actual_spacing: float) -> None:
    if stitch_length >= actual_spacing:
        raise ValueError("stitch_length must be smaller than actual stitch spacing")


def distribute_distances(
    length: float,
    spacing: float,
    *,
    distribution: str = "fixed_spacing",
    count: int | None = None,
    include_start: bool = False,
    include_end: bool = False,
    min_count: int = 1,
    first_margin: float | None = None,
    last_margin: float | None = None,
) -> list[float]:
    validate_distribution(spacing, distribution, count)
    if length <= 0:
        return []

    has_margins = first_margin is not None or last_margin is not None
    if has_margins:
        fm = first_margin if first_margin is not None else 0.0
        lm = last_margin if last_margin is not None else 0.0
        usable = length - fm - lm
        if usable <= 0:
            return []
        if distribution == "fixed_spacing":
            distances = [fm]
            pos = fm + spacing
            while pos <= length - lm + 1e-9:
                distances.append(min(pos, length - lm))
                pos += spacing
            return distances
        # fit_evenly with explicit margins: endpoints at fm and length-lm
        interval_count = max(1, round(usable / spacing))
        actual_spacing = usable / interval_count
        return [fm + i * actual_spacing for i in range(interval_count + 1)]

    if distribution == "fixed_spacing":
        distances = [0.0] if include_start else []
        position = spacing
        while position < length - 1e-9:
            distances.append(position)
            position += spacing
        if include_end and (not distances or abs(distances[-1] - length) > 1e-9):
            distances.append(length)
        return distances

    # fit_evenly: half-offset by default (first stitch at actual/2 from each end)
    actual_spacing = fitted_spacing(length, spacing)
    interval_count = max(1, round(length / spacing))
    if include_start and include_end:
        distances = [i * actual_spacing for i in range(interval_count + 1)]
    elif include_start:
        distances = [i * actual_spacing for i in range(interval_count)]
    elif include_end:
        distances = [(i + 1) * actual_spacing for i in range(interval_count)]
    else:
        # Half-offset: each stitch centred in its interval
        distances = [(i + 0.5) * actual_spacing for i in range(interval_count)]
    if len(distances) < min_count:
        return [length / 2]
    return distances


def _connected_chains(n_edges: int, selected: list[int]) -> list[list[int]]:
    """Split selected edge indices into groups of consecutive connected chains.

    Two edges are connected when they share a corner (edge i ends where edge i+1
    starts). Wrap-around is handled via modular arithmetic.
    """
    if not selected:
        return []
    selected_set = set(selected)
    chain_starts = [i for i in selected if (i - 1) % n_edges not in selected_set]
    if not chain_starts:
        # All selected edges form one closed loop; pick an arbitrary start.
        chain_starts = [selected[0]]
    chains: list[list[int]] = []
    visited: set[int] = set()
    for start in sorted(chain_starts):
        if start in visited:
            continue
        chain: list[int] = []
        j = start
        while j in selected_set and j not in visited:
            chain.append(j)
            visited.add(j)
            j = (j + 1) % n_edges
        if chain:
            chains.append(chain)
    return chains


def _polyline_cumulative(
    waypoints: list[Point],
) -> tuple[list[tuple[Point, Point, float]], list[float]]:
    """Return (segments, cumulative_distances) for a list of waypoints."""
    segs: list[tuple[Point, Point, float]] = []
    cumul: list[float] = [0.0]
    for i in range(len(waypoints) - 1):
        p1, p2 = waypoints[i], waypoints[i + 1]
        d = distance(p1, p2)
        segs.append((p1, p2, d))
        cumul.append(cumul[-1] + d)
    return segs, cumul


def _point_and_dir_on_polyline(
    segs: list[tuple[Point, Point, float]],
    cumul: list[float],
    pos: float,
) -> tuple[Point, tuple[float, float]]:
    """Return (point, unit_edge_vector) at arc-length pos along a polyline."""
    for i, (p1, p2, seg_len) in enumerate(segs):
        if cumul[i + 1] >= pos - 1e-9:
            local = pos - cumul[i]
            if seg_len > 1e-12:
                ex = (p2.x - p1.x) / seg_len
                ey = (p2.y - p1.y) / seg_len
            else:
                ex, ey = 1.0, 0.0
            return Point(p1.x + ex * local, p1.y + ey * local), (ex, ey)
    # Fallback: clamp to end of last segment
    p1, p2, seg_len = segs[-1]
    if seg_len > 1e-12:
        ex = (p2.x - p1.x) / seg_len
        ey = (p2.y - p1.y) / seg_len
    else:
        ex, ey = 1.0, 0.0
    return p2, (ex, ey)


def points_on_polyline_chain(
    waypoints: list[Point],
    spacing: float,
    distribution: str = "fixed_spacing",
    first_margin: float | None = None,
    last_margin: float | None = None,
) -> list[Point]:
    """Distribute hole points along a polyline defined by *waypoints*.

    When no explicit margins are given, ``fixed_spacing`` centres stitches
    along the total chain length (same aesthetic as per-edge centring, but
    now applied across the whole chain).  ``fit_evenly`` uses half-offset so
    the margin at each open end ≈ actual_spacing / 2.
    """
    if len(waypoints) < 2:
        return []
    segs, cumul = _polyline_cumulative(waypoints)
    total = cumul[-1]
    if total <= 0:
        return []
    has_margins = first_margin is not None or last_margin is not None
    if has_margins:
        positions = distribute_distances(
            total, spacing, distribution=distribution,
            first_margin=first_margin, last_margin=last_margin,
        )
    elif distribution == "fixed_spacing":
        positions = positions_on_side_center(total, spacing, include_corners=False)
    else:
        positions = distribute_distances(total, spacing, distribution=distribution)
    result: list[Point] = []
    for pos in positions:
        pt, _ = _point_and_dir_on_polyline(segs, cumul, pos)
        result.append(pt)
    return result


def segments_on_polyline_chain(
    waypoints: list[Point],
    spacing: float,
    stitch_length: float,
    stitch_angle_deg: float = 0.0,
    distribution: str = "fixed_spacing",
    first_margin: float | None = None,
    last_margin: float | None = None,
) -> list[tuple[Point, Point]]:
    """Distribute stitch segments along a polyline defined by *waypoints*.

    Same centring / half-offset logic as :func:`points_on_polyline_chain`.
    """
    if len(waypoints) < 2:
        return []
    segs, cumul = _polyline_cumulative(waypoints)
    total = cumul[-1]
    if total <= 0:
        return []
    has_margins = first_margin is not None or last_margin is not None
    if has_margins:
        positions = distribute_distances(
            total, spacing, distribution=distribution,
            first_margin=first_margin, last_margin=last_margin,
        )
    elif distribution == "fixed_spacing":
        positions = positions_on_side_center(total, spacing, include_corners=False)
    else:
        positions = distribute_distances(total, spacing, distribution=distribution)
    if positions:
        actual_spacing = fitted_spacing(total, spacing) if distribution == "fit_evenly" else spacing
        validate_stitch_length(stitch_length, actual_spacing)
    result: list[tuple[Point, Point]] = []
    angle_rad = stitch_angle_deg * pi / 180
    half = stitch_length / 2
    for pos in positions:
        pt, (ex, ey) = _point_and_dir_on_polyline(segs, cumul, pos)
        dx = ex * cos(angle_rad) - ey * sin(angle_rad)
        dy = ex * sin(angle_rad) + ey * cos(angle_rad)
        result.append((
            Point(pt.x - dx * half, pt.y - dy * half),
            Point(pt.x + dx * half, pt.y + dy * half),
        ))
    return result


def _rounded_rect_chain_waypoints(
    x: float,
    y: float,
    w: float,
    h: float,
    inner_radii: tuple[float, float, float, float],
    chain: list[int],
    arc_steps: int = 8,
) -> list[Point]:
    """Build waypoints for a continuous edge chain on the inner contour of a
    rounded rectangle.

    x, y, w, h  — inner rectangle coordinates (inset already applied).
    inner_radii — (tl, tr, br, bl) radii of the inner contour.
    chain       — ordered list of edge indices (0=top, 1=right, 2=bottom, 3=left).
    arc_steps   — intermediate arc sample points per corner (higher = smoother).
    """
    tl, tr, br, bl = inner_radii

    # Start and end of each edge's straight segment
    edge_start = {
        0: Point(x + tl, y),
        1: Point(x + w, y + tr),
        2: Point(x + w - br, y + h),
        3: Point(x, y + h - bl),
    }
    edge_end = {
        0: Point(x + w - tr, y),
        1: Point(x + w, y + h - br),
        2: Point(x + bl, y + h),
        3: Point(x, y + tl),
    }
    # Arc connecting edge i to edge (i+1)%4: (center, start_angle, end_angle, radius)
    arc_after: dict[int, tuple[Point, float, float, float]] = {
        0: (Point(x + w - tr, y + tr), -pi / 2, 0.0, tr),
        1: (Point(x + w - br, y + h - br), 0.0, pi / 2, br),
        2: (Point(x + bl, y + h - bl), pi / 2, pi, bl),
        3: (Point(x + tl, y + tl), pi, 3 * pi / 2, tl),
    }

    if not chain:
        return []

    waypoints: list[Point] = [edge_start[chain[0]]]
    for chain_idx, edge_idx in enumerate(chain):
        is_last = chain_idx == len(chain) - 1
        waypoints.append(edge_end[edge_idx])
        if not is_last:
            center, a0, a1, ar = arc_after[edge_idx]
            if ar > 1e-9:
                for step in range(1, arc_steps + 1):
                    t = step / (arc_steps + 1)
                    angle = a0 + t * (a1 - a0)
                    waypoints.append(Point(center.x + ar * cos(angle), center.y + ar * sin(angle)))
            waypoints.append(edge_start[chain[chain_idx + 1]])
    return waypoints


def points_on_selected_edges(
    edge_defs,
    edges,
    spacing,
    include_corners=None,
    distribution="fixed_spacing",
    count=None,
    path_mode="continuous",
    first_margin=None,
    last_margin=None,
) -> list[Point]:
    if include_corners is not None:
        raise ValueError(
            "include_corners has been removed; use first_margin / last_margin instead"
        )
    validate_distribution(spacing, distribution, count)
    selected = list(range(len(edge_defs))) if edges == "all" else list(edges)
    n = len(edge_defs)

    if edges == "all":
        return points_on_closed_edges(edge_defs, spacing, False, distribution, count)

    if path_mode == "per_edge":
        result: list[Point] = []
        for index in selected:
            p1, p2 = edge_defs[index]
            result.extend(points_on_line(p1, p2, spacing, False, distribution, count))
        return deduplicate_points(result)

    chains = _connected_chains(n, selected)
    result = []
    for chain in chains:
        waypoints = [edge_defs[chain[0]][0]] + [edge_defs[i][1] for i in chain]
        result.extend(
            points_on_polyline_chain(
                waypoints, spacing, distribution,
                first_margin=first_margin, last_margin=last_margin,
            )
        )
    return deduplicate_points(result)


def segments_on_selected_edges(
    edge_defs,
    edges,
    spacing,
    stitch_length,
    include_corners=None,
    stitch_angle_deg=0.0,
    distribution="fixed_spacing",
    count=None,
    path_mode="continuous",
    first_margin=None,
    last_margin=None,
) -> list[tuple[Point, Point]]:
    if include_corners is not None:
        raise ValueError(
            "include_corners has been removed; use first_margin / last_margin instead"
        )
    validate_distribution(spacing, distribution, count)
    selected = list(range(len(edge_defs))) if edges == "all" else list(edges)
    n = len(edge_defs)

    if edges == "all":
        return segments_on_closed_edges(
            edge_defs, spacing, stitch_length, False, stitch_angle_deg, distribution, count
        )

    if path_mode == "per_edge":
        result: list[tuple[Point, Point]] = []
        for index in selected:
            p1, p2 = edge_defs[index]
            result.extend(
                segments_on_line(p1, p2, spacing, stitch_length, False, stitch_angle_deg, distribution, count)
            )
        return result

    chains = _connected_chains(n, selected)
    result = []
    for chain in chains:
        waypoints = [edge_defs[chain[0]][0]] + [edge_defs[i][1] for i in chain]
        result.extend(
            segments_on_polyline_chain(
                waypoints, spacing, stitch_length, stitch_angle_deg, distribution,
                first_margin=first_margin, last_margin=last_margin,
            )
        )
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
    distribution: str = "fixed_spacing",
    count: int | None = None,
) -> list[tuple[Point, Point]]:
    validate_distribution(spacing, distribution, count)
    result: list[tuple[Point, Point]] = []
    for a, b in edge_defs:
        length = distance(a, b)
        if length == 0:
            continue
        if distribution == "fixed_spacing":
            positions = positions_on_side_center(length, spacing, include_corners)
            adjusted = adjust_stitch_positions_and_lengths(
                positions,
                length,
                include_corners,
                spacing,
                stitch_length,
            )
        else:
            positions = distribute_distances(
                length,
                spacing,
                distribution=distribution,
                count=count,
                include_start=include_corners,
                include_end=include_corners,
            )
            validate_stitch_length(stitch_length, fitted_spacing(length, spacing))
            adjusted = [(position, stitch_length) for position in positions]
        for local_pos, local_stitch_length in adjusted:
            result.append(segment_on_edge(a, b, local_pos, local_stitch_length, stitch_angle_deg))
    return result


def points_on_closed_edges(
    edge_defs: list[tuple[Point, Point]],
    spacing: float,
    include_corners: bool,
    distribution: str = "fixed_spacing",
    count: int | None = None,
) -> list[Point]:
    validate_distribution(spacing, distribution, count)
    result: list[Point] = []
    for a, b in edge_defs:
        length = distance(a, b)
        if length == 0:
            continue
        if distribution == "fixed_spacing":
            positions = positions_on_side_center(length, spacing, include_corners)
            positions = adjust_positions_near_corners(
                positions,
                length,
                include_corners,
                spacing,
            )
        else:
            positions = distribute_distances(
                length,
                spacing,
                distribution=distribution,
                count=count,
                include_start=include_corners,
                include_end=include_corners,
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
    distribution: str = "fixed_spacing",
    count: int | None = None,
) -> list[Point]:
    validate_distribution(spacing, distribution, count)
    length = distance(p1, p2)
    if length == 0:
        return []
    dx = (p2.x - p1.x) / length
    dy = (p2.y - p1.y) / length
    points = []
    positions = (
        positions_on_line(length, spacing, include_corners)
        if distribution == "fixed_spacing"
        else distribute_distances(
            length,
            spacing,
            distribution=distribution,
            count=count,
            include_start=include_corners,
            include_end=include_corners,
        )
    )
    for pos in positions:
        points.append(Point(p1.x + dx * pos, p1.y + dy * pos))
    return points


def segments_on_line(
    p1: Point,
    p2: Point,
    spacing: float,
    stitch_length: float,
    include_corners: bool = False,
    stitch_angle_deg: float = 0.0,
    distribution: str = "fixed_spacing",
    count: int | None = None,
) -> list[tuple[Point, Point]]:
    validate_distribution(spacing, distribution, count)
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
    if distribution == "fixed_spacing":
        positions = positions_on_line(length, spacing, include_corners)
    else:
        positions = distribute_distances(
            length,
            spacing,
            distribution=distribution,
            count=count,
            include_start=include_corners,
            include_end=include_corners,
        )
        validate_stitch_length(stitch_length, fitted_spacing(length, spacing))
    for pos in positions:
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


def rounded_polygon_contour(points: list[Point], radii: list[float], arc_steps: int = 12) -> list[Point]:
    if len(points) < 3 or len(points) != len(radii):
        return []
    if not any(radii):
        return points

    start_points: list[Point] = []
    end_points: list[Point] = []
    for i in range(len(points)):
        prev_p = points[(i - 1) % len(points)]
        p = points[i]
        next_p = points[(i + 1) % len(points)]
        cut = min(
            max(0.0, radii[i]),
            distance(p, prev_p) / 2,
            distance(p, next_p) / 2,
        )
        start_points.append(move_towards(p, prev_p, cut))
        end_points.append(move_towards(p, next_p, cut))

    contour: list[Point] = [end_points[0]]
    for i in range(1, len(points) + 1):
        idx = i % len(points)
        contour.append(start_points[idx])
        control = points[idx]
        a = start_points[idx]
        b = end_points[idx]
        if distance(a, b) > 1e-9:
            for step in range(1, arc_steps):
                t = step / arc_steps
                contour.append(quadratic_bezier(a, control, b, t))
        contour.append(b)

    return deduplicate_points(contour)


def rounded_polygon_path_d(points: list[Point], radii: list[float]) -> str:
    if len(points) < 3 or len(points) != len(radii):
        return ""
    if not any(radii):
        return _straight_path_d([(p.x, p.y) for p in points])

    start_points: list[Point] = []
    end_points: list[Point] = []
    for i in range(len(points)):
        prev_p = points[(i - 1) % len(points)]
        p = points[i]
        next_p = points[(i + 1) % len(points)]
        cut = min(
            max(0.0, radii[i]),
            distance(p, prev_p) / 2,
            distance(p, next_p) / 2,
        )
        start_points.append(move_towards(p, prev_p, cut))
        end_points.append(move_towards(p, next_p, cut))

    parts = [f"M {end_points[0].x:.3f} {end_points[0].y:.3f}"]
    for i in range(1, len(points) + 1):
        idx = i % len(points)
        parts.append(f"L {start_points[idx].x:.3f} {start_points[idx].y:.3f}")
        if distance(start_points[idx], end_points[idx]) <= 1e-9:
            continue
        parts.append(
            f"Q {points[idx].x:.3f} {points[idx].y:.3f} "
            f"{end_points[idx].x:.3f} {end_points[idx].y:.3f}"
        )
    return " ".join(parts) + " Z"


def rounded_rectangle_contour(
    x: float,
    y: float,
    width: float,
    height: float,
    radius: float,
    arc_steps: int = 12,
    radii: "tuple[float, float, float, float] | None" = None,
) -> list[Point]:
    """
    Closed polyline approximating a rounded rectangle.

    ``radius`` applies the same rounding to all four corners. Pass ``radii``
    as (tl, tr, br, bl) to control each corner independently; a value of 0
    yields a sharp corner. ``radii`` takes precedence over ``radius``.
    """
    if width <= 0 or height <= 0:
        return []

    if radii is None:
        r = max(0.0, min(radius, width / 2, height / 2))
        radii = (r, r, r, r)
    tl, tr, br, bl = (max(0.0, min(r, width / 2, height / 2)) for r in radii)

    if tl == tr == br == bl == 0.0:
        return [
            Point(x, y),
            Point(x + width, y),
            Point(x + width, y + height),
            Point(x, y + height),
        ]

    contour: list[Point] = []

    def add_arc(cx: float, cy: float, r: float, start_angle: float, end_angle: float) -> None:
        for step in range(1, arc_steps + 1):
            t = step / arc_steps
            angle = start_angle + (end_angle - start_angle) * t
            contour.append(Point(cx + r * cos(angle), cy + r * sin(angle)))

    contour.append(Point(x + tl, y))
    contour.append(Point(x + width - tr, y))
    if tr > 0:
        add_arc(x + width - tr, y + tr, tr, -pi / 2, 0.0)
    contour.append(Point(x + width, y + height - br))
    if br > 0:
        add_arc(x + width - br, y + height - br, br, 0.0, pi / 2)
    contour.append(Point(x + bl, y + height))
    if bl > 0:
        add_arc(x + bl, y + height - bl, bl, pi / 2, pi)
    contour.append(Point(x, y + tl))
    if tl > 0:
        add_arc(x + tl, y + tl, tl, pi, 3 * pi / 2)

    return deduplicate_points(contour)


def stitch_segments_on_closed_polyline(
    polyline: list[Point],
    spacing: float,
    stitch_length: float,
    stitch_angle_deg: float,
    include_corners: bool,
    distribution: str = "fixed_spacing",
    count: int | None = None,
) -> list[tuple[Point, Point]]:
    validate_distribution(spacing, distribution, count)
    edges = [(polyline[i], polyline[(i + 1) % len(polyline)]) for i in range(len(polyline))]
    lengths = [distance(a, b) for a, b in edges]
    total = sum(lengths)
    if total <= 0:
        return []

    positions = positions_on_closed_length(
        total,
        spacing,
        include_corners,
        distribution=distribution,
        count=count,
    )
    if distribution == "fit_evenly":
        validate_stitch_length(stitch_length, fitted_spacing(total, spacing))
    return map_stitch_positions_on_closed_edges(edges, lengths, positions, stitch_length, stitch_angle_deg)


def points_on_closed_polyline(
    polyline: list[Point],
    spacing: float,
    include_corners: bool,
    distribution: str = "fixed_spacing",
    count: int | None = None,
) -> list[Point]:
    validate_distribution(spacing, distribution, count)
    edges = [(polyline[i], polyline[(i + 1) % len(polyline)]) for i in range(len(polyline))]
    lengths = [distance(a, b) for a, b in edges]
    total = sum(lengths)
    if total <= 0:
        return []

    positions = positions_on_closed_length(
        total,
        spacing,
        include_corners,
        distribution=distribution,
        count=count,
    )
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
    distribution: str = "fixed_spacing",
    count: int | None = None,
) -> list[float]:
    validate_distribution(spacing, distribution, count)
    if total_length <= 0:
        return []

    if distribution == "fit_evenly":
        interval_count = max(1, round(total_length / spacing))
        step = total_length / interval_count
        offset = 0.0 if include_corners else step / 2
        return [offset + i * step for i in range(interval_count)]

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


# ---------------------------------------------------------------------------
# Polygon path helpers
# ---------------------------------------------------------------------------

def _straight_path_d(points: "list[tuple[float, float]]") -> str:
    """Closed SVG path from a list of (x, y) tuples using straight lines."""
    return "M " + " L ".join(f"{x:.3f} {y:.3f}" for x, y in points) + " Z"


def _smooth_path_d(points: "list[tuple[float, float]]") -> str:
    """
    Closed SVG path using quadratic Bézier curves.

    Each original point becomes a control point; midpoints between consecutive
    control points become anchor points. This produces a natural smooth curve
    that passes close to (but not exactly through) each original point.
    """
    if len(points) < 3:
        return _straight_path_d(points)

    d = f"M {points[0][0]:.3f} {points[0][1]:.3f}"
    for i in range(1, len(points) - 1):
        cx, cy = points[i]
        nx, ny = points[i + 1]
        mid_x = (cx + nx) / 2
        mid_y = (cy + ny) / 2
        d += f" Q {cx:.3f} {cy:.3f} {mid_x:.3f} {mid_y:.3f}"
    cx, cy = points[-1]
    fx, fy = points[0]
    d += f" Q {cx:.3f} {cy:.3f} {fx:.3f} {fy:.3f}"
    d += " Z"
    return d


# ---------------------------------------------------------------------------
# Polyline offset and mirroring
# ---------------------------------------------------------------------------

def offset_polyline(
    points: "list[tuple[float, float]]",
    distance: float,
    side: str = "right",
    miter_limit: float = 8.0,
) -> "list[tuple[float, float]]":
    """
    Offset an open polyline by ``distance`` mm on the given ``side``.

    ``side`` means the right-hand or left-hand side relative to the direction
    of travel along the polyline (independent of screen orientation).

    In SVG (Y grows downward):
    - A segment going **right** → ``side="right"`` offsets **upward** (−Y).
    - A segment going **down**  → ``side="right"`` offsets **rightward** (+X).

    For the lighter-sleeve left edge (running top→bottom), ``side="right"``
    therefore moves the seam inward (toward the centre).

    Sharp corners are mitered up to ``miter_limit × distance``. Beyond that
    limit the corner is bevel-cut (averaged normals are used instead).
    """
    if len(points) < 2:
        return list(points)

    if side not in ("left", "right"):
        raise ValueError("side must be 'left' or 'right'")

    # Build one offset segment per input segment.
    offset_segs: list[tuple[tuple, tuple, tuple]] = []
    for (x1, y1), (x2, y2) in zip(points, points[1:]):
        dx, dy = x2 - x1, y2 - y1
        length = hypot(dx, dy)
        if length == 0:
            offset_segs.append(((x1, y1), (x2, y2), (0.0, 0.0)))
            continue
        ux, uy = dx / length, dy / length
        nx, ny = (uy, -ux) if side == "right" else (-uy, ux)
        offset_segs.append((
            (x1 + nx * distance, y1 + ny * distance),
            (x2 + nx * distance, y2 + ny * distance),
            (nx, ny),
        ))

    result: list[tuple[float, float]] = [offset_segs[0][0]]

    for i in range(1, len(points) - 1):
        orig_x, orig_y = points[i]
        prev = offset_segs[i - 1]
        curr = offset_segs[i]

        inter = line_intersection(
            Point(*prev[0]), Point(*prev[1]),
            Point(*curr[0]), Point(*curr[1]),
        )

        if inter is not None and hypot(inter.x - orig_x, inter.y - orig_y) <= distance * miter_limit:
            result.append((inter.x, inter.y))
        else:
            # Miter too long — bevel with averaged normals.
            nx = (prev[2][0] + curr[2][0]) / 2
            ny = (prev[2][1] + curr[2][1]) / 2
            ln = hypot(nx, ny)
            if ln > 0:
                nx, ny = nx / ln, ny / ln
            else:
                nx, ny = prev[2]
            result.append((orig_x + nx * distance, orig_y + ny * distance))

    result.append(offset_segs[-1][1])
    return result


def mirror_polyline(
    points: "list[tuple[float, float]]",
    center_x: float,
) -> "list[tuple[float, float]]":
    """
    Mirror a polyline horizontally around ``center_x``.

    Useful for generating the right-hand stitch path from a left-hand one.
    """
    return [(2 * center_x - x, y) for x, y in points]


# ---------------------------------------------------------------------------
# Internal: closed-polygon offset used by Polygon.hole_points / stitch_segments
# ---------------------------------------------------------------------------

def _offset_closed_polygon(
    points: "list[tuple[float, float]]",
    distance: float,
) -> "list[tuple[float, float]]":
    """
    Offset a closed polygon inward by ``distance``.

    The inward direction is determined automatically from the polygon's
    winding order (signed area in SVG Y-down coordinates).
    """
    n = len(points)
    if n < 3:
        return list(points)

    # Signed area via the Shoelace formula.
    # Positive → CW winding in SVG (Y down) = CCW in standard math coords.
    # For a CW polygon the interior lies to the LEFT of each edge, so use
    # side="left" to offset inward.  For CCW use side="right".
    area2 = sum(
        points[i][0] * points[(i + 1) % n][1] - points[(i + 1) % n][0] * points[i][1]
        for i in range(n)
    )
    side = "left" if area2 > 0 else "right"

    offset_segs: list[tuple[tuple, tuple, tuple]] = []
    for i in range(n):
        x1, y1 = points[i]
        x2, y2 = points[(i + 1) % n]
        dx, dy = x2 - x1, y2 - y1
        length = hypot(dx, dy)
        if length == 0:
            offset_segs.append(((x1, y1), (x2, y2), (0.0, 0.0)))
            continue
        ux, uy = dx / length, dy / length
        nx, ny = (uy, -ux) if side == "right" else (-uy, ux)
        offset_segs.append((
            (x1 + nx * distance, y1 + ny * distance),
            (x2 + nx * distance, y2 + ny * distance),
            (nx, ny),
        ))

    miter_limit = 8.0
    result: list[tuple[float, float]] = []
    for i in range(n):
        orig_x, orig_y = points[i]
        prev = offset_segs[(i - 1) % n]
        curr = offset_segs[i]

        inter = line_intersection(
            Point(*prev[0]), Point(*prev[1]),
            Point(*curr[0]), Point(*curr[1]),
        )

        if inter is not None and hypot(inter.x - orig_x, inter.y - orig_y) <= distance * miter_limit:
            result.append((inter.x, inter.y))
        else:
            nx = (prev[2][0] + curr[2][0]) / 2
            ny = (prev[2][1] + curr[2][1]) / 2
            ln = hypot(nx, ny)
            if ln > 0:
                nx, ny = nx / ln, ny / ln
            else:
                nx, ny = prev[2]
            result.append((orig_x + nx * distance, orig_y + ny * distance))

    return result


# ---------------------------------------------------------------------------
# Open-polyline stitch segments
# ---------------------------------------------------------------------------

def stitch_segments_on_open_polyline(
    points: "list[tuple[float, float]]",
    spacing: float,
    stitch_length: float,
    stitch_angle_deg: float = 0.0,
    distribution: str = "fixed_spacing",
    count: int | None = None,
) -> "list[tuple[Point, Point]]":
    """
    Return stitch segments placed every ``spacing`` mm along an open polyline.

    The first stitch is placed ``spacing`` mm from the start of the path.
    ``stitch_angle_deg=0`` aligns stitches with the local path direction;
    ``stitch_angle_deg=45`` rotates them 45 degrees.
    """
    validate_distribution(spacing, distribution, count)
    result: list[tuple[Point, Point]] = []

    if distribution == "fit_evenly":
        segment_lengths = [
            hypot(x2 - x1, y2 - y1)
            for (x1, y1), (x2, y2) in zip(points, points[1:])
        ]
        total_length = sum(segment_lengths)
        if total_length <= 0:
            return []
        actual_spacing = fitted_spacing(total_length, spacing)
        validate_stitch_length(stitch_length, actual_spacing)
        positions = distribute_distances(
            total_length,
            spacing,
            distribution=distribution,
            count=count,
            include_start=False,
            include_end=False,
        )
        position_index = 0
        traversed = 0.0
        for ((x1, y1), (x2, y2)), seg_len in zip(zip(points, points[1:]), segment_lengths):
            if seg_len == 0:
                continue
            dx, dy = x2 - x1, y2 - y1
            ux, uy = dx / seg_len, dy / seg_len
            angle_rad = stitch_angle_deg * pi / 180
            sx = ux * cos(angle_rad) - uy * sin(angle_rad)
            sy = ux * sin(angle_rad) + uy * cos(angle_rad)
            half = stitch_length / 2
            seg_end = traversed + seg_len
            while position_index < len(positions) and positions[position_index] <= seg_end + 1e-9:
                position = positions[position_index]
                if position >= traversed - 1e-9:
                    t = max(0.0, min(1.0, (position - traversed) / seg_len))
                    cx = x1 + dx * t
                    cy = y1 + dy * t
                    result.append((
                        Point(cx - sx * half, cy - sy * half),
                        Point(cx + sx * half, cy + sy * half),
                    ))
                position_index += 1
            traversed = seg_end
        return result

    total = 0.0
    next_pos = spacing

    for (x1, y1), (x2, y2) in zip(points, points[1:]):
        dx, dy = x2 - x1, y2 - y1
        seg_len = hypot(dx, dy)
        if seg_len == 0:
            continue

        ux, uy = dx / seg_len, dy / seg_len
        angle_rad = stitch_angle_deg * pi / 180
        sx = ux * cos(angle_rad) - uy * sin(angle_rad)
        sy = ux * sin(angle_rad) + uy * cos(angle_rad)
        half = stitch_length / 2

        seg_end = total + seg_len
        while next_pos < seg_end:
            t = (next_pos - total) / seg_len
            cx = x1 + dx * t
            cy = y1 + dy * t
            result.append((
                Point(cx - sx * half, cy - sy * half),
                Point(cx + sx * half, cy + sy * half),
            ))
            next_pos += spacing
        total += seg_len

    return result
