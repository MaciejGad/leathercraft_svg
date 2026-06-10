"""
Visual regression tests for leathercraft_dsl.

Save / update all baselines:
    .venv/bin/python -m tests.test_dsl_visual --save-baseline

Run regression checks:
    .venv/bin/python -m pytest tests/test_dsl_visual.py
    # or without pytest:
    .venv/bin/python -m tests.test_dsl_visual
"""

from __future__ import annotations

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


def _compile_dsl(dsl_text: str) -> bytes:
    from leathercraft_dsl import compile_document, parse
    doc = parse(dsl_text)
    svg = compile_document(doc)
    return svg.to_png_bytes(background_color="white")


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
# DSL scene builders
# ---------------------------------------------------------------------------


def _dsl_rectangle_holes_all_edges() -> bytes:
    return _compile_dsl("""
size 100 60

rectangle panel
  at 10 10
  size 80 40
end

holes
  source panel
  edges all
  margin 5
  spacing 8
  radius 1.2
end
""")


def _dsl_rectangle_holes_partial_edges() -> bytes:
    return _compile_dsl("""
size 100 60

rectangle panel
  at 10 10
  size 80 40
end

holes
  source panel
  edges top bottom
  margin 5
  spacing 8
  radius 1
end
""")


def _dsl_rectangle_stitch_0deg() -> bytes:
    return _compile_dsl("""
size 100 60

rectangle panel
  at 10 10
  size 80 40
end

stitches
  source panel
  edges all
  margin 5
  spacing 8
  length 3
  angle 0
end
""")


def _dsl_rectangle_stitch_45deg() -> bytes:
    return _compile_dsl("""
size 100 60

rectangle panel
  at 10 10
  size 80 40
end

stitches
  source panel
  edges all
  margin 5
  spacing 8
  length 3
  angle 45
end
""")


def _dsl_rounded_rect_holes() -> bytes:
    return _compile_dsl("""
size 140 90

rounded_rectangle panel
  at 20 15
  size 100 60
  radius 10
end

holes
  source panel
  margin 7
  spacing 8
  radius 1.4
end
""")


def _dsl_rounded_rect_stitch_partial() -> bytes:
    return _compile_dsl("""
size 140 90

rounded_rectangle panel
  at 20 15
  size 100 60
  radius 10
end

stitches
  source panel
  edges right bottom left
  margin 7
  spacing 8
  length 3.5
  angle 45
end
""")


def _dsl_rectangle_holes_except_top() -> bytes:
    return _compile_dsl("""
size 120 90

rounded_rectangle pocket
  at 10 10
  size 100 70
  radius 8
end

holes
  source pocket
  edges except_top
  margin 5
  spacing 8
  radius 1.2
end
""")


def _dsl_lighter_sleeve() -> bytes:
    return _compile_dsl("""
pattern lighter_sleeve
size 150 112

layer cut red 0.12
layer stitch blue 0.35

symmetry 75

outer smooth mirrored
  75 14
  59 11
  43 8
  28 11
  17 11
  18 27
  18 36
  36 42
  40 51
  40 74
  37 97
  47 102
  61 105
  75 105
end

stitches
  margin 4
  spacing 5
  length 3.8
  angle 0
  mirror

  path
    43 15
    28 11
    17 11
    18 27
    18 36
    36 42
    40 51
    40 74
    37 97
    47 102
    61 105
    75 105
  end
end

hole keyring
  mirror
  x_from_center 30
  y 21
  radius 2.2
end
""")


def _dsl_single_hole() -> bytes:
    return _compile_dsl("""
size 80 60

hole pin
  at 40 30
  radius 3
end
""")


def _dsl_mirrored_holes() -> bytes:
    return _compile_dsl("""
size 150 60

symmetry 75

hole left_right
  mirror
  x_from_center 30
  y 30
  radius 2
end
""")


def _dsl_outer_straight() -> bytes:
    return _compile_dsl("""
size 100 100

outer straight
  20 10
  80 10
  90 90
  10 90
end
""")


def _dsl_outer_smooth_mirrored() -> bytes:
    return _compile_dsl("""
size 150 100

symmetry 75

outer smooth mirrored
  75 10
  50 15
  30 40
  30 70
  50 85
  75 90
end
""")


def _dsl_custom_path_stitches_mirror() -> bytes:
    return _compile_dsl("""
size 150 112

symmetry 75

outer smooth mirrored
  75 10
  50 15
  30 40
  30 70
  50 85
  75 90
end

stitches
  margin 4
  spacing 6
  length 3
  mirror

  path
    50 15
    30 40
    30 70
    50 85
    75 90
  end
end
""")


def _dsl_circle_holes() -> bytes:
    return _compile_dsl("""
size 100 100

circle ring
  at 50 50
  radius 35
end

holes
  source ring
  margin 7
  spacing 8
  radius 1.5
end
""")


def _dsl_circle_stitch_0deg() -> bytes:
    return _compile_dsl("""
size 100 100

circle ring
  at 50 50
  radius 35
end

stitches
  source ring
  margin 7
  spacing 8
  length 3.5
  angle 0
end
""")


def _dsl_circle_stitch_45deg() -> bytes:
    return _compile_dsl("""
size 100 100

circle ring
  at 50 50
  radius 35
end

stitches
  source ring
  margin 7
  spacing 8
  length 3.5
  angle 45
end
""")


def _dsl_triangle_holes_all_edges() -> bytes:
    return _compile_dsl("""
size 120 90

triangle tri
  p1 60 10
  p2 110 80
  p3 10 80
end

holes
  source tri
  edges all
  margin 6
  spacing 8
  radius 1.2
end
""")


def _dsl_triangle_holes_partial_edges() -> bytes:
    return _compile_dsl("""
size 120 90

triangle tri
  p1 60 10
  p2 110 80
  p3 10 80
end

holes
  source tri
  edges 0 2
  margin 6
  spacing 8
  radius 1.2
end
""")


def _dsl_triangle_stitch_45deg() -> bytes:
    return _compile_dsl("""
size 120 90

triangle tri
  p1 60 10
  p2 110 80
  p3 10 80
end

stitches
  source tri
  edges all
  margin 6
  spacing 8
  length 3.5
  angle 45
end
""")


def _dsl_triangle_box_form() -> bytes:
    return _compile_dsl("""
size 120 90

triangle tri
  at 10 10
  size 100 70
end

holes
  source tri
  edges 0 1
  margin 6
  spacing 8
  radius 1.2
end
""")


def _dsl_rounded_triangle_holes_straight() -> bytes:
    return _compile_dsl("""
size 130 100

rounded_triangle rtri
  p1 65 10
  p2 120 90
  p3 10 90
  radius 12
end

holes
  source rtri
  margin 6
  spacing 8
  radius 1.5
end
""")


def _dsl_rounded_triangle_holes_rounded_path() -> bytes:
    return _compile_dsl("""
size 130 100

rounded_triangle rtri
  p1 65 10
  p2 120 90
  p3 10 90
  radius 12
end

holes
  source rtri
  rounded_path
  margin 6
  spacing 8
  radius 1.5
end
""")


def _dsl_rounded_triangle_stitch_rounded_path() -> bytes:
    return _compile_dsl("""
size 130 100

rounded_triangle rtri
  p1 65 10
  p2 120 90
  p3 10 90
  radius 12
end

stitches
  source rtri
  rounded_path
  margin 6
  spacing 8
  length 3.5
  angle 0
end
""")


# ---------------------------------------------------------------------------
# Scenario registry  name → builder
# ---------------------------------------------------------------------------

def _dsl_per_corner_rounded_rect() -> bytes:
    return _compile_dsl("""
size 120 90

rounded_rectangle card
  at 10 10
  size 100 70
  radius_tl 18
  radius_tr 18
end

stitches
  source card
  margin 5
  spacing 6
  length 3
end
""")


def _dsl_arc_ring_stitches() -> bytes:
    return _compile_dsl("""
size 130 80

arc strap_end
  at 65 70
  radius 55
  inner_radius 30
  from_angle 180
  to_angle 360
end

stitches
  source strap_end
  margin 5
  spacing 6
  length 3
end
""")


def _dsl_arc_wedge_holes() -> bytes:
    return _compile_dsl("""
size 130 80

arc fan
  at 65 70
  radius 55
  from_angle 180
  to_angle 360
end

holes
  source fan
  margin 6
  spacing 8
  radius 1.2
end
""")


def _dsl_ellipse_stitches() -> bytes:
    return _compile_dsl("""
size 130 90

ellipse oval
  at 65 45
  rx 55
  ry 35
end

stitches
  source oval
  margin 5
  spacing 6
  length 3
end
""")


def _dsl_ellipse_holes() -> bytes:
    return _compile_dsl("""
size 130 90

ellipse oval
  at 65 45
  size 110 70
end

holes
  source oval
  margin 7
  spacing 8
  radius 1.5
end
""")


def _dsl_regular_polygon_holes() -> bytes:
    return _compile_dsl("""
size 120 120

regular_polygon hex
  at 60 60
  radius 42
  sides 6
end

holes
  source hex
  margin 6
  spacing 8
  radius 1.2
end
""")


def _dsl_regular_polygon_stitches() -> bytes:
    return _compile_dsl("""
size 120 120

regular_polygon oct
  at 60 60
  radius 40
  sides 8
  rotation 22.5
end

stitches
  source oct
  edges 0 1 2 3
  margin 5
  spacing 8
  length 3
  angle 30
end
""")


def _dsl_stadium_stitches() -> bytes:
    return _compile_dsl("""
size 140 60

stadium fob
  at 10 15
  size 120 30
end

stitches
  source fob
  margin 4
  spacing 5
  length 3
end
""")


def _dsl_stadium_holes() -> bytes:
    return _compile_dsl("""
size 140 60

stadium fob
  at 10 15
  size 120 30
end

holes
  source fob
  margin 5
  spacing 8
  radius 1.5
end
""")


def _dsl_stadium_vertical() -> bytes:
    return _compile_dsl("""
size 60 140

stadium tag
  at 15 10
  size 30 120
end

stitches
  source tag
  margin 4
  spacing 5
  length 3
end
""")


SCENARIOS: dict[str, callable] = {
    "dsl_rectangle_holes_all_edges.png": _dsl_rectangle_holes_all_edges,
    "dsl_rectangle_holes_partial_edges.png": _dsl_rectangle_holes_partial_edges,
    "dsl_rectangle_stitch_0deg.png": _dsl_rectangle_stitch_0deg,
    "dsl_rectangle_stitch_45deg.png": _dsl_rectangle_stitch_45deg,
    "dsl_rounded_rect_holes.png": _dsl_rounded_rect_holes,
    "dsl_rounded_rect_stitch_partial.png": _dsl_rounded_rect_stitch_partial,
    "dsl_rectangle_holes_except_top.png": _dsl_rectangle_holes_except_top,
    "dsl_lighter_sleeve.png": _dsl_lighter_sleeve,
    "dsl_single_hole.png": _dsl_single_hole,
    "dsl_mirrored_holes.png": _dsl_mirrored_holes,
    "dsl_outer_straight.png": _dsl_outer_straight,
    "dsl_outer_smooth_mirrored.png": _dsl_outer_smooth_mirrored,
    "dsl_custom_path_stitches_mirror.png": _dsl_custom_path_stitches_mirror,
    # --- new shapes ---
    "dsl_circle_holes.png": _dsl_circle_holes,
    "dsl_circle_stitch_0deg.png": _dsl_circle_stitch_0deg,
    "dsl_circle_stitch_45deg.png": _dsl_circle_stitch_45deg,
    "dsl_triangle_holes_all_edges.png": _dsl_triangle_holes_all_edges,
    "dsl_triangle_holes_partial_edges.png": _dsl_triangle_holes_partial_edges,
    "dsl_triangle_stitch_45deg.png": _dsl_triangle_stitch_45deg,
    "dsl_triangle_box_form.png": _dsl_triangle_box_form,
    "dsl_rounded_triangle_holes_straight.png": _dsl_rounded_triangle_holes_straight,
    "dsl_rounded_triangle_holes_rounded_path.png": _dsl_rounded_triangle_holes_rounded_path,
    "dsl_rounded_triangle_stitch_rounded_path.png": _dsl_rounded_triangle_stitch_rounded_path,
    # --- arc / sector ---
    "dsl_arc_ring_stitches.png": _dsl_arc_ring_stitches,
    "dsl_arc_wedge_holes.png": _dsl_arc_wedge_holes,
    # --- per-corner rounded rectangle ---
    "dsl_per_corner_rounded_rect.png": _dsl_per_corner_rounded_rect,
    # --- ellipse ---
    "dsl_ellipse_stitches.png": _dsl_ellipse_stitches,
    "dsl_ellipse_holes.png": _dsl_ellipse_holes,
    # --- regular polygon ---
    "dsl_regular_polygon_holes.png": _dsl_regular_polygon_holes,
    "dsl_regular_polygon_stitches.png": _dsl_regular_polygon_stitches,
    # --- stadium ---
    "dsl_stadium_stitches.png": _dsl_stadium_stitches,
    "dsl_stadium_holes.png": _dsl_stadium_holes,
    "dsl_stadium_vertical.png": _dsl_stadium_vertical,
}


# ---------------------------------------------------------------------------
# Test class
# ---------------------------------------------------------------------------


class TestDslVisualRegression(unittest.TestCase):
    pass


def _make_test(name: str, builder):
    def test_method(self):
        data = builder()
        _compare(self, name, data)
    test_method.__name__ = f"test_{name.replace('.png', '')}"
    return test_method


for _name, _builder in SCENARIOS.items():
    _method = _make_test(_name, _builder)
    setattr(TestDslVisualRegression, _method.__name__, _method)


# ---------------------------------------------------------------------------
# CLI: --save-baseline
# ---------------------------------------------------------------------------


def _save_all_baselines() -> None:
    BASELINES.mkdir(exist_ok=True)
    for name, builder in SCENARIOS.items():
        print(f"  saving {name} ...", end=" ", flush=True)
        data = builder()
        (BASELINES / name).write_bytes(data)
        print("ok")
    print("All DSL baselines saved.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--save-baseline",
        action="store_true",
        help="Write all DSL baselines from the current render output",
    )
    args, remaining = parser.parse_known_args()

    if args.save_baseline:
        _save_all_baselines()
    else:
        sys.argv = [sys.argv[0]] + remaining
        unittest.main()
