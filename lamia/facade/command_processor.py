"""
Command processing utilities for Lamia facade.

This module handles the conversion from strings to Command objects
and the Python execution attempt logic.
"""

import logging
from typing import Union, Optional, Dict, Any

from lamia.interpreter.python_runner import run_python_code
from lamia.interpreter.commands import Command
from lamia.validation.base import TrackingContext
from .command_parser import CommandParser
from .result_types import LamiaResult

logger = logging.getLogger(__name__)


def process_string_command(command: str) -> tuple[Command, Optional[LamiaResult]]:
    """
    Process a string command by attempting Python execution first,
    then falling back to command parsing.
    
    Args:
        command: String command to process
        
    Returns:
        Tuple of (Command object, LamiaResult if Python succeeded or None)
    """
    # Try Python execution first
    try:
        result = run_python_code(command, mode='interactive')
        python_context = TrackingContext(
            data_provider_name="python",
            command_type="python",
            metadata={"mode": "interactive"}
        )
        python_result = LamiaResult(
            result_text=str(result) if result is not None else "", 
            typed_result=result, 
            tracking_context=python_context
        )
        # Return dummy command since we have a result already
        return None, python_result
    except SyntaxError as e:
        logger.debug(f"Syntax error: {e} in command: {command}")
        pass
    except Exception as e:
        logger.debug(f"Python code execution failed: {e}")
        pass

    # Parse string command to Command object
    current_parser = CommandParser(command)
    parsed_command = current_parser.parsed_command
    
    return parsed_command, None