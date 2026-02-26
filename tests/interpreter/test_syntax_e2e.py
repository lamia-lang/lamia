"""End-to-end tests for all Lamia .hu syntax variants.

Tests the REAL pipeline with real HTTP servers:

    .hu source → preprocess → detect → transform → exec → lamia.run()
    → engine → managers → adapters → HTTP servers → validators → result

Web tests use a real headless Chrome navigating to a local HTTP server.
LLM tests use the real LLM pipeline calling a local mock OpenAI-compatible server.

The ONLY mock is the LLM HTTP server itself.  The adapter that talks to it
(``MockServerLLMAdapter``) makes real ``aiohttp`` network calls.

Categories
----------
A.  LLM function syntax      — ``def f() -> Type: "prompt"``
B.  LLM expression syntax    — ``"prompt" -> Type``
C.  Web function syntax       — ``def f() -> Type: "url"``       (integration)
D.  Web expression syntax     — ``"url" -> Type``                 (integration)
E.  Documentation / edge cases — return statements, params, etc.
"""

import http.server
import json
import os
import pytest
import shutil
import tempfile
import threading
from typing import Optional

import aiohttp
from pydantic import BaseModel

from lamia import LLMModel
from lamia.adapters.llm.base import BaseLLMAdapter, LLMResponse
from lamia.async_bridge import EventLoopManager
from lamia.facade.lamia import Lamia
from lamia.interpreter.command_types import CommandType
from lamia.interpreter.hybrid_executor import HybridExecutor


# ---------------------------------------------------------------------------
# Test HTML constants
# ---------------------------------------------------------------------------

WEB_HTML = "<html><body><h1>Hello</h1><p>World</p></body></html>"
LLM_HTML = "<html><body><h1>Cats</h1><p>Cats are great</p></body></html>"


# ---------------------------------------------------------------------------
# Mock LLM adapter — real aiohttp calls to the mock LLM HTTP server
# ---------------------------------------------------------------------------

class MockServerLLMAdapter(BaseLLMAdapter):
    """Adapter that makes *real* HTTP calls to a local mock LLM server."""

    def __init__(self, base_url: str):
        self._base_url = base_url
        self._session: Optional[aiohttp.ClientSession] = None

    @classmethod
    def name(cls) -> str:
        return "mock-llm"

    @classmethod
    def env_var_names(cls) -> list[str]:
        return []

    @classmethod
    def is_remote(cls) -> bool:
        return False

    async def async_initialize(self) -> None:
        self._session = aiohttp.ClientSession()

    async def generate(self, prompt: str, model: LLMModel) -> LLMResponse:
        assert self._session is not None
        url = f"{self._base_url}/v1/chat/completions"
        payload = {
            "model": model.name,
            "messages": [{"role": "user", "content": prompt}],
        }
        async with self._session.post(url, json=payload) as resp:
            data = await resp.json()
            return LLMResponse(
                text=data["choices"][0]["message"]["content"],
                raw_response=data,
                model=model.name,
                usage=data.get("usage", {
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": 0,
                }),
            )

    async def close(self) -> None:
        if self._session:
            await self._session.close()


# ---------------------------------------------------------------------------
# HTTP servers
# ---------------------------------------------------------------------------

class _HTMLHandler(http.server.BaseHTTPRequestHandler):
    """Serves ``WEB_HTML`` at any path."""

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(WEB_HTML.encode())

    def log_message(self, format, *args):  # noqa: A002
        pass


class _LLMHandler(http.server.BaseHTTPRequestHandler):
    """Serves OpenAI-compatible chat-completion responses with ``LLM_HTML``."""

    def do_POST(self):
        content_len = int(self.headers.get("Content-Length", 0))
        self.rfile.read(content_len)
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        body = json.dumps({
            "id": "mock-1",
            "object": "chat.completion",
            "choices": [{
                "index": 0,
                "message": {"role": "assistant", "content": LLM_HTML},
                "finish_reason": "stop",
            }],
            "model": "mock-model",
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 20,
                "total_tokens": 30,
            },
        })
        self.wfile.write(body.encode())

    def log_message(self, format, *args):  # noqa: A002
        pass


def _start_server(handler_cls) -> tuple:
    server = http.server.HTTPServer(("127.0.0.1", 0), handler_cls)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, f"http://127.0.0.1:{port}"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def html_server():
    server, url = _start_server(_HTMLHandler)
    yield url
    server.shutdown()


@pytest.fixture(scope="module")
def llm_server():
    server, url = _start_server(_LLMHandler)
    yield url
    server.shutdown()


@pytest.fixture(scope="module")
def lamia_instance(llm_server):
    """Real Lamia with a real adapter that makes real HTTP calls to mock LLM server.

    The only patch: ``LLMManager.create_adapter_from_config`` returns our
    ``MockServerLLMAdapter`` instead of OllamaAdapter.  Everything else —
    engine, command parser, validators, file I/O — is the real production code.
    """
    lamia = Lamia(
        "ollama:test-model",
        web_config={"browser_options": {"headless": True}},
    )

    mock_adapter = MockServerLLMAdapter(llm_server)
    EventLoopManager.run_coroutine(mock_adapter.async_initialize())

    llm_mgr = lamia._engine.manager_factory.get_manager(CommandType.LLM)

    async def _create_adapter(model: LLMModel, with_retries: bool = True) -> BaseLLMAdapter:
        return mock_adapter

    llm_mgr.create_adapter_from_config = _create_adapter  # type: ignore[assignment]

    yield lamia

    EventLoopManager.run_coroutine(mock_adapter.close())
    try:
        EventLoopManager.run_coroutine(lamia._engine.cleanup())
    except Exception:
        pass
    EventLoopManager.shutdown()
    # Prevent Lamia.__del__ from re-creating the event loop during
    # interpreter shutdown (which spawns a daemon thread that can't be joined).
    lamia._engine = None  # type: ignore[assignment]


@pytest.fixture(scope="module")
def executor(lamia_instance):
    return HybridExecutor(lamia_instance)


@pytest.fixture
def tmp_dir():
    d = tempfile.mkdtemp()
    yield d
    shutil.rmtree(d)


@pytest.fixture(autouse=True)
def _reset_stuck_detection(lamia_instance):
    """Clear the WebManager's stuck-detection history between tests."""
    try:
        web_mgr = lamia_instance._engine.manager_factory._manager_instances.get(
            CommandType.WEB
        )
        if web_mgr is not None:
            web_mgr.recent_actions.clear()
    except Exception:
        pass


def _write_hu(tmp_dir: str, code: str, name: str = "test.hu") -> str:
    path = os.path.join(tmp_dir, name)
    with open(path, "w") as f:
        f.write(code)
    return path


# ===========================================================================
# A. LLM FUNCTION SYNTAX — def f() -> Type: "prompt"
# ===========================================================================

class TestLLMFunctionSyntax:
    """Prompt → mock LLM HTTP server → real validator pipeline."""

    def test_html(self, executor, tmp_dir):
        """def f() -> HTML: "prompt"  →  returns raw HTML string."""
        path = _write_hu(tmp_dir, '''
def gen() -> HTML:
    "Generate HTML about cats"

result = gen()
''')
        g: dict = {}
        executor.execute_file(path, g)
        assert "<html>" in g["result"]
        assert "<h1>Cats</h1>" in g["result"]

    def test_html_model(self, executor, tmp_dir):
        """def f() -> HTML[Model]: "prompt"  →  returns parsed Pydantic model."""
        path = _write_hu(tmp_dir, '''
class CatModel(BaseModel):
    h1: str
    p: str

def gen() -> HTML[CatModel]:
    "Generate HTML about cats"

result = gen()
''')
        g: dict = {}
        executor.execute_file(path, g)
        assert g["result"].h1 == "Cats"
        assert g["result"].p == "Cats are great"

    def test_file_write(self, executor, tmp_dir):
        """def f() -> File(HTML, "path"): "prompt"  →  writes HTML to file."""
        out = os.path.join(tmp_dir, "llm_out.html")
        path = _write_hu(tmp_dir, f'''
def gen() -> File(HTML, "{out}"):
    "Generate HTML about cats"

gen()
''')
        executor.execute_file(path)
        with open(out) as f:
            content = f.read()
        assert "<h1>Cats</h1>" in content

    def test_file_write_typed(self, executor, tmp_dir):
        """def f() -> File(HTML[M], "path"): "prompt"  →  validates + writes raw HTML."""
        out = os.path.join(tmp_dir, "llm_typed.html")
        path = _write_hu(tmp_dir, f'''
class CatModel(BaseModel):
    h1: str
    p: str

def gen() -> File(HTML[CatModel], "{out}"):
    "Generate HTML about cats"

result = gen()
''')
        g: dict = {}
        executor.execute_file(path, g)
        with open(out) as f:
            content = f.read()
        assert "<h1>Cats</h1>" in content
        assert g["result"].h1 == "Cats"


# ===========================================================================
# B. LLM EXPRESSION SYNTAX — "prompt" -> Type
# ===========================================================================

class TestLLMExpressionSyntax:
    """Expression-level arrow syntax with LLM prompts."""

    def test_html(self, executor, tmp_dir):
        path = _write_hu(tmp_dir, '"Generate HTML about cats" -> HTML')
        executor.execute_file(path)

    def test_html_assigned(self, executor, tmp_dir):
        """result = "prompt" -> HTML  assigns raw HTML text to variable."""
        path = _write_hu(tmp_dir, '''
result = "Generate HTML about cats" -> HTML
''')
        g: dict = {}
        executor.execute_file(path, g)
        assert "<html>" in g["result"]
        assert "<h1>Cats</h1>" in g["result"]

    def test_html_model(self, executor, tmp_dir):
        path = _write_hu(tmp_dir, '''
class CatModel(BaseModel):
    h1: str
    p: str

"Generate HTML about cats" -> HTML[CatModel]
''')
        executor.execute_file(path)

    def test_html_model_assigned(self, executor, tmp_dir):
        """result = "prompt" -> HTML[Model]  assigns parsed model to variable."""
        path = _write_hu(tmp_dir, '''
class CatModel(BaseModel):
    h1: str
    p: str

result = "Generate HTML about cats" -> HTML[CatModel]
''')
        g: dict = {}
        executor.execute_file(path, g)
        assert g["result"].h1 == "Cats"
        assert g["result"].p == "Cats are great"

    def test_file_write(self, executor, tmp_dir):
        out = os.path.join(tmp_dir, "llm_expr.html")
        path = _write_hu(tmp_dir, f'"Generate HTML about cats" -> File(HTML, "{out}")')
        executor.execute_file(path)
        with open(out) as f:
            assert "<h1>Cats</h1>" in f.read()

    def test_file_write_typed(self, executor, tmp_dir):
        out = os.path.join(tmp_dir, "llm_expr_typed.html")
        path = _write_hu(tmp_dir, f'''
class CatModel(BaseModel):
    h1: str
    p: str

"Generate HTML about cats" -> File(HTML[CatModel], "{out}")
''')
        executor.execute_file(path)
        with open(out) as f:
            assert "<h1>Cats</h1>" in f.read()


# ===========================================================================
# C. WEB FUNCTION SYNTAX — def f() -> Type: "url"  (needs Chrome)
# ===========================================================================

@pytest.mark.integration
class TestWebFunctionSyntax:
    """URL string body → real Selenium navigation → local HTML server."""

    def test_html(self, executor, html_server, tmp_dir):
        path = _write_hu(tmp_dir, f'''
def get_page() -> HTML:
    "{html_server}"

result = get_page()
''')
        g: dict = {}
        executor.execute_file(path, g)
        assert "<h1>Hello</h1>" in g["result"]

    def test_html_model(self, executor, html_server, tmp_dir):
        path = _write_hu(tmp_dir, f'''
class PageModel(BaseModel):
    h1: str
    p: str

def get_page() -> HTML[PageModel]:
    "{html_server}"

result = get_page()
''')
        g: dict = {}
        executor.execute_file(path, g)
        assert g["result"].h1 == "Hello"
        assert g["result"].p == "World"

    def test_file_write(self, executor, html_server, tmp_dir):
        out = os.path.join(tmp_dir, "web_out.html")
        path = _write_hu(tmp_dir, f'''
def get_page() -> File(HTML, "{out}"):
    "{html_server}"

get_page()
''')
        executor.execute_file(path)
        with open(out) as f:
            assert "<h1>Hello</h1>" in f.read()

    def test_file_write_typed(self, executor, html_server, tmp_dir):
        out = os.path.join(tmp_dir, "web_typed.html")
        path = _write_hu(tmp_dir, f'''
class PageModel(BaseModel):
    h1: str
    p: str

def get_page() -> File(HTML[PageModel], "{out}"):
    "{html_server}"

result = get_page()
''')
        g: dict = {}
        executor.execute_file(path, g)
        with open(out) as f:
            assert "<h1>Hello</h1>" in f.read()
        assert g["result"].h1 == "Hello"


# ===========================================================================
# D. WEB EXPRESSION SYNTAX — "url" -> Type  (needs Chrome)
# ===========================================================================

@pytest.mark.integration
class TestWebExpressionSyntax:
    """Expression-level arrow syntax with URL strings — real browser."""

    def test_html(self, executor, html_server, tmp_dir):
        path = _write_hu(tmp_dir, f'"{html_server}" -> HTML')
        executor.execute_file(path)

    def test_html_assigned(self, executor, html_server, tmp_dir):
        """result = "url" -> HTML  assigns raw HTML text to variable."""
        path = _write_hu(tmp_dir, f'''
result = "{html_server}" -> HTML
''')
        g: dict = {}
        executor.execute_file(path, g)
        assert "<h1>Hello</h1>" in g["result"]

    def test_html_model(self, executor, html_server, tmp_dir):
        path = _write_hu(tmp_dir, f'''
class PageModel(BaseModel):
    h1: str
    p: str

"{html_server}" -> HTML[PageModel]
''')
        executor.execute_file(path)

    def test_html_model_assigned(self, executor, html_server, tmp_dir):
        """result = "url" -> HTML[Model]  assigns parsed model to variable."""
        path = _write_hu(tmp_dir, f'''
class PageModel(BaseModel):
    h1: str
    p: str

result = "{html_server}" -> HTML[PageModel]
''')
        g: dict = {}
        executor.execute_file(path, g)
        assert g["result"].h1 == "Hello"
        assert g["result"].p == "World"

    def test_file_write(self, executor, html_server, tmp_dir):
        out = os.path.join(tmp_dir, "web_expr.html")
        path = _write_hu(tmp_dir, f'"{html_server}" -> File(HTML, "{out}")')
        executor.execute_file(path)
        with open(out) as f:
            assert "<h1>Hello</h1>" in f.read()

    def test_file_write_typed(self, executor, html_server, tmp_dir):
        out = os.path.join(tmp_dir, "web_expr_typed.html")
        path = _write_hu(tmp_dir, f'''
class PageModel(BaseModel):
    h1: str
    p: str

"{html_server}" -> File(HTML[PageModel], "{out}")
''')
        executor.execute_file(path)
        with open(out) as f:
            assert "<h1>Hello</h1>" in f.read()


# ===========================================================================
# E. DOCUMENTATION / EDGE CASES
# ===========================================================================

class TestDocumentationSyntax:
    """Edge cases documenting when Lamia transforms vs. leaves Python alone."""

    def test_return_statement_stays_python(self, executor, tmp_dir):
        """``def f(): return "value"`` → regular Python, lamia.run() never called."""
        path = _write_hu(tmp_dir, '''
def greet():
    return "hello"

result = greet()
''')
        g: dict = {}
        executor.execute_file(path, g)
        assert g["result"] == "hello"

    def test_annotated_return_stays_python(self, executor, tmp_dir):
        """``def f() -> str: return "value"`` → annotation + return = Python."""
        path = _write_hu(tmp_dir, '''
def greet() -> str:
    return "hello"

result = greet()
''')
        g: dict = {}
        executor.execute_file(path, g)
        assert g["result"] == "hello"

    def test_no_return_type_string_body_is_llm(self, executor, tmp_dir):
        """``def f(): "prompt"`` → no return type, string body = LLM, returns None."""
        path = _write_hu(tmp_dir, '''
def ask():
    "Tell me a joke"

result = ask()
''')
        g: dict = {}
        executor.execute_file(path, g)
        assert g["result"] is None

    def test_parameter_substitution(self, executor, tmp_dir):
        """``def f(x): "Write about {x}"`` → parameter is substituted into prompt."""
        path = _write_hu(tmp_dir, '''
def write_about(topic: str) -> HTML:
    "Write about {topic}"

result = write_about("cats")
''')
        g: dict = {}
        executor.execute_file(path, g)
        assert "<html>" in g["result"]

    def test_string_path_routed_as_llm_not_file_read(self, executor, tmp_dir):
        """``def f() -> JSON: "./config.json"`` → sent to LLM, not file system.

        The mock LLM returns HTML which fails JSON validation, proving the
        command was routed through the LLM pipeline.
        """
        path = _write_hu(tmp_dir, '''
def read_config() -> JSON:
    "./config.json"

result = read_config()
''')
        with pytest.raises(ValueError, match="All models failed"):
            executor.execute_file(path)
