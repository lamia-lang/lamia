"""Patterns for placeholders in Lamia prompt templates."""

import re

# {param} or {param:default}; group 1 is the name, group 2 the default.
PARAM_RE = re.compile(r'\{(\w+)(?::([^}]*))?\}')
# {@path}; group 1 is the reference.
FILE_REFERENCE_RE = re.compile(r'\{@([^}]+)\}')
# {@name} where name is an identifier that a caller argument may replace; group 1 is the name.
FILE_REFERENCE_VARIABLE_RE = re.compile(r'\{@(\w+)\}')
