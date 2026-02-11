"""Interactive eval CLI for ``lamia eval <script>``."""

import argparse
import asyncio
import logging
import sys
import traceback
from pathlib import Path
from typing import Optional, Sequence, Type

from lamia import Lamia
from lamia.cli.api_key_utils import detect_api_key, handle_api_key
from lamia.cli.cli_styling import Colors, setup_cli_logging
from lamia.cli.prompts import display_numbered_list, input_number, pick_from_list
from lamia.cli.scaffold import REMOTE_PROVIDER_MODELS
from lamia.errors import MissingAPIKeysError
from lamia.eval.evaluator import EvaluationResult, ModelEvaluator
from lamia.interpreter.command_parser import CommandParser
from lamia.interpreter.commands import LLMCommand
from lamia.interpreter.detectors.llm_command_detector import (
    FileWriteReturnType,
    LLMFunctionInfo,
    ParametricReturnType,
    ReturnType,
    SimpleReturnType,
)
from lamia.interpreter.hybrid_syntax_parser import HybridSyntaxParser
from lamia.types import BaseType
from lamia import types as lamia_types

logger = logging.getLogger(__name__)

_STRATEGIES: list[tuple[str, str]] = [
    ("binary_search", "fewest API calls"),
    ("step_back", "tests from cheapest up"),
]

_MAX_PROMPT_PREVIEW = 80


def handle_eval() -> None:
    """Handle ``lamia eval <script>`` — interactive model evaluation."""
    parser = argparse.ArgumentParser(prog="lamia eval")
    parser.add_argument("script", help="Script file to evaluate")
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args(sys.argv[2:])

    setup_cli_logging(args.log_level.upper())

    script_path = Path(args.script)
    if not script_path.is_file():
        logger.error(f"File not found: {args.script}")
        sys.exit(1)

    # Parse script to extract LLM prompts
    source = script_path.read_text()
    llm_prompts = _extract_llm_prompts(source)
    if not llm_prompts:
        logger.error("No LLM prompts found in script")
        sys.exit(1)

    print("\n=== Model Evaluation Setup ===\n")

    # Detect API keys — show all providers with status (same UX as lamia init)
    project_dir = str(Path.cwd())
    provider_items: list[tuple[str, str]] = []
    for provider in REMOTE_PROVIDER_MODELS:
        key, env_var, source_label = detect_api_key(provider, project_dir)
        label = f"{env_var} via {source_label}" if key else "no API key"
        provider_items.append((provider, label))

    # Pick provider — _handle_api_key will prompt for key if missing
    provider = pick_from_list("Provider", provider_items)
    handle_api_key(project_dir, provider)

    models = REMOTE_PROVIDER_MODELS.get(provider, [])
    if not models:
        logger.error(f"No models defined for provider '{provider}'")
        sys.exit(1)

    # Show models and pick range
    display_numbered_list(f"{provider} models (cheapest → most capable)", models)
    max_idx = input_number(
        f"  Most capable model (upper bound) [default: {len(models)}]: ",
        len(models), len(models),
    )
    min_idx = input_number(
        f"  Cheapest model (lower bound) [default: 1]: ",
        max_idx, 1,
    )

    # Evaluator expects most-capable first
    selected = [f"{provider}:{name}" for name, _ in models[min_idx - 1:max_idx]]
    selected.reverse()

    strategy = pick_from_list("Strategy", _STRATEGIES)

    print(
        f"\nFound {len(llm_prompts)} LLM prompt(s)."
        f" Evaluating with {len(selected)} models ({strategy})...\n"
    )

    # Create Lamia with first selected model as placeholder (evaluator overrides per call)
    try:
        lamia = Lamia(selected[0])
    except MissingAPIKeysError as e:
        logger.error(f"Missing API keys: {e}")
        sys.exit(1)

    try:
        asyncio.run(_run_evaluation(lamia, llm_prompts, selected, strategy))
    except MissingAPIKeysError as e:
        logger.error(f"Missing API keys: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Evaluation failed: {e}")
        if logging.getLogger().level <= logging.DEBUG:
            traceback.print_exc()
        sys.exit(1)

def _extract_llm_prompts(
    source: str,
) -> list[tuple[str, Optional[Type[BaseType]]]]:
    """Parse hybrid source and return ``(prompt, resolved_return_type)`` pairs.

    The preprocessor handles ``'prompt' -> Type`` shorthand natively,
    converting it to a synthetic function definition before detection.
    Only commands classified as LLM (not web/filesystem) are included.
    """
    parsed = HybridSyntaxParser().parse(source)
    prompts: list[tuple[str, Optional[Type[BaseType]]]] = []
    for info in parsed.get("llm_functions", {}).values():
        if not isinstance(info, LLMFunctionInfo):
            continue
        if not isinstance(CommandParser(info.command).parsed_command, LLMCommand):
            continue
        prompts.append((info.command, _resolve_return_type(info.return_type)))
    return prompts


def _resolve_type_name(name: Optional[str]) -> Optional[Type[BaseType]]:
    """Resolve a type name string (e.g. ``'HTML'``) to a ``BaseType`` subclass."""
    if not name:
        return None
    resolved = getattr(lamia_types, name, None)
    if resolved is not None and isinstance(resolved, type) and issubclass(resolved, BaseType):
        return resolved
    return None


def _resolve_return_type(
    rt: Optional[ReturnType],
) -> Optional[Type[BaseType]]:
    """Best-effort resolution of a parsed return type to an actual ``BaseType`` subclass."""
    if rt is None:
        return None
    if isinstance(rt, (SimpleReturnType, ParametricReturnType)):
        return _resolve_type_name(rt.base_type)
    if isinstance(rt, FileWriteReturnType) and rt.inner_return_type is not None:
        return _resolve_return_type(rt.inner_return_type)
    return None

async def _run_evaluation(
    lamia: Lamia,
    prompts: Sequence[tuple[str, Optional[Type[BaseType]]]],
    models: list[str],
    strategy: str,
) -> None:
    """Evaluate each prompt and print coloured results. Stops on first all-fail."""
    async with ModelEvaluator(lamia_instance=lamia) as evaluator:
        for idx, (prompt_text, return_type) in enumerate(prompts, 1):
            _print_prompt_header(idx, len(prompts), prompt_text)
            result = await evaluator.evaluate_prompt(
                prompt_text, return_type, models, strategy,
            )
            _print_attempt_results(result)

            if not result.success:
                print(
                    f"\n{Colors.RED}All models failed on prompt #{idx}."
                    f" Stopping evaluation.{Colors.RESET}\n"
                )
                return

    print(f"All {len(prompts)} prompt(s) evaluated successfully.\n")

def _print_prompt_header(idx: int, total: int, prompt_text: str) -> None:
    preview = prompt_text.replace("\n", " ").strip()
    if len(preview) > _MAX_PROMPT_PREVIEW:
        preview = preview[:_MAX_PROMPT_PREVIEW] + "..."
    print(f"[{idx}/{total}] {Colors.CYAN}{preview}{Colors.RESET}")


def _print_attempt_results(result: EvaluationResult) -> None:
    for attempt in result.attempts:
        if attempt.success:
            status = f"{Colors.GREEN}PASS{Colors.RESET}"
        else:
            status = f"{Colors.RED}FAIL{Colors.RESET}"
        cost_str = f" ({attempt.cost})" if attempt.cost else ""
        error_str = f" — {attempt.error}" if attempt.error else ""
        print(f"{status} {attempt.model}{cost_str}{error_str}")
    if result.success and result.minimum_working_model:
        print(f"→ cheapest: {Colors.GREEN}{result.minimum_working_model}{Colors.RESET}")