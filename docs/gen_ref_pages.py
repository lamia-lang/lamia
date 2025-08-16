"""Generate the code reference pages and navigation."""

from pathlib import Path
import mkdocs_gen_files

nav = mkdocs_gen_files.Nav()

# Set up paths
root = Path(__file__).parent.parent
src = root / "lamia"

# Only include these core modules that are likely to work
INCLUDE_MODULES = {
    "lamia",
    "lamia.types", 
    "lamia.errors",
    "lamia.type_converter",
    "lamia.env_loader",
    "lamia.validation",
    "lamia.validation.base",
    "lamia.validation.validators",
    "lamia.validation.validators.atomic_type_validator",
    "lamia.validation.validators.length_validator",
    "lamia.validation.validators.regex_validator",
    "lamia.validation.validators.object_validator",
    "lamia.validation.validators.functional_validator",
    "lamia.validation.validators.file_validators",
    "lamia.validation.validators.file_validators.json_validator",
    "lamia.validation.validators.file_validators.csv_validator",
    "lamia.validation.validators.file_validators.html_validator",
    "lamia.validation.validators.file_validators.xml_validator",
    "lamia.validation.validators.file_validators.yaml_validator",
    "lamia.validation.validators.file_validators.markdown_validator",
    "lamia.facade",
    "lamia.facade.lamia",
    "lamia.facade.config_builder",
    "lamia.facade.result_types",
    "lamia.facade.command_parser",
    "lamia.facade.command_processor",
    "lamia.adapters",
    "lamia.adapters.filesystem",
    "lamia.adapters.filesystem.base",
    "lamia.adapters.filesystem.local_fs_adapter",
    "lamia.adapters.llm",
    "lamia.adapters.llm.base",
    "lamia.adapters.llm.openai_adapter",
    "lamia.adapters.llm.anthropic_adapter",
    "lamia.cli",
    "lamia.cli.cli",
    "lamia.actions",
    "lamia.actions.file",
    "lamia.actions.http",
}

# Generate documentation for all Python files in the lamia package
for path in sorted(src.rglob("*.py")):
    # Skip __pycache__ and other irrelevant directories
    if "__pycache__" in str(path):
        continue
    
    # Calculate module path relative to the project root
    module_path = path.relative_to(root).with_suffix("")
    doc_path = path.relative_to(root).with_suffix(".md")
    full_doc_path = Path("reference", doc_path)

    # Convert path parts to a tuple for navigation
    parts = tuple(module_path.parts)

    # Handle __init__.py files
    if parts[-1] == "__init__":
        parts = parts[:-1]
        doc_path = doc_path.with_name("index.md")
        full_doc_path = full_doc_path.with_name("index.md")
    # Skip __main__.py files
    elif parts[-1] == "__main__":
        continue

    # Create the module identifier for mkdocstrings
    identifier = ".".join(parts)
    
    # Only include modules in our safe list
    if identifier not in INCLUDE_MODULES:
        continue

    # Add to navigation
    nav[parts] = doc_path.as_posix()

    # Create the documentation file
    with mkdocs_gen_files.open(full_doc_path, "w") as fd:
        # Add a title based on the module name
        title = parts[-1] if parts else "lamia"
        print(f"# {title}\n", file=fd)
        
        # Add the mkdocstrings directive
        print(f"::: {identifier}", file=fd)

    # Set the edit path to link back to the source file
    mkdocs_gen_files.set_edit_path(full_doc_path, path)

# Generate the navigation file
with mkdocs_gen_files.open("reference/SUMMARY.md", "w") as nav_file:
    nav_file.writelines(nav.build_literate_nav())