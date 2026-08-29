"""Script analysis utilities — no cloud dependencies."""

import ast
from dataclasses import dataclass, fields
from pathlib import Path

from lamia.interpreter.detectors import LLMCommandDetector
from lamia.interpreter.ast_analyzer import ActionNamespaceAnalyzer
from lamia.interpreter.commands import WebCommand, FileCommand


@dataclass
class ScriptCapabilities:
    """Cloud-agnostic metadata about what a .lm script uses."""

    uses_llm: bool = False
    uses_browser: bool = False
    uses_files: bool = False
    uses_file_context: bool = False


def script_capability_field_names() -> tuple[str, ...]:
    """Return ordered ScriptCapabilities field names for contract tests."""
    return tuple(field.name for field in fields(ScriptCapabilities))


def script_writes_files(script_path: Path) -> bool:
    """Whether the script references file-write operations anywhere in source."""
    capabilities = analyze_script(script_path)
    return capabilities.uses_files or capabilities.uses_file_context


def analyze_script(script_path: Path) -> ScriptCapabilities:
    """Analyze a .lm script using existing Lamia AST infrastructure.

    Uses LLMCommandDetector to find resolved LLM commands and
    ActionNamespaceAnalyzer to detect web/file namespace usage.
    """
    try:
        source = script_path.read_text()
    except OSError:
        return ScriptCapabilities()

    try:
        tree = ast.parse(source)
    except SyntaxError:
        return ScriptCapabilities()

    llm_functions = LLMCommandDetector().detect_commands(source)

    ns_analyzer = ActionNamespaceAnalyzer()
    ns_analyzer.visit(tree)

    return ScriptCapabilities(
        uses_llm=len(llm_functions) > 0,
        uses_browser=(
            WebCommand.__name__ in ns_analyzer.used_types
            or "web" in ns_analyzer.used_namespaces
            or "session" in ns_analyzer.used_namespaces
        ),
        uses_files=(
            FileCommand.__name__ in ns_analyzer.used_types
            or "file" in ns_analyzer.used_namespaces
        ),
        uses_file_context="files" in ns_analyzer.used_namespaces,
    )


