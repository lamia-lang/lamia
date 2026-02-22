import asyncio
import signal
import sys
import os
import readline  # For better input handling (command history)
from typing import Optional
import ast
import argparse
import select
import yaml
import logging
import runpy
import traceback

from lamia import Lamia
from lamia.async_bridge import EventLoopManager
from lamia.errors import (
    MissingAPIKeysError,
    ExternalOperationTransientError,
    ExternalOperationPermanentError,
    ExternalOperationRateLimitError,
    ExternalOperationError,
)
from .scaffold import create_minimal_config, ensure_extensions_folder, update_config_with_extensions, create_env_file, create_config_from_wizard_result
from .init_wizard import run_init_wizard
from .eval_cli import handle_eval
from .cli_styling import setup_cli_logging
from lamia.interpreter.command_types import CommandType
from lamia.interpreter.hybrid_executor import HybridExecutor

# Hybrid syntax file extensions that should be processed
HYBRID_EXTENSIONS = {'.hu', '.lm'}

logger = logging.getLogger(__name__)

async def interactive_mode(lamia: Lamia):
    """Run Lamia in interactive mode, processing user prompts."""
    logger.info("Lamia Interactive Mode")
    logger.info("Enter your prompts")

    prompt_str = "\n🤖 > (SEND=submit, CANCEL=discard, STOP=interrupt, STATS=stats, Command/Ctrl C or EXIT=quit)\n> "

    running_task = None

    # Flag to indicate an immediate command like STATS was executed
    do_stats_command = False

    while True:
        try:
            # Multiline input: keep reading until 'SEND' is entered on a new line
            lines = []
            while True:
                line = input(prompt_str if not lines else "> ")
                # Immediate command: STATS (case-insensitive) without SEND
                if not lines and line.strip().upper() == "STATS":
                    stats = lamia.get_validation_stats()
                    print("\n📊 Validation statistics:")
                    print("----------------------------------------")
                    print(stats)
                    print("----------------------------------------")
                    do_stats_command = True
                    break  # break out of inner input loop
                if line.strip() == "SEND":
                    break
                if line.strip().upper() == "CANCEL":
                    logger.info("Prompt cancelled. Start typing a new prompt.")
                    lines = []
                    # Show the prompt again for a new input
                    continue
                # Immediate exit: only when typed alone before any real content (no SEND needed)
                if not lines and line.strip().lower() in ['exit', 'quit', ':q']:
                    logger.info("\nGoodbye! 👋")
                    if running_task and not running_task.done():
                        running_task.cancel()
                    _graceful_shutdown(lamia)
                    return  # unreachable, but satisfies type checkers
                if line.strip():
                    lines.append(line)
            # If an immediate command like STATS was executed, restart outer loop
            if do_stats_command:
                do_stats_command = False
                continue

            user_input = "\n".join(lines).strip()

            if not user_input:
                logger.info("Prompt is empty. Start typing a new prompt.")
                continue

            # Generate LLM response
            logger.info("\nThinking... 🤔 (type STOP to interrupt)")
            running_task = asyncio.create_task(lamia.run_async(user_input, _full_result=True))
            while not running_task.done():
                try:
                    await asyncio.wait_for(asyncio.shield(running_task), timeout=0.2)
                except asyncio.TimeoutError:
                    # Check for STOP command from user
                    if sys.stdin in select.select([sys.stdin], [], [], 0)[0]:
                        stop_input = sys.stdin.readline().strip()
                        if stop_input.upper() == 'STOP':
                            running_task.cancel()
                            logger.warning("Prompt interrupted by user (STOP). Start typing a new prompt.")
                            break
                        elif user_input.lower() in ['exit', 'quit', ':q']:
                            logger.info("\nGoodbye! 👋")
                            break
            if running_task.done() and not running_task.cancelled():
                result = running_task.result()
                # TODO: use a logger without timestamps, etc
                print("🔮 Response:")
                print("----------------------------------------")
                print(result.result_text)
                print("----------------------------------------")
                
                # Show detailed info for LLM responses
                if result.tracking_context.command_type == CommandType.LLM:
                    if result.tracking_context:
                        print(f"Model: {result.tracking_context.data_provider_name}")
                        
                        # Extract usage from metadata if available
                        if result.tracking_context.metadata and "usage" in result.tracking_context.metadata:
                            usage = result.tracking_context.metadata["usage"]
                            # Format usage similar to the README example
                            usage_parts = []
                            if 'prompt_tokens' in usage:
                                usage_parts.append(f"'prompt_tokens': {usage['prompt_tokens']}")
                            elif 'input_tokens' in usage:
                                usage_parts.append(f"'prompt_tokens': {usage['input_tokens']}")
                            
                            if 'completion_tokens' in usage:
                                usage_parts.append(f"'completion_tokens': {usage['completion_tokens']}")
                            elif 'output_tokens' in usage:
                                usage_parts.append(f"'completion_tokens': {usage['output_tokens']}")
                            
                            if 'total_tokens' in usage:
                                usage_parts.append(f"'total_tokens': {usage['total_tokens']}")
                            
                            if usage_parts:
                                print(f"Tokens used: {{{', '.join(usage_parts)}}}")
                else:
                    print(f"Executed by: {result.tracking_context.command_type}")
        except KeyboardInterrupt:
            logger.info("\n\nGoodbye! 👋")
            if running_task and not running_task.done():
                running_task.cancel()
            _graceful_shutdown(lamia)
            return  # unreachable
        except SystemExit:
            logger.info("\nGoodbye! 👋")
            if running_task and not running_task.done():
                running_task.cancel()
            _graceful_shutdown(lamia)
            return  # unreachable
        except Exception as e:
            traceback.print_exc()
            logger.error(f"❌ Error: {str(e)}")
            logger.error(traceback.format_exc())
            continue

def main():
    """Main entry point for the Lamia CLI."""
    _install_sigint_handler()

    if len(sys.argv) > 1 and sys.argv[1] == "init":
        parser = argparse.ArgumentParser(
            description="Lamia CLI",
            epilog="""
            Subcommands:
            init        Initialize a new Lamia project (see 'init --help' for options like --with-extensions)

            For help on a subcommand, run:
            lamia <subcommand> --help
            """
        )
        subparsers = parser.add_subparsers(dest="command", required=True, help="Subcommands (use '<subcommand> --help' for details)")
        init_parser = subparsers.add_parser("init", help="Initialize a new Lamia project in the current directory")
        init_parser.add_argument("--with-extensions", action="store_true", help="Also scaffold the extensions folder structure (adapters, validators)")
        parser.add_argument('--log-level', default='INFO', help='Set logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)')
        args = parser.parse_args()
        if args.command == "init":
            config_path = os.path.join(os.getcwd(), "config.yaml")

            # Check for existing config (re-init support)
            if os.path.exists(config_path):
                print("config.yaml already exists in this directory.")
                raw = input("Overwrite with a new configuration? [y/N]: ").strip().lower()
                if raw not in ("y", "yes"):
                    print("Init cancelled.")
                    return

            project_dir = os.getcwd()

            # Run the interactive wizard (handles API key saving internally)
            wizard_result = run_init_wizard(project_dir=project_dir, with_extensions=args.with_extensions)

            # Generate config.yaml from wizard result
            create_config_from_wizard_result(config_path, wizard_result)
            print("Created config.yaml")

            # Handle extensions folder
            if args.with_extensions:
                ext_path = ensure_extensions_folder(project_dir)
                update_config_with_extensions(config_path)
                print(f"Extensions folder scaffolded at: {ext_path}")

            # TODO: create_minimal_config is kept for programmatic/test use;
            #       the wizard path above is the primary init flow.

            print("\nDone! Run 'lamia <file.hu>' or 'lamia' for interactive mode.")
            return
        return
    elif len(sys.argv) > 1 and sys.argv[1] == "eval":
        handle_eval()
        return
    else:
        parser = argparse.ArgumentParser(
            description="Lamia CLI",
            epilog="""
            For help on a subcommand, run:
            lamia <subcommand> --help
            """
        )
        
        # Check if first arg is 'cache' subcommand
        if len(sys.argv) > 1 and sys.argv[1] == 'cache':
            # Handle cache subcommand
            from .cache_cli import CacheCLI
            import argparse as cache_argparse
            
            cache_parser = cache_argparse.ArgumentParser(
                description='Manage Lamia selector resolution cache',
                prog='lamia cache'
            )
            cache_subparsers = cache_parser.add_subparsers(dest='cache_command', help='Cache command to execute')
            
            # List command
            list_parser = cache_subparsers.add_parser('list', help='List cached selectors')
            list_parser.add_argument('--url', help='Filter by URL')
            list_parser.add_argument('--description', help='Filter by description')
            
            # Add command  
            add_parser = cache_subparsers.add_parser('add', help='Add a selector resolution to cache')
            add_parser.add_argument('original', help='Original selector that failed')
            add_parser.add_argument('resolved', help='Working selector to use instead')
            add_parser.add_argument('url', help='URL where this resolution applies')
            add_parser.add_argument('--context', help='Optional parent context for scoped cache')
            
            # Clear command
            clear_parser = cache_subparsers.add_parser('clear', help='Clear cache entries')
            clear_parser.add_argument('--description', help='Clear entries matching description')
            clear_parser.add_argument('--url', help='Clear entries matching URL')
            clear_parser.add_argument('--all', action='store_true', help='Clear entire cache')
            
            # Stats command
            stats_parser = cache_subparsers.add_parser('stats', help='Show cache statistics')
            
            # Parse cache args (skip 'cache' in sys.argv)
            cache_args = cache_parser.parse_args(sys.argv[2:])
            
            # Execute cache command
            cli = CacheCLI()
            if cache_args.cache_command == 'list':
                cli.list_cache(url_filter=cache_args.url, description_filter=cache_args.description)
            elif cache_args.cache_command == 'add':
                cli.add_selector(
                    original_selector=cache_args.original,
                    resolved_selector=cache_args.resolved,
                    url=cache_args.url,
                    parent_context=cache_args.context
                )
            elif cache_args.cache_command == 'clear':
                if not (cache_args.description or cache_args.url or cache_args.all):
                    print("Error: Must specify --description, --url, or --all", file=sys.stderr)
                    sys.exit(1)
                cli.clear_cache(description=cache_args.description, url=cache_args.url, all_entries=cache_args.all)
            elif cache_args.cache_command == 'stats':
                cli.stats()
            else:
                cache_parser.print_help()
            
            sys.exit(0)
        
        # Regular CLI arguments
        parser.add_argument('filename', nargs='?', help='Prompt file to read from (if not provided, runs in interactive mode)')
        parser.add_argument('--file', '-f', type=str, help='Read prompt from a file instead of interactive mode')
        parser.add_argument('--config', '-c', type=str, help='Path to config file (optional)')
        parser.add_argument('--log-level', default='INFO', help='Set logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)')
        parser.add_argument('--no-cache', action='store_true', help='Disable selector resolution cache (forces fresh resolution)')
        args = parser.parse_args()

    # Setup colored logging for CLI
    setup_cli_logging(args.log_level.upper())

    prompt_file = args.filename or args.file
    config_path = args.config

    config_dict = None
    if config_path:
        logger.info(f"Using configuration from: {config_path}")
        with open(config_path, 'r') as f:
            config_dict = yaml.safe_load(f)
    elif os.path.exists("config.yaml"):
        logger.info("Using configuration from: config.yaml")
        with open("config.yaml", 'r') as f:
            config_dict = yaml.safe_load(f)
    else:
        logger.error("Error: --config or a config.yaml file is required for CLI operation. Run 'lamia init' to create a config.yaml.")
        sys.exit(1)

    # Note: Lazy loading is now handled by HybridExecutor for .hu files
    # Python files still need sys.path management for regular execution

    lamia = None
    try:
        # Handle --no-cache flag
        if args.no_cache:
            logger.info("Cache disabled via --no-cache flag")
            if config_dict is None:
                config_dict = {}
            if 'web' not in config_dict:
                config_dict['web'] = {}
            if 'selector_resolution' not in config_dict['web']:
                config_dict['web']['selector_resolution'] = {}
            config_dict['web']['selector_resolution']['cache_enabled'] = False
        
        # Create Lamia instance with config
        logger.info("Creating Lamia instance...")
        lamia = Lamia.from_config(config_dict)
        
        logger.info("✅ Lamia instance created successfully")
        
        if prompt_file:
            # File execution - no async needed
            file_ext = os.path.splitext(prompt_file)[1].lower()
            
            if file_ext in HYBRID_EXTENSIONS:
                # Process hybrid syntax file with lazy loading enabled
                try:
                    logger.info(f"Processing hybrid syntax file: {prompt_file}")
                    executor = HybridExecutor(lamia)
                    executor.execute_file(prompt_file, enable_lazy_dependency_loading=True)
                    sys.exit(0)
                except ExternalOperationTransientError as e:
                    _log_external_error("❌ External operation failed after all retries", e)
                    sys.exit(1)
                except ExternalOperationPermanentError as e:
                    _log_external_error("❌ Permanent failure", e)
                    sys.exit(1)
                except ExternalOperationRateLimitError as e:
                    _log_external_error("❌ Rate limit exceeded", e)
                    sys.exit(1)
                except SyntaxError as e:
                    logger.error(f"❌ Syntax error in hybrid file: {e}")
                    logger.error(f"Line {e.lineno}: {e.text}")
                    if logger.level <= logging.DEBUG:
                        traceback.print_exc()
                    sys.exit(1)
                except ImportError as e:
                    logger.error(f"❌ Missing dependency: {e}")
                    if logger.level <= logging.DEBUG:
                        traceback.print_exc()
                    sys.exit(1)
                except KeyboardInterrupt:
                    _graceful_shutdown(lamia)
                except Exception as e:
                    # Fallback - check if it looks like a syntax/parsing error
                    error_msg = str(e).lower()
                    if any(keyword in error_msg for keyword in ['parse', 'syntax', 'transform', 'ast']):
                        logger.error(f"❌ Error processing hybrid syntax file: {e}")
                    else:
                        logger.error(f"❌ Runtime error: {e}")
                    # Always show traceback for unexpected errors
                    traceback.print_exc()
                    sys.exit(1)
            else:
                # Regular Python file
                try:
                    logger.info(f"Executing script: {prompt_file}")
                    runpy.run_path(prompt_file, run_name="__main__")
                    sys.exit(0)
                except KeyboardInterrupt:
                    _graceful_shutdown(lamia)
                except Exception as e:
                    logger.error(f"❌ Error executing script: {e}")
                    traceback.print_exc()
                    sys.exit(1)
        else:
            # Interactive mode - needs async
            async def run_interactive():
                await interactive_mode(lamia)
            
            asyncio.run(run_interactive())
            
    except MissingAPIKeysError as e:
        logger.error(f"❌ Missing API Keys: {str(e)}")
        logger.error("Please check your .env file or config.yaml for required API keys.")
        sys.exit(1)
    except Exception as e:
        traceback.print_exc()
        logger.error(f"❌ Error: {e}")
        logger.error("Check your config.yaml and logs for details.")
        sys.exit(1)
    except KeyboardInterrupt:
        _graceful_shutdown(lamia)


def _install_sigint_handler() -> None:
    """Install a SIGINT handler that immediately silences loggers and exits.

    When Ctrl+C is pressed the OS sends SIGINT to the whole process group,
    killing ChromeDriver instantly.  In-flight Selenium calls then fail and
    urllib3 retries each one, flooding the console with warnings.
    Raising KeyboardInterrupt from the handler is not enough because asyncio
    absorbs it and the loop continues processing fields against a dead browser.
    Instead we mute every noisy logger and terminate the process directly.
    """
    def _handler(signum: int, frame: object) -> None:
        logging.getLogger("urllib3").setLevel(logging.CRITICAL)
        logging.getLogger("selenium").setLevel(logging.CRITICAL)
        logging.getLogger("lamia").setLevel(logging.CRITICAL)
        print("\nShutting down...", flush=True)
        os._exit(0)

    signal.signal(signal.SIGINT, _handler)


def _graceful_shutdown(lamia_instance: 'Optional[Lamia]') -> None:
    """Clean up resources and terminate the process.

    Uses os._exit() to bypass asyncio's loop-teardown which would otherwise
    block waiting for cancelled tasks to drain.
    """
    logger.info("\nShutting down...")
    if lamia_instance is not None:
        try:
            EventLoopManager.run_coroutine(lamia_instance._engine.cleanup())
        except Exception:
            pass
    EventLoopManager.shutdown()
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(0)


def _log_external_error(prefix: str, exc: Exception) -> None:
    """Log user-facing external errors without stack traces unless debugging."""
    logger.error(f"{prefix}: {exc}")
    should_show_trace = logger.level <= logging.DEBUG and not isinstance(exc, ExternalOperationError)
    if should_show_trace:
        traceback.print_exc()

if __name__ == "__main__":
    main() 