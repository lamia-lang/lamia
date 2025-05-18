import asyncio
import sys
import os
import readline  # For better input handling (command history)
from typing import Optional

from .llm_manager import generate_response

async def interactive_mode():
    """Run Lamia in interactive mode, processing user prompts."""
    print("\nLamia Interactive Mode")
    print("Enter your prompts (Ctrl+C or 'exit' to quit)")
    print("----------------------------------------")

    while True:
        try:
            # Get user input with a prompt
            user_input = input("\n🤖 > ").strip()
            
            # Check for exit commands
            if user_input.lower() in ['exit', 'quit', ':q']:
                print("\nGoodbye! 👋")
                break
                
            if not user_input:
                continue
                
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
                
        except KeyboardInterrupt:
            print("\n\nGoodbye! 👋")
            break
        except Exception as e:
            print(f"\n❌ Error: {str(e)}")
            continue

def main():
    """Main entry point for the Lamia CLI."""
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