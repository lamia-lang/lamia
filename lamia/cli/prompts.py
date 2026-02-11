"""Shared interactive CLI prompt helpers used by init wizard and eval."""


def input_yes_no(prompt: str, default: bool = True) -> bool:
    suffix = " [Y/n]: " if default else " [y/N]: "
    while True:
        raw = input(prompt + suffix).strip().lower()
        if not raw:
            return default
        if raw in ("y", "yes"):
            return True
        if raw in ("n", "no"):
            return False
        print("  Please answer yes or no (y/n).")


def input_number(prompt: str, max_val: int, default: int = 1) -> int:
    """Ask user to pick a 1-based number."""
    while True:
        raw = input(prompt).strip()
        if not raw:
            return default
        if raw.lower() in ("q", "quit", "exit"):
            return default
        try:
            val = int(raw)
            if 1 <= val <= max_val:
                return val
        except ValueError:
            pass
        print(f"  Please enter a number between 1 and {max_val}.")


def pick_from_list(heading: str, items: list[tuple[str, str]], default_idx: int = 0) -> str:
    """Show a numbered list of ``(value, description)`` tuples and return the chosen value."""
    display_numbered_list(heading, items, default_idx)
    idx = input_number(f"  Select number [default: {default_idx + 1}]: ", len(items), default_idx + 1)
    return items[idx - 1][0]


def display_numbered_list(heading: str, items: list[tuple[str, str]], default_idx: int = -1) -> None:
    """Print a numbered list. Marks the default if ``default_idx >= 0``."""
    print(f"  {heading}:")
    for i, (name, desc) in enumerate(items, 1):
        marker = " (default)" if i == default_idx + 1 else ""
        suffix = f" ({desc})" if desc else ""
        print(f"    {i}. {name}{suffix}{marker}")