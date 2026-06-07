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
col_x = [20, 145, 270]

doc = SvgDocument(width_mm=390, height_mm=410)


def add_variant(
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

    angle = 0 if variant == "stitch_0" else 45
    doc.add_stitch_pattern(
        shape,
        spacing=8.0,
        stitch_length=3.5,
        stitch_angle_deg=angle,
        inset=inset,
        layer="stitch",
        stitch_thickness=0.8,
        placement="dense",
        rounded_path=rounded_path,
    )


def add_row(shapes: list, inset: float, hole_radius: float = 1.2, rounded_path: bool = False) -> None:
    add_variant(shapes[0], "holes", inset, hole_radius, rounded_path)
    add_variant(shapes[1], "stitch_0", inset, hole_radius, rounded_path)
    add_variant(shapes[2], "stitch_45", inset, hole_radius, rounded_path)


# Rectangle row: holes | stitch 0 | stitch 45
add_row(
    [
        Rectangle(col_x[0], row_y[0], 90, 55),
        Rectangle(col_x[1], row_y[0], 90, 55),
        Rectangle(col_x[2], row_y[0], 90, 55),
    ],
    inset=6.0,
    hole_radius=1.0,
)

# Rounded rectangle row: holes | stitch 0 | stitch 45
add_row(
    [
        RoundedRectangle(col_x[0], row_y[1], 90, 55, radius=10),
        RoundedRectangle(col_x[1], row_y[1], 90, 55, radius=10),
        RoundedRectangle(col_x[2], row_y[1], 90, 55, radius=10),
    ],
    inset=7.0,
    hole_radius=1.4,
)

# Circle row: holes | stitch 0 | stitch 45
add_row(
    [
        Circle(col_x[0] + 45, row_y[2] + 30, 28),
        Circle(col_x[1] + 45, row_y[2] + 30, 28),
        Circle(col_x[2] + 45, row_y[2] + 30, 28),
    ],
    inset=7.0,
    hole_radius=1.5,
)

# Triangle row: holes | stitch 0 | stitch 45
add_row(
    [
        Triangle.from_box(col_x[0], row_y[3], 90, 65),
        Triangle.from_box(col_x[1], row_y[3], 90, 65),
        Triangle.from_box(col_x[2], row_y[3], 90, 65),
    ],
    inset=7.0,
    hole_radius=1.5,
)

# Rounded triangle row: holes | stitch 0 | stitch 45
add_row(
    [
        RoundedTriangle(Point(col_x[0] + 45, row_y[4]), Point(col_x[0] + 90, row_y[4] + 70), Point(col_x[0], row_y[4] + 70), radius=12),
        RoundedTriangle(Point(col_x[1] + 45, row_y[4]), Point(col_x[1] + 90, row_y[4] + 70), Point(col_x[1], row_y[4] + 70), radius=12),
        RoundedTriangle(Point(col_x[2] + 45, row_y[4]), Point(col_x[2] + 90, row_y[4] + 70), Point(col_x[2], row_y[4] + 70), radius=12),
    ],
    inset=6.0,
    hole_radius=1.5,
    rounded_path=True,
)

doc.save("example_shapes.svg")
doc.save_png("example_shapes.png", background_color="white")
print("Generated: example_shapes.svg")
print("Generated: example_shapes.png")
