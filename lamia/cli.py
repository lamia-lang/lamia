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

from lamia.lamia import Lamia
from lamia.engine.llm.llm_manager import MissingAPIKeysError
from lamia.utils import scaffold

async def interactive_mode(lamia: Lamia):
    """Run Lamia in interactive mode, processing user prompts."""
    print("\nLamia Interactive Mode")
    print("Enter your prompts (type 'SEND' on a new line to finish, type CANCEL to discard current input, Ctrl+C to quit, type STOP to interrupt a running prompt, 'exit' to quit)")
    print("----------------------------------------")

    prompt_str = "\n🤖 > (SEND=submit, CANCEL=discard, STOP=interrupt, Command/Ctrl C or EXIT=quit)\n> "

    running_task = None
    loop = asyncio.get_event_loop()

    while True:
        try:
            # Multiline input: keep reading until 'SEND' is entered on a new line
            lines = []
            while True:
                line = input(prompt_str if not lines else "> ")
                if line.strip() == "SEND":
                    break
                if line.strip().upper() == "CANCEL":
                    print("Prompt cancelled. Start typing a new prompt.")
                    lines = []
                    # Show the prompt again for a new input
                    continue
                # Check for exit commands
                if line.lower() in ['exit', 'quit', ':q']:
                    print("\nGoodbye! 👋")
                    exit(0)
                lines.append(line)
            user_input = "\n".join(lines).strip()

            if not user_input:
                print("Prompt is empty. Start typing a new prompt.")
                continue

            # Generate LLM response
            print("\nThinking... 🤔 (type STOP to interrupt)")
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
                            print("Prompt interrupted by user (STOP). Start typing a new prompt.")
                            break
                        elif user_input.lower() in ['exit', 'quit', ':q']:
                            print("\nGoodbye! 👋")
                            break
            if running_task.done() and not running_task.cancelled():
                result = running_task.result()
                print("\n🔮 Response:")
                print("----------------------------------------")
                print(result.result)
                print("----------------------------------------")
                # Add model info if available
                print(f"Executed by: {result.executor}")
        except KeyboardInterrupt:
            print("\n\nGoodbye! 👋")
            break
        except Exception as e:
            print(f"\n❌ Error: {str(e)}")
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
                        print(f"❌ Module name conflict: '{mod_name}.py' found in both '{module_names[mod_name]}' and '{dirpath}'. Please rename one of them.")
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
                                        print(f"❌ Function name conflict: function '{func_name}' found in both '{prev_path}' and '{mod_path}'. Please rename one of them or use explicit imports (e.g., 'from <module> import <func>').")
                                        sys.exit(1)
                                    function_names[func_name] = (mod_name, mod_path)
                    except Exception as e:
                        print(f"Warning: Could not parse {mod_path}: {e}")

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
                print("Created config.yaml")
            else:
                print("config.yaml already exists")
            if args.with_extensions:
                ext_path = scaffold.ensure_extensions_folder(os.getcwd())
                updated = scaffold.update_config_with_extensions(config_path)
                print(f"Extensions folder scaffolded at: {ext_path}")
                if updated:
                    print("config.yaml updated with extensions_folder key.")
            env_path = os.path.join(os.getcwd(), ".env")
            env_created = scaffold.create_env_file(env_path)
            if env_created:
                print("Created .env file with dummy API keys.")
            else:
                print(".env file already exists.")
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

    # Setup logging globally for CLI
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    prompt_file = args.filename or args.file
    config_path = args.config

    config_dict = None
    if config_path:
        print(f"Using configuration from: {config_path}")
        with open(config_path, 'r') as f:
            config_dict = yaml.safe_load(f)
    elif os.path.exists("config.yaml"):
        print("Using configuration from: config.yaml")
        with open("config.yaml", 'r') as f:
            config_dict = yaml.safe_load(f)
    else:
        print("❌ Error: --config is required for CLI operation.", file=sys.stderr)
        sys.exit(1)

    # Add this before running the user script
    add_all_py_dirs_to_syspath_and_check_conflicts(os.getcwd())

    async def run():
        try:
            # Create Lamia instance with config
            print("Creating Lamia instance...")
            lamia = Lamia.from_config(config_dict)
            
            print("✅ Lamia instance created successfully")
            
            if prompt_file:
                # Read prompt from file and execute as a Python script using runpy
                try:
                    print(f"Executing script: {prompt_file}")
                    runpy.run_path(prompt_file, run_name="__main__")
                    sys.exit(0)
                except Exception as e:
                    print(f"❌ Error executing script: {e}", file=sys.stderr)
                    sys.exit(1)
            else:
                # Run interactive mode
                await interactive_mode(lamia)
                
        except MissingAPIKeysError as e:
            print(f"❌ Missing API Keys: {str(e)}", file=sys.stderr)
            print("Please check your .env file or config.yaml for required API keys.", file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            print(f"❌ Error: {e}", file=sys.stderr)
            print("Check your config.yaml and logs for details.", file=sys.stderr)
            sys.exit(1)
        except KeyboardInterrupt:
            print("\n\nGoodbye! 👋")
            sys.exit(0)

    asyncio.run(run())

if __name__ == "__main__":
    main() 