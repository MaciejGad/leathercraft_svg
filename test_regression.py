"""
Visual regression test for a rectangle with holes.

First run (no baseline yet):
    .venv/bin/python test_regression.py --save-baseline

Subsequent runs (compare against baseline):
    .venv/bin/python test_regression.py

The baseline PNG is committed to the repo so any rendering change
that shifts pixels will be caught immediately.
"""

import argparse
import hashlib
import sys
import unittest
from pathlib import Path

BASELINE = Path(__file__).parent / "test_baseline_rectangle.png"


def render_png() -> bytes:
    from leathercraft_svg import Rectangle, SvgDocument

    doc = SvgDocument(width_mm=100, height_mm=60)
    shape = Rectangle(10, 10, 80, 40)
    doc.add_shape(shape, layer="cut")
    doc.add_holes(shape, edges="all", spacing=8.0, hole_radius=1.2, inset=5.0, layer="stitch")
    return doc.to_png_bytes()


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class RectangleRegressionTest(unittest.TestCase):
    def test_rectangle_matches_baseline(self):
        if not BASELINE.exists():
            self.skipTest(
                f"No baseline found at {BASELINE.name}. "
                "Run with --save-baseline to create it."
            )
        current = render_png()
        expected = BASELINE.read_bytes()
        self.assertEqual(
            sha256(current),
            sha256(expected),
            "PNG output differs from baseline — possible rendering regression.\n"
            f"Re-run with --save-baseline to update if the change is intentional.",
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--save-baseline", action="store_true", help="Write current output as the new baseline")
    args, remaining = parser.parse_known_args()

    if args.save_baseline:
        png = render_png()
        BASELINE.write_bytes(png)
        print(f"Baseline saved: {BASELINE.name} ({len(png)} bytes, sha256={sha256(png)[:16]}…)")
        sys.exit(0)

    sys.argv = [sys.argv[0]] + remaining
    unittest.main()
