from laser_svg import (
    Circle,
    PlacementMode,
    Point,
    Rectangle,
    RoundedRectangle,
    RoundedTriangle,
    SvgDocument,
    Triangle,
)

row_y = [20, 95, 170, 245, 320]
col_x = [20, 145, 270]

def add_variant(
    doc: SvgDocument,
    shape,
    variant: str,
    inset: float,
    placement: PlacementMode,
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
            placement=placement,
            rounded_path=rounded_path,
        )
        return

    angle = 0 if variant == "stitch_0" else 45
    doc.add_stitch_pattern(
        shape,
        spacing=8.0,
        stitch_length=3.5,
        stitch_angle_deg=angle,
        inset=inset,
        layer="stitch",
        stitch_thickness=0.8,
        placement=placement,
        rounded_path=rounded_path,
    )


def add_row(
    doc: SvgDocument,
    shapes: list,
    inset: float,
    placement: PlacementMode,
    hole_radius: float = 1.2,
    rounded_path: bool = False,
) -> None:
    add_variant(doc, shapes[0], "holes", inset, placement, hole_radius, rounded_path)
    add_variant(doc, shapes[1], "stitch_0", inset, placement, hole_radius, rounded_path)
    add_variant(doc, shapes[2], "stitch_45", inset, placement, hole_radius, rounded_path)


def generate_example(placement: PlacementMode, stem: str) -> None:
    doc = SvgDocument(width_mm=390, height_mm=410)

    # Rectangle row: holes | stitch 0 | stitch 45
    add_row(
        doc,
        [
            Rectangle(col_x[0], row_y[0], 90, 55),
            Rectangle(col_x[1], row_y[0], 90, 55),
            Rectangle(col_x[2], row_y[0], 90, 55),
        ],
        inset=6.0,
        placement=placement,
        hole_radius=1.0,
    )

    # Rounded rectangle row: holes | stitch 0 | stitch 45
    add_row(
        doc,
        [
            RoundedRectangle(col_x[0], row_y[1], 90, 55, radius=10),
            RoundedRectangle(col_x[1], row_y[1], 90, 55, radius=10),
            RoundedRectangle(col_x[2], row_y[1], 90, 55, radius=10),
        ],
        inset=7.0,
        placement=placement,
        hole_radius=1.4,
    )

    # Circle row: holes | stitch 0 | stitch 45
    add_row(
        doc,
        [
            Circle(col_x[0] + 45, row_y[2] + 30, 28),
            Circle(col_x[1] + 45, row_y[2] + 30, 28),
            Circle(col_x[2] + 45, row_y[2] + 30, 28),
        ],
        inset=7.0,
        placement=placement,
        hole_radius=1.5,
    )

    # Triangle row: holes | stitch 0 | stitch 45
    add_row(
        doc,
        [
            Triangle.from_box(col_x[0], row_y[3], 90, 65),
            Triangle.from_box(col_x[1], row_y[3], 90, 65),
            Triangle.from_box(col_x[2], row_y[3], 90, 65),
        ],
        inset=7.0,
        placement=placement,
        hole_radius=1.5,
    )

    # Rounded triangle row: holes | stitch 0 | stitch 45
    add_row(
        doc,
        [
            RoundedTriangle(Point(col_x[0] + 45, row_y[4]), Point(col_x[0] + 90, row_y[4] + 70), Point(col_x[0], row_y[4] + 70), radius=12),
            RoundedTriangle(Point(col_x[1] + 45, row_y[4]), Point(col_x[1] + 90, row_y[4] + 70), Point(col_x[1], row_y[4] + 70), radius=12),
            RoundedTriangle(Point(col_x[2] + 45, row_y[4]), Point(col_x[2] + 90, row_y[4] + 70), Point(col_x[2], row_y[4] + 70), radius=12),
        ],
        inset=6.0,
        placement=placement,
        hole_radius=1.5,
        rounded_path=True,
    )

    svg_path = f"{stem}.svg"
    png_path = f"{stem}.png"
    doc.save(svg_path)
    doc.save_png(png_path, background_color="white")
    print(f"Generated: {svg_path}")
    print(f"Generated: {png_path}")


generate_example("centered", "example_shapes_centered")
generate_example("dense", "example_shapes_dense")
