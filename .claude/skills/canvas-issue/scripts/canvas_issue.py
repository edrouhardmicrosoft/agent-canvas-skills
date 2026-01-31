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
# Issue Body Generation Functions
# =============================================================================


def extract_selections(session_data: dict) -> list:
    """
    Extract element info from session.json for issue body.

    Args:
        session_data: Dictionary from session.json

    Returns:
        List of dicts with selector, tag, text, screenshot_path
    """
    selections = []
    for event in session_data.get("events", {}).get("selections", []):
        # Only process "picker" source selections to avoid duplicates
        if event.get("source") != "picker":
            continue

        element = event.get("payload", {}).get("element", {})
        selections.append(
            {
                "selector": element.get("selector", "unknown"),
                "tag": element.get("tag", ""),
                "text": (element.get("text") or "")[:100],  # Limit text to 100 chars
                "screenshot_path": event.get("screenshot", {}).get("path"),
            }
        )
    return selections


def generate_issue_body(
    session_data: dict,
    user_description: Optional[str] = None,
    screenshot_urls: Optional[Dict[str, str]] = None,
) -> str:
    """
    Generate a Markdown issue body from session data.

    Args:
        session_data: Dictionary from session.json
        user_description: Optional user-provided description
        screenshot_urls: Optional dict mapping screenshot paths to gist URLs

    Returns:
        Markdown string with sections: Description, Page Info, Selected Elements, Screenshots
    """
    screenshot_urls = screenshot_urls or {}
    sections = []

    # 1. Description section (if provided)
    if user_description:
        sections.append(f"## Description\n\n{user_description}")

    # 2. Page Info section (always present)
    url = session_data.get("url", "")
    session_id = session_data.get("sessionId", "")
    page_info = f"## Page Info\n\n- **URL**: {url}"
    if session_id:
        page_info += f"\n- **Session ID**: {session_id}"
    sections.append(page_info)

    # 3. Selected Elements section (always present, may be empty)
    selections = extract_selections(session_data)
    elements_section = "## Selected Elements\n\n"

    if selections:
        elements_section += "| # | Selector | Tag | Text Preview |\n"
        elements_section += "|---|----------|-----|──────────────|\n"

        for idx, sel in enumerate(selections, 1):
            selector = sel["selector"] or "unknown"
            tag = sel["tag"] or ""
            text = sel["text"] or ""
            elements_section += f"| {idx} | `{selector}` | {tag} | {text} |\n"
    else:
        elements_section += "(No elements selected)\n"

    sections.append(elements_section)

    # 3b. Design Review Issues section (from "Add to Issue" button)
    design_elements = session_data.get("elements", [])
    if design_elements:
        issues_section = "## Design Review Issues\n\n"
        issues_section += "| # | Selector | Issue(s) |\n"
        issues_section += "|---|----------|----------|\n"

        for idx, el in enumerate(design_elements, 1):
            selector = el.get("selector", "unknown")
            rules = el.get("rules", [])
            issues_str = (
                ", ".join(r.get("message") or r.get("id", "unknown") for r in rules)
                or "No issues"
            )
            issues_section += f"| {idx} | `{selector}` | {issues_str} |\n"

        sections.append(issues_section)

    # 4. Screenshots section (only if images exist)
    if screenshot_urls:
        screenshots_section = "## Screenshots\n\n"
        screenshots_section += "| # | Description | Preview |\n"
        screenshots_section += "|---|-------------|----------|\n"

        for idx, (path, url) in enumerate(screenshot_urls.items(), 1):
            # Generate description from path
            if path.endswith("before.png"):
                desc = "Page screenshot"
            else:
                # Extract selection index from path like "selection_001.png"
                desc = f"Selection {idx - 1}" if idx > 1 else "Screenshot"

            filename = Path(path).name
            screenshots_section += f"| {idx} | {desc} | ![{filename}]({url}) |\n"

        sections.append(screenshots_section)

    return "\n\n".join(sections)


# =============================================================================
# Gist Upload Functions
# =============================================================================


def upload_to_gist(file_paths: list) -> dict:
    """
    Upload multiple files to a single public gist and return raw URLs.

    Args:
        file_paths: List of file paths to upload

    Returns:
        Dictionary with:
        - On success: {"gist_url": "https://...", "files": {"filename": {"raw_url": "..."}}}
        - On error: {"error": "error message"}
    """
    # Validate gh authentication
    if not check_gh_authenticated():
        return {"error": "gh not authenticated"}

    # Validate file count
    if len(file_paths) > 5:
        return {"error": f"Too many files ({len(file_paths)}), max 5"}

    # Validate file sizes and existence
    files_to_upload = []
    total_size = 0
    max_file_size = 10 * 1024 * 1024  # 10MB
    max_total_size = 25 * 1024 * 1024  # 25MB

    for file_path in file_paths:
        path = Path(file_path)
        if not path.exists():
            return {"error": f"File not found: {file_path}"}

        file_size = path.stat().st_size
        if file_size > max_file_size:
            return {
                "error": f"File too large: {path.name} ({file_size / 1024 / 1024:.1f}MB), max 10MB"
            }

        total_size += file_size
        if total_size > max_total_size:
            return {
                "error": f"Total size exceeds 25MB limit. Processed {len(files_to_upload)} files before exceeding limit."
            }

        files_to_upload.append(file_path)

    if not files_to_upload:
        return {"error": "No valid files to upload"}

    # Create gist with all files
    cmd = ["gh", "gist", "create", "--public"] + files_to_upload
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        return {"error": f"Failed to create gist: {result.stderr.strip()}"}

    gist_url = result.stdout.strip()

    # Extract gist ID from URL (e.g., https://gist.github.com/username/abc123def)
    gist_id = gist_url.split("/")[-1]

    # Get file info via API to retrieve raw URLs
    api_cmd = ["gh", "api", f"/gists/{gist_id}"]
    api_result = subprocess.run(api_cmd, capture_output=True, text=True)

    if api_result.returncode != 0:
        return {"error": f"Failed to retrieve gist data: {api_result.stderr.strip()}"}

    try:
        gist_data = json.loads(api_result.stdout)
    except json.JSONDecodeError:
        return {"error": "Failed to parse gist API response"}

    # Build file-to-raw_url mapping
    files = {}
    for filename, file_info in gist_data.get("files", {}).items():
        files[filename] = {"raw_url": file_info.get("raw_url", "")}

    return {"gist_url": gist_url, "files": files}


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

    # Subcommand: upload-gist
    upload_gist_parser = subparsers.add_parser(
        "upload-gist",
        help="Upload one or more files to a public gist and return raw URLs",
    )
    upload_gist_parser.add_argument(
        "files",
        nargs="+",
        help="File paths to upload (max 5 files, max 10MB per file)",
    )

    # Subcommand: generate-body
    generate_body_parser = subparsers.add_parser(
        "generate-body",
        help="Generate Markdown issue body from session data",
    )
    generate_body_parser.add_argument(
        "--mock",
        action="store_true",
        help="Generate body with mock data (for testing)",
    )
    generate_body_parser.add_argument(
        "--session",
        type=str,
        help="Session ID to read from .canvas/sessions/<id>/session.json",
    )
    generate_body_parser.add_argument(
        "--description",
        type=str,
        help="User-provided description to include in body",
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

    # Handle upload-gist subcommand
    if args.command == "upload-gist":
        result = upload_to_gist(args.files)
        print(json.dumps(result))
        return 0

    # Handle generate-body subcommand
    if args.command == "generate-body":
        # Determine session data source
        session_data = None

        if args.mock:
            # Use mock data for testing
            session_data = {
                "url": "http://localhost:3000",
                "sessionId": "ses-mock-test",
                "events": {
                    "selections": [
                        {
                            "source": "picker",
                            "payload": {
                                "element": {
                                    "selector": ".btn-primary",
                                    "tag": "button",
                                    "text": "Submit",
                                }
                            },
                        }
                    ]
                },
            }
        elif args.session:
            # Load from session.json
            session_path = Path(".canvas/sessions") / args.session / "session.json"
            if not session_path.exists():
                print(
                    f"Error: Session file not found: {session_path}",
                    file=sys.stderr,
                )
                return 1

            try:
                with open(session_path, "r") as f:
                    session_data = json.load(f)
            except json.JSONDecodeError as e:
                print(f"Error: Failed to parse session JSON: {e}", file=sys.stderr)
                return 1
        else:
            print(
                "Error: Either --mock or --session must be specified",
                file=sys.stderr,
            )
            return 1

        # Generate and output the issue body
        body = generate_issue_body(session_data, user_description=args.description)
        print(body)
        return 0

    # No command specified - show help
    if not args.command:
        parser.print_help()
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
