#!/usr/bin/env python3
"""
leathercraft_server — web-based editor for .lcraft pattern files.

Provides a split-pane UI: CodeMirror editor on the left, live SVG preview
on the right.  The browser sends the raw source to the server for compilation;
the server returns SVG or an error message.

Usage:
    python leathercraft_server.py                 # http://127.0.0.1:5000
    python leathercraft_server.py --port 8080
    python leathercraft_server.py --host 0.0.0.0  # expose on LAN
    python leathercraft_server.py --debug          # Flask debug / auto-reload
"""

from __future__ import annotations

import argparse
import io
from pathlib import Path

from flask import Flask, Response, jsonify, request, send_file, send_from_directory

from leathercraft_dsl import DslError, compile_document, parse

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = Flask(__name__, static_folder="static")


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.route("/")
def index() -> Response:
    return send_from_directory("static", "index.html")


@app.route("/pyodide")
def pyodide_index() -> Response:
    return send_from_directory("static", "pyodide_index.html")


@app.route("/pyodide_editor.js")
def pyodide_editor_js() -> Response:
    return send_from_directory("static", "pyodide_editor.js")


@app.route("/pyodide_runtime.js")
def pyodide_runtime_js() -> Response:
    return send_from_directory("static", "pyodide_runtime.js")


@app.route("/tutorial")
@app.route("/tutorial.html")
def tutorial_index() -> Response:
    return send_from_directory("static", "tutorial.html")


@app.route("/tutorial.js")
def tutorial_js() -> Response:
    return send_from_directory("static", "tutorial.js")


@app.route("/leathercraft_svg.py")
def leathercraft_svg_source() -> Response:
    return send_file(Path(app.root_path) / "leathercraft_svg.py", mimetype="text/x-python")


@app.route("/leathercraft_dsl.py")
def leathercraft_dsl_source() -> Response:
    return send_file(Path(app.root_path) / "leathercraft_dsl.py", mimetype="text/x-python")


@app.route("/api/compile", methods=["POST"])
def compile_endpoint() -> Response:
    """Compile .lcraft source → SVG string.

    Request body (JSON): { "source": "<lcraft text>" }
    Response (JSON):     { "svg": "<svg string>", "error": null }
                      or { "svg": null, "error": "<message>" }
    """
    data = request.get_json(force=True, silent=True) or {}
    source: str = data.get("source", "")

    try:
        doc = parse(source)
        svg_doc = compile_document(doc)
        return jsonify({"svg": svg_doc.to_svg(), "error": None})
    except DslError as exc:
        return jsonify({"svg": None, "error": str(exc)})
    except Exception as exc:  # noqa: BLE001
        return jsonify({"svg": None, "error": f"Internal error: {exc}"}), 500


@app.route("/api/export/svg", methods=["POST"])
def export_svg() -> Response:
    """Compile source and return SVG file for download."""
    data = request.get_json(force=True, silent=True) or {}
    source: str = data.get("source", "")
    filename: str = data.get("filename", "pattern") + ".svg"

    try:
        doc = parse(source)
        svg_str = compile_document(doc).to_svg()
        buf = io.BytesIO(svg_str.encode("utf-8"))
        return send_file(
            buf,
            mimetype="image/svg+xml",
            as_attachment=True,
            download_name=filename,
        )
    except DslError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": f"Internal error: {exc}"}), 500


@app.route("/api/export/png", methods=["POST"])
def export_png() -> Response:
    """Compile source and return PNG file for download."""
    data = request.get_json(force=True, silent=True) or {}
    source: str = data.get("source", "")
    filename: str = data.get("filename", "pattern") + ".png"

    try:
        doc = parse(source)
        png_bytes = compile_document(doc).to_png_bytes()
        return send_file(
            io.BytesIO(png_bytes),
            mimetype="image/png",
            as_attachment=True,
            download_name=filename,
        )
    except DslError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": f"Internal error: {exc}"}), 500


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="leathercraft_server",
        description="Web editor for .lcraft pattern files.",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Bind address (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=5000,
        help="Port to listen on (default: 5000)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable Flask debug mode (auto-reload on file change)",
    )
    args = parser.parse_args(argv)

    url = f"http://{args.host}:{args.port}"
    print(f"leathercraft editor  →  {url}")
    app.run(host=args.host, port=args.port, debug=args.debug)


if __name__ == "__main__":
    main()
