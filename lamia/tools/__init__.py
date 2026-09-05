"""Centralized tool infrastructure for Lamia.

Submodules:
- definitions: tool names, IDE tool definitions, file-context tool definitions
- dispatch: execution logic for every tool
- file_context: LLM calls made inside ``with files()`` contexts
- parsing: text-based tool-call extraction and formatting
- loop: unified tool-loop runner
"""
