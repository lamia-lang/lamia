# Contributing to Lamia

## Development Setup

1. Clone the repository
2. Create a virtual environment: `python -m venv venv`
3. Activate: `source venv/bin/activate` (Unix) or `venv\Scripts\activate` (Windows)
4. Install development dependencies: `pip install -e ".[dev]"`
5. Run tests: `pytest tests/`

## Documentation

Documentation is built with [MkDocs](https://www.mkdocs.org/) using the [Material](https://squidfunnel.github.io/mkdocs-material/) theme.

### Building Docs Locally

```bash
# Install documentation dependencies
pip install -r requirements-docs.txt

# Serve with live reload at http://localhost:8000
mkdocs serve

# Build static files
mkdocs build
```

### Deploying Docs

Documentation auto-deploys on every push to the main branch via GitHub Actions.

To deploy manually:

```bash
mkdocs gh-deploy --force
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

- `black` for formatting
- `isort` for import sorting
- `flake8` for linting
- No `hasattr` usage — use typed approaches
- No local imports — all imports must be global
- Add unit tests for new functionality