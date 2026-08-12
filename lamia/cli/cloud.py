"""Handle ``lamia cloud <subcommand>`` — cloud provider management."""

import argparse
import sys
from pathlib import Path

from lamia.git import (
    canonical_remote_identity,
    get_remote_origin,
    set_repository_ci_variables,
)


def handle_cloud() -> None:
    """Entry point for ``lamia cloud ...``."""
    parser = argparse.ArgumentParser(
        prog="lamia cloud",
        description="Manage cloud provider integrations",
    )
    sub = parser.add_subparsers(dest="subcommand")

    connect_p = sub.add_parser(
        "connect",
        help="Connect the current git repository for source-based cloud builds",
    )
    connect_p.add_argument(
        "--project-root", type=str, default=".",
        help="Project root directory (default: current directory)",
    )
    connect_p.add_argument(
        "--branch", type=str, default="main",
        help="Branch allowed for CI deployments (default: main)",
    )

    status_p = sub.add_parser(
        "status",
        help="Check whether the current repository is connected",
    )
    status_p.add_argument(
        "--project-root", type=str, default=".",
        help="Project root directory (default: current directory)",
    )

    disconnect_p = sub.add_parser(
        "disconnect",
        help="Remove cloud connection for the current repository",
    )
    disconnect_p.add_argument(
        "--project-root", type=str, default=".",
        help="Project root directory (default: current directory)",
    )

    args = parser.parse_args(sys.argv[2:])

    if args.subcommand == "connect":
        _cloud_connect(args)
    elif args.subcommand == "status":
        _cloud_status(args)
    elif args.subcommand == "disconnect":
        _cloud_disconnect(args)
    else:
        parser.print_help()
        sys.exit(1)


def _get_connector(project_root: Path):
    """Load a RepositoryConnector for the project. Exits on failure."""
    try:
        from lamia_cloud import get_connector
        return get_connector(project_root)
    except ImportError:
        print(
            "lamia-cloud is not installed. Install it with:\n"
            "  pip install lamia-lang[cloud]",
            file=sys.stderr,
        )
        sys.exit(1)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


def _cloud_connect(args) -> None:
    root = Path(args.project_root).resolve()
    branch = getattr(args, "branch", "main")
    repo_url = get_remote_origin(str(root))
    if not repo_url:
        print(
            "Not a git repository or no remote origin found.\n"
            "Run this command from inside a git repository with a remote.",
            file=sys.stderr,
        )
        sys.exit(1)

    identity = canonical_remote_identity(repo_url)
    print(f"Detected repository: {identity or repo_url}")

    connector = _get_connector(root)
    print("Connecting to cloud provider...")

    try:
        result = connector.connect_repository(repo_url, branch=branch)
    except Exception as exc:
        print(f"Connection failed: {exc}", file=sys.stderr)
        sys.exit(1)

    if not result.get("connected"):
        print(f"Connection incomplete: {result.get('message', 'unknown')}", file=sys.stderr)
        sys.exit(1)

    print(f"{result.get('message', 'Connected.')} Git mode enabled for deploys.")

    connection_id = result.get("connection_id")
    if not connection_id:
        print(
            "ERROR: Connection succeeded but connection ID was not returned.\n"
            "Please update lamia-cloud to the latest released version.",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        set_repository_ci_variables(
            repo_url=repo_url,
            connection_id=connection_id,
        )
    except RuntimeError as exc:
        print(
            f"ERROR: Failed to configure GitHub CI variables automatically: {exc}\n"
            "Please run `lamia cloud connect` again and complete GitHub authorization.",
            file=sys.stderr,
        )
        sys.exit(1)

    print(
        "\nGitHub CI variables configured successfully.\n"
        "Do NOT store CI auth fields in config.yaml."
    )

    print(
        "\nThen use this workflow pattern:\n"
        "\n"
        "  name: Deploy\n"
        "  on:\n"
        "    push:\n"
        f"      branches: [{branch}]\n"
        "  jobs:\n"
        "    deploy:\n"
        "      runs-on: ubuntu-latest\n"
        "      permissions:\n"
        "        id-token: write\n"
        "        contents: read\n"
        "      env:\n"
        "        LAMIA_CONNECTION_ID: ${{ vars.LAMIA_CONNECTION_ID }}\n"
        "      steps:\n"
        "        - uses: actions/checkout@v4\n"
        "        - run: pip install lamia-lang[cloud]\n"
        "        - run: lamia schedule add main.lm --every day --remote"
    )
    print(
        "\nLAMIA_CONNECTION_ID is already stored as a repository variable; "
        "the workflow only references it.\n"
        "Security: use 'push' trigger only. Never use 'pull_request_target'."
    )


def _cloud_disconnect(args) -> None:
    root = Path(args.project_root).resolve()
    repo_url = get_remote_origin(str(root))
    if not repo_url:
        print("Not a git repository or no remote origin found.", file=sys.stderr)
        sys.exit(1)

    identity = canonical_remote_identity(repo_url)
    connector = _get_connector(root)

    print(f"Disconnecting {identity or repo_url}...")
    try:
        result = connector.disconnect_repository(repo_url)
    except Exception as exc:
        print(f"Disconnect failed: {exc}", file=sys.stderr)
        sys.exit(1)

    for item in result.get("deleted", []):
        print(f"  Deleted: {item}")

    print("Repository disconnected. CI deployments will no longer authenticate.")


def _cloud_status(args) -> None:
    root = Path(args.project_root).resolve()
    repo_url = get_remote_origin(str(root))
    if not repo_url:
        print("Not a git repository or no remote origin found.", file=sys.stderr)
        sys.exit(1)

    identity = canonical_remote_identity(repo_url)
    connector = _get_connector(root)

    try:
        connected = connector.is_repository_connected(repo_url)
    except Exception as exc:
        print(f"Status check failed: {exc}", file=sys.stderr)
        sys.exit(1)

    if connected:
        print(f"Repository {identity or repo_url}: connected")
    else:
        print(f"Repository {identity or repo_url}: not connected")
        print("Run 'lamia cloud connect' to set up source-based builds.")
        sys.exit(1)
