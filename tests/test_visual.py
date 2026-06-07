"""
Visual regression tests — one baseline PNG per rendered scenario.

Save / update all baselines:
    .venv/bin/python -m tests.test_visual --save-baseline

Run regression checks:
    .venv/bin/python -m pytest tests/test_visual.py
    # or without pytest:
    .venv/bin/python -m tests.test_visual
"""

import argparse
import hashlib
import sys
import unittest
from pathlib import Path

BASELINES = Path(__file__).parent / "baselines"

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def render(doc) -> bytes:
    return doc.to_png_bytes(background_color="white")


def _compare(test_case: unittest.TestCase, name: str, data: bytes) -> None:
    path = BASELINES / name
    if not path.exists():
        test_case.skipTest(f"No baseline: {name}. Run with --save-baseline.")
    expected = path.read_bytes()
    test_case.assertEqual(
        sha256(data),
        sha256(expected),
        f"PNG '{name}' differs from baseline — rendering regression detected.\n"
        "Run with --save-baseline to update if the change is intentional.",
    )


# ---------------------------------------------------------------------------
# scene builders (each returns png bytes)
# ---------------------------------------------------------------------------

def _rectangle_holes_all_edges() -> bytes:
    from leathercraft_svg import Rectangle, SvgDocument
    doc = SvgDocument(100, 60)
    s = Rectangle(10, 10, 80, 40)
    doc.add_shape(s, layer="cut")
    doc.add_holes(s, edges="all", spacing=8.0, hole_radius=1.2, inset=5.0, layer="stitch")
    return render(doc)


def _rectangle_holes_partial_edges() -> bytes:
    from leathercraft_svg import Rectangle, SvgDocument
    doc = SvgDocument(100, 60)
    s = Rectangle(10, 10, 80, 40)
    doc.add_shape(s, layer="cut")
    doc.add_holes(s, edges=[0, 2], spacing=8.0, hole_radius=1.0, inset=5.0, layer="stitch")
    return render(doc)


def _rectangle_holes_include_corners() -> bytes:
    from leathercraft_svg import Rectangle, SvgDocument
    doc = SvgDocument(100, 60)
    s = Rectangle(10, 10, 80, 40)
    doc.add_shape(s, layer="cut")
    doc.add_holes(s, spacing=8.0, hole_radius=1.0, inset=5.0, include_corners=True, layer="stitch")
    return render(doc)


def _rectangle_stitch_0deg() -> bytes:
    from leathercraft_svg import Rectangle, SvgDocument
    doc = SvgDocument(100, 60)
    s = Rectangle(10, 10, 80, 40)
    doc.add_shape(s, layer="cut")
    doc.add_stitch_pattern(s, spacing=8.0, stitch_length=3.0, stitch_angle_deg=0.0, inset=5.0, layer="stitch", stitch_thickness=0.5)
    return render(doc)


def _rectangle_stitch_45deg() -> bytes:
    from leathercraft_svg import Rectangle, SvgDocument
    doc = SvgDocument(100, 60)
    s = Rectangle(10, 10, 80, 40)
    doc.add_shape(s, layer="cut")
    doc.add_stitch_pattern(s, spacing=8.0, stitch_length=3.0, stitch_angle_deg=45.0, inset=5.0, layer="stitch", stitch_thickness=0.5)
    return render(doc)


def _rounded_rectangle_holes_all_edges() -> bytes:
    from leathercraft_svg import RoundedRectangle, SvgDocument
    doc = SvgDocument(140, 90)
    s = RoundedRectangle(20, 15, 100, 60, radius=10)
    doc.add_shape(s, layer="cut")
    doc.add_holes(s, spacing=8.0, hole_radius=1.4, inset=7.0, layer="stitch")
    return render(doc)


def _rounded_rectangle_stitch_partial() -> bytes:
    from leathercraft_svg import RoundedRectangle, SvgDocument
    doc = SvgDocument(140, 90)
    s = RoundedRectangle(20, 15, 100, 60, radius=10)
    doc.add_shape(s, layer="cut")
    doc.add_stitch_pattern(
        s, edges=[1, 2, 3], spacing=8.0, stitch_length=3.5,
        stitch_angle_deg=45.0, inset=7.0, layer="stitch", stitch_thickness=0.8,
    )
    return render(doc)


def _circle_holes() -> bytes:
    from leathercraft_svg import Circle, SvgDocument
    doc = SvgDocument(100, 100)
    s = Circle(50, 50, 35)
    doc.add_shape(s, layer="cut")
    doc.add_holes(s, spacing=8.0, hole_radius=1.5, inset=7.0, layer="stitch")
    return render(doc)


def _circle_stitch_0deg() -> bytes:
    from leathercraft_svg import Circle, SvgDocument
    doc = SvgDocument(100, 100)
    s = Circle(50, 50, 35)
    doc.add_shape(s, layer="cut")
    doc.add_stitch_pattern(s, spacing=8.0, stitch_length=3.5, stitch_angle_deg=0.0, inset=7.0, layer="stitch", stitch_thickness=0.8)
    return render(doc)


def _circle_stitch_45deg() -> bytes:
    from leathercraft_svg import Circle, SvgDocument
    doc = SvgDocument(100, 100)
    s = Circle(50, 50, 35)
    doc.add_shape(s, layer="cut")
    doc.add_stitch_pattern(s, spacing=8.0, stitch_length=3.5, stitch_angle_deg=45.0, inset=7.0, layer="stitch", stitch_thickness=0.8)
    return render(doc)


def _triangle_holes_all_edges() -> bytes:
    from leathercraft_svg import Point, SvgDocument, Triangle
    doc = SvgDocument(120, 90)
    s = Triangle(Point(60, 10), Point(110, 80), Point(10, 80))
    doc.add_shape(s, layer="cut")
    doc.add_holes(s, spacing=8.0, hole_radius=1.2, inset=6.0, layer="stitch")
    return render(doc)


def _triangle_holes_partial_edges() -> bytes:
    from leathercraft_svg import Point, SvgDocument, Triangle
    doc = SvgDocument(120, 90)
    s = Triangle(Point(60, 10), Point(110, 80), Point(10, 80))
    doc.add_shape(s, layer="cut")
    doc.add_holes(s, edges=[0, 2], spacing=8.0, hole_radius=1.2, inset=6.0, layer="stitch")
    return render(doc)


def _triangle_stitch_45deg() -> bytes:
    from leathercraft_svg import Point, SvgDocument, Triangle
    doc = SvgDocument(120, 90)
    s = Triangle(Point(60, 10), Point(110, 80), Point(10, 80))
    doc.add_shape(s, layer="cut")
    doc.add_stitch_pattern(s, spacing=8.0, stitch_length=3.5, stitch_angle_deg=45.0, inset=6.0, layer="stitch", stitch_thickness=0.8)
    return render(doc)


def _rounded_triangle_holes_straight() -> bytes:
    from leathercraft_svg import Point, RoundedTriangle, SvgDocument
    doc = SvgDocument(130, 100)
    s = RoundedTriangle(Point(65, 10), Point(120, 90), Point(10, 90), radius=12)
    doc.add_shape(s, layer="cut")
    doc.add_holes(s, spacing=8.0, hole_radius=1.5, inset=6.0, layer="stitch", rounded_path=False)
    return render(doc)


def _rounded_triangle_holes_rounded_path() -> bytes:
    from leathercraft_svg import Point, RoundedTriangle, SvgDocument
    doc = SvgDocument(130, 100)
    s = RoundedTriangle(Point(65, 10), Point(120, 90), Point(10, 90), radius=12)
    doc.add_shape(s, layer="cut")
    doc.add_holes(s, spacing=8.0, hole_radius=1.5, inset=6.0, layer="stitch", rounded_path=True)
    return render(doc)


def _rounded_triangle_stitch_rounded_path() -> bytes:
    from leathercraft_svg import Point, RoundedTriangle, SvgDocument
    doc = SvgDocument(130, 100)
    s = RoundedTriangle(Point(65, 10), Point(120, 90), Point(10, 90), radius=12)
    doc.add_shape(s, layer="cut")
    doc.add_stitch_pattern(
        s, spacing=8.0, stitch_length=3.5, stitch_angle_deg=0.0,
        inset=6.0, layer="stitch", stitch_thickness=0.8, rounded_path=True,
    )
    return render(doc)


def _all_shapes_gallery() -> bytes:
    """Mirrors the layout produced by all_shapes.py."""
    from leathercraft_svg import (
        Circle, Point, Rectangle, RoundedRectangle, RoundedTriangle,
        SvgDocument, Triangle,
    )

    row_y = [20, 95, 170, 245, 320]
    col_x = [20, 145, 270, 395, 520]

    doc = SvgDocument(width_mm=640, height_mm=410)

    for cx in col_x:
        s = Rectangle(cx, row_y[0], 90, 55)
        doc.add_shape(s, layer="cut")
        doc.add_holes(s, spacing=8.0, hole_radius=1.0, inset=6.0, layer="stitch")

    for cx in col_x:
        s = RoundedRectangle(cx, row_y[1], 90, 55, radius=10)
        doc.add_shape(s, layer="cut")
        doc.add_holes(s, spacing=8.0, hole_radius=1.4, inset=7.0, layer="stitch")

    for cx in col_x:
        s = Circle(cx + 45, row_y[2] + 30, 28)
        doc.add_shape(s, layer="cut")
        doc.add_holes(s, spacing=8.0, hole_radius=1.5, inset=7.0, layer="stitch")

    for cx in col_x:
        s = Triangle.from_box(cx, row_y[3], 90, 65)
        doc.add_shape(s, layer="cut")
        doc.add_holes(s, spacing=8.0, hole_radius=1.5, inset=7.0, layer="stitch")

    for cx in col_x:
        s = RoundedTriangle(
            Point(cx + 45, row_y[4]), Point(cx + 90, row_y[4] + 70), Point(cx, row_y[4] + 70),
            radius=12,
        )
        doc.add_shape(s, layer="cut")
        doc.add_holes(s, spacing=8.0, hole_radius=1.5, inset=6.0, layer="stitch", rounded_path=True)

    return render(doc)


# ---------------------------------------------------------------------------
# test cases → baseline name mapping
# ---------------------------------------------------------------------------

SCENARIOS: list[tuple[str, object]] = [
    ("rectangle_holes_all_edges.png",           _rectangle_holes_all_edges),
    ("rectangle_holes_partial_edges.png",        _rectangle_holes_partial_edges),
    ("rectangle_holes_include_corners.png",      _rectangle_holes_include_corners),
    ("rectangle_stitch_0deg.png",                _rectangle_stitch_0deg),
    ("rectangle_stitch_45deg.png",               _rectangle_stitch_45deg),
    ("rounded_rectangle_holes.png",              _rounded_rectangle_holes_all_edges),
    ("rounded_rectangle_stitch_partial.png",     _rounded_rectangle_stitch_partial),
    ("circle_holes.png",                         _circle_holes),
    ("circle_stitch_0deg.png",                   _circle_stitch_0deg),
    ("circle_stitch_45deg.png",                  _circle_stitch_45deg),
    ("triangle_holes_all_edges.png",             _triangle_holes_all_edges),
    ("triangle_holes_partial_edges.png",         _triangle_holes_partial_edges),
    ("triangle_stitch_45deg.png",                _triangle_stitch_45deg),
    ("rounded_triangle_holes_straight.png",      _rounded_triangle_holes_straight),
    ("rounded_triangle_holes_rounded_path.png",  _rounded_triangle_holes_rounded_path),
    ("rounded_triangle_stitch_rounded_path.png", _rounded_triangle_stitch_rounded_path),
    ("all_shapes_gallery.png",                   _all_shapes_gallery),
]


# ---------------------------------------------------------------------------
# test class — one test method per scenario
# ---------------------------------------------------------------------------

def _make_test(name: str, builder):
    def test_method(self):
        _compare(self, name, builder())
    test_method.__name__ = "test_" + name.removesuffix(".png")
    return test_method


class VisualRegressionTests(unittest.TestCase):
    pass


for _name, _builder in SCENARIOS:
    setattr(VisualRegressionTests, "test_" + _name.removesuffix(".png"), _make_test(_name, _builder))


# ---------------------------------------------------------------------------
# CLI: --save-baseline
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--save-baseline", action="store_true", help="Write all baselines from the current render output")
    args, remaining = parser.parse_known_args()

    if args.save_baseline:
        BASELINES.mkdir(parents=True, exist_ok=True)
        for name, builder in SCENARIOS:
            data = builder()
            path = BASELINES / name
            path.write_bytes(data)
            print(f"  saved {name} ({len(data)} bytes, sha256={sha256(data)[:16]}…)")
        print(f"\nAll {len(SCENARIOS)} baselines saved to {BASELINES}")
        sys.exit(0)

    sys.argv = [sys.argv[0]] + remaining
    unittest.main()
