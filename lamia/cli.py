import asyncio
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

from lamia.lamia import Lamia
from lamia.errors import MissingAPIKeysError
from lamia.utils import scaffold
from lamia.utils.cli_styling import setup_cli_logging
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
                # Check for exit commands
                if line.lower() in ['exit', 'quit', ':q']:
                    logger.info("\nGoodbye! 👋")
                    return
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
            running_task = asyncio.create_task(lamia.run_async(user_input))
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
                if result.execution_context.command_type == CommandType.LLM:
                    if result.execution_context:
                        print(f"Model: {result.execution_context.data_provider_name}")
                        
                        # Extract usage from metadata if available
                        if result.execution_context.metadata and "usage" in result.execution_context.metadata:
                            usage = result.execution_context.metadata["usage"]
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
                    print(f"Executed by: {result.execution_context.command_type}")
        except KeyboardInterrupt:
            logger.info("\n\nGoodbye! 👋")
            break
        except Exception as e:
            traceback.print_exc()
            logger.error(f"❌ Error: {str(e)}")
            logger.error(traceback.format_exc())
            continue

def main():
    """Main entry point for the Lamia CLI."""
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
            created = scaffold.create_minimal_config(config_path, with_extensions=args.with_extensions)
            if created:
                logger.info("✅ Created config.yaml")
            else:
                logger.warning("config.yaml already exists")
            if args.with_extensions:
                ext_path = scaffold.ensure_extensions_folder(os.getcwd())
                updated = scaffold.update_config_with_extensions(config_path)
                logger.info(f"✅ Extensions folder scaffolded at: {ext_path}")
                if updated:
                    logger.info("✅ config.yaml updated with extensions_folder key.")
            env_path = os.path.join(os.getcwd(), ".env")
            env_created = scaffold.create_env_file(env_path)
            if env_created:
                logger.info("✅ Created .env file with dummy API keys.")
            else:
                logger.warning(".env file already exists.")
            return
        return
    else:
        parser = argparse.ArgumentParser(
            description="Lamia CLI",
            epilog="""
            For help on a subcommand, run:
            lamia <subcommand> --help
            """
        )
        parser.add_argument('filename', nargs='?', help='Prompt file to read from (if not provided, runs in interactive mode)')
        parser.add_argument('--file', '-f', type=str, help='Read prompt from a file instead of interactive mode')
        parser.add_argument('--config', '-c', type=str, help='Path to config file (optional)')
        parser.add_argument('--log-level', default='INFO', help='Set logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)')
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
        logger.error("❌ Error: --config is required for CLI operation.")
        sys.exit(1)

    # Note: Lazy loading is now handled by HybridExecutor for .hu files
    # Python files still need sys.path management for regular execution

    try:
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
                    executor.execute_file(prompt_file, enable_lazy_loading=True)
                    sys.exit(0)
                except Exception as e:
                    logger.error(f"❌ Error processing hybrid syntax file: {e}")
                    sys.exit(1)
            else:
                # Regular Python file
                try:
                    logger.info(f"Executing script: {prompt_file}")
                    runpy.run_path(prompt_file, run_name="__main__")
                    sys.exit(0)
                except Exception as e:
                    logger.error(f"❌ Error executing script: {e}")
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
        logger.info("\n\nGoodbye! 👋")
        sys.exit(0)

if __name__ == "__main__":
    main() 