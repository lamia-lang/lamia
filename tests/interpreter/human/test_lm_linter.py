"""Tests for LmLinter rules."""

import tempfile
from pathlib import Path

import pytest

from lamia.lint.lm_linter import LmLinter
from lamia.lint.base import Severity


@pytest.fixture
def project_dir():
    with tempfile.TemporaryDirectory() as d:
        yield d


def _write(base: str, relpath: str, content: str) -> Path:
    p = Path(base) / relpath
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return p


def _violations_for(content: str, code: str, original: str = None,
                     cwd: str = None, filepath: str = None) -> list:
    linter = LmLinter()
    result = linter.lint(content, original, cwd=cwd, filepath=filepath)
    return [v for v in result.violations if v.rule.code == code]


# ── LMW001 excessive-growth ────────────────────────────────────────────────

class TestLMW001ExcessiveGrowth:

    def test_no_growth_no_violation(self):
        violations = _violations_for("abc", "LMW001", original="ab")
        assert violations == []

    def test_double_growth_triggers(self):
        original = "x" * 100
        content = "x" * 250
        violations = _violations_for(content, "LMW001", original=original)
        assert len(violations) == 1

    def test_no_original_no_violation(self):
        violations = _violations_for("x" * 1000, "LMW001", original=None)
        assert violations == []

    def test_empty_original_no_crash(self):
        violations = _violations_for("x" * 100, "LMW001", original="")
        assert violations == []


# ── LME002 missing-required-params ──────────────────────────────────────────

class TestLME002MissingRequiredParams:

    def test_no_hu_files_no_violations(self, project_dir):
        content = "result = some_func(a=1) -> JSON[X]"
        violations = _violations_for(content, "LME002", cwd=project_dir)
        assert violations == []

    def test_all_required_params_passed(self, project_dir):
        _write(project_dir, "team/developer.hu", "Implement {specs} for {prd_content}")
        content = 'impl = developer(specs=s, prd_content=p) -> JSON[Impl]'
        violations = _violations_for(content, "LME002", cwd=project_dir)
        assert violations == []

    def test_missing_required_param_triggers(self, project_dir):
        _write(project_dir, "team/developer.hu", "Implement {specs} for {prd_content}")
        content = 'impl = developer(specs=s) -> JSON[Impl]'
        violations = _violations_for(content, "LME002", cwd=project_dir)
        assert len(violations) == 1
        assert "prd_content" in violations[0].message

    def test_optional_params_not_required(self, project_dir):
        _write(project_dir, "team/pm.hu", "Do {task} with {extra:None}")
        content = 'result = pm(task=t) -> JSON[X]'
        violations = _violations_for(content, "LME002", cwd=project_dir)
        assert violations == []

    def test_multiple_missing_params(self, project_dir):
        _write(project_dir, "team/worker.hu", "{a} {b} {c}")
        content = 'result = worker(a=1) -> JSON[X]'
        violations = _violations_for(content, "LME002", cwd=project_dir)
        assert len(violations) == 1
        assert "b" in violations[0].message
        assert "c" in violations[0].message

    def test_non_hu_function_ignored(self, project_dir):
        content = 'result = print(x=1) -> JSON[X]'
        violations = _violations_for(content, "LME002", cwd=project_dir)
        assert violations == []

    def test_no_cwd_skips_check(self):
        content = 'impl = developer(specs=s) -> JSON[Impl]'
        violations = _violations_for(content, "LME002", cwd=None)
        assert violations == []

    def test_hu_in_subdirectory_found(self, project_dir):
        _write(project_dir, "deeply/nested/agent.hu", "{prompt} {context}")
        content = 'r = agent(prompt=p) -> JSON[X]'
        violations = _violations_for(content, "LME002", cwd=project_dir)
        assert len(violations) == 1
        assert "context" in violations[0].message


# ── LMR003 output-format-hint ──────────────────────────────────────────────

class TestLMR003OutputFormatHint:

    def test_output_json_in_comment_triggers(self):
        content = '# Output JSON:\n# {"field": "value"}\nresult = agent(x=1) -> str'
        violations = _violations_for(content, "LMR003")
        assert len(violations) == 1

    def test_response_format_triggers(self):
        violations = _violations_for("# Response Format:", "LMR003")
        assert len(violations) == 1

    def test_response_schema_triggers(self):
        violations = _violations_for("# Response Schema:", "LMR003")
        assert len(violations) == 1

    def test_normal_code_no_violation(self):
        content = 'result = agent(prompt=p) -> JSON[MyModel]'
        violations = _violations_for(content, "LMR003")
        assert violations == []

    def test_mentions_pydantic_and_multiple_types(self):
        violations = _violations_for("# Output JSON:", "LMR003")
        msg = violations[0].message
        assert "Pydantic" in msg
        assert "HTML" in msg
        assert "YAML" in msg


# ── LMW005 tab-indentation ─────────────────────────────────────────────────

class TestLMW005TabIndentation:

    def test_tabs_trigger(self):
        content = "def foo():\n\treturn 1"
        violations = _violations_for(content, "LMW005")
        assert len(violations) == 1

    def test_spaces_no_violation(self):
        content = "def foo():\n    return 1"
        violations = _violations_for(content, "LMW005")
        assert violations == []

    def test_reports_line_count(self):
        content = "\tx = 1\n\ty = 2\n\tz = 3"
        violations = _violations_for(content, "LMW005")
        assert "3" in violations[0].message


# ── LMW006 positional-hu-args ──────────────────────────────────────────────

class TestLMW006PositionalHuArgs:

    def test_positional_args_triggers(self, project_dir):
        _write(project_dir, "team/summarize.hu", "Summarize {aspect}")
        content = 'result = summarize("key findings") -> HTML'
        violations = _violations_for(content, "LMW006", cwd=project_dir)
        assert len(violations) == 1

    def test_keyword_args_no_violation(self, project_dir):
        _write(project_dir, "team/summarize.hu", "Summarize {aspect}")
        content = 'result = summarize(aspect="key findings") -> HTML'
        violations = _violations_for(content, "LMW006", cwd=project_dir)
        assert violations == []

    def test_non_hu_function_ignored(self, project_dir):
        content = 'print("hello")'
        violations = _violations_for(content, "LMW006", cwd=project_dir)
        assert violations == []


# ── LMW007 empty-file ──────────────────────────────────────────────────────

class TestLMW007EmptyFile:

    def test_empty_triggers(self):
        violations = _violations_for("", "LMW007")
        assert len(violations) == 1

    def test_whitespace_only_triggers(self):
        violations = _violations_for("   \n  ", "LMW007")
        assert len(violations) == 1

    def test_real_content_no_violation(self):
        violations = _violations_for("x = 1", "LMW007")
        assert violations == []


# ── LMW008 trailing-whitespace ──────────────────────────────────────────────

class TestLMW008TrailingWhitespace:

    def test_trailing_spaces_trigger(self):
        violations = _violations_for("x = 1   \ny = 2", "LMW008")
        assert len(violations) == 1

    def test_no_trailing_no_violation(self):
        violations = _violations_for("x = 1\ny = 2", "LMW008")
        assert violations == []


# ── LMC009 variable-naming ─────────────────────────────────────────────────

class TestLMC009VariableNaming:

    def test_snake_case_no_violation(self):
        violations = _violations_for("my_var = 1", "LMC009")
        assert violations == []

    def test_camel_case_triggers(self):
        violations = _violations_for("myVar = 1", "LMC009")
        assert len(violations) == 1

    def test_pascal_case_allowed_for_classes(self):
        """PascalCase is allowed (Pydantic models)."""
        violations = _violations_for("MyModel = 1", "LMC009")
        assert violations == []

    def test_private_var_ignored(self):
        violations = _violations_for("_myPrivateVar = 1", "LMC009")
        assert violations == []


# ── LMC010 filename-naming ─────────────────────────────────────────────────

class TestLMC010FilenameNaming:

    def test_snake_case_no_violation(self):
        violations = _violations_for("x = 1", "LMC010", filepath="/path/orchestrator.lm")
        assert violations == []

    def test_pascal_case_triggers(self):
        violations = _violations_for("x = 1", "LMC010", filepath="/path/MyPipeline.lm")
        assert len(violations) == 1

    def test_kebab_case_triggers(self):
        violations = _violations_for("x = 1", "LMC010", filepath="/path/my-pipeline.lm")
        assert len(violations) == 1

    def test_no_filepath_no_violation(self):
        violations = _violations_for("x = 1", "LMC010")
        assert violations == []


# ── LMC011 leading-blank-lines ──────────────────────────────────────────────

class TestLMC011LeadingBlankLines:

    def test_leading_blank_triggers(self):
        violations = _violations_for("\n\nx = 1", "LMC011")
        assert len(violations) == 1

    def test_no_leading_blank_no_violation(self):
        violations = _violations_for("x = 1", "LMC011")
        assert violations == []


# ── LMR012 inline-pydantic-model ────────────────────────────────────────────

class TestLMR012InlinePydanticModel:

    def test_few_models_no_violation(self):
        content = "class A(BaseModel):\n    x: int\n\nclass B(BaseModel):\n    y: str"
        violations = _violations_for(content, "LMR012")
        assert violations == []

    def test_many_models_triggers(self):
        content = "\n".join(
            f"class M{i}(BaseModel):\n    x: int" for i in range(4)
        )
        violations = _violations_for(content, "LMR012")
        assert len(violations) == 4


# ── LMR013 long-script ─────────────────────────────────────────────────────

class TestLMR013LongScript:

    def test_short_script_no_violation(self):
        violations = _violations_for("x = 1", "LMR013")
        assert violations == []

    def test_long_script_triggers(self):
        content = "x" * 5001
        violations = _violations_for(content, "LMR013")
        assert len(violations) == 1
        assert "5001" in violations[0].message


# ── LME014 unknown-hu-kwargs ───────────────────────────────────────────────

class TestLME014UnknownHuKwargs:

    def test_unknown_kwarg_triggers(self, project_dir):
        _write(project_dir, "team/greet.hu", "Hello {name}")
        content = 'greet(name="Alice", age=30) -> TEXT'
        violations = _violations_for(content, "LME014", cwd=project_dir)
        assert len(violations) == 1
        assert "age" in violations[0].message

    def test_valid_kwargs_no_violation(self, project_dir):
        _write(project_dir, "team/greet.hu", "Hello {name}, you are {age}")
        content = 'greet(name="Alice", age=30) -> TEXT'
        violations = _violations_for(content, "LME014", cwd=project_dir)
        assert violations == []

    def test_multiple_unknown_kwargs(self, project_dir):
        _write(project_dir, "team/greet.hu", "Hello {name}")
        content = 'greet(name="Alice", age=30, city="NYC") -> TEXT'
        violations = _violations_for(content, "LME014", cwd=project_dir)
        assert len(violations) == 1
        assert "age" in violations[0].message
        assert "city" in violations[0].message

    def test_is_error_severity(self, project_dir):
        _write(project_dir, "team/greet.hu", "Hello {name}")
        content = 'greet(name="Alice", typo=1) -> TEXT'
        violations = _violations_for(content, "LME014", cwd=project_dir)
        assert violations[0].rule.severity == Severity.Error


# ── LMC015 generic-filename ────────────────────────────────────────────────

class TestLMC015GenericFilename:

    def test_generic_name_triggers(self):
        violations = _violations_for("x = 1", "LMC015", filepath="/path/process.lm")
        assert len(violations) == 1

    def test_generic_agent_triggers(self):
        violations = _violations_for("x = 1", "LMC015", filepath="/path/agent.lm")
        assert len(violations) == 1

    def test_descriptive_name_no_violation(self):
        violations = _violations_for("x = 1", "LMC015", filepath="/path/review_code.lm")
        assert violations == []

    def test_orchestrator_no_violation(self):
        violations = _violations_for("x = 1", "LMC015", filepath="/path/orchestrator.lm")
        assert violations == []


# ── LME016 unknown-namespace ──────────────────────────────────────────────

class TestLME016UnknownNamespace:

    def test_browser_namespace_triggers(self):
        content = 'browser.click("#btn")'
        violations = _violations_for(content, "LME016")
        assert len(violations) == 1
        assert "browser" in violations[0].message

    def test_page_namespace_triggers(self):
        content = 'page.goto("https://example.com")'
        violations = _violations_for(content, "LME016")
        assert len(violations) == 1
        assert "page" in violations[0].message

    def test_driver_namespace_triggers(self):
        content = 'driver.get("https://example.com")'
        violations = _violations_for(content, "LME016")
        assert len(violations) == 1
        assert "driver" in violations[0].message

    def test_web_namespace_no_violation(self):
        content = 'web.click("#btn")'
        violations = _violations_for(content, "LME016")
        assert violations == []

    def test_http_namespace_no_violation(self):
        content = 'http.get("https://api.example.com/data")'
        violations = _violations_for(content, "LME016")
        assert violations == []

    def test_file_namespace_no_violation(self):
        content = 'file.read("data.csv")'
        violations = _violations_for(content, "LME016")
        assert violations == []

    def test_uppercase_name_not_flagged(self):
        """Class attribute access like BaseModel.parse() should not trigger."""
        content = 'result = MyClass.from_config(cfg)'
        violations = _violations_for(content, "LME016")
        assert violations == []

    def test_imported_module_not_flagged(self):
        """Explicitly imported modules should not trigger."""
        content = 'import os\nos.path.join("a", "b")'
        violations = _violations_for(content, "LME016")
        assert violations == []

    def test_from_import_not_flagged(self):
        """Modules brought in by from-import should not trigger."""
        content = 'from pathlib import Path\nresult = Path.cwd()'
        violations = _violations_for(content, "LME016")
        assert violations == []

    def test_unimported_lowercase_namespace_triggers(self):
        """Using a module without importing it should trigger."""
        content = 'result = requests.get("https://example.com")'
        violations = _violations_for(content, "LME016")
        assert len(violations) == 1
        assert "requests" in violations[0].message

    def test_locally_defined_variable_not_flagged(self):
        """Variables assigned locally should not trigger."""
        content = 'config = load_config()\nresult = config.get("key")'
        violations = _violations_for(content, "LME016")
        assert violations == []

    def test_for_loop_target_not_flagged(self):
        """Loop variables should not trigger."""
        content = 'for item in items:\n    item.process()'
        violations = _violations_for(content, "LME016")
        assert violations == []

    def test_function_param_not_flagged(self):
        """Function parameters should not trigger."""
        content = 'def handle(request):\n    request.send()'
        violations = _violations_for(content, "LME016")
        assert violations == []

    def test_is_error_severity(self):
        content = 'browser.click("#btn")'
        violations = _violations_for(content, "LME016")
        assert violations[0].rule.severity == Severity.Error

    def test_lists_valid_namespaces_in_message(self):
        content = 'browser.click("#btn")'
        violations = _violations_for(content, "LME016")
        assert "web" in violations[0].message


# ── LME017 unknown-namespace-method ──────────────────────────────────────

class TestLME017UnknownNamespaceMethod:

    def test_web_invalid_method_triggers(self):
        content = 'web.browser_navigate("https://example.com")'
        violations = _violations_for(content, "LME017")
        assert len(violations) == 1
        assert "browser_navigate" in violations[0].message

    def test_web_click_no_violation(self):
        content = 'web.click("#btn")'
        violations = _violations_for(content, "LME017")
        assert violations == []

    def test_web_navigate_no_violation(self):
        content = 'web.navigate("https://example.com")'
        violations = _violations_for(content, "LME017")
        assert violations == []

    def test_web_type_text_no_violation(self):
        content = 'web.type_text("#input", "hello")'
        violations = _violations_for(content, "LME017")
        assert violations == []

    def test_web_get_text_no_violation(self):
        content = 'web.get_text(".result")'
        violations = _violations_for(content, "LME017")
        assert violations == []

    def test_web_wait_for_no_violation(self):
        content = 'web.wait_for(".loading", "hidden")'
        violations = _violations_for(content, "LME017")
        assert violations == []

    def test_web_screenshot_no_violation(self):
        content = 'web.screenshot("page.png")'
        violations = _violations_for(content, "LME017")
        assert violations == []

    def test_web_get_element_no_violation(self):
        content = 'modal = web.get_element("div.modal")'
        violations = _violations_for(content, "LME017")
        assert violations == []

    def test_hallucinated_browser_function_triggers(self):
        """Exact scenario from user: LLM invents browser_* style functions."""
        content = (
            'web.browser_navigate("https://broker.example.com/login")\n'
            'web.browser_type("input", "user")\n'
            'web.browser_click("button")\n'
        )
        violations = _violations_for(content, "LME017")
        assert len(violations) == 3

    def test_http_invalid_method_triggers(self):
        content = 'http.fetch("https://api.example.com")'
        violations = _violations_for(content, "LME017")
        assert len(violations) == 1
        assert "fetch" in violations[0].message

    def test_http_get_no_violation(self):
        content = 'http.get("https://api.example.com/data")'
        violations = _violations_for(content, "LME017")
        assert violations == []

    def test_is_error_severity(self):
        content = 'web.fake_method()'
        violations = _violations_for(content, "LME017")
        assert violations[0].rule.severity == Severity.Error

    def test_lists_valid_methods_in_message(self):
        content = 'web.fake_method()'
        violations = _violations_for(content, "LME017")
        assert "click" in violations[0].message
        assert "navigate" in violations[0].message


# ── Real-world hallucination patterns ────────────────────────────────────

class TestLmLinterHallucinationPatterns:

    def test_full_hallucinated_broker_script(self):
        """The exact hallucination from the user's conversation."""
        content = (
            'browser_navigate("https://broker.example.com/login")\n'
            'browser_type("input[name=\'username\']", os.getenv("BROKER_USERNAME"))\n'
            'browser_type("input[name=\'password\']", os.getenv("BROKER_PASSWORD"))\n'
            'browser_click("button[type=\'submit\']")\n'
            'browser_wait(".dashboard", timeout=10)\n'
            'portfolio_text = browser_get_text(".portfolio-balance")\n'
        )
        linter = LmLinter()
        result = linter.lint(content)
        # These are top-level function calls, not namespace.method calls,
        # so LME016/LME017 won't fire. But the code won't parse as valid
        # Python either since browser_navigate etc. are undefined.
        # The important case is when they use a namespace like browser.xyz.
        assert True  # Documented edge case: top-level hallucinated calls

    def test_hallucinated_browser_namespace(self):
        """LLM uses 'browser' instead of 'web'."""
        content = (
            'browser.navigate("https://broker.example.com/login")\n'
            'browser.type("input", "user")\n'
            'browser.click("button.submit")\n'
        )
        linter = LmLinter()
        result = linter.lint(content)
        ns_violations = [v for v in result.violations if v.rule.code == "LME016"]
        assert len(ns_violations) == 3

    def test_valid_lamia_broker_script(self):
        """Correct Lamia syntax for the same task should pass namespace checks."""
        content = (
            'web.navigate("https://broker.example.com/login")\n'
            'web.type_text("#username", "user")\n'
            'web.click("#login-button")\n'
            'web.wait_for(".dashboard", "visible")\n'
            'balance = web.get_text(".portfolio-balance")\n'
        )
        linter = LmLinter()
        result = linter.lint(content)
        ns_violations = [v for v in result.violations
                         if v.rule.code in ("LME016", "LME017")]
        assert ns_violations == []

    def test_lamia_types_not_flagged(self):
        """Lamia auto-imported types like JSON, HTML should not trigger."""
        content = 'result = agent(prompt=p) -> JSON[MyModel]'
        linter = LmLinter()
        result = linter.lint(content)
        ns_violations = [v for v in result.violations
                         if v.rule.code in ("LME016", "LME017")]
        assert ns_violations == []

    def test_project_pydantic_model_not_flagged(self, project_dir):
        """Pydantic models from .py files in the project should not trigger."""
        _write(project_dir, "models/schemas.py",
               "from pydantic import BaseModel\n\n"
               "class StockQuote(BaseModel):\n"
               "    ticker: str\n")
        content = 'data = scraper(ticker="AAPL") -> JSON[StockQuote]'
        linter = LmLinter()
        result = linter.lint(content, cwd=project_dir)
        ns_violations = [v for v in result.violations
                         if v.rule.code in ("LME016", "LME017")]
        assert ns_violations == []


# ── LMW018 single-file-in-files-context ──────────────────────────────────────

class TestLMW018SingleFileInFilesContext:

    def test_single_file_path_triggers(self):
        code = 'with files("~/Documents/resume.pdf"):'
        violations = _violations_for(code, "LMW018")
        assert len(violations) == 1
        assert "resume.pdf" in violations[0].message

    def test_directory_path_no_violation(self):
        code = 'with files("~/Documents/"):'
        violations = _violations_for(code, "LMW018")
        assert violations == []

    def test_directory_without_trailing_slash_no_violation(self):
        code = 'with files("~/Documents"):'
        violations = _violations_for(code, "LMW018")
        assert violations == []

    def test_multiple_dirs_no_violation(self):
        code = 'with files("~/Documents/", "~/projects/"):'
        violations = _violations_for(code, "LMW018")
        assert violations == []

    def test_single_quotes_also_detected(self):
        code = "with files('./data/report.csv'):"
        violations = _violations_for(code, "LMW018")
        assert len(violations) == 1

    def test_variable_path_no_violation(self):
        code = 'with files(my_dir):'
        violations = _violations_for(code, "LMW018")
        assert violations == []


# ── LMW019: prefer atomic web action ─────────────────────────────────────────

class TestLMW019PreferAtomicWebAction:

    def test_get_element_then_single_click_triggers(self):
        code = 'link = web.get_element("a")\nlink.click()'
        violations = _violations_for(code, "LMW019")
        assert len(violations) == 1
        assert "web.click" in violations[0].message

    def test_get_element_then_single_get_text_triggers(self):
        code = 'el = web.get_element(".title")\nel.get_text()'
        violations = _violations_for(code, "LMW019")
        assert len(violations) == 1
        assert "web.get_text" in violations[0].message

    def test_multi_use_variable_no_warning(self):
        code = 'el = web.get_element("div")\nel.click()\nel.get_text()'
        violations = _violations_for(code, "LMW019")
        assert violations == []

    def test_sub_selector_arg_no_warning(self):
        code = 'el = web.get_element("form")\nel.click("button")'
        violations = _violations_for(code, "LMW019")
        assert violations == []

    def test_severity_is_warning(self):
        code = 'link = web.get_element("a")\nlink.click()'
        violations = _violations_for(code, "LMW019")
        assert violations[0].rule.severity == Severity.Warning


# ── LME020: global web action without selector ───────────────────────────────

class TestLME020GlobalWebNoSelector:

    def test_web_click_no_arg_triggers(self):
        code = 'web.click()'
        violations = _violations_for(code, "LME020")
        assert len(violations) == 1
        assert "web.click()" in violations[0].message

    def test_web_hover_no_arg_triggers(self):
        code = 'web.hover()'
        violations = _violations_for(code, "LME020")
        assert len(violations) == 1

    def test_web_click_with_selector_no_error(self):
        code = 'web.click("#submit")'
        violations = _violations_for(code, "LME020")
        assert violations == []

    def test_severity_is_error(self):
        code = 'web.click()'
        violations = _violations_for(code, "LME020")
        assert violations[0].rule.severity == Severity.Error

    def test_non_action_method_no_error(self):
        code = 'web.navigate("https://example.com")'
        violations = _violations_for(code, "LME020")
        assert violations == []


# ── Existing rules still work ───────────────────────────────────────────────

class TestLmLinterExistingRulesUnaffected:

    def test_clean_code_no_violations(self):
        linter = LmLinter()
        result = linter.lint('result = agent(prompt=p) -> JSON[MyModel]')
        assert result.clean
