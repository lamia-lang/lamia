# Contributing to Lamia

## Development Setup

1. Clone the repository
2. Create a virtual environment: `python -m venv venv`
3. Activate: `source venv/bin/activate` (Unix) or `venv\Scripts\activate` (Windows)
4. Install development dependencies: `pip install -e ".[dev]"`
5. Run tests: `pytest tests/`

Note, If you're new to virtual environments, you can skip steps 2-3, but installing into a virtual environment avoids dependency conflicts.

## Documentation

Documentation is built with [MkDocs](https://www.mkdocs.org/) using the [Material](https://squidfunk.github.io/mkdocs-material/) theme.

### Building Docs Locally

```bash
# Install documentation dependencies
pip install -e ".[docs]"

# Serve with live reload at http://localhost:8000
mkdocs serve

# Build static files
mkdocs build
```

### Documentation Structure

- `docs/` — User-facing documentation (served via MkDocs)
- `lamia/*/README.md` — Developer-facing module documentation (for source code navigation)
- `README.md` — Project overview and quick start

When adding a new feature:

1. Add developer docs to the relevant package README
2. Add user-facing docs to the appropriate `docs/` page
3. Update `mkdocs.yml` nav if adding a new page

## Code Style

- No `hasattr` usage — use typed approaches
- No local imports — all imports must be global
- Add unit tests for new functionality