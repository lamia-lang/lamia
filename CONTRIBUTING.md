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

## Version Compatibility

### When releasing a new `lamia-lang` to PyPI

1. Update `lamia-ide/initial-lamia-version.txt` in the IDE repo to the new version, so that new IDE builds install the latest version on first launch.
2. If the release changes the IDE communication protocol, bump `IDE_API_VERSION` in `lamia/cli/cli.py` (currently `"0.1"`). This version is the contract between the lamia CLI and the IDE extension — it's reported via `lamia --version --json` as `ide_api`, and the IDE checks it before allowing updates. Examples of what it covers: the JSON message format between the IDE and `lamia ide-mode`, the `--version --json` output shape, and any CLI flags the IDE relies on.
   - **Minor bump** (e.g. `"0.1"` → `"0.2"`): new capabilities that the IDE can optionally use (e.g. a new JSON field, a new command flag). Older IDE versions still work. The IDE allows the update and shows a hint to update the extension for new features.
   - **Major bump** (e.g. `"0.1"` → `"1.0"`): breaking changes that older IDE versions cannot handle (e.g. removed/renamed JSON fields, changed message protocol). The IDE **blocks** the lamia update until the user updates the IDE extension. Coordinate with `IDE_SUPPORTED_API_MAJOR` in `lamia-ide/extension/src/updateChecker.ts`.

### When `lamia-cloud` publishes a breaking release

`lamia` depends on `lamia-cloud` as an optional extra — see `pyproject.toml` `[project.optional-dependencies]` (currently `lamia-cloud>=0.3.0`). When `lamia-cloud` makes a breaking change, update the lower bound in `pyproject.toml` to match the new minimum required version.

## Code Style and Testing

- Typed Python code is preferred
- Add unit tests for new functionality
- Make sure that all tests pass by running `pytest`