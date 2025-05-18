import asyncio
import sys
import os
import readline  # For better input handling (command history)
from typing import Optional
import ast
from lamia.adapters.llm.validation.validators import HTMLValidator
import argparse

from .llm_manager import generate_response

async def interactive_mode():
    """Run Lamia in interactive mode, processing user prompts."""
    print("\nLamia Interactive Mode")
    print("Enter your prompts (type 'END' on a new line to finish, Ctrl+C to quit or cancel, type STOP to cancel a prompt before sending, 'exit' to quit)")
    print("----------------------------------------")

    while True:
        try:
            # Multiline input: keep reading until 'END' is entered on a new line
            lines = []
            print("\n🤖 > (type 'END' on a new line to finish)")
            while True:
                line = input()
                if line.strip() == "END":
                    break
                lines.append(line)
            user_input = "\n".join(lines).strip()
            
            # Support STOP keyword to cancel prompt
            if user_input.strip().upper() == 'STOP':
                print("Prompt cancelled.")
                continue
            
            # Check for validator command
            validate_html = False
            if user_input.lower().endswith('validate:html'):
                validate_html = True
                user_input = user_input[:-(len('validate:html'))].rstrip()
            original_prompt = user_input  # Save for retry if needed
            
            # Check for exit commands
            if user_input.lower() in ['exit', 'quit', ':q']:
                print("\nGoodbye! 👋")
                break
                
            if not user_input:
                continue
                
            # Try to evaluate as a Python expression or code
            if run_python_code(user_input, mode='interactive'):
                continue  # Skip LLM call if Python code executed
            
            # Generate and print response
            print("\nThinking... 🤔")
            response = await generate_response(user_input)
            
            print("\n🔮 Response:")
            print("----------------------------------------")
            print(response.text)
            print("----------------------------------------")
            print(f"Model: {response.model}")
            if response.usage:
                print(f"Tokens used: {response.usage}")
            
            # If requested, validate as HTML
            if validate_html:
                validator = HTMLValidator()
                validation_result = await validator.validate(response.text)
                print("\n🛡️ HTML Validation Result:")
                print("----------------------------------------")
                if validation_result.is_valid:
                    print("✅ Valid HTML!")
                else:
                    print(f"❌ Invalid HTML: {validation_result.error_message}")
                    print("----------------------------------------")
                    # Retry with correction prompt
                    correction = "Please correct your output to be valid HTML."
                    retry_prompt = f"{original_prompt}\n{correction}"
                    print("\nRetrying with correction prompt...")
                    retry_response = await generate_response(retry_prompt)
                    print("\n🔄 Retry Response:")
                    print("----------------------------------------")
                    print(retry_response.text)
                    print("----------------------------------------")
                    retry_validation = await validator.validate(retry_response.text)
                    print("\n🛡️ Retry HTML Validation Result:")
                    print("----------------------------------------")
                    if retry_validation.is_valid:
                        print("✅ Valid HTML after retry!")
                    else:
                        print(f"❌ Still invalid HTML: {retry_validation.error_message}")
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
    args = parser.parse_args()

    prompt_file = args.filename or args.file
    if prompt_file:
        # Read prompt from file and try to execute as Python code first
        try:
            with open(prompt_file, 'r') as f:
                prompt = f.read()
            if run_python_code(prompt, mode='file', show_banner=False):
                sys.exit(0)
            # If not Python, send to LLM
            response = asyncio.run(generate_response(prompt))
            print(response.text)
        except Exception as e:
            print(f"Error reading file or generating response: {e}", file=sys.stderr)
            sys.exit(1)
        sys.exit(0)
    # Otherwise, run interactive mode
    try:
        asyncio.run(interactive_mode())
    except KeyboardInterrupt:
        print("\nGoodbye! 👋")
        sys.exit(0)
    except Exception as e:
        print(f"Fatal error: {str(e)}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main() 