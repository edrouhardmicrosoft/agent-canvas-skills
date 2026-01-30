#!/usr/bin/env python3
"""
Canvas Issue CLI - GitHub issue management for design QA.

Provides CLI subcommands for checking GitHub CLI status, creating issues,
and managing issue templates.

Usage:
    python scripts/canvas_issue.py check-gh
    python scripts/canvas_issue.py create-issue --title "..." --body "..."
    python scripts/canvas_issue.py list-issues
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional, Dict, Any


# =============================================================================
# GitHub CLI Detection Functions
# =============================================================================


def check_gh_installed() -> bool:
    """
    Check if the 'gh' CLI tool is installed and available in PATH.

    Returns:
        True if 'gh' is found in PATH, False otherwise.
    """
    return shutil.which("gh") is not None


def check_gh_authenticated() -> bool:
    """
    Check if the 'gh' CLI tool is authenticated with GitHub.

    Runs 'gh auth status' and checks if it exits with code 0.

    Returns:
        True if authenticated, False otherwise.
    """
    try:
        result = subprocess.run(
            ["gh", "auth", "status"],
            capture_output=True,
            timeout=5,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def get_gh_username() -> Optional[str]:
    """
    Extract the GitHub username from 'gh auth status' output.

    The output format is typically: "Logged in to github.com account USERNAME"

    Returns:
        The username string if authenticated, None otherwise.
    """
    try:
        result = subprocess.run(
            ["gh", "auth", "status"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            return None

        # Parse username from output
        # Format: "Logged in to github.com account octocat"
        output = result.stdout.strip()
        parts = output.split()

        # Find "account" keyword and get next part (username)
        if "account" in parts:
            account_idx = parts.index("account")
            if account_idx + 1 < len(parts):
                return parts[account_idx + 1]

        return None
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None


def get_gh_status() -> Dict[str, Any]:
    """
    Get comprehensive GitHub CLI status.

    Returns a dictionary with:
        - installed (bool): Whether 'gh' is in PATH
        - authenticated (bool): Whether user is logged in
        - username (str|null): The authenticated username, or null if not authenticated
    """
    installed = check_gh_installed()
    authenticated = check_gh_authenticated() if installed else False
    username = get_gh_username() if authenticated else None

    return {
        "installed": installed,
        "authenticated": authenticated,
        "username": username,
    }


# =============================================================================
# Config Management Functions
# =============================================================================


def get_config() -> Dict[str, Any]:
    """
    Read the canvas config file at .canvas/config.json.

    Returns:
        Dictionary with config contents, or empty dict if file doesn't exist.
    """
    config_path = Path(".canvas/config.json")
    if not config_path.exists():
        return {}

    try:
        with open(config_path, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}


def set_config(key_path: str, value: Any) -> None:
    """
    Update the canvas config file with nested key support.

    Args:
        key_path: Dot-separated path (e.g., "github.repo")
        value: Value to set

    Creates .canvas/config.json if it doesn't exist.
    """
    config_dir = Path(".canvas")
    config_dir.mkdir(exist_ok=True)

    config_path = config_dir / "config.json"
    config = get_config()

    # Navigate/create nested structure
    keys = key_path.split(".")
    current = config
    for key in keys[:-1]:
        if key not in current:
            current[key] = {}
        current = current[key]

    # Set the final value
    current[keys[-1]] = value

    # Write config file
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)


def get_github_repo() -> Optional[str]:
    """
    Get the configured GitHub repo (owner/repo format).

    Returns:
        The repo string (e.g., "owner/repo"), or None if not configured.
    """
    config = get_config()
    return config.get("github", {}).get("repo")


def set_github_repo(owner_repo: str) -> None:
    """
    Set the GitHub repo configuration.

    Args:
        owner_repo: Repository in "owner/repo" format

    Raises:
        ValueError: If format is invalid (not exactly one slash)
    """
    # Validate format
    if owner_repo.count("/") != 1:
        raise ValueError("Repository must be in 'owner/repo' format")

    set_config("github.repo", owner_repo)


# =============================================================================
# CLI Entry Point
# =============================================================================


def main():
    """Main CLI entry point with argparse subcommands."""
    parser = argparse.ArgumentParser(
        description="Canvas Issue CLI - GitHub issue management for design QA",
        prog="canvas_issue.py",
    )

    subparsers = parser.add_subparsers(dest="command", help="Subcommand to run")

    # Subcommand: check-gh
    check_gh_parser = subparsers.add_parser(
        "check-gh",
        help="Check GitHub CLI installation and authentication status",
    )

    # Subcommand: get-repo
    get_repo_parser = subparsers.add_parser(
        "get-repo",
        help="Get the configured GitHub repository",
    )

    # Subcommand: set-repo
    set_repo_parser = subparsers.add_parser(
        "set-repo",
        help="Set the GitHub repository (owner/repo format)",
    )
    set_repo_parser.add_argument(
        "repo",
        help="Repository in 'owner/repo' format",
    )

    # Parse arguments
    args = parser.parse_args()

    # Handle check-gh subcommand
    if args.command == "check-gh":
        status = get_gh_status()
        print(json.dumps(status))
        return 0

    # Handle get-repo subcommand
    if args.command == "get-repo":
        repo = get_github_repo()
        if repo:
            print(repo)
        else:
            print("")
        return 0

    # Handle set-repo subcommand
    if args.command == "set-repo":
        try:
            set_github_repo(args.repo)
            return 0
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 0

    # No command specified - show help
    if not args.command:
        parser.print_help()
        return 0

    return 0


if __name__ == "__main__":
    import argparse

    sys.exit(main())
