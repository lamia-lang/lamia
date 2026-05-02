"""Tests for HuLinter.

Comprehensive test suite covering all HU lint rules with real-world
scenarios based on typical LLM-generated content and user requests.
"""

import tempfile
from pathlib import Path

import pytest

from lamia.lint.hu_linter import HuLinter, _TOO_MANY_PARAMS_THRESHOLD
from lamia.lint.base import Severity


def _violations_for_code(content: str, code: str, **kwargs) -> list:
    linter = HuLinter()
    result = linter.lint(content, **kwargs)
    return [v for v in result.violations if v.rule.code == code]


def _all_violations(content: str, **kwargs) -> list:
    linter = HuLinter()
    result = linter.lint(content, **kwargs)
    return result.violations


def _violation_codes(content: str, **kwargs) -> set:
    return {v.rule.code for v in _all_violations(content, **kwargs)}


def _write(base: str, relpath: str, content: str) -> Path:
    p = Path(base) / relpath
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return p


@pytest.fixture
def project_dir():
    with tempfile.TemporaryDirectory() as d:
        yield d


# ═══════════════════════════════════════════════════════════════════════════
# HUE001 — yaml-front-matter
# ═══════════════════════════════════════════════════════════════════════════

class TestHUE001YamlFrontMatter:

    def test_yaml_front_matter_triggers(self):
        content = "---\ntitle: My Agent\n---\nDo something."
        violations = _violations_for_code(content, "HUE001")
        assert len(violations) == 1

    def test_yaml_front_matter_is_error(self):
        content = "---\ntitle: test\n---\nContent."
        violations = _violations_for_code(content, "HUE001")
        assert violations[0].rule.severity == Severity.Error

    def test_yaml_front_matter_only_at_start(self):
        content = "Some text\n---\ntitle: test\n---\nMore text."
        violations = _violations_for_code(content, "HUE001")
        assert violations == []

    def test_yaml_front_matter_llm_style(self):
        """LLMs often add YAML front matter when writing markdown-style prompts."""
        content = "---\nrole: assistant\nmodel: gpt-4\ntemperature: 0.7\n---\nYou are a helpful assistant."
        violations = _violations_for_code(content, "HUE001")
        assert len(violations) == 1

    def test_no_front_matter_clean(self):
        content = "You are a helpful assistant.\nDo your best."
        violations = _violations_for_code(content, "HUE001")
        assert violations == []

    def test_triple_dash_in_middle_not_front_matter(self):
        content = "Step 1: Do this.\n---\nStep 2: Do that.\n---\nDone."
        violations = _violations_for_code(content, "HUE001")
        assert violations == []


# ═══════════════════════════════════════════════════════════════════════════
# HUE019 — escaped-param
# ═══════════════════════════════════════════════════════════════════════════

class TestHUE019EscapedParam:

    def test_double_braces_without_cwd_no_violation(self):
        violations = _violations_for_code("Hello {{name}}", "HUE019")
        assert violations == []

    def test_double_braces_with_caller_triggers(self, project_dir):
        hu_path = _write(project_dir, "greet.hu", "Hello {{name}}, welcome!")
        _write(project_dir, "main.lm", 'greet(name="Alice") -> TEXT')
        violations = _violations_for_code(
            "Hello {{name}}, welcome!", "HUE019",
            cwd=project_dir, filepath=str(hu_path),
        )
        assert len(violations) == 1
        assert "name" in violations[0].message

    def test_double_braces_without_caller_no_violation(self, project_dir):
        hu_path = _write(project_dir, "example.hu", "Format: {{key: value}}")
        _write(project_dir, "main.lm", 'result = example() -> TEXT')
        violations = _violations_for_code(
            "Format: {{key: value}}", "HUE019",
            cwd=project_dir, filepath=str(hu_path),
        )
        assert violations == []

    def test_single_braces_no_violation(self, project_dir):
        hu_path = _write(project_dir, "greet.hu", "Hello {name}")
        violations = _violations_for_code(
            "Hello {name}", "HUE019",
            cwd=project_dir, filepath=str(hu_path),
        )
        assert violations == []

    def test_is_error_severity(self, project_dir):
        hu_path = _write(project_dir, "greet.hu", "{{name}}")
        _write(project_dir, "main.lm", 'greet(name="x") -> TEXT')
        violations = _violations_for_code(
            "{{name}}", "HUE019",
            cwd=project_dir, filepath=str(hu_path),
        )
        assert violations[0].rule.severity == Severity.Error

    def test_llm_typical_double_braces_in_prompt(self, project_dir):
        """LLMs frequently use {{param}} instead of {param} when writing .hu files."""
        content = (
            "You are a developer.\n\n"
            "Specifications:\n{{specs}}\n\n"
            "PRD Content:\n{{prd_content}}\n\n"
            "Existing Code:\n{{existing_code}}\n"
        )
        hu_path = _write(project_dir, "developer.hu", content)
        _write(project_dir, "main.lm",
               'developer(specs=s, prd_content=p, existing_code=c) -> JSON[Dev]')
        violations = _violations_for_code(
            content, "HUE019",
            cwd=project_dir, filepath=str(hu_path),
        )
        assert len(violations) == 3
        names = {v.snippet.strip("{}") for v in violations}
        assert names == {"specs", "prd_content", "existing_code"}

    def test_multiple_escaped_params_all_caught(self, project_dir):
        content = "Task: {{task_name}}\nPriority: {{priority}}\nAssignee: {{assignee}}"
        hu_path = _write(project_dir, "task.hu", content)
        _write(project_dir, "run.lm",
               'task(task_name="x", priority="high", assignee="Bob") -> TEXT')
        violations = _violations_for_code(
            content, "HUE019",
            cwd=project_dir, filepath=str(hu_path),
        )
        assert len(violations) == 3


# ═══════════════════════════════════════════════════════════════════════════
# HUW002 — markdown-header
# ═══════════════════════════════════════════════════════════════════════════

class TestHUW002MarkdownHeader:

    def test_h1_triggers(self):
        violations = _violations_for_code("# My Header\nsome content", "HUW002")
        assert len(violations) >= 1

    def test_h2_triggers(self):
        violations = _violations_for_code("## Section Title\ncontent", "HUW002")
        assert len(violations) >= 1

    def test_h3_triggers(self):
        violations = _violations_for_code("### Sub Section\ncontent", "HUW002")
        assert len(violations) >= 1

    def test_h6_triggers(self):
        violations = _violations_for_code("###### Deep Heading\ncontent", "HUW002")
        assert len(violations) >= 1

    def test_no_header_clean(self):
        violations = _violations_for_code("Just plain text.", "HUW002")
        assert violations == []

    def test_hash_in_prose_no_trigger(self):
        """# must be followed by space+text to be a heading."""
        violations = _violations_for_code("#hashtag no space", "HUW002")
        assert violations == []

    def test_llm_role_header(self):
        """LLMs love to add ## Role, ## Instructions headers."""
        content = "## Role\nYou are an expert.\n\n## Instructions\nDo the task.\n\n## Output\nReturn JSON."
        violations = _violations_for_code(content, "HUW002")
        assert len(violations) == 3

    def test_llm_numbered_sections(self):
        """LLMs often structure prompts with # 1. Section headers."""
        content = "# 1. Analysis\nAnalyze code.\n\n# 2. Implementation\nWrite code."
        violations = _violations_for_code(content, "HUW002")
        assert len(violations) == 2

    def test_multiple_headers_in_long_prompt(self):
        content = "# Overview\nIntro.\n\n## Details\nMore.\n\n### Sub-point\nEven more.\n\n## Conclusion\nDone."
        violations = _violations_for_code(content, "HUW002")
        assert len(violations) == 4


# ═══════════════════════════════════════════════════════════════════════════
# HUW003 — markdown-bold
# ═══════════════════════════════════════════════════════════════════════════

class TestHUW003MarkdownBold:

    def test_asterisk_bold_triggers(self):
        violations = _violations_for_code("This is **important** text.", "HUW003")
        assert len(violations) >= 1

    def test_underscore_bold_triggers(self):
        violations = _violations_for_code("This is __important__ text.", "HUW003")
        assert len(violations) >= 1

    def test_no_bold_clean(self):
        violations = _violations_for_code("Plain text with no formatting.", "HUW003")
        assert violations == []

    def test_llm_bold_section_headers(self):
        """LLMs love using **Section:** as pseudo-headers."""
        content = (
            "**Your Role:**\nYou are a developer.\n\n"
            "**Instructions:**\nFollow the specs.\n\n"
            "**Important Notes:**\nDon't break things.\n"
        )
        violations = _violations_for_code(content, "HUW003")
        assert len(violations) == 3

    def test_llm_bold_labels_in_output_schema(self):
        """LLMs use **bold** for field labels in inline schemas."""
        content = (
            "Fields:\n"
            "- **status**: PASS or FAIL\n"
            "- **issues**: List of problems\n"
            "- **score**: 1-10 rating\n"
        )
        violations = _violations_for_code(content, "HUW003")
        assert len(violations) == 3

    def test_bold_with_colon_typical_llm(self):
        """Common LLM pattern: **Label:** value."""
        content = "**Specifications:**\nThe specs here.\n**PRD Context:**\nThe PRD."
        violations = _violations_for_code(content, "HUW003")
        assert len(violations) == 2

    def test_single_asterisk_not_bold(self):
        """Single * is italic, not bold."""
        violations = _violations_for_code("a * b * c multiplication", "HUW003")
        assert violations == []


# ═══════════════════════════════════════════════════════════════════════════
# HUW004 — markdown-italic
# ═══════════════════════════════════════════════════════════════════════════

class TestHUW004MarkdownItalic:

    def test_asterisk_italic_triggers(self):
        violations = _violations_for_code("This is *important* text.", "HUW004")
        assert len(violations) >= 1

    def test_underscore_italic_triggers(self):
        violations = _violations_for_code("This is _important_ text.", "HUW004")
        assert len(violations) >= 1

    def test_no_italic_clean(self):
        violations = _violations_for_code("Plain text only.", "HUW004")
        assert violations == []

    def test_single_char_not_italic(self):
        """Single character between * shouldn't trigger (too short)."""
        violations = _violations_for_code("Use *a* here.", "HUW004")
        assert violations == []

    def test_underscores_in_param_names_no_trigger(self):
        """snake_case params like {my_param} should not trigger italic."""
        violations = _violations_for_code("Use {my_param} here.", "HUW004")
        assert violations == []

    def test_file_path_with_underscores_no_trigger(self):
        """File paths like test_utils.py shouldn't trigger."""
        violations = _violations_for_code("Check the test_utils.py file.", "HUW004")
        assert violations == []


# ═══════════════════════════════════════════════════════════════════════════
# HUW005 — markdown-strikethrough
# ═══════════════════════════════════════════════════════════════════════════

class TestHUW005MarkdownStrikethrough:

    def test_strikethrough_triggers(self):
        violations = _violations_for_code("This is ~~removed~~ text.", "HUW005")
        assert len(violations) >= 1

    def test_no_strikethrough_clean(self):
        violations = _violations_for_code("Plain text.", "HUW005")
        assert violations == []

    def test_tilde_in_path_no_trigger(self):
        violations = _violations_for_code("Home is ~/projects/", "HUW005")
        assert violations == []


# ═══════════════════════════════════════════════════════════════════════════
# HUW006 — markdown-link
# ═══════════════════════════════════════════════════════════════════════════

class TestHUW006MarkdownLink:

    def test_markdown_link_triggers(self):
        violations = _violations_for_code("See [documentation](https://example.com)", "HUW006")
        assert len(violations) >= 1

    def test_plain_url_no_trigger(self):
        violations = _violations_for_code("Visit https://example.com for more.", "HUW006")
        assert violations == []

    def test_no_links_clean(self):
        violations = _violations_for_code("No links here.", "HUW006")
        assert violations == []

    def test_llm_reference_links(self):
        """LLMs sometimes add reference links in documentation-style prompts."""
        content = (
            "For more info see [API docs](https://api.example.com/docs) "
            "and [the guide](https://guide.example.com)."
        )
        violations = _violations_for_code(content, "HUW006")
        assert len(violations) == 2


# ═══════════════════════════════════════════════════════════════════════════
# HUW007 — markdown-image
# ═══════════════════════════════════════════════════════════════════════════

class TestHUW007MarkdownImage:

    def test_image_triggers(self):
        violations = _violations_for_code("![logo](image.png)", "HUW007")
        assert len(violations) >= 1

    def test_no_images_clean(self):
        violations = _violations_for_code("No images here.", "HUW007")
        assert violations == []


# ═══════════════════════════════════════════════════════════════════════════
# HUW008 — markdown-code-fence
# ═══════════════════════════════════════════════════════════════════════════

class TestHUW008MarkdownCodeFence:

    def test_code_fence_with_language_triggers(self):
        content = "Example:\n```python\nprint('hello')\n```"
        violations = _violations_for_code(content, "HUW008")
        assert len(violations) >= 1

    def test_code_fence_json_triggers(self):
        content = "Output:\n```json\n{\"key\": \"value\"}\n```"
        violations = _violations_for_code(content, "HUW008")
        assert len(violations) >= 1

    def test_bare_code_fence_triggers(self):
        """Bare ``` without language tag should also trigger."""
        content = "Example:\n```\nsome code\n```"
        violations = _violations_for_code(content, "HUW008")
        assert len(violations) >= 1

    def test_no_fences_clean(self):
        violations = _violations_for_code("Plain text with no code fences.", "HUW008")
        assert violations == []

    def test_llm_output_schema_in_fences(self):
        """LLMs embed JSON schemas in code fences constantly."""
        content = (
            "Return your analysis as follows:\n"
            "```json\n"
            "{\n"
            '  "status": "PASS|FAIL",\n'
            '  "issues": [{"severity": "HIGH", "description": "..."}]\n'
            "}\n"
            "```\n"
        )
        violations = _violations_for_code(content, "HUW008")
        assert len(violations) >= 1

    def test_llm_multiple_fenced_blocks(self):
        """LLMs may include multiple code fence blocks."""
        content = (
            "Step 1:\n```python\nx = 1\n```\n\n"
            "Step 2:\n```bash\necho hello\n```\n"
        )
        violations = _violations_for_code(content, "HUW008")
        assert len(violations) >= 2

    def test_triple_backtick_inline_no_trigger(self):
        """Backticks mid-line (not at start) are inline code, handled by HUW014."""
        violations = _violations_for_code("Use the `code` command.", "HUW008")
        assert violations == []


# ═══════════════════════════════════════════════════════════════════════════
# HUW009 — markdown-blockquote
# ═══════════════════════════════════════════════════════════════════════════

class TestHUW009MarkdownBlockquote:

    def test_blockquote_triggers(self):
        violations = _violations_for_code("> This is a quote", "HUW009")
        assert len(violations) >= 1

    def test_no_blockquote_clean(self):
        violations = _violations_for_code("No quotes here.", "HUW009")
        assert violations == []

    def test_greater_than_in_code_no_trigger(self):
        """Greater-than in expressions like x > 5 should not trigger."""
        violations = _violations_for_code("if x > 5 then do it", "HUW009")
        assert violations == []


# ═══════════════════════════════════════════════════════════════════════════
# HUW010 — markdown-table
# ═══════════════════════════════════════════════════════════════════════════

class TestHUW010MarkdownTable:

    def test_table_triggers(self):
        content = "| Column 1 | Column 2 |\n| --- | --- |\n| val1 | val2 |"
        violations = _violations_for_code(content, "HUW010")
        assert len(violations) >= 1

    def test_no_table_clean(self):
        violations = _violations_for_code("No tables here.", "HUW010")
        assert violations == []

    def test_pipe_in_text_no_trigger(self):
        """Single pipe in text shouldn't be a table."""
        violations = _violations_for_code("Use cat file | grep pattern", "HUW010")
        assert violations == []

    def test_llm_comparison_table(self):
        """LLMs love creating comparison tables in prompts."""
        content = (
            "| Feature | Status | Priority |\n"
            "| ------- | ------ | -------- |\n"
            "| Auth    | Done   | High     |\n"
            "| Search  | WIP    | Medium   |\n"
        )
        violations = _violations_for_code(content, "HUW010")
        assert len(violations) >= 2


# ═══════════════════════════════════════════════════════════════════════════
# HUW011 — markdown-horizontal-rule
# ═══════════════════════════════════════════════════════════════════════════

class TestHUW011MarkdownHorizontalRule:

    def test_triple_dash_triggers(self):
        violations = _violations_for_code("Above\n---\nBelow", "HUW011")
        assert len(violations) >= 1

    def test_triple_asterisk_triggers(self):
        violations = _violations_for_code("Above\n***\nBelow", "HUW011")
        assert len(violations) >= 1

    def test_triple_underscore_triggers(self):
        violations = _violations_for_code("Above\n___\nBelow", "HUW011")
        assert len(violations) >= 1

    def test_first_line_dash_no_trigger(self):
        """--- on line 1 could be YAML front matter, skip for this rule."""
        violations = _violations_for_code("---\nContent below", "HUW011")
        assert violations == []

    def test_no_hr_clean(self):
        violations = _violations_for_code("Plain text.", "HUW011")
        assert violations == []

    def test_llm_section_separator(self):
        """LLMs use --- as section separators."""
        content = "Section 1 content.\n\n---\n\nSection 2 content.\n\n---\n\nSection 3."
        violations = _violations_for_code(content, "HUW011")
        assert len(violations) == 2


# ═══════════════════════════════════════════════════════════════════════════
# HUW012 — html-tag
# ═══════════════════════════════════════════════════════════════════════════

class TestHUW012HtmlTag:

    def test_div_tag_triggers(self):
        violations = _violations_for_code("<div>content</div>", "HUW012")
        assert len(violations) >= 1

    def test_br_tag_triggers(self):
        violations = _violations_for_code("Line one<br>Line two", "HUW012")
        assert len(violations) >= 1

    def test_no_html_clean(self):
        violations = _violations_for_code("No HTML here.", "HUW012")
        assert violations == []

    def test_angle_brackets_in_generics_no_trigger(self):
        """Type annotations like List<str> shouldn't trigger."""
        violations = _violations_for_code("Use List<str> type.", "HUW012")
        assert violations == []

    def test_llm_html_formatting(self):
        """LLMs sometimes use HTML when asked to format output."""
        content = "<p>Introduction</p>\n<ul>\n<li>Point 1</li>\n<li>Point 2</li>\n</ul>"
        violations = _violations_for_code(content, "HUW012")
        assert len(violations) >= 3


# ═══════════════════════════════════════════════════════════════════════════
# HUW013 — emoji
# ═══════════════════════════════════════════════════════════════════════════

class TestHUW013Emoji:

    def test_emoji_triggers(self):
        violations = _violations_for_code("Hello 🎉 world", "HUW013")
        assert len(violations) >= 1

    def test_no_emoji_clean(self):
        violations = _violations_for_code("No emojis here.", "HUW013")
        assert violations == []

    def test_llm_emoji_heavy_prompt(self):
        """LLMs love adding emojis for 'friendliness'."""
        content = "🎯 Goal: Build the app\n🔧 Tools: Python\n✅ Tests: Required\n🚀 Deploy: AWS"
        violations = _violations_for_code(content, "HUW013")
        assert len(violations) >= 1

    def test_multiple_emojis(self):
        content = "Step 1 ✅\nStep 2 ⚠️\nStep 3 ❌"
        violations = _violations_for_code(content, "HUW013")
        assert len(violations) >= 1


# ═══════════════════════════════════════════════════════════════════════════
# HUW014 — markdown-inline-code
# ═══════════════════════════════════════════════════════════════════════════

class TestHUW014MarkdownInlineCode:

    def test_inline_code_triggers(self):
        violations = _violations_for_code("Use the `print` function.", "HUW014")
        assert len(violations) >= 1

    def test_no_backticks_clean(self):
        violations = _violations_for_code("Use the print function.", "HUW014")
        assert violations == []

    def test_llm_backtick_params(self):
        """LLMs wrap parameter names in backticks."""
        content = "Set `user_name` to the input value and `max_retries` to 3."
        violations = _violations_for_code(content, "HUW014")
        assert len(violations) == 2

    def test_llm_backtick_commands(self):
        """LLMs wrap commands in backticks."""
        content = "Run `npm install` then `npm start` to begin."
        violations = _violations_for_code(content, "HUW014")
        assert len(violations) == 2

    def test_llm_backtick_file_paths(self):
        """LLMs wrap file paths in backticks."""
        content = "Edit the `src/main.py` file and check `tests/test_main.py`."
        violations = _violations_for_code(content, "HUW014")
        assert len(violations) == 2


# ═══════════════════════════════════════════════════════════════════════════
# HUW015 — markdown-task-list
# ═══════════════════════════════════════════════════════════════════════════

class TestHUW015MarkdownTaskList:

    def test_unchecked_task_triggers(self):
        violations = _violations_for_code("- [ ] Do this task", "HUW015")
        assert len(violations) >= 1

    def test_checked_task_triggers(self):
        violations = _violations_for_code("- [x] Done task", "HUW015")
        assert len(violations) >= 1

    def test_no_tasks_clean(self):
        violations = _violations_for_code("- Regular list item", "HUW015")
        assert violations == []

    def test_llm_checklist(self):
        """LLMs create checklists for review criteria."""
        content = (
            "Review checklist:\n"
            "- [ ] Code compiles\n"
            "- [ ] Tests pass\n"
            "- [x] Documentation updated\n"
            "- [ ] Security review done\n"
        )
        violations = _violations_for_code(content, "HUW015")
        assert len(violations) == 4


# ═══════════════════════════════════════════════════════════════════════════
# HUW016 — excessive-growth
# ═══════════════════════════════════════════════════════════════════════════

class TestHUW016ExcessiveGrowth:

    def test_no_original_no_violation(self):
        violations = _violations_for_code("New content here.", "HUW016")
        assert violations == []

    def test_slight_growth_no_violation(self):
        original = "You are a helpful assistant that reviews code carefully."
        content = "You are a helpful assistant that reviews code carefully and reports issues."
        violations = _violations_for_code(content, "HUW016", original=original)
        assert violations == []

    def test_double_growth_triggers(self):
        original = "Short."
        content = "Short." + " extra" * 20
        violations = _violations_for_code(content, "HUW016", original=original)
        assert len(violations) == 1

    def test_llm_bloating_prompt(self):
        """LLMs tend to massively expand prompts with verbose explanations."""
        original = "You are a QA analyst. Review the code."
        content = original + "\n" + "Detailed instructions:\n" * 50
        violations = _violations_for_code(content, "HUW016", original=original)
        assert len(violations) == 1

    def test_empty_original_no_violation(self):
        violations = _violations_for_code("Content.", "HUW016", original="")
        assert violations == []


# ═══════════════════════════════════════════════════════════════════════════
# HUW017 — too-many-params
# ═══════════════════════════════════════════════════════════════════════════

class TestHUW017TooManyParams:

    def test_no_params_no_violation(self):
        violations = _violations_for_code("Just plain text with no placeholders.", "HUW017")
        assert violations == []

    def test_few_params_no_violation(self):
        content = " ".join(f"{{p{i}}}" for i in range(5))
        violations = _violations_for_code(content, "HUW017")
        assert violations == []

    def test_exactly_at_threshold_no_violation(self):
        content = " ".join(f"{{p{i}}}" for i in range(_TOO_MANY_PARAMS_THRESHOLD))
        violations = _violations_for_code(content, "HUW017")
        assert violations == []

    def test_one_over_threshold_triggers(self):
        content = " ".join(f"{{p{i}}}" for i in range(_TOO_MANY_PARAMS_THRESHOLD + 1))
        violations = _violations_for_code(content, "HUW017")
        assert len(violations) == 1

    def test_violation_mentions_param_count(self):
        n = _TOO_MANY_PARAMS_THRESHOLD + 5
        content = " ".join(f"{{p{i}}}" for i in range(n))
        violations = _violations_for_code(content, "HUW017")
        assert str(n) in violations[0].message

    def test_violation_suggests_file_reference(self):
        content = " ".join(f"{{p{i}}}" for i in range(_TOO_MANY_PARAMS_THRESHOLD + 1))
        violations = _violations_for_code(content, "HUW017")
        assert "{@" in violations[0].message

    def test_violation_reported_at_file_level(self):
        content = " ".join(f"{{p{i}}}" for i in range(_TOO_MANY_PARAMS_THRESHOLD + 1))
        violations = _violations_for_code(content, "HUW017")
        assert violations[0].line == 0

    def test_duplicate_params_count_as_one(self):
        content = " ".join(f"{{p{i % 5}}}" for i in range(15))
        violations = _violations_for_code(content, "HUW017")
        assert violations == []

    def test_optional_params_counted_too(self):
        content = " ".join(
            f"{{p{i}:default}}" if i % 2 == 0 else f"{{p{i}}}"
            for i in range(_TOO_MANY_PARAMS_THRESHOLD + 1)
        )
        violations = _violations_for_code(content, "HUW017")
        assert len(violations) == 1

    def test_file_context_refs_not_counted(self):
        file_refs = " ".join(f"{{@file{i}.txt}}" for i in range(20))
        param_refs = " ".join(f"{{p{i}}}" for i in range(5))
        content = file_refs + " " + param_refs
        violations = _violations_for_code(content, "HUW017")
        assert violations == []

    def test_only_one_hu017_violation_even_with_many_params(self):
        content = " ".join(f"{{p{i}}}" for i in range(30))
        violations = _violations_for_code(content, "HUW017")
        assert len(violations) == 1


# ═══════════════════════════════════════════════════════════════════════════
# HUW021 — empty-file
# ═══════════════════════════════════════════════════════════════════════════

class TestHUW021EmptyFile:

    def test_empty_string_triggers(self):
        violations = _violations_for_code("", "HUW021")
        assert len(violations) == 1

    def test_whitespace_only_triggers(self):
        violations = _violations_for_code("   \n  \n  ", "HUW021")
        assert len(violations) == 1

    def test_real_content_no_violation(self):
        violations = _violations_for_code("Summarize this text.", "HUW021")
        assert violations == []


# ═══════════════════════════════════════════════════════════════════════════
# HUW022 — trailing-whitespace
# ═══════════════════════════════════════════════════════════════════════════

class TestHUW022TrailingWhitespace:

    def test_trailing_spaces_trigger(self):
        violations = _violations_for_code("hello   \nworld", "HUW022")
        assert len(violations) == 1

    def test_no_trailing_no_violation(self):
        violations = _violations_for_code("hello\nworld", "HUW022")
        assert violations == []

    def test_multiple_lines_with_trailing(self):
        content = "line1   \nline2\nline3\t\nline4"
        violations = _violations_for_code(content, "HUW022")
        assert len(violations) == 1
        assert "2 line(s)" in violations[0].message

    def test_tabs_as_trailing(self):
        violations = _violations_for_code("hello\t\nworld", "HUW022")
        assert len(violations) == 1


# ═══════════════════════════════════════════════════════════════════════════
# HUW029 — example-output-block (NEW RULE)
# ═══════════════════════════════════════════════════════════════════════════

class TestHUW029ExampleOutputBlock:

    def test_embedded_json_schema_triggers(self):
        """The exact scenario from the user's complaint."""
        content = (
            "You are a developer.\n\n"
            "Output complete implementation.\n\n"
            "{\n"
            '  "files": [\n'
            "    {\n"
            '      "path": "src/main.py",\n'
            '      "content": "print(hello)",\n'
            '      "reviews": []\n'
            "    }\n"
            "  ]\n"
            "}\n"
        )
        violations = _violations_for_code(content, "HUW029")
        assert len(violations) >= 1

    def test_simple_json_object_triggers(self):
        content = (
            "Analyze this.\n\n"
            "{\n"
            '  "status": "PASS",\n'
            '  "score": 8\n'
            "}\n"
        )
        violations = _violations_for_code(content, "HUW029")
        assert len(violations) >= 1

    def test_json_array_block_triggers(self):
        content = (
            "Return tasks as:\n\n"
            "[\n"
            "  {\n"
            '    "id": "task-001",\n'
            '    "title": "Do something"\n'
            "  }\n"
            "]\n"
        )
        violations = _violations_for_code(content, "HUW029")
        assert len(violations) >= 1

    def test_no_json_block_clean(self):
        content = "You are a helpful assistant.\nPlease review the code in {code}."
        violations = _violations_for_code(content, "HUW029")
        assert violations == []

    def test_single_param_braces_no_trigger(self):
        """Regular {param} placeholders should NOT trigger."""
        content = "Hello {name}, your task is {task_description}."
        violations = _violations_for_code(content, "HUW029")
        assert violations == []

    def test_llm_nested_json_schema(self):
        """LLMs embed complex nested JSON schemas as examples."""
        content = (
            "Provide your analysis.\n\n"
            "{\n"
            '  "change_type": "NEW|INCREMENTAL|MAJOR_REWRITE",\n'
            '  "change_summary": "Brief summary",\n'
            '  "tasks": [\n'
            "    {\n"
            '      "id": "task-001",\n'
            '      "title": "Task title",\n'
            '      "priority": "high",\n'
            '      "acceptance_criteria": ["criterion 1"]\n'
            "    }\n"
            "  ],\n"
            '  "risks": []\n'
            "}\n"
        )
        violations = _violations_for_code(content, "HUW029")
        assert len(violations) >= 1

    def test_llm_output_example_with_files_array(self):
        """The exact developer.hu pattern that wasn't caught."""
        content = (
            "You are a Senior Software Engineer.\n\n"
            "Specifications:\n{specs}\n\n"
            "IMPORTANT:\n"
            "- The files array contains ALL files in the project\n"
            "- Each file object has: path, content, reviews\n\n"
            "Example output for adding endpoint:\n\n"
            "{\n"
            '  "files": [\n'
            "    {\n"
            '      "path": "routes/users.py",\n'
            '      "content": "from flask import Blueprint",\n'
            '      "reviews": []\n'
            "    },\n"
            "    {\n"
            '      "path": "models.py",\n'
            '      "content": "from sqlalchemy import db",\n'
            '      "reviews": []\n'
            "    }\n"
            "  ]\n"
            "}\n"
        )
        violations = _violations_for_code(content, "HUW029")
        assert len(violations) >= 1

    def test_is_warning_severity(self):
        content = "{\n\"key\": \"val\",\n\"key2\": \"val2\"\n}\n"
        violations = _violations_for_code(content, "HUW029")
        if violations:
            assert violations[0].rule.severity == Severity.Warning

    def test_block_without_json_keys_no_trigger(self):
        """A block with braces but no JSON keys is not an example output."""
        content = "Some code:\n{\n  x = 1\n  y = 2\n}\n"
        violations = _violations_for_code(content, "HUW029")
        assert violations == []

    def test_multiple_json_blocks_multiple_violations(self):
        """Multiple embedded JSON blocks should each trigger."""
        content = (
            "Block 1:\n"
            "{\n"
            '  "status": "ok",\n'
            '  "code": 200\n'
            "}\n\n"
            "Block 2:\n"
            "{\n"
            '  "error": "not found",\n'
            '  "code": 404\n'
            "}\n"
        )
        violations = _violations_for_code(content, "HUW029")
        assert len(violations) >= 2

    # ── YAML example detection ──

    def test_yaml_example_block_triggers(self):
        """YAML-style key: value blocks should be caught."""
        content = (
            "Provide your analysis.\n\n"
            "status: PASS\n"
            "score: 8\n"
            "issues: none\n"
        )
        violations = _violations_for_code(content, "HUW029")
        assert len(violations) >= 1

    def test_yaml_nested_example_triggers(self):
        """Nested YAML example output."""
        content = (
            "Return assessment.\n\n"
            "status: FAIL\n"
            "score: 3\n"
            "issues:\n"
            "  - severity: HIGH\n"
            "    description: SQL injection\n"
            "deployment_ready: false\n"
        )
        violations = _violations_for_code(content, "HUW029")
        assert len(violations) >= 1

    def test_yaml_single_key_no_trigger(self):
        """A single key: value line is normal prose, not an example."""
        content = "Priority: high\nDo the task."
        violations = _violations_for_code(content, "HUW029")
        assert violations == []

    def test_yaml_two_keys_no_trigger(self):
        """Only 2 consecutive key: value lines -- not enough for an example."""
        content = "status: ok\nscore: 5\nSome other text."
        violations = _violations_for_code(content, "HUW029")
        assert violations == []

    def test_llm_yaml_config_example(self):
        """LLMs embed YAML config examples in prompts."""
        content = (
            "Generate a config file.\n\n"
            "name: my_app\n"
            "version: 1.0\n"
            "database: postgres\n"
            "port: 5432\n"
        )
        violations = _violations_for_code(content, "HUW029")
        assert len(violations) >= 1

    # ── XML example detection ──

    def test_xml_example_block_triggers(self):
        """Multi-line XML example blocks should be caught."""
        content = (
            "Return your analysis.\n\n"
            "<response>\n"
            "  <status>PASS</status>\n"
            "  <score>8</score>\n"
            "</response>\n"
        )
        violations = _violations_for_code(content, "HUW029")
        assert len(violations) >= 1

    def test_xml_nested_example_triggers(self):
        """Nested XML example output."""
        content = (
            "Provide report.\n\n"
            "<report>\n"
            "  <summary>All tests pass</summary>\n"
            "  <issues>\n"
            "    <issue severity='high'>Memory leak</issue>\n"
            "  </issues>\n"
            "</report>\n"
        )
        violations = _violations_for_code(content, "HUW029")
        assert len(violations) >= 1

    def test_single_xml_tag_no_trigger(self):
        """A single HTML-like tag is caught by HUW012, not HUW029."""
        content = "Use the <code>example</code> tag."
        violations = _violations_for_code(content, "HUW029")
        assert violations == []


# ═══════════════════════════════════════════════════════════════════════════
# HUR018 — output-format-hint (expanded patterns)
# ═══════════════════════════════════════════════════════════════════════════

class TestHUR018OutputFormatHint:

    def test_output_json_colon_triggers(self):
        violations = _violations_for_code("Output JSON:", "HUR018")
        assert len(violations) >= 1

    def test_markdown_bold_output_json_triggers(self):
        violations = _violations_for_code("**Output JSON:**", "HUR018")
        assert len(violations) >= 1

    def test_response_format_triggers(self):
        violations = _violations_for_code("Response Format:", "HUR018")
        assert len(violations) >= 1

    def test_return_type_triggers(self):
        violations = _violations_for_code("Return Type:", "HUR018")
        assert len(violations) >= 1

    def test_case_insensitive(self):
        violations = _violations_for_code("output json:", "HUR018")
        assert len(violations) >= 1

    def test_normal_prose_no_violation(self):
        violations = _violations_for_code("Parse the input and validate it.", "HUR018")
        assert violations == []

    def test_mentions_pydantic_and_multiple_types(self):
        violations = _violations_for_code("Output JSON:", "HUR018")
        msg = violations[0].message
        assert "Pydantic" in msg
        assert "HTML" in msg
        assert "YAML" in msg

    def test_output_as_json_triggers(self):
        """LLM writes: 'output your analysis as JSON'."""
        content = "Output your analysis as JSON with all fields."
        violations = _violations_for_code(content, "HUR018")
        assert len(violations) >= 1

    def test_respond_with_json_triggers(self):
        content = "Respond with JSON containing the results."
        violations = _violations_for_code(content, "HUR018")
        assert len(violations) >= 1

    def test_return_a_json_object_triggers(self):
        content = "Return a JSON object with status and issues."
        violations = _violations_for_code(content, "HUR018")
        assert len(violations) >= 1

    def test_produce_yaml_triggers(self):
        content = "Produce the output as YAML format."
        violations = _violations_for_code(content, "HUR018")
        assert len(violations) >= 1

    def test_generate_csv_triggers(self):
        content = "Generate the report as CSV file."
        violations = _violations_for_code(content, "HUR018")
        assert len(violations) >= 1

    def test_example_output_colon_triggers(self):
        content = "Example output:"
        violations = _violations_for_code(content, "HUR018")
        assert len(violations) >= 1

    def test_sample_response_colon_triggers(self):
        content = "Sample response:"
        violations = _violations_for_code(content, "HUR018")
        assert len(violations) >= 1

    def test_your_output_should_triggers(self):
        content = "Your output should contain the analysis."
        violations = _violations_for_code(content, "HUR018")
        assert len(violations) >= 1

    def test_your_response_must_triggers(self):
        content = "Your response must include all fields."
        violations = _violations_for_code(content, "HUR018")
        assert len(violations) >= 1

    def test_output_format_colon_alone_triggers(self):
        """Standalone 'Output:' on its own line."""
        content = "Instructions above.\n\nOutput:\n\nMore text."
        violations = _violations_for_code(content, "HUR018")
        assert len(violations) >= 1

    def test_bold_output_format_triggers(self):
        """**Output Format:** pattern."""
        content = "**Output Format:**"
        violations = _violations_for_code(content, "HUR018")
        assert len(violations) >= 1

    def test_expected_schema_triggers(self):
        content = "Expected Schema:"
        violations = _violations_for_code(content, "HUR018")
        assert len(violations) >= 1

    def test_output_in_regular_sentence_no_trigger(self):
        """'output' used naturally in a sentence without format instructions."""
        content = "The function processes the input and returns the output to the caller."
        violations = _violations_for_code(content, "HUR018")
        assert violations == []

    def test_llm_full_output_section_triggers(self):
        """Full LLM-generated output section header."""
        content = (
            "You are a QA analyst.\n\n"
            "**Output JSON:**\n"
            "Return your analysis.\n"
        )
        violations = _violations_for_code(content, "HUR018")
        assert len(violations) >= 1

    def test_response_structure_triggers(self):
        content = "Response Structure:"
        violations = _violations_for_code(content, "HUR018")
        assert len(violations) >= 1


# ═══════════════════════════════════════════════════════════════════════════
# HUC020 — param-naming
# ═══════════════════════════════════════════════════════════════════════════

class TestHUC020ParamNaming:

    def test_snake_case_no_violation(self):
        violations = _violations_for_code("Use {user_name} and {max_count}", "HUC020")
        assert violations == []

    def test_camel_case_triggers(self):
        violations = _violations_for_code("Hello {userName}", "HUC020")
        assert len(violations) == 1

    def test_suggests_snake_case(self):
        violations = _violations_for_code("{userName}", "HUC020")
        assert "user_name" in violations[0].message

    def test_pascal_case_triggers(self):
        violations = _violations_for_code("{MaxRetries}", "HUC020")
        assert len(violations) == 1

    def test_single_lowercase_word_ok(self):
        violations = _violations_for_code("{name}", "HUC020")
        assert violations == []

    def test_file_refs_not_checked(self):
        violations = _violations_for_code("{@MyFile.txt}", "HUC020")
        assert violations == []

    def test_is_convention_severity(self):
        violations = _violations_for_code("{userName}", "HUC020")
        assert violations[0].rule.severity == Severity.Convention

    def test_llm_camel_case_params(self):
        """LLMs often write params in camelCase."""
        content = "Review {codeContent} with {testResults} and {buildConfig}."
        violations = _violations_for_code(content, "HUC020")
        assert len(violations) == 3

    def test_all_caps_triggers(self):
        violations = _violations_for_code("{API_KEY}", "HUC020")
        # API_KEY starts with uppercase A, fails snake_case
        assert len(violations) == 1


# ═══════════════════════════════════════════════════════════════════════════
# HUC023 — short-param-name
# ═══════════════════════════════════════════════════════════════════════════

class TestHUC023ShortParamName:

    def test_single_letter_triggers(self):
        violations = _violations_for_code("Use {x} here", "HUC023")
        assert len(violations) == 1

    def test_two_letters_no_violation(self):
        violations = _violations_for_code("Use {id} here", "HUC023")
        assert violations == []

    def test_descriptive_name_no_violation(self):
        violations = _violations_for_code("{user_name}", "HUC023")
        assert violations == []

    def test_llm_single_letter_params(self):
        """LLMs sometimes use single-letter params for brevity."""
        content = "Calculate {x} + {y} = {z}"
        violations = _violations_for_code(content, "HUC023")
        assert len(violations) == 3


# ═══════════════════════════════════════════════════════════════════════════
# HUC024 — verbose-param-name
# ═══════════════════════════════════════════════════════════════════════════

class TestHUC024VerboseParamName:

    def test_very_long_name_triggers(self):
        long_name = "a" * 31
        violations = _violations_for_code(f"{{{long_name}}}", "HUC024")
        assert len(violations) == 1

    def test_normal_length_no_violation(self):
        violations = _violations_for_code("{user_name}", "HUC024")
        assert violations == []

    def test_exactly_at_threshold_no_violation(self):
        name = "a" * 30
        violations = _violations_for_code(f"{{{name}}}", "HUC024")
        assert violations == []

    def test_llm_over_descriptive_param(self):
        """LLMs sometimes create excessively descriptive param names."""
        content = "{the_complete_list_of_all_user_requirements_and_specifications}"
        violations = _violations_for_code(content, "HUC024")
        assert len(violations) == 1


# ═══════════════════════════════════════════════════════════════════════════
# HUC025 — filename-naming
# ═══════════════════════════════════════════════════════════════════════════

class TestHUC025FilenameNaming:

    def test_snake_case_no_violation(self):
        violations = _violations_for_code(
            "content", "HUC025", filepath="/path/review_code.hu",
        )
        assert violations == []

    def test_pascal_case_triggers(self):
        violations = _violations_for_code(
            "content", "HUC025", filepath="/path/ReviewCode.hu",
        )
        assert len(violations) == 1

    def test_kebab_case_triggers(self):
        violations = _violations_for_code(
            "content", "HUC025", filepath="/path/review-code.hu",
        )
        assert len(violations) == 1

    def test_suggests_snake_case(self):
        violations = _violations_for_code(
            "content", "HUC025", filepath="/path/ReviewCode.hu",
        )
        assert "review_code" in violations[0].message

    def test_no_filepath_no_violation(self):
        violations = _violations_for_code("content", "HUC025")
        assert violations == []

    def test_llm_creates_camel_case_file(self):
        violations = _violations_for_code(
            "content", "HUC025", filepath="/team/changeAnalyzer.hu",
        )
        assert len(violations) == 1
        assert "change_analyzer" in violations[0].message


# ═══════════════════════════════════════════════════════════════════════════
# HUC026 — leading-blank-lines
# ═══════════════════════════════════════════════════════════════════════════

class TestHUC026LeadingBlankLines:

    def test_leading_blank_triggers(self):
        violations = _violations_for_code("\n\nSome content", "HUC026")
        assert len(violations) == 1

    def test_no_leading_blank_no_violation(self):
        violations = _violations_for_code("Content starts here", "HUC026")
        assert violations == []

    def test_leading_whitespace_triggers(self):
        violations = _violations_for_code("  \n\nContent", "HUC026")
        assert len(violations) == 1

    def test_single_newline_triggers(self):
        violations = _violations_for_code("\nContent", "HUC026")
        assert len(violations) == 1


# ═══════════════════════════════════════════════════════════════════════════
# HUC028 — generic-filename
# ═══════════════════════════════════════════════════════════════════════════

class TestHUC028GenericFilename:

    def test_generic_name_triggers(self):
        violations = _violations_for_code(
            "content", "HUC028", filepath="/path/agent.hu",
        )
        assert len(violations) == 1

    def test_generic_prompt_triggers(self):
        violations = _violations_for_code(
            "content", "HUC028", filepath="/path/prompt.hu",
        )
        assert len(violations) == 1

    def test_generic_template_triggers(self):
        violations = _violations_for_code(
            "content", "HUC028", filepath="/path/template.hu",
        )
        assert len(violations) == 1

    def test_generic_helper_triggers(self):
        violations = _violations_for_code(
            "content", "HUC028", filepath="/path/helper.hu",
        )
        assert len(violations) == 1

    def test_generic_handler_triggers(self):
        violations = _violations_for_code(
            "content", "HUC028", filepath="/path/handler.hu",
        )
        assert len(violations) == 1

    def test_descriptive_name_no_violation(self):
        violations = _violations_for_code(
            "content", "HUC028", filepath="/path/review_code.hu",
        )
        assert violations == []

    def test_no_filepath_no_violation(self):
        violations = _violations_for_code("content", "HUC028")
        assert violations == []

    def test_role_based_name_no_violation(self):
        violations = _violations_for_code(
            "content", "HUC028", filepath="/team/qa_analyst.hu",
        )
        assert violations == []


# ═══════════════════════════════════════════════════════════════════════════
# HUR027 — long-prompt
# ═══════════════════════════════════════════════════════════════════════════

class TestHUR027LongPrompt:

    def test_short_prompt_no_violation(self):
        violations = _violations_for_code("Short prompt.", "HUR027")
        assert violations == []

    def test_long_prompt_triggers(self):
        content = "x" * 3001
        violations = _violations_for_code(content, "HUR027")
        assert len(violations) == 1
        assert "3001" in violations[0].message

    def test_exactly_at_threshold_no_violation(self):
        content = "x" * 3000
        violations = _violations_for_code(content, "HUR027")
        assert violations == []

    def test_llm_verbose_prompt_triggers(self):
        """LLMs create very verbose prompts with extensive instructions."""
        lines = [f"Rule {i}: Follow this guideline." for i in range(200)]
        content = "\n".join(lines)
        assert len(content) > 3000
        violations = _violations_for_code(content, "HUR027")
        assert len(violations) == 1


# ═══════════════════════════════════════════════════════════════════════════
# Feedback ordering
# ═══════════════════════════════════════════════════════════════════════════

class TestFeedbackOrdering:

    def test_errors_before_warnings(self, project_dir):
        hu_path = _write(project_dir, "greet.hu", "# Header\n{{name}}")
        _write(project_dir, "main.lm", 'greet(name="x") -> TEXT')
        linter = HuLinter()
        result = linter.lint(
            "# Header\n{{name}}",
            cwd=project_dir, filepath=str(hu_path),
        )
        msg = result.feedback_message()
        lines = msg.split("\n")
        rule_lines = [l for l in lines if l.strip().startswith("[")]
        if len(rule_lines) >= 2:
            assert "HUE019" in rule_lines[0]

    def test_errors_before_refactor(self, project_dir):
        hu_path = _write(project_dir, "greet.hu", "{{param}}\nOutput JSON:")
        _write(project_dir, "main.lm", 'greet(param="x") -> TEXT')
        linter = HuLinter()
        result = linter.lint(
            "{{param}}\nOutput JSON:",
            cwd=project_dir, filepath=str(hu_path),
        )
        msg = result.feedback_message()
        error_pos = msg.find("HUE019")
        refactor_pos = msg.find("HUR018")
        if error_pos >= 0 and refactor_pos >= 0:
            assert error_pos < refactor_pos


# ═══════════════════════════════════════════════════════════════════════════
# Cross-rule: existing rules still work
# ═══════════════════════════════════════════════════════════════════════════

class TestHuLinterExistingRulesUnaffected:

    def test_emoji_still_detected(self):
        violations = _violations_for_code("Hello 🎉 world", "HUW013")
        assert len(violations) >= 1

    def test_markdown_header_still_detected(self):
        violations = _violations_for_code("# My Header\nsome content", "HUW002")
        assert len(violations) >= 1

    def test_clean_file_still_clean(self):
        linter = HuLinter()
        result = linter.lint("Plain text with {one_param} placeholder.")
        assert result.clean


# ═══════════════════════════════════════════════════════════════════════════
# Cross-rule: real-world LLM-generated .hu files
# ═══════════════════════════════════════════════════════════════════════════

class TestRealWorldLLMGenerated:
    """Tests covering realistic full .hu files that LLMs typically generate.

    These are the patterns that escape detection because they combine
    multiple rule violations in ways that individual rule tests don't cover.
    """

    def test_llm_developer_prompt_with_embedded_schema(self):
        """Realistic developer.hu that an LLM would generate."""
        content = (
            "You are a Senior Software Engineer implementing features.\n\n"
            "**Specifications:**\n"
            "{{specs}}\n\n"
            "**PRD Context:**\n"
            "{{prd_content}}\n\n"
            "**Output Format:**\n"
            "```json\n"
            "{\n"
            '  "files": [\n'
            "    {\n"
            '      "path": "relative/path/to/file.py",\n'
            '      "content": "full file content here",\n'
            '      "reviews": []\n'
            "    }\n"
            "  ]\n"
            "}\n"
            "```\n\n"
            "IMPORTANT:\n"
            "- Provide complete, runnable file content\n"
        )
        codes = _violation_codes(content)
        assert "HUW003" in codes, "Should detect **bold** sections"
        assert "HUW008" in codes, "Should detect code fences"
        assert "HUR018" in codes, "Should detect output format instructions"
        assert "HUW029" in codes, "Should detect JSON example block"

    def test_llm_qa_prompt_with_all_formatting(self):
        """Realistic QA analyst prompt with typical LLM formatting."""
        content = (
            "# QA Assessment\n\n"
            "You are an **Expert QA Analyst**.\n\n"
            "## Analysis Areas\n\n"
            "1. **Functional Correctness** - Does it work?\n"
            "2. **Security** - Any vulnerabilities?\n\n"
            "**Output JSON:**\n\n"
            "```json\n"
            "{\n"
            '  "status": "PASS|FAIL",\n'
            '  "issues": []\n'
            "}\n"
            "```\n\n"
            "✅ Be thorough\n"
            "🎯 Focus on critical issues\n"
        )
        codes = _violation_codes(content)
        assert "HUW002" in codes, "Should detect # headers"
        assert "HUW003" in codes, "Should detect **bold**"
        assert "HUW008" in codes, "Should detect code fences"
        assert "HUW013" in codes, "Should detect emojis"
        assert "HUR018" in codes, "Should detect output format hint"

    def test_llm_product_manager_with_examples(self):
        """Realistic PM prompt with embedded JSON examples."""
        content = (
            "You are a Product Manager.\n\n"
            "Current PRD:\n{prd_content}\n\n"
            "Previous Version:\n{previous_version}\n\n"
            "Analyze changes and produce tasks.\n\n"
            "Example output:\n\n"
            "{\n"
            '  "change_type": "INCREMENTAL",\n'
            '  "tasks": [\n'
            "    {\n"
            '      "id": "task-001",\n'
            '      "title": "Add endpoint"\n'
            "    }\n"
            "  ]\n"
            "}\n"
        )
        codes = _violation_codes(content)
        assert "HUW029" in codes, "Should detect embedded JSON example"
        assert "HUR018" in codes, "Should detect 'Example output:'"

    def test_llm_reviewer_with_html_and_tables(self):
        """Realistic reviewer prompt with HTML and tables."""
        content = (
            "Review the code.\n\n"
            "| Criteria | Weight |\n"
            "| -------- | ------ |\n"
            "| Security | High   |\n"
            "| Quality  | Medium |\n\n"
            "<b>Critical issues</b> must be fixed.\n"
        )
        codes = _violation_codes(content)
        assert "HUW010" in codes, "Should detect markdown tables"
        assert "HUW012" in codes, "Should detect HTML tags"

    def test_llm_prompt_with_task_list_and_links(self):
        """LLMs add task lists and reference links."""
        content = (
            "Follow this checklist:\n"
            "- [ ] Check code quality\n"
            "- [ ] Run tests\n"
            "- [x] Review documentation\n\n"
            "See [style guide](https://example.com/style) for details.\n"
        )
        codes = _violation_codes(content)
        assert "HUW015" in codes, "Should detect task lists"
        assert "HUW006" in codes, "Should detect markdown links"

    def test_clean_hu_file_no_violations(self):
        """A properly written .hu file should have zero violations."""
        content = (
            "You are a code reviewer focused on production quality.\n\n"
            "Review the following code:\n{code}\n\n"
            "Previous review comments:\n{previous_reviews}\n\n"
            "Focus on:\n"
            "- Correctness and edge cases\n"
            "- Security vulnerabilities\n"
            "- Performance issues\n"
            "- Code maintainability\n\n"
            "Provide specific, actionable feedback with file and line references."
        )
        linter = HuLinter()
        result = linter.lint(content, filepath="/team/code_reviewer.hu")
        assert result.clean, (
            f"Clean .hu file should have no violations, got: "
            f"{[(v.rule.code, v.message) for v in result.violations]}"
        )

    def test_llm_overwrites_clean_file_with_markdown(self):
        """Simulates LLM rewriting a clean file and adding formatting."""
        original = (
            "You are a developer.\n\n"
            "Implement the specs in {specs}.\n"
            "Use the existing code in {existing_code}.\n"
        )
        llm_rewrite = (
            "# Developer Agent\n\n"
            "You are a **Senior Software Engineer**.\n\n"
            "## Specifications\n"
            "{{specs}}\n\n"
            "## Existing Code\n"
            "{{existing_code}}\n\n"
            "**Output Format:**\n"
            "```json\n"
            '{"files": [{"path": "...", "content": "..."}]}\n'
            "```\n"
        )
        codes = _violation_codes(llm_rewrite, original=original)
        assert "HUW002" in codes, "Should detect # headers"
        assert "HUW003" in codes, "Should detect **bold**"
        assert "HUW008" in codes, "Should detect code fences"
        assert "HUR018" in codes, "Should detect output format hint"
        assert "HUW016" in codes, "Should detect excessive growth"

    def test_llm_respond_with_json_instruction(self):
        """LLMs write 'respond with JSON' which wasn't caught before."""
        content = (
            "You are an analyzer.\n\n"
            "Analyze the input in {data}.\n\n"
            "Respond with JSON containing status and findings."
        )
        codes = _violation_codes(content)
        assert "HUR018" in codes

    def test_llm_generate_output_as_yaml(self):
        """LLMs write 'generate ... as YAML' which wasn't caught before."""
        content = (
            "You are a config generator.\n\n"
            "Generate the configuration as YAML based on {requirements}."
        )
        codes = _violation_codes(content)
        assert "HUR018" in codes

    def test_llm_your_response_should_pattern(self):
        """LLMs write 'your response should...' output instructions."""
        content = (
            "You are a code reviewer.\n\n"
            "Review the code in {code}.\n\n"
            "Your response should contain all found issues."
        )
        codes = _violation_codes(content)
        assert "HUR018" in codes

    def test_llm_standalone_output_header(self):
        """LLMs write 'Output:' as a standalone section header."""
        content = (
            "Analyze the data.\n\n"
            "Output:\n\n"
            "Provide the results."
        )
        codes = _violation_codes(content)
        assert "HUR018" in codes

    def test_llm_sample_output_label(self):
        """LLMs write 'Sample output:' before examples."""
        content = (
            "Generate a report.\n\n"
            "Sample output:\n"
            "The report should contain..."
        )
        codes = _violation_codes(content)
        assert "HUR018" in codes

    def test_llm_inline_code_everywhere(self):
        """LLMs wrap everything in backticks."""
        content = (
            "Check if `user_id` is valid, then call `authenticate()` "
            "and store the result in `session_token`."
        )
        violations = _violations_for_code(content, "HUW014")
        assert len(violations) == 3

    def test_llm_blockquote_notes(self):
        """LLMs use blockquotes for notes and warnings."""
        content = (
            "Review the code.\n\n"
            "> Note: Security issues are critical.\n"
            "> Warning: Performance matters too.\n"
        )
        violations = _violations_for_code(content, "HUW009")
        assert len(violations) == 2
