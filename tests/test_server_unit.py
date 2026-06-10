import pytest

from leathercraft_server import app


@pytest.fixture()
def client():
    app.config.update(TESTING=True)
    with app.test_client() as test_client:
        yield test_client


def test_index_route_serves_existing_editor(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"Leathercraft Editor" in response.data


def test_pyodide_route_serves_browser_editor(client):
    response = client.get("/pyodide")
    assert response.status_code == 200
    assert b"Leathercraft Browser Editor" in response.data
    assert b"pyodide_editor.js" in response.data
    assert b"tutorial.html" in response.data


def test_pyodide_editor_script_is_served(client):
    response = client.get("/pyodide_editor.js")
    assert response.status_code == 200
    assert b"bootstrapPyodide" in response.data


def test_shared_browser_runtime_script_is_served(client):
    response = client.get("/pyodide_runtime.js")
    assert response.status_code == 200
    assert b"createPyodideCompiler" in response.data


def test_tutorial_routes_are_served(client):
    html_response = client.get("/tutorial.html")
    assert html_response.status_code == 200
    assert b"Learn .lcraft in the Browser" in html_response.data
    assert b"tutorial.js" in html_response.data

    js_response = client.get("/tutorial.js")
    assert js_response.status_code == 200
    assert b"tutorialSamples" in js_response.data


def test_python_sources_are_served_for_browser_mode(client):
    for route, expected in (
        ("/leathercraft_svg.py", b"class SvgDocument"),
        ("/leathercraft_dsl.py", b"def compile_document"),
    ):
        response = client.get(route)
        assert response.status_code == 200
        assert expected in response.data


def test_compile_api_still_works(client):
    response = client.post(
        "/api/compile",
        json={"source": "pattern x\nsize 10 10\n"},
    )
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["error"] is None
    assert payload["svg"] is not None
