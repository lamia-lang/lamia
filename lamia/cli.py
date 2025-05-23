import asyncio
import sys
import os
import readline  # For better input handling (command history)
from typing import Optional
import ast
import argparse
import select

from lamia.engine import LamiaEngine
from lamia.engine.llm_manager import MissingAPIKeysError

async def interactive_mode(engine: LamiaEngine):
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

            # Try to evaluate as a Python expression or code
            if run_python_code(user_input, mode='interactive'):
                continue  # Skip LLM call if Python code executed

            # Generate and print response using LamiaEngine
            print("\nThinking... 🤔 (type STOP to interrupt)")
            running_task = asyncio.create_task(engine.generate(user_input))
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
                response = running_task.result()
                print("\n🔮 Response:")
                print("----------------------------------------")
                print(response.text)
                print("----------------------------------------")
                print(f"Model: {response.model}")
                if hasattr(response, 'usage') and response.usage:
                    print(f"Tokens used: {response.usage}")
                # If validation info is present in response, print it
                if hasattr(response, 'validation_result') and response.validation_result is not None:
                    print("\n🛡️ Validation Result:")
                    print("----------------------------------------")
                    if response.validation_result.get('is_valid', False):
                        print("✅ Valid output!")
                    else:
                        print(f"❌ Invalid output: {response.validation_result.get('error_message', 'Unknown error')}")
                    print("----------------------------------------")
        except KeyboardInterrupt:
            print("\n\nGoodbye! 👋")
            break
        except Exception as e:
            print(f"\n❌ Error: {str(e)}")
            continue

def run_python_code(user_input: str, mode: str = 'interactive', show_banner: bool = True) -> bool:
    """Try to execute user_input as Python code or expression. Returns True if executed, False otherwise.
    mode: 'interactive' or 'file' -- controls output behavior to match Python CLI/REPL."""
    try:
        expr_ast = ast.parse(user_input, mode='eval')
        result = eval(compile(expr_ast, '<string>', mode='eval'))
        if show_banner:
            print("\n🐍 Python Result:")
            print("----------------------------------------")
        print(result)
        if show_banner:
            print("----------------------------------------")
        return True
    except Exception:
        pass
    try:
        code_ast = ast.parse(user_input, mode='exec')
        local_vars = {}
        exec(compile(code_ast, '<string>', mode='exec'), {}, local_vars)
        # Only in interactive mode, print the result of the last expression if present and not a print call
        if mode == 'interactive' and code_ast.body and isinstance(code_ast.body[-1], ast.Expr):
            last_expr = code_ast.body[-1]
            # Don't print if the last expression is a print() call
            if not (isinstance(last_expr.value, ast.Call) and getattr(last_expr.value.func, 'id', None) == 'print'):
                result = eval(compile(ast.Expression(last_expr.value), '<string>', mode='eval'), {}, local_vars)
                if result is not None:
                    if show_banner:
                        print("\n🐍 Python Result:")
                        print("----------------------------------------")
                    print(result)
                    if show_banner:
                        print("----------------------------------------")
        return True
    except Exception:
        pass
    return False

def main():
    """Main entry point for the Lamia CLI."""
    parser = argparse.ArgumentParser(description="Lamia CLI")
    parser.add_argument('filename', nargs='?', help='Prompt file to read from (if not provided, runs in interactive mode)')
    parser.add_argument('--file', '-f', type=str, help='Read prompt from a file instead of interactive mode')
    parser.add_argument('--config', '-c', type=str, help='Path to config file (optional)')
    args = parser.parse_args()

    prompt_file = args.filename or args.file
    config_path = args.config

    async def run():
        engine = LamiaEngine(config_path)
        try:
            engine_started = await engine.start()
        except MissingAPIKeysError as e:
            print(str(e), file=sys.stderr)
            await engine.stop()
            sys.exit(1)
        except Exception as e:
            print(f"❌ Error: Failed to start the Lamia engine: {e}", file=sys.stderr)
            print("Check your config.yaml and logs for details.", file=sys.stderr)
            await engine.stop()
            sys.exit(1)
        if not engine_started:
            print("❌ Error: Failed to start the Lamia engine. Check your configuration and logs.", file=sys.stderr)
            await engine.stop()
            sys.exit(1)
        try:
            if prompt_file:
                # Read prompt from file and try to execute as Python code first
                try:
                    with open(prompt_file, 'r') as f:
                        prompt = f.read()
                    if run_python_code(prompt, mode='file', show_banner=False):
                        await engine.stop()
                        sys.exit(0)
                    # If not Python, send to engine
                    response = await engine.generate(prompt)
                    print(response.text)
                    if hasattr(response, 'validation_result') and response.validation_result is not None:
                        print("\n🛡️ Validation Result:")
                        print("----------------------------------------")
                        if response.validation_result.get('is_valid', False):
                            print("✅ Valid output!")
                        else:
                            print(f"❌ Invalid output: {response.validation_result.get('error_message', 'Unknown error')}")
                        print("----------------------------------------")
                except Exception as e:
                    print(f"Error reading file or generating response: {e}", file=sys.stderr)
                    await engine.stop()
                    sys.exit(1)
                await engine.stop()
                sys.exit(0)
            # Otherwise, run interactive mode
            await interactive_mode(engine)
        except KeyboardInterrupt:
            print("\nGoodbye! 👋")
            sys.exit(0)
        except Exception as e:
            print(f"Fatal error: {str(e)}", file=sys.stderr)
            sys.exit(1)
        finally:
            await engine.stop()

    asyncio.run(run())

if __name__ == "__main__":
    main() 