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

import json
import shutil
import subprocess
import sys
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

    # Parse arguments
    args = parser.parse_args()

    # Handle check-gh subcommand
    if args.command == "check-gh":
        status = get_gh_status()
        print(json.dumps(status))
        return 0

    # No command specified - show help
    if not args.command:
        parser.print_help()
        return 0

    return 0


if __name__ == "__main__":
    import argparse

    sys.exit(main())
