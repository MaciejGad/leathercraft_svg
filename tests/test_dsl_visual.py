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


# ---------------------------------------------------------------------------
# Scenario registry  name → builder
# ---------------------------------------------------------------------------

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
