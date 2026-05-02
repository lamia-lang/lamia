""".hu file linter.

.hu files are plain-text prompt templates with {param} placeholders and
{@file} context references.  They should contain NO markdown formatting,
no YAML front matter, no emojis, no HTML.  Just clean, readable text
that an LLM can consume without visual decoration.

Rule index (code format: HU{severity}{NNN}, sorted by severity):
  ── Errors (must fix) ──
  HUE001  E  yaml-front-matter       YAML front matter is not valid in .hu
  HUE019  E  escaped-param           {{param}} used but caller passes it as arg
  ── Warnings (should fix) ──
  HUW002  W  markdown-header          # headings are formatting
  HUW003  W  markdown-bold            **bold** / __bold__ is formatting
  HUW004  W  markdown-italic          *italic* / _italic_ is formatting
  HUW005  W  markdown-strikethrough   ~~strike~~ is formatting
  HUW006  W  markdown-link            [text](url) -- use plain URLs
  HUW007  W  markdown-image           ![alt](url) not useful in prompts
  HUW008  W  markdown-code-fence      ```lang fences are formatting
  HUW009  W  markdown-blockquote      > quotes are formatting
  HUW010  W  markdown-table           | pipe tables | are formatting
  HUW011  W  markdown-horizontal-rule --- / *** / ___ are formatting
  HUW012  W  html-tag                 HTML tags don't belong in prompts
  HUW013  W  emoji                    emojis are decorative
  HUW014  W  markdown-inline-code     `backtick code` is formatting
  HUW015  W  markdown-task-list       - [ ] task lists are formatting
  HUW016  W  excessive-growth         content grew >2x original
  HUW017  W  too-many-params          >10 {param} placeholders
  HUW021  W  empty-file               .hu file has no content
  HUW022  W  trailing-whitespace      trailing whitespace on lines
  HUW029  W  example-output-block    embedded example outputs belong in Lamia types
  ── Convention ──
  HUC020  C  param-naming             params should use snake_case
  HUC023  C  short-param-name         single-char param names are unclear
  HUC024  C  verbose-param-name       param name is excessively long (>30 chars)
  HUC025  C  filename-naming          .hu filename should be snake_case
  HUC026  C  leading-blank-lines      file starts with blank lines
  HUC028  C  generic-filename         generic names like agent.hu say nothing
  ── Refactor ──
  HUR018  R  output-format-hint       use Lamia -> return types, not inline schemas
  HUR027  R  long-prompt              prompt is very long (>3000 chars)
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from lamia.lint.base import BaseLinter, LintRule, LintViolation, LintResult, Severity
from lamia.lint.find_usage import find_usage

_GROWTH_RATIO = 2.0

# ── Rules ───────────────────────────────────────────────────────────────────

YAML_FRONT_MATTER = LintRule(
    code="HUE001",
    severity=Severity.Error,
    name="yaml-front-matter",
    description="YAML front matter (---...---) is not valid in .hu files",
    pattern=re.compile(r"\A---[ \t]*\n.*?\n---[ \t]*\n", re.DOTALL),
)

ESCAPED_PARAM = LintRule(
    code="HUE019",
    severity=Severity.Error,
    name="escaped-param",
    description=(
        "{{%s}} escapes the braces, making this a literal instead of a parameter, "
        "but an .lm caller passes %s= as an argument. Use {%s}"
    ),
)
_ESCAPED_PARAM_RE = re.compile(r"\{\{(\w+)(?::[^}]*)?\}\}")

MD_HEADER = LintRule(
    code="HUW002",
    severity=Severity.Warning,
    name="markdown-header",
    description="Markdown headers (# Title) are formatting -- .hu files are plain text",
    pattern=re.compile(r"^#{1,6}\s+\S", re.MULTILINE),
)

MD_BOLD = LintRule(
    code="HUW003",
    severity=Severity.Warning,
    name="markdown-bold",
    description="Markdown bold (**text** or __text__) is formatting",
    pattern=re.compile(r"\*\*[^*\n]+\*\*|__[^_\n]+__"),
)

MD_ITALIC = LintRule(
    code="HUW004",
    severity=Severity.Warning,
    name="markdown-italic",
    description="Markdown italic (*text* or _text_) is formatting",
    pattern=re.compile(r"(?<!\w)\*[^*\n]{2,}\*(?!\w)|(?<!\w)_[^_\n]{2,}_(?!\w)"),
)

MD_STRIKETHROUGH = LintRule(
    code="HUW005",
    severity=Severity.Warning,
    name="markdown-strikethrough",
    description="Markdown strikethrough (~~text~~) is formatting",
    pattern=re.compile(r"~~[^~\n]+~~"),
)

MD_LINK = LintRule(
    code="HUW006",
    severity=Severity.Warning,
    name="markdown-link",
    description="Markdown links [text](url) are formatting -- use plain URLs",
    pattern=re.compile(r"\[([^\]]+)\]\(([^)]+)\)"),
)

MD_IMAGE = LintRule(
    code="HUW007",
    severity=Severity.Warning,
    name="markdown-image",
    description="Markdown images ![alt](url) are not useful in prompts",
    pattern=re.compile(r"!\[([^\]]*)\]\(([^)]+)\)"),
)

MD_CODE_FENCE = LintRule(
    code="HUW008",
    severity=Severity.Warning,
    name="markdown-code-fence",
    description="Code fences (```) are markdown formatting -- .hu files are plain text",
    pattern=re.compile(r"^```", re.MULTILINE),
)

MD_BLOCKQUOTE = LintRule(
    code="HUW009",
    severity=Severity.Warning,
    name="markdown-blockquote",
    description="Blockquotes (> text) are markdown formatting",
    pattern=re.compile(r"^>\s+\S", re.MULTILINE),
)

MD_TABLE = LintRule(
    code="HUW010",
    severity=Severity.Warning,
    name="markdown-table",
    description="Markdown tables (| col | col |) are formatting",
    pattern=re.compile(r"^\|.+\|.+\|$", re.MULTILINE),
)

MD_HORIZONTAL_RULE = LintRule(
    code="HUW011",
    severity=Severity.Warning,
    name="markdown-horizontal-rule",
    description="Markdown horizontal rules (--- or ***) are formatting",
    pattern=re.compile(r"^(?:---|\*\*\*|___)\s*$", re.MULTILINE),
)

HTML_TAG = LintRule(
    code="HUW012",
    severity=Severity.Warning,
    name="html-tag",
    description="HTML tags are not appropriate in .hu prompt templates",
    pattern=re.compile(
        r"</?(?:div|span|p|br|hr|table|tr|td|th|ul|ol|li|"
        r"h[1-6]|a|img|pre|code|em|strong|b|i)\b",
        re.IGNORECASE,
    ),
)

EMOJI = LintRule(
    code="HUW013",
    severity=Severity.Warning,
    name="emoji",
    description="Emojis are decorative -- .hu files should be clean text",
    pattern=re.compile(
        "["
        "\U0001F300-\U0001F9FF"
        "\U00002600-\U000027BF"
        "\U0001FA00-\U0001FAFF"
        "\U00002702-\U000027B0"
        "\U0000FE00-\U0000FE0F"
        "\U0000200D"
        "\U000024C2-\U0001F251"
        "]+",
    ),
)

MD_INLINE_CODE = LintRule(
    code="HUW014",
    severity=Severity.Warning,
    name="markdown-inline-code",
    description="Inline code (`code`) is markdown formatting",
    pattern=re.compile(r"(?<!`)`(?!`)[^`\n]+`(?!`)"),
)

MD_TASK_LIST = LintRule(
    code="HUW015",
    severity=Severity.Warning,
    name="markdown-task-list",
    description="Markdown task lists (- [ ] / - [x]) are formatting",
    pattern=re.compile(r"^[-*]\s+\[[ xX]\]", re.MULTILINE),
)

EXCESSIVE_GROWTH = LintRule(
    code="HUW016",
    severity=Severity.Warning,
    name="excessive-growth",
    description="Content grew disproportionately -- make minimal, targeted changes",
)

TOO_MANY_PARAMS = LintRule(
    code="HUW017",
    severity=Severity.Warning,
    name="too-many-params",
    description="Too many {param} placeholders -- consider using {@file} to include large content",
)

EMPTY_FILE = LintRule(
    code="HUW021",
    severity=Severity.Warning,
    name="empty-file",
    description=".hu file has no meaningful content",
)

TRAILING_WHITESPACE = LintRule(
    code="HUW022",
    severity=Severity.Warning,
    name="trailing-whitespace",
    description="Line has trailing whitespace",
    pattern=re.compile(r"[ \t]+$", re.MULTILINE),
)

OUTPUT_FORMAT_HINT = LintRule(
    code="HUR018",
    severity=Severity.Refactor,
    name="output-format-hint",
    description=(
        "Don't embed output format instructions in the prompt. "
        "Lamia has built-in return type validation (JSON, HTML, YAML, XML, CSV, Markdown) "
        "-- define a Pydantic model and use -> Type[Model] on the call site"
    ),
)
_OUTPUT_FORMAT_PATTERNS = [
    # "Output JSON:", "**Response Format:**", "Return Type:", "Expected Schema:"
    re.compile(
        r"(?:^|\n)\s*\*{0,2}(?:output|response|return|expected)\s+"
        r"(?:json|format|schema|structure|type)"
        r"\s*:?\s*\*{0,2}\s*:",
        re.IGNORECASE,
    ),
    # "output ... as JSON", "respond with JSON", "return a JSON object"
    re.compile(
        r"(?:output|respond|reply|return|produce|generate)\s+.*?\b"
        r"(?:as|with|in|a)\s+(?:json|yaml|xml|csv)\b",
        re.IGNORECASE,
    ),
    # "Example output:", "Example response:", "Sample output:"
    re.compile(
        r"(?:^|\n)\s*\*{0,2}(?:example|sample)\s+"
        r"(?:output|response|result|json)"
        r"\s*:?\s*\*{0,2}\s*:",
        re.IGNORECASE,
    ),
    # "Your output should", "your response must", "format your response as"
    re.compile(
        r"(?:your|the)\s+(?:output|response)\s+(?:should|must|will|format)",
        re.IGNORECASE,
    ),
    # "Output:" alone at start of line (common LLM pattern)
    re.compile(
        r"^(?:\*{2})?Output(?:\s+Format)?(?:\*{2})?:\s*$",
        re.MULTILINE | re.IGNORECASE,
    ),
]

PARAM_NAMING = LintRule(
    code="HUC020",
    severity=Severity.Convention,
    name="param-naming",
    description="Parameter {%s} should use snake_case (e.g. {%s})",
)

SHORT_PARAM_NAME = LintRule(
    code="HUC023",
    severity=Severity.Convention,
    name="short-param-name",
    description="Parameter {%s} is too short -- use a descriptive name",
)

VERBOSE_PARAM_NAME = LintRule(
    code="HUC024",
    severity=Severity.Convention,
    name="verbose-param-name",
    description="Parameter {%s} is very long (%d chars) -- consider a shorter name",
)

FILENAME_NAMING = LintRule(
    code="HUC025",
    severity=Severity.Convention,
    name="filename-naming",
    description=".hu filename '%s' should be snake_case (e.g. '%s')",
)

LEADING_BLANK_LINES = LintRule(
    code="HUC026",
    severity=Severity.Convention,
    name="leading-blank-lines",
    description="File starts with blank lines -- content should begin on line 1",
    pattern=re.compile(r"\A\s*\n", re.DOTALL),
)

GENERIC_FILENAME = LintRule(
    code="HUC028",
    severity=Severity.Convention,
    name="generic-filename",
    description=(
        ".hu filename '%s' is too generic -- use a role-based name (researcher, reviewer) "
        "or action-based name (summarize, extract)"
    ),
)

_GENERIC_HU_NAMES = {
    "agent", "prompt", "template", "helper", "util", "utils",
    "worker", "task", "handler", "processor", "default",
}

EXAMPLE_OUTPUT_BLOCK = LintRule(
    code="HUW029",
    severity=Severity.Warning,
    name="example-output-block",
    description=(
        "Don't embed example outputs in .hu files. "
        ".hu prompts should be output-agnostic -- Lamia handles output "
        "format validation via -> Type[Model] on the call site"
    ),
)
# Heuristic: a standalone JSON object/array block (3+ lines with "key": patterns)
_EXAMPLE_JSON_BLOCK_RE = re.compile(
    r"^\s*[\[{]\s*$\n"
    r"(?:.*\n){1,}?"
    r"^\s*[\]}]\s*$",
    re.MULTILINE,
)
_JSON_KEY_RE = re.compile(r'"[a-z_A-Z][a-z_A-Z0-9]*"\s*:')

LONG_PROMPT = LintRule(
    code="HUR027",
    severity=Severity.Refactor,
    name="long-prompt",
    description=(
        "Prompt is %d chars -- consider splitting into focused sub-prompts "
        "or moving large content to {@file} references"
    ),
)

_TOO_MANY_PARAMS_THRESHOLD = 10
_VERBOSE_PARAM_THRESHOLD = 30
_LONG_PROMPT_THRESHOLD = 3000
_PARAM_COUNT_RE = re.compile(r'\{(\w+)(?::[^}]*)?\}')
_SNAKE_CASE_RE = re.compile(r'^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$')
_FILENAME_SNAKE_RE = re.compile(r'^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$')

ALL_RULES = [
    YAML_FRONT_MATTER, ESCAPED_PARAM,
    MD_HEADER, MD_BOLD, MD_ITALIC, MD_STRIKETHROUGH,
    MD_LINK, MD_IMAGE, MD_CODE_FENCE, MD_BLOCKQUOTE, MD_TABLE,
    MD_HORIZONTAL_RULE, HTML_TAG, EMOJI, MD_INLINE_CODE, MD_TASK_LIST,
    EXCESSIVE_GROWTH, TOO_MANY_PARAMS, EMPTY_FILE, TRAILING_WHITESPACE,
    EXAMPLE_OUTPUT_BLOCK,
    PARAM_NAMING, SHORT_PARAM_NAME, VERBOSE_PARAM_NAME,
    FILENAME_NAMING, LEADING_BLANK_LINES, GENERIC_FILENAME,
    OUTPUT_FORMAT_HINT, LONG_PROMPT,
]


def _find_lm_caller_kwargs(hu_stem: str, cwd: str) -> set[str]:
    """Collect kwarg names passed to hu_stem(...) in .lm files under cwd."""
    refs = find_usage(hu_stem, cwd, extensions=("*.lm",))
    kwargs: set[str] = set()
    call_re = re.compile(rf"\b{re.escape(hu_stem)}\s*\(([^)]*)\)")
    kwarg_re = re.compile(r"(\w+)\s*=")
    for ref in refs:
        for m in call_re.finditer(ref.text):
            kwargs.update(kwarg_re.findall(m.group(1)))
    return kwargs


class HuLinter(BaseLinter):
    """Linter for .hu (human prompt template) files."""

    def __init__(self) -> None:
        super().__init__()
        self.rules = list(ALL_RULES)

    def lint(
        self,
        content: str,
        original: Optional[str] = None,
        cwd: Optional[str] = None,
        filepath: Optional[str] = None,
    ) -> LintResult:
        violations: list[LintViolation] = []

        # ── Pattern-based rules ─────────────────────────────────────────
        for rule in self.rules:
            if rule.pattern is None:
                continue

            if rule is YAML_FRONT_MATTER:
                m = rule.pattern.search(content)
                if m:
                    violations.append(LintViolation(
                        rule=rule, line=1,
                        message=rule.description,
                        snippet=m.group()[:80],
                    ))
                continue

            if rule is MD_HORIZONTAL_RULE:
                for m in rule.pattern.finditer(content):
                    lineno = content[:m.start()].count("\n") + 1
                    if lineno == 1:
                        continue
                    violations.append(LintViolation(
                        rule=rule, line=lineno,
                        message=rule.description,
                        snippet=m.group().strip(),
                    ))
                continue

            if rule is TRAILING_WHITESPACE:
                count = len(list(rule.pattern.finditer(content)))
                if count:
                    violations.append(LintViolation(
                        rule=rule, line=0,
                        message=f"{count} line(s) have trailing whitespace",
                    ))
                continue

            if rule is LEADING_BLANK_LINES:
                if rule.pattern.match(content):
                    violations.append(LintViolation(
                        rule=rule, line=1, message=rule.description,
                    ))
                continue

            for m in rule.pattern.finditer(content):
                lineno = content[:m.start()].count("\n") + 1
                violations.append(LintViolation(
                    rule=rule, line=lineno,
                    message=rule.description,
                    snippet=m.group()[:60],
                ))

        # ── Empty file ──────────────────────────────────────────────────
        if not content.strip():
            violations.append(LintViolation(
                rule=EMPTY_FILE, line=0, message=EMPTY_FILE.description,
            ))

        # ── Excessive growth ────────────────────────────────────────────
        if original is not None and len(original) > 0:
            ratio = len(content) / len(original)
            if ratio > _GROWTH_RATIO:
                violations.append(LintViolation(
                    rule=EXCESSIVE_GROWTH, line=0,
                    message=f"Content grew {ratio:.1f}x ({len(original)} -> {len(content)} chars)",
                ))

        # ── Param analysis ──────────────────────────────────────────────
        unique_params = set(
            m.group(1) for m in _PARAM_COUNT_RE.finditer(content)
            if not m.group(1).startswith("@")
        )

        if len(unique_params) > _TOO_MANY_PARAMS_THRESHOLD:
            violations.append(LintViolation(
                rule=TOO_MANY_PARAMS, line=0,
                message=(
                    f"Found {len(unique_params)} params -- if this file "
                    f"contains large embedded content (JSON, CSS, code), "
                    f"consider moving it to a separate file and using "
                    f"{{@filename}} to include it"
                ),
            ))

        for name in unique_params:
            if not _SNAKE_CASE_RE.match(name):
                suggested = re.sub(r'(?<=[a-z0-9])([A-Z])', r'_\1', name).lower()
                for m in re.finditer(r'\{' + re.escape(name) + r'(?::[^}]*)?\}', content):
                    lineno = content[:m.start()].count("\n") + 1
                    violations.append(LintViolation(
                        rule=PARAM_NAMING, line=lineno,
                        message=PARAM_NAMING.description % (name, suggested),
                        snippet=m.group(),
                    ))
                    break

            if len(name) == 1:
                violations.append(LintViolation(
                    rule=SHORT_PARAM_NAME, line=0,
                    message=SHORT_PARAM_NAME.description % name,
                ))

            if len(name) > _VERBOSE_PARAM_THRESHOLD:
                violations.append(LintViolation(
                    rule=VERBOSE_PARAM_NAME, line=0,
                    message=VERBOSE_PARAM_NAME.description % (name, len(name)),
                ))

        # ── Escaped param (cross-file: needs cwd) ──────────────────────
        escaped_names = set(
            m.group(1).split(":")[0] for m in _ESCAPED_PARAM_RE.finditer(content)
        )
        if escaped_names and cwd:
            hu_stem = None
            if filepath:
                hu_stem = Path(filepath).stem
            caller_kwargs = _find_lm_caller_kwargs(hu_stem, cwd) if hu_stem else set()
            conflicting = escaped_names & caller_kwargs
            for name in conflicting:
                for m in _ESCAPED_PARAM_RE.finditer(content):
                    pname = m.group(1).split(":")[0]
                    if pname != name:
                        continue
                    lineno = content[:m.start()].count("\n") + 1
                    violations.append(LintViolation(
                        rule=ESCAPED_PARAM, line=lineno,
                        message=ESCAPED_PARAM.description % (name, name, name),
                        snippet=m.group(),
                    ))

        # ── Filename checks ─────────────────────────────────────────────
        if filepath:
            stem = Path(filepath).stem
            if not _FILENAME_SNAKE_RE.match(stem):
                suggested = re.sub(r'(?<=[a-z0-9])([A-Z])', r'_\1', stem)
                suggested = re.sub(r'[-\s]+', '_', suggested).lower()
                violations.append(LintViolation(
                    rule=FILENAME_NAMING, line=0,
                    message=FILENAME_NAMING.description % (stem + ".hu", suggested + ".hu"),
                ))
            if stem in _GENERIC_HU_NAMES:
                violations.append(LintViolation(
                    rule=GENERIC_FILENAME, line=0,
                    message=GENERIC_FILENAME.description % (stem + ".hu"),
                ))

        # ── Long prompt ─────────────────────────────────────────────────
        if len(content) > _LONG_PROMPT_THRESHOLD:
            violations.append(LintViolation(
                rule=LONG_PROMPT, line=0,
                message=LONG_PROMPT.description % len(content),
            ))

        # ── Output format hints (multi-pattern) ───────────────────────
        for pat in _OUTPUT_FORMAT_PATTERNS:
            for m in pat.finditer(content):
                lineno = content[:m.start()].count("\n") + 1
                violations.append(LintViolation(
                    rule=OUTPUT_FORMAT_HINT, line=lineno,
                    message=OUTPUT_FORMAT_HINT.description,
                    snippet=m.group().strip()[:60],
                ))

        # ── Example output blocks ─────────────────────────────────────
        for m in _EXAMPLE_JSON_BLOCK_RE.finditer(content):
            block = m.group()
            if len(_JSON_KEY_RE.findall(block)) >= 2:
                lineno = content[:m.start()].count("\n") + 1
                violations.append(LintViolation(
                    rule=EXAMPLE_OUTPUT_BLOCK, line=lineno,
                    message=EXAMPLE_OUTPUT_BLOCK.description,
                    snippet=block.split("\n")[0].strip()[:60],
                ))

        return LintResult(violations=violations)
