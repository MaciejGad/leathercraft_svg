function browserModuleUrl(filename) {
  return new URL(`./${filename}`, window.location.href).toString();
}

async function loadProjectModules(pyodideRuntime) {
  const moduleFiles = ["leathercraft_svg.py", "leathercraft_dsl.py"];
  for (const filename of moduleFiles) {
    const response = await fetch(browserModuleUrl(filename));
    if (!response.ok) {
      throw new Error(`Failed to fetch ${filename}: ${response.status} ${response.statusText}`);
    }
    const source = await response.text();
    pyodideRuntime.FS.writeFile(`/${filename}`, source);
  }
}

async function initializePythonCompiler(pyodideRuntime) {
  await pyodideRuntime.runPythonAsync(`
import json
import sys

if "/" not in sys.path:
    sys.path.insert(0, "/")

from leathercraft_dsl import DslError, compile_document, parse

def compile_lcraft_to_svg(source: str) -> str:
    try:
        doc = parse(source)
        svg = compile_document(doc).to_svg()
        return json.dumps({"svg": svg, "error": None})
    except DslError as exc:
        return json.dumps({"svg": None, "error": str(exc)})
    except Exception as exc:
        return json.dumps({"svg": None, "error": f"Internal error: {exc}"})
`);
}

function createPyodideCompiler() {
  let pyodide = null;
  let ready = false;
  let loadingPromise = null;

  async function compile(source) {
    pyodide.globals.set("browser_source_text", source);
    try {
      const result = await pyodide.runPythonAsync("compile_lcraft_to_svg(browser_source_text)");
      return JSON.parse(result);
    } finally {
      pyodide.globals.delete("browser_source_text");
    }
  }

  async function ensureReady(progressCallback = null) {
    if (ready) return;
    if (loadingPromise) return loadingPromise;
    if (typeof loadPyodide !== "function") {
      throw new Error("Pyodide runtime script is unavailable.");
    }

    loadingPromise = (async () => {
      progressCallback?.("busy", "loading pyodide");
      pyodide = await loadPyodide();
      progressCallback?.("busy", "loading modules");
      await loadProjectModules(pyodide);
      progressCallback?.("busy", "initializing compiler");
      await initializePythonCompiler(pyodide);
      await compile("pattern smoke_test\nsize 10 10\n");
      ready = true;
      progressCallback?.("ready", "ready");
    })();

    try {
      await loadingPromise;
    } finally {
      if (!ready) loadingPromise = null;
    }
  }

  return {
    ensureReady,
    compile,
    isReady() {
      return ready;
    },
  };
}

window.LeathercraftPyodide = {
  browserModuleUrl,
  createPyodideCompiler,
};
