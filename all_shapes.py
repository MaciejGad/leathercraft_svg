from math import atan2, degrees

from laser_svg import (
    Circle,
    Point,
    Rectangle,
    RoundedRectangle,
    RoundedTriangle,
    SvgDocument,
    Triangle,
)

row_y = [20, 95, 170, 245, 320]
col_x = [20, 145, 270, 395, 520]

MISSING_EDGE_MAP = {
    Rectangle: [1, 2, 3],
    RoundedRectangle: [1, 2, 3],
    Triangle: [0, 1],
    RoundedTriangle: [0, 1],
}


def angle_in_sector(angle_deg: float, start_deg: float, extent_deg: float) -> bool:
    angle = angle_deg % 360
    start = start_deg % 360
    end = (start + extent_deg) % 360
    if extent_deg >= 360:
        return True
    if start <= end:
        return start <= angle <= end
    return angle >= start or angle <= end


def add_circle_holes_with_gap(
    doc: SvgDocument,
    circle: Circle,
    spacing: float,
    hole_radius: float,
    inset: float,
    layer: str,
    gap_start_deg: float = -135.0,
    gap_extent_deg: float = 90.0,
) -> None:
    points = circle.hole_points(spacing=spacing, inset=inset)
    for p in points:
        angle = degrees(atan2(p.y - circle.cy, p.x - circle.cx))
        if angle_in_sector(angle, gap_start_deg, gap_extent_deg):
            continue
        doc.add_circle(p.x, p.y, hole_radius, layer=layer)


def add_circle_stitches_with_gap(
    doc: SvgDocument,
    circle: Circle,
    spacing: float,
    stitch_length: float,
    inset: float,
    layer: str,
    stitch_thickness: float,
    stitch_angle_deg: float,
    gap_start_deg: float = -135.0,
    gap_extent_deg: float = 90.0,
) -> None:
    segments = circle.stitch_segments(
        spacing=spacing,
        stitch_length=stitch_length,
        inset=inset,
        stitch_angle_deg=stitch_angle_deg,
    )
    for p1, p2 in segments:
        cx = (p1.x + p2.x) / 2
        cy = (p1.y + p2.y) / 2
        angle = degrees(atan2(cy - circle.cy, cx - circle.cx))
        if angle_in_sector(angle, gap_start_deg, gap_extent_deg):
            continue
        doc.add_line(p1.x, p1.y, p2.x, p2.y, layer=layer, stroke_width=stitch_thickness)

def add_variant(
    doc: SvgDocument,
    shape,
    variant: str,
    inset: float,
    hole_radius: float = 1.2,
    rounded_path: bool = False,
) -> None:
    doc.add_shape(shape, layer="cut")
    if variant == "holes":
        doc.add_holes(
            shape,
            spacing=8.0,
            hole_radius=hole_radius,
            inset=inset,
            layer="stitch",
            rounded_path=rounded_path,
        )
        return

    if variant == "holes_gap":
        if isinstance(shape, Circle):
            add_circle_holes_with_gap(
                doc,
                shape,
                spacing=8.0,
                hole_radius=hole_radius,
                inset=inset,
                layer="stitch",
            )
            return

        edges = MISSING_EDGE_MAP.get(type(shape), [0, 1, 2])
        doc.add_holes(
            shape,
            edges=edges,
            spacing=8.0,
            hole_radius=hole_radius,
            inset=inset,
            layer="stitch",
            rounded_path=rounded_path,
        )
        return

    angle = 0 if variant == "stitch_0" else 45
    if variant == "stitch_gap":
        if isinstance(shape, Circle):
            add_circle_stitches_with_gap(
                doc,
                shape,
                spacing=8.0,
                stitch_length=3.5,
                inset=inset,
                layer="stitch",
                stitch_thickness=0.8,
                stitch_angle_deg=0.0,
            )
            return

        edges = MISSING_EDGE_MAP.get(type(shape), [0, 1, 2])
        doc.add_stitch_pattern(
            shape,
            edges=edges,
            spacing=8.0,
            stitch_length=3.5,
            stitch_angle_deg=0.0,
            inset=inset,
            layer="stitch",
            stitch_thickness=0.8,
            rounded_path=rounded_path,
        )
        return

    doc.add_stitch_pattern(
        shape,
        spacing=8.0,
        stitch_length=3.5,
        stitch_angle_deg=angle,
        inset=inset,
        layer="stitch",
        stitch_thickness=0.8,
        rounded_path=rounded_path,
    )


def add_row(
    doc: SvgDocument,
    shapes: list,
    inset: float,
    hole_radius: float = 1.2,
    rounded_path: bool = False,
) -> None:
    add_variant(doc, shapes[0], "holes", inset, hole_radius, rounded_path)
    add_variant(doc, shapes[1], "holes_gap", inset, hole_radius, rounded_path)
    add_variant(doc, shapes[2], "stitch_0", inset, hole_radius, rounded_path)
    add_variant(doc, shapes[3], "stitch_45", inset, hole_radius, rounded_path)
    add_variant(doc, shapes[4], "stitch_gap", inset, hole_radius, rounded_path)


def generate_example(stem: str) -> None:
    doc = SvgDocument(width_mm=640, height_mm=410)

    # Rectangle row: holes | stitch 0 | stitch 45
    add_row(
        doc,
        [
            Rectangle(col_x[0], row_y[0], 90, 55),
            Rectangle(col_x[1], row_y[0], 90, 55),
            Rectangle(col_x[2], row_y[0], 90, 55),
            Rectangle(col_x[3], row_y[0], 90, 55),
            Rectangle(col_x[4], row_y[0], 90, 55),
        ],
        inset=6.0,
        hole_radius=1.0,
    )

    # Rounded rectangle row: holes | stitch 0 | stitch 45
    add_row(
        doc,
        [
            RoundedRectangle(col_x[0], row_y[1], 90, 55, radius=10),
            RoundedRectangle(col_x[1], row_y[1], 90, 55, radius=10),
            RoundedRectangle(col_x[2], row_y[1], 90, 55, radius=10),
            RoundedRectangle(col_x[3], row_y[1], 90, 55, radius=10),
            RoundedRectangle(col_x[4], row_y[1], 90, 55, radius=10),
        ],
        inset=7.0,
        hole_radius=1.4,
    )

    # Circle row: holes | stitch 0 | stitch 45
    add_row(
        doc,
        [
            Circle(col_x[0] + 45, row_y[2] + 30, 28),
            Circle(col_x[1] + 45, row_y[2] + 30, 28),
            Circle(col_x[2] + 45, row_y[2] + 30, 28),
            Circle(col_x[3] + 45, row_y[2] + 30, 28),
            Circle(col_x[4] + 45, row_y[2] + 30, 28),
        ],
        inset=7.0,
        hole_radius=1.5,
    )

    # Triangle row: holes | stitch 0 | stitch 45
    add_row(
        doc,
        [
            Triangle.from_box(col_x[0], row_y[3], 90, 65),
            Triangle.from_box(col_x[1], row_y[3], 90, 65),
            Triangle.from_box(col_x[2], row_y[3], 90, 65),
            Triangle.from_box(col_x[3], row_y[3], 90, 65),
            Triangle.from_box(col_x[4], row_y[3], 90, 65),
        ],
        inset=7.0,
        hole_radius=1.5,
    )

    # Rounded triangle row: holes | stitch 0 | stitch 45
    add_row(
        doc,
        [
            RoundedTriangle(Point(col_x[0] + 45, row_y[4]), Point(col_x[0] + 90, row_y[4] + 70), Point(col_x[0], row_y[4] + 70), radius=12),
            RoundedTriangle(Point(col_x[1] + 45, row_y[4]), Point(col_x[1] + 90, row_y[4] + 70), Point(col_x[1], row_y[4] + 70), radius=12),
            RoundedTriangle(Point(col_x[2] + 45, row_y[4]), Point(col_x[2] + 90, row_y[4] + 70), Point(col_x[2], row_y[4] + 70), radius=12),
            RoundedTriangle(Point(col_x[3] + 45, row_y[4]), Point(col_x[3] + 90, row_y[4] + 70), Point(col_x[3], row_y[4] + 70), radius=12),
            RoundedTriangle(Point(col_x[4] + 45, row_y[4]), Point(col_x[4] + 90, row_y[4] + 70), Point(col_x[4], row_y[4] + 70), radius=12),
        ],
        inset=6.0,
        hole_radius=1.5,
        rounded_path=True,
    )

    svg_path = f"{stem}.svg"
    png_path = f"{stem}.png"
    doc.save(svg_path)
    doc.save_png(png_path, background_color="white")
    print(f"Generated: {svg_path}")
    print(f"Generated: {png_path}")


generate_example("all_shapes")
