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
                if hasattr(result, 'executor') and str(result.executor) == "CommandType.LLM":
                    if result.model:
                        print(f"Model: {result.model}")
                    if result.usage:
                        # Format usage similar to the README example
                        usage_parts = []
                        if 'prompt_tokens' in result.usage:
                            usage_parts.append(f"'prompt_tokens': {result.usage['prompt_tokens']}")
                        elif 'input_tokens' in result.usage:
                            usage_parts.append(f"'prompt_tokens': {result.usage['input_tokens']}")
                        
                        if 'completion_tokens' in result.usage:
                            usage_parts.append(f"'completion_tokens': {result.usage['completion_tokens']}")
                        elif 'output_tokens' in result.usage:
                            usage_parts.append(f"'completion_tokens': {result.usage['output_tokens']}")
                        
                        if 'total_tokens' in result.usage:
                            usage_parts.append(f"'total_tokens': {result.usage['total_tokens']}")
                        
                        if usage_parts:
                            print(f"Tokens used: {{{', '.join(usage_parts)}}}")
                else:
                    print(f"Executed by: {result.executor}")
        except KeyboardInterrupt:
            logger.info("\n\nGoodbye! 👋")
            break
        except Exception as e:
            traceback.print_exc()
            logger.error(f"❌ Error: {str(e)}")
            logger.error(traceback.format_exc())
            continue

def add_all_py_dirs_to_syspath_and_check_conflicts(root_dir):
    module_names = {}
    function_names = {}
    if ".lamia" in os.listdir(root_dir):
        # It's a Lamia special folder we don't allow conflicting filenames and function names
        for dirpath, dirnames, filenames in os.walk(root_dir):
            py_files = [f for f in filenames if f.endswith('.py')]
            if py_files:
                sys.path.insert(0, dirpath)
                for f in py_files:
                    mod_name = os.path.splitext(f)[0]
                    mod_path = os.path.join(dirpath, f)
                    # Check for module name conflicts
                    if mod_name in module_names:
                        logger.error(f"Module name conflict: '{mod_name}.py' found in both '{module_names[mod_name]}' and '{dirpath}'. Please rename one of them.")
                        sys.exit(1)
                    module_names[mod_name] = dirpath
                    # Check for function name conflicts
                    try:
                        with open(mod_path, 'r') as file:
                            node = ast.parse(file.read(), filename=mod_path)
                            for n in node.body:
                                if isinstance(n, ast.FunctionDef):
                                    func_name = n.name
                                    if func_name in function_names:
                                        prev_mod, prev_path = function_names[func_name]
                                        logger.error(f"Function name conflict: function '{func_name}' found in both '{prev_path}' and '{mod_path}'. Please rename one of them or use explicit imports (e.g., 'from <module> import <func>').")
                                        sys.exit(1)
                                    function_names[func_name] = (mod_name, mod_path)
                    except Exception as e:
                        logger.warning(f"Could not parse {mod_path}: {e}")

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

    # Add this before running the user script
    add_all_py_dirs_to_syspath_and_check_conflicts(os.getcwd())

    async def run():
        try:
            # Create Lamia instance with config
            logger.info("Creating Lamia instance...")
            lamia = Lamia.from_config(config_dict)
            
            logger.info("✅ Lamia instance created successfully")
            
            if prompt_file:
                # Read prompt from file and execute as a Python script using runpy
                try:
                    logger.info(f"Executing script: {prompt_file}")
                    runpy.run_path(prompt_file, run_name="__main__")
                    sys.exit(0)
                except Exception as e:
                    logger.error(f"❌ Error executing script: {e}")
                    sys.exit(1)
            else:
                # Run interactive mode
                await interactive_mode(lamia)
                
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

    asyncio.run(run())

if __name__ == "__main__":
    main() 