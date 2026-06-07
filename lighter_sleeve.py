"""
Symmetric lighter sleeve pattern for leather laser cutting.

This pattern is based on / inspired by the free lighter sleeve template
published by Juchcik:

https://juchcik.pl/userdata/public/assets//etui_na_zapalcznik%C4%99.pdf

The generated SVG is a custom, symmetrical reconstruction intended for
personal leathercraft experimentation.
"""

from math import hypot, cos, sin, radians
from leathercraft_svg import SvgDocument, StrokeStyle


def mirror_points(points, center_x):
    """
    Mirror points horizontally around the given center X axis.
    """
    return [(2 * center_x - x, y) for x, y in points]


def mirror_segments(segments, center_x):
    """
    Mirror stitch segments horizontally around the given center X axis.
    """
    return [
        (
            2 * center_x - x1,
            y1,
            2 * center_x - x2,
            y2,
        )
        for x1, y1, x2, y2 in segments
    ]


def straight_path_from_points(points):
    """
    Build a closed SVG path from a list of points using straight lines.
    """
    return "M " + " L ".join(f"{x:.2f},{y:.2f}" for x, y in points) + " Z"


def smooth_path_from_points(points):
    """
    Build a closed SVG path using quadratic Bézier curves.
    """
    if len(points) < 3:
        return straight_path_from_points(points)

    d = f"M {points[0][0]:.2f},{points[0][1]:.2f}"

    for i in range(1, len(points) - 1):
        control_x, control_y = points[i]
        next_x, next_y = points[i + 1]

        mid_x = (control_x + next_x) / 2
        mid_y = (control_y + next_y) / 2

        d += f" Q {control_x:.2f},{control_y:.2f} {mid_x:.2f},{mid_y:.2f}"

    last_control_x, last_control_y = points[-1]
    first_x, first_y = points[0]

    d += f" Q {last_control_x:.2f},{last_control_y:.2f} {first_x:.2f},{first_y:.2f}"
    d += " Z"

    return d


def unit_vector(x1, y1, x2, y2):
    """
    Return a normalized direction vector for a segment.
    """
    dx = x2 - x1
    dy = y2 - y1
    length = hypot(dx, dy)

    if length == 0:
        return 0.0, 0.0

    return dx / length, dy / length


def normal_for_segment(x1, y1, x2, y2, side):
    """
    Return a normal vector for a segment.

    In SVG coordinates, Y grows downward.
    For a polyline going from top to bottom along the left edge,
    side='right' moves the offset toward the inside of the pattern.
    """
    ux, uy = unit_vector(x1, y1, x2, y2)

    if side == "right":
        return uy, -ux

    if side == "left":
        return -uy, ux

    raise ValueError("side must be 'left' or 'right'")


def line_intersection(p1, p2, p3, p4):
    """
    Return intersection point of two infinite lines:
    line p1->p2 and line p3->p4.

    If lines are parallel or almost parallel, return None.
    """
    x1, y1 = p1
    x2, y2 = p2
    x3, y3 = p3
    x4, y4 = p4

    denominator = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)

    if abs(denominator) < 1e-9:
        return None

    px = (
        (x1 * y2 - y1 * x2) * (x3 - x4)
        - (x1 - x2) * (x3 * y4 - y3 * x4)
    ) / denominator

    py = (
        (x1 * y2 - y1 * x2) * (y3 - y4)
        - (y1 - y2) * (x3 * y4 - y3 * x4)
    ) / denominator

    return px, py


def offset_polyline(points, distance, side="right", miter_limit=8.0):
    """
    Create an offset polyline at a fixed distance from the source polyline.

    This works by:
    1. Offsetting every segment by its normal vector.
    2. Intersecting neighboring offset segments.
    3. Falling back to averaged normals when the intersection is too far away.

    This is not a full closed-polygon offset, but it works well for creating
    a stitch line parallel to an open outer edge.
    """
    if len(points) < 2:
        return points[:]

    offset_segments = []

    for p1, p2 in zip(points, points[1:]):
        x1, y1 = p1
        x2, y2 = p2

        nx, ny = normal_for_segment(x1, y1, x2, y2, side)

        offset_segments.append(
            (
                (x1 + nx * distance, y1 + ny * distance),
                (x2 + nx * distance, y2 + ny * distance),
                (nx, ny),
            )
        )

    result = []

    first_offset_start, _, _ = offset_segments[0]
    result.append(first_offset_start)

    for i in range(1, len(points) - 1):
        original_x, original_y = points[i]

        previous_start, previous_end, previous_normal = offset_segments[i - 1]
        next_start, next_end, next_normal = offset_segments[i]

        intersection = line_intersection(
            previous_start,
            previous_end,
            next_start,
            next_end,
        )

        if intersection is None:
            nx = (previous_normal[0] + next_normal[0]) / 2
            ny = (previous_normal[1] + next_normal[1]) / 2
            length = hypot(nx, ny)

            if length == 0:
                nx, ny = previous_normal
            else:
                nx /= length
                ny /= length

            intersection = (
                original_x + nx * distance,
                original_y + ny * distance,
            )

        if hypot(intersection[0] - original_x, intersection[1] - original_y) > distance * miter_limit:
            nx = (previous_normal[0] + next_normal[0]) / 2
            ny = (previous_normal[1] + next_normal[1]) / 2
            length = hypot(nx, ny)

            if length == 0:
                nx, ny = previous_normal
            else:
                nx /= length
                ny /= length

            intersection = (
                original_x + nx * distance,
                original_y + ny * distance,
            )

        result.append(intersection)

    _, last_offset_end, _ = offset_segments[-1]
    result.append(last_offset_end)

    return result


def stitch_segments_on_polyline(points, spacing, stitch_length, angle_deg=0):
    """
    Return short stitch segments distributed continuously every `spacing` mm
    along the whole polyline.

    angle_deg = 0 means the stitch is parallel to the local path direction.
    angle_deg = 45 means the stitch is diagonal relative to the local path direction.
    """
    result = []

    total_distance = 0.0
    next_stitch_distance = spacing

    for (x1, y1), (x2, y2) in zip(points, points[1:]):
        dx = x2 - x1
        dy = y2 - y1
        segment_length = hypot(dx, dy)

        if segment_length == 0:
            continue

        ux = dx / segment_length
        uy = dy / segment_length

        angle = radians(angle_deg)
        sx = ux * cos(angle) - uy * sin(angle)
        sy = ux * sin(angle) + uy * cos(angle)

        segment_start_distance = total_distance
        segment_end_distance = total_distance + segment_length

        while next_stitch_distance < segment_end_distance:
            local_distance = next_stitch_distance - segment_start_distance
            t = local_distance / segment_length

            cx = x1 + dx * t
            cy = y1 + dy * t

            half = stitch_length / 2

            result.append(
                (
                    cx - sx * half,
                    cy - sy * half,
                    cx + sx * half,
                    cy + sy * half,
                )
            )

            next_stitch_distance += spacing

        total_distance += segment_length

    return result


doc = SvgDocument(
    width_mm=150,
    height_mm=112,
    styles={
        "cut": StrokeStyle("#ff0000", 0.12),
        "stitch": StrokeStyle("#0000ff", 0.35),
        "debug": StrokeStyle("#00aa00", 0.12),
    },
)

center_x = 75
top_y = 8

# Define only the left half of the outer cut line.
# The right side will be generated automatically as a mirror copy.
left_outline = [
    (center_x, top_y + 6),

    (center_x - 16, top_y + 3),
    (center_x - 32, top_y + 0),
    (center_x - 47, top_y + 3),
    (center_x - 58, top_y + 3),

    (center_x - 57, top_y + 10),
    (center_x - 56, top_y + 19),
    (center_x - 57, top_y + 28),

    (center_x - 49, top_y + 30),
    (center_x - 39, top_y + 34),
    (center_x - 35, top_y + 43),

    (center_x - 35, top_y + 66),
    (center_x - 36, top_y + 80),
    (center_x - 38, top_y + 89),

    (center_x - 28, top_y + 94),
    (center_x - 14, top_y + 97),
    (center_x, top_y + 97),
]

right_outline = mirror_points(left_outline, center_x)
outline = left_outline + list(reversed(right_outline[1:-1]))

doc.add_path(smooth_path_from_points(outline), layer="cut")

# Symmetric keyring attachment holes.
# Holes are placed higher and closer to the outer side edges.
keyring_hole_offset_x = 45
keyring_hole_y = top_y + 15
keyring_hole_radius = 2.2

left_keyring_hole_x = center_x - keyring_hole_offset_x
right_keyring_hole_x = center_x + keyring_hole_offset_x

doc.add_circle(
    left_keyring_hole_x,
    keyring_hole_y,
    keyring_hole_radius,
    layer="cut",
)

doc.add_circle(
    right_keyring_hole_x,
    keyring_hole_y,
    keyring_hole_radius,
    layer="cut",
)

#doc.add_circle(43, 15, 1, layer="debug")  # Reference point for measurements

# Use the real outer edge as the source for the stitch path.
# The top decorative edge is intentionally skipped.
left_outer_edge_for_stitching = [
    # Start the stitch line around x=43, y=15.
    # This point is on the upper left side, but still below the top decorative edge.
    (43, 10),

    # Continue along the actual outer edge.
    (center_x - 47, top_y + 3),
    (center_x - 58, top_y + 3),

    (center_x - 57, top_y + 10),
    (center_x - 56, top_y + 19),
    (center_x - 57, top_y + 28),

    (center_x - 49, top_y + 30),
    (center_x - 39, top_y + 34),
    (center_x - 35, top_y + 43),

    (center_x - 35, top_y + 66),
    (center_x - 36, top_y + 80),
    (center_x - 38, top_y + 89),

    (center_x - 28, top_y + 94),
    (center_x - 14, top_y + 97),
    (center_x, top_y + 97),
]
stitch_margin = 4.0

left_seam = offset_polyline(
    left_outer_edge_for_stitching,
    distance=stitch_margin,
    side="right",
)

left_stitches = stitch_segments_on_polyline(
    left_seam,
    spacing=6,
    stitch_length=2.4,
    angle_deg=0,
)

right_stitches = mirror_segments(left_stitches, center_x)

for x1, y1, x2, y2 in left_stitches + right_stitches:
    doc.add_line(x1, y1, x2, y2, layer="stitch")

# Optional debug preview of the computed inset stitch path.
# Uncomment these lines if you want to see the generated stitch guide path.
# doc.add_path(straight_path_from_points(left_seam), layer="debug")
# doc.add_path(straight_path_from_points(mirror_points(left_seam, center_x)), layer="debug")

doc.save("lighter_sleeve.svg")
doc.save_png("lighter_sleeve.png", background_color="white")