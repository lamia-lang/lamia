"""Handle ``lamia cloud <subcommand>`` — cloud provider management."""

import argparse
import sys
from pathlib import Path

from lamia.git import get_remote_origin, canonical_remote_identity


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

    status_p = sub.add_parser(
        "status",
        help="Check whether the current repository is connected",
    )
    status_p.add_argument(
        "--project-root", type=str, default=".",
        help="Project root directory (default: current directory)",
    )

    args = parser.parse_args(sys.argv[2:])

    if args.subcommand == "connect":
        _cloud_connect(args)
    elif args.subcommand == "status":
        _cloud_status(args)
    else:
        parser.print_help()
        sys.exit(1)


def _get_deployer(project_root: Path):
    """Load a CloudDeployer for the project. Exits on failure."""
    try:
        from lamia_cloud import get_deployer
        return get_deployer(project_root)
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

    deployer = _get_deployer(root)
    print("Connecting to cloud provider...")

    try:
        result = deployer.connect_repository(repo_url)
    except Exception as exc:
        print(f"Connection failed: {exc}", file=sys.stderr)
        sys.exit(1)

    if result.get("connected"):
        print(f"{result.get('message', 'Connected.')} Git mode enabled for deploys.")
    else:
        print(f"Connection incomplete: {result.get('message', 'unknown')}", file=sys.stderr)
        sys.exit(1)


def _cloud_status(args) -> None:
    root = Path(args.project_root).resolve()
    repo_url = get_remote_origin(str(root))
    if not repo_url:
        print("Not a git repository or no remote origin found.", file=sys.stderr)
        sys.exit(1)

    identity = canonical_remote_identity(repo_url)
    deployer = _get_deployer(root)

    try:
        connected = deployer.is_repository_connected(repo_url)
    except Exception as exc:
        print(f"Status check failed: {exc}", file=sys.stderr)
        sys.exit(1)

    if connected:
        print(f"Repository {identity or repo_url}: connected")
    else:
        print(f"Repository {identity or repo_url}: not connected")
        print("Run 'lamia cloud connect' to set up source-based builds.")
        sys.exit(1)
