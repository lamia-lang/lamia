"""Tests for lamia inspect CLI — executable step detection."""

import pytest

from lamia.cli.inspect_cli import (
    has_top_level_steps,
    get_executable_lines,
    _analyze,
    _check_duplicate_functions,
    _check_cross_file_duplicates,
)


class TestHasTopLevelSteps:
    def test_file_with_top_level_function_call(self):
        source = "\n".join([
            "def submit_order(order):",
            "    return 'submitted'",
            "",
            "def buy_winner_stock():",
            "    submit_order('AAPL')",
            "",
            "buy_winner_stock()",
        ])
        assert has_top_level_steps(source) is True

    def test_file_with_commented_out_call(self):
        source = "\n".join([
            "def submit_order(order):",
            "    return 'submitted'",
            "",
            "def buy_winner_stock():",
            "    submit_order('AAPL')",
            "",
            "#buy_winner_stock()",
        ])
        assert has_top_level_steps(source) is False

    def test_file_with_for_loop_at_top_level(self):
        source = "\n".join([
            "def stock_data(ticker):",
            "    pass",
            "",
            "tickers = ['AAPL', 'NVDA']",
            "for ticker in tickers:",
            "    stock_data(ticker)",
        ])
        assert has_top_level_steps(source) is True

    def test_file_with_with_block_at_top_level(self):
        source = "\n".join([
            "def fetch_data():",
            "    pass",
            "",
            "with open('output.txt') as f:",
            "    f.write('hello')",
        ])
        assert has_top_level_steps(source) is True

    def test_file_with_only_definitions(self):
        source = "\n".join([
            "import os",
            "from pathlib import Path",
            "",
            "def submit_order(order):",
            "    return 'submitted'",
            "",
            "class Order:",
            "    pass",
        ])
        assert has_top_level_steps(source) is False

    def test_empty_file(self):
        assert has_top_level_steps("") is False

    def test_file_with_only_imports(self):
        source = "\n".join([
            "import os",
            "from sys import argv",
        ])
        assert has_top_level_steps(source) is False

    def test_print_call_at_top_level(self):
        source = "\n".join([
            "def helper():",
            "    return 42",
            "",
            "print('hello')",
        ])
        assert has_top_level_steps(source) is True

    def test_while_loop(self):
        source = "while True:\n    pass"
        assert has_top_level_steps(source) is True

    def test_if_block_at_top_level(self):
        source = "\n".join([
            "def main():",
            "    pass",
            "",
            "if __name__ == '__main__':",
            "    main()",
        ])
        assert has_top_level_steps(source) is True

    def test_syntax_error_returns_false(self):
        source = "data = './users.json' -> JSON:"
        assert has_top_level_steps(source) is False

    def test_only_async_def_no_call(self):
        source = "\n".join([
            "import asyncio",
            "",
            "async def main():",
            "    await asyncio.sleep(1)",
        ])
        assert has_top_level_steps(source) is False


class TestGetExecutableLines:
    def test_returns_line_numbers_of_steps(self):
        source = "\n".join([
            "def helper():",
            "    pass",
            "",
            "print('start')",
            "for x in [1, 2]:",
            "    helper()",
        ])
        lines = get_executable_lines(source)
        assert 4 in lines
        assert 5 in lines

    def test_empty_file(self):
        assert get_executable_lines("") == []

    def test_definitions_only(self):
        source = "\n".join([
            "import os",
            "def foo():",
            "    pass",
        ])
        assert get_executable_lines(source) == []

    def test_invalid_syntax_returns_empty(self):
        source = '"prompt" -> File(HTML, "out.html"):'
        assert get_executable_lines(source) == []


class TestPlaygroundFilesExecutable:
    """Tests using actual playground .lm file content to verify executability."""

    def test_basic_file_context(self):
        source = (
            'def answer_question(question="What are my main skills?"):\n'
            '    """\n'
            '    Answer: {question}\n'
            '\n'
            '    Use information from {@resume.pdf} and {@cover_letter.txt}\n'
            '    """\n'
            '\n'
            'with files("~/Documents/", "~/projects/"):\n'
            '    answer = answer_question(question="What are my main skills?")\n'
            '    print(answer)\n'
        )
        assert has_top_level_steps(source) is True

    def test_hello_greet(self):
        source = (
            "def greet():\n"
            '    "Write a short, friendly greeting for a new Lamia user"\n'
            "\n"
            "result = greet()\n"
            "print(result)"
        )
        assert has_top_level_steps(source) is True

    def test_draft_email_caller(self):
        source = (
            'email = draft_email(recipient="the team")\n'
            "print(email)\n"
            "\n"
            'email_formal = draft_email(recipient="the team", tone="formal", topic="Q3 results")\n'
            "print(email_formal)"
        )
        assert has_top_level_steps(source) is True

    def test_file_read(self):
        source = (
            "def read_data():\n"
            '    "./data/input.txt"\n'
            "\n"
            "def load_settings() -> JSON:\n"
            '    "../config/settings.json"\n'
            "\n"
            "def read_logs():\n"
            '    "/var/log/application.log"\n'
            "\n"
            'print(file.read("data.csv", encoding="latin-1"))\n'
            "print(load_settings())\n"
            "print(read_data())\n"
        )
        assert has_top_level_steps(source) is True

    def test_ai_selectors(self):
        source = (
            'web.navigate("https://example.com")\n'
            "\n"
            'web.click("Sign in button")\n'
            'web.type_text("Search input field", "lamia framework")\n'
            'web.wait_for("Loading spinner", "hidden")'
        )
        assert has_top_level_steps(source) is True

    def test_json_model_validation(self):
        source = (
            "class UserProfile(BaseModel):\n"
            "    name: str\n"
            "    age: int\n"
            "    email: str\n"
            "\n"
            "def get_user() -> JSON[UserProfile]:\n"
            '    "Generate a user profile"\n'
            "\n"
            "user = get_user()\n"
            'print(f"Name: {user.name}, Age: {user.age}, Email: {user.email}")'
        )
        assert has_top_level_steps(source) is True

    def test_orchestrator_pattern(self):
        source = (
            "class PRD(BaseModel):\n"
            "    title: str\n"
            "    requirements: str\n"
            "\n"
            "class Implementation(BaseModel):\n"
            "    code: str\n"
            "    tests: str\n"
            "\n"
            "class Review(BaseModel):\n"
            "    approved: bool\n"
            "    findings: str\n"
            "\n"
            'brief = "Build a REST API for todo items with CRUD operations"\n'
            "\n"
            "prd = product_manager(brief=brief) -> JSON[PRD]\n"
            "code = developer(specs=prd) -> JSON[Implementation]\n"
            "review = reviewer(code=code, specs=prd) -> JSON[Review]\n"
            "\n"
            "if not review.approved:\n"
            "    code = developer(specs=prd, feedback=review.findings) -> JSON[Implementation]\n"
            "\n"
            'print(f"PRD: {prd.title}")\n'
            'print(f"Review approved: {review.approved}")'
        )
        assert has_top_level_steps(source) is True

    def test_file_output(self):
        source = '"small html" -> File(HTML, "landing.html")'
        assert has_top_level_steps(source) is True

    def test_mixed_vars_and_files(self):
        source = (
            'with files("~/Documents/"):\n'
            "    def answer_question(question, company, models=\"openai:gpt-4\"):\n"
            '        """\n'
            "        Answer this {company} job application question: {question}\n"
            "\n"
            "        Use {@resume.pdf} for background information.\n"
            '        """\n'
            "\n"
            'answer = answer_question(question="Why do you want to work here?", company="Acme Corp")\n'
            "print(answer)"
        )
        assert has_top_level_steps(source) is True

    def test_web_full_actions(self):
        source = (
            'web.navigate("https://example.com")\n'
            "\n"
            'web.click("#login-button")\n'
            'web.type_text("#username", "user@example.com")\n'
            'web.hover(".dropdown-menu")\n'
            "\n"
            'text = web.get_text(".result")\n'
            'visible = web.is_visible(".modal")\n'
            'enabled = web.is_enabled("button.submit")\n'
            "\n"
            'web.wait_for(".loading", "hidden")\n'
            'web.scroll_to("#footer")\n'
            "\n"
            'web.select_option("#country", "US")\n'
            'web.submit_form("#login-form")\n'
            "\n"
            'web.screenshot("page.png")'
        )
        assert has_top_level_steps(source) is True

    def test_review_code_caller(self):
        source = (
            "class ReviewResult(BaseModel):\n"
            '    findings: str = Field(description="List of issues found")\n'
            '    severity: str = Field(description="Overall severity: low, medium, high")\n'
            "\n"
            'with files("./"):\n'
            '    result = review_code(language="python", source_file="orchestrator_pattern.lm") -> JSON[ReviewResult]\n'
            '    print(f"Severity: {result.severity}")\n'
            "    print(result.findings)"
        )
        assert has_top_level_steps(source) is True


class TestPlaygroundFilesNonExecutable:
    """Tests for files correctly identified as non-executable."""

    def test_async_parallel_definitions_only(self):
        source = (
            "import asyncio\n"
            "\n"
            "async def get_weather() -> JSON:\n"
            '    "https://api.weather.com/current"\n'
            "\n"
            "async def read_config() -> JSON:\n"
            '    "./config.json"\n'
            "\n"
            "async def fetch_webpage() -> HTML:\n"
            '    "https://news.example.com"\n'
            "\n"
            "async def main():\n"
            "    results = await asyncio.gather(\n"
            "        get_weather(),\n"
            "        read_config(),\n"
            "        fetch_webpage()\n"
            "    )"
        )
        assert has_top_level_steps(source) is False

    def test_interpreter_complete_workflow_definitions_only(self):
        source = (
            "import asyncio\n"
            "\n"
            "def load_user_data() -> JSON:\n"
            '    "./users.json"\n'
            "\n"
            "def fetch_external_data() -> JSON:\n"
            '    "https://api.example.com/data"\n'
            "\n"
            "def create_user_report():\n"
            "    '''\n"
            "    Generate a detailed user activity report including:\n"
            "    - User engagement metrics\n"
            "    - Most active features\n"
            "    - Recommendations for improvement\n"
            "    '''\n"
            "\n"
            "def generate_dashboard() -> HTML:\n"
            '    "Create an admin dashboard with user statistics and charts"\n'
            "\n"
            "async def generate_admin_content():\n"
            "    user_data, external_data = await asyncio.gather(\n"
            "        load_user_data(),\n"
            "        fetch_external_data()\n"
            "    )\n"
            "\n"
            "    report = await create_user_report()\n"
            "    dashboard = await generate_dashboard()\n"
            "\n"
            "    return report, dashboard"
        )
        assert has_top_level_steps(source) is False


class TestBatchInspect:
    """Tests for the batch inspection path (_inspect_batch)."""

    def test_batch_mixed_valid_and_invalid(self, tmp_path):
        valid = tmp_path / "valid.lm"
        valid.write_text("result = greet()\nprint(result)")

        invalid = tmp_path / "invalid.lm"
        invalid.write_text('data = "./x.json" -> JSON:')

        defs_only = tmp_path / "defs.lm"
        defs_only.write_text("def foo():\n    pass")

        missing = tmp_path / "missing.lm"

        from lamia.cli.inspect_cli import _inspect_batch
        import io
        from contextlib import redirect_stdout

        buf = io.StringIO()
        with redirect_stdout(buf):
            _inspect_batch(
                [str(valid), str(invalid), str(defs_only), str(missing)],
                as_json=True,
            )

        import json
        output = json.loads(buf.getvalue())
        results = output["results"]

        assert results[str(valid)]["executable"] is True
        assert results[str(invalid)]["executable"] is False
        assert results[str(defs_only)]["executable"] is False
        assert results[str(missing)]["executable"] is False
        assert results[str(missing)]["error"] == "file not found"


class TestPlaygroundFilesSyntaxErrors:
    """Files with unsupported syntax are correctly marked non-executable."""

    def test_simplified_syntax_trailing_colon(self):
        source = (
            'data = "./users.json" -> JSON:\n'
            "\n"
            'page = "Create a login form" -> HTML:\n'
            "\n"
            'summary = "Write a summary" -> TEXT:\n'
            "\n"
            "print(summary)"
        )
        assert has_top_level_steps(source) is False

    def test_file_write_to_disk_trailing_colon(self):
        source = (
            '"./users.json" -> File(JSON, "users.json")\n'
            "\n"
            '"Create a login form" -> File(HTML, "login.html")\n'
            "\n"
            '"Write a summary" -> File(TEXT, "summary.txt")'
        )
        # This syntax is valid and represents top-level executable file writes.
        assert has_top_level_steps(source) is True

    def test_lm_style_file_ops_trailing_colon(self):
        source = (
            '"Create a landing page" -> File(HTML, "index.html"):\n'
            '"Generate test data" -> File(CSV, "fixtures.csv"):\n'
            "\n"
            'in_memory = "Generate test data" -> File(CSV, "fixtures_copy.csv"):\n'
            "print(in_memory)"
        )
        assert has_top_level_steps(source) is False


class TestDiagnosticsOutput:
    """Tests for the diagnostics field returned by _analyze."""

    def test_valid_source_has_empty_diagnostics(self):
        result = _analyze("x = 1\nprint(x)")
        assert result.diagnostics == []
        assert result.executable is True

    def test_syntax_error_returns_diagnostic_with_line_and_message(self):
        result = _analyze("def foo(\n")
        assert result.executable is False
        assert len(result.diagnostics) == 1
        diag = result.diagnostics[0]
        assert diag["severity"] == "error"
        assert diag["line"] >= 1
        assert "message" in diag
        assert diag["source"] in ("lamia-parser", "lamia-ast")

    def test_syntax_error_diagnostic_has_col(self):
        result = _analyze("x = (1 +\n")
        assert len(result.diagnostics) == 1
        diag = result.diagnostics[0]
        assert "col" in diag
        assert isinstance(diag["col"], int)

    def test_lamia_specific_syntax_error(self):
        source = 'data = "./users.json" -> JSON:'
        result = _analyze(source)
        assert result.executable is False
        assert len(result.diagnostics) >= 1
        assert result.diagnostics[0]["severity"] == "error"

    def test_multiple_errors_stop_at_first(self):
        source = "def (\ndef (\n"
        result = _analyze(source)
        assert result.executable is False
        assert len(result.diagnostics) == 1

    def test_definitions_only_no_diagnostics(self):
        source = "def foo():\n    pass\n\ndef bar():\n    pass"
        result = _analyze(source)
        assert result.executable is False
        assert result.diagnostics == []

    def test_batch_includes_diagnostics_per_file(self, tmp_path):
        good = tmp_path / "good.lm"
        good.write_text("print('hello')")

        bad = tmp_path / "bad.lm"
        bad.write_text("def foo(\n")

        from lamia.cli.inspect_cli import _inspect_batch
        import io
        import json
        from contextlib import redirect_stdout

        buf = io.StringIO()
        with redirect_stdout(buf):
            _inspect_batch([str(good), str(bad)], as_json=True)

        output = json.loads(buf.getvalue())
        results = output["results"]

        assert "diagnostics" not in results[str(good)]
        assert len(results[str(bad)]["diagnostics"]) == 1
        assert results[str(bad)]["diagnostics"][0]["severity"] == "error"


class TestSemanticDiagnostics:
    """Tests for cross-file call validation and inline def mismatch."""

    def test_missing_required_arg_detected(self, tmp_path):
        hu_file = tmp_path / "greet.hu"
        hu_file.write_text("Hello {name}, welcome to {company}!")

        lm_file = tmp_path / "caller.lm"
        lm_file.write_text('greet(name="Alice")\n')

        with open(str(lm_file)) as f:
            source = f.read()
        result = _analyze(source, str(lm_file))

        errors = [d for d in result.diagnostics if d["severity"] == "error"]
        assert len(errors) == 1
        assert "company" in errors[0]["message"]
        assert "missing required" in errors[0]["message"]

    def test_all_args_provided_no_error(self, tmp_path):
        hu_file = tmp_path / "greet.hu"
        hu_file.write_text("Hello {name}, welcome to {company}!")

        lm_file = tmp_path / "caller.lm"
        lm_file.write_text('greet(name="Alice", company="Acme")\n')

        with open(str(lm_file)) as f:
            source = f.read()
        result = _analyze(source, str(lm_file))

        errors = [d for d in result.diagnostics if d["severity"] == "error"]
        assert len(errors) == 0

    def test_unresolved_function_flagged(self, tmp_path):
        lm_file = tmp_path / "caller.lm"
        lm_file.write_text('nonexistent_func(x="1")\n')

        with open(str(lm_file)) as f:
            source = f.read()
        result = _analyze(source, str(lm_file))

        errors = [d for d in result.diagnostics if d["severity"] == "error"]
        assert len(errors) == 1
        assert "Unresolved function" in errors[0]["message"]
        assert "nonexistent_func" in errors[0]["message"]

    def test_inline_def_template_mismatch(self, tmp_path):
        lm_file = tmp_path / "defs.lm"
        lm_file.write_text(
            'def summarize(aspect) -> HTML:\n'
            '    "Focus on {aspect} under {max_words:200} words about {@doc}"\n'
        )

        with open(str(lm_file)) as f:
            source = f.read()
        result = _analyze(source, str(lm_file))

        warnings = [d for d in result.diagnostics if d["severity"] == "warning"]
        assert len(warnings) == 1
        assert "max_words" in warnings[0]["message"]
        assert "doc" in warnings[0]["message"]

    def test_inline_def_typed_params_reports_dedicated_warning(self, tmp_path):
        lm_file = tmp_path / "typed.lm"
        lm_file.write_text(
            "def generate_report(data: dict, style: str):\n"
            '    "Create a {style} report based on: {data}"\n'
            '\n'
            'report = generate_report(data={"sales": 100, "returns": 5}, style="executive")\n'
            "print(report)\n"
        )

        source = lm_file.read_text()
        result = _analyze(source, str(lm_file))

        typed = [d for d in result.diagnostics if "uses typed parameters" in d["message"]]
        missing = [
            d for d in result.diagnostics
            if "placeholders not present in function params" in d["message"]
        ]

        assert len(typed) == 1
        assert typed[0]["severity"] == "error"
        assert "data" in typed[0]["message"]
        assert "style" in typed[0]["message"]
        assert "untyped params" in typed[0]["message"]
        assert len(missing) == 0

    def test_inline_def_missing_placeholders_keeps_missing_message(self, tmp_path):
        lm_file = tmp_path / "missing.lm"
        lm_file.write_text(
            "def generate_report(data, style):\n"
            '    "Create a {style} report based on: {data} and {region}"\n'
        )

        source = lm_file.read_text()
        result = _analyze(source, str(lm_file))

        warnings = [d for d in result.diagnostics if d["severity"] == "warning"]
        missing = [d for d in warnings if "placeholders not present in function params" in d["message"]]

        assert len(missing) == 1
        assert "region" in missing[0]["message"]

    def test_local_def_not_flagged_as_unresolved(self, tmp_path):
        lm_file = tmp_path / "local.lm"
        lm_file.write_text(
            'def helper():\n'
            '    "Do something"\n'
            '\n'
            'helper()\n'
        )

        with open(str(lm_file)) as f:
            source = f.read()
        result = _analyze(source, str(lm_file))

        errors = [d for d in result.diagnostics if d["severity"] == "error"]
        assert len(errors) == 0

    def test_builtins_not_flagged(self, tmp_path):
        lm_file = tmp_path / "builtins.lm"
        lm_file.write_text('print("hello")\nresult = len([1,2,3])\n')

        with open(str(lm_file)) as f:
            source = f.read()
        result = _analyze(source, str(lm_file))

        errors = [d for d in result.diagnostics if d["severity"] == "error"]
        assert len(errors) == 0

    def test_lamia_keywords_not_flagged(self, tmp_path):
        lm_file = tmp_path / "keywords.lm"
        lm_file.write_text(
            'with files("~/docs/"):\n'
            '    with session("my_sess"):\n'
            '        result = File(JSON, "out.json")\n'
        )

        with open(str(lm_file)) as f:
            source = f.read()
        result = _analyze(source, str(lm_file))

        errors = [d for d in result.diagnostics if d["severity"] == "error"]
        assert len(errors) == 0

    def test_commented_lines_not_checked(self, tmp_path):
        hu_file = tmp_path / "greet.hu"
        hu_file.write_text("Hello {name}!")

        lm_file = tmp_path / "caller.lm"
        lm_file.write_text('#greet()\nprint("ok")\n')

        with open(str(lm_file)) as f:
            source = f.read()
        result = _analyze(source, str(lm_file))

        errors = [d for d in result.diagnostics if "greet" in d.get("message", "")]
        assert len(errors) == 0


class TestDuplicateFunctionDetection:

    def test_intra_file_duplicate_flagged(self):
        source = (
            'def add_rows():\n'
            '    "Generate CSV rows"\n'
            '\n'
            'def add_rows():\n'
            '    "Add rand row"\n'
        )
        diags = _check_duplicate_functions(source)
        assert len(diags) == 1
        assert diags[0]["severity"] == "error"
        assert "Duplicate function 'add_rows'" in diags[0]["message"]
        assert "line 1" in diags[0]["message"]
        assert diags[0]["line"] == 4

    def test_no_duplicate_no_diagnostic(self):
        source = (
            'def foo():\n'
            '    "do foo"\n'
            '\n'
            'def bar():\n'
            '    "do bar"\n'
        )
        diags = _check_duplicate_functions(source)
        assert len(diags) == 0

    def test_triple_duplicate_two_diagnostics(self):
        source = (
            'def f():\n    pass\n\n'
            'def f():\n    pass\n\n'
            'def f():\n    pass\n'
        )
        diags = _check_duplicate_functions(source)
        assert len(diags) == 2

    def test_intra_file_via_analyze(self):
        source = (
            'def greet():\n'
            '    "Hello"\n'
            '\n'
            'def greet():\n'
            '    "Hi"\n'
            '\n'
            'greet()\n'
        )
        result = _analyze(source)
        dup_diags = [d for d in result.diagnostics if "Duplicate function" in d.get("message", "")]
        assert len(dup_diags) == 1

    def test_cross_file_duplicate_flagged(self, tmp_path):
        other = tmp_path / "other.lm"
        other.write_text('def shared_fn():\n    "do stuff"\n')

        current = tmp_path / "current.lm"
        source = 'def shared_fn():\n    "do other stuff"\n'
        current.write_text(source)

        diags = _check_cross_file_duplicates(source, str(current))
        assert len(diags) == 1
        assert diags[0]["severity"] == "warning"
        assert "shared_fn" in diags[0]["message"]
        assert "other.lm" in diags[0]["message"]

    def test_cross_file_no_collision(self, tmp_path):
        other = tmp_path / "other.lm"
        other.write_text('def helper():\n    "help"\n')

        current = tmp_path / "current.lm"
        source = 'def unique_fn():\n    "unique"\n'
        current.write_text(source)

        diags = _check_cross_file_duplicates(source, str(current))
        assert len(diags) == 0
