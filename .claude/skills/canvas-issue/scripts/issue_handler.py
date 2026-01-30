"""
Issue Handler - Event handler module for agent_canvas.py integration.

This module provides functions for handling issue-related events from the
canvas bus event loop. It is designed to be imported by agent_canvas.py,
not run as a standalone script.

Usage (from agent_canvas.py):
    from issue_handler import handle_issue_event

    for event in events:
        if event.get("type", "").startswith("issue."):
            handle_issue_event(page, event, session_id, all_selections)
"""

import json
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

# Import from canvas_issue.py (same directory)
from canvas_issue import (
    get_gh_status,
    get_github_repo,
    set_github_repo,
    generate_issue_body,
    upload_to_gist,
)


# =============================================================================
# Event Emission Helper
# =============================================================================


def emit_event(page: Any, event_type: str, payload: Dict[str, Any]) -> None:
    """
    Emit an event back to the JavaScript canvas bus.

    Args:
        page: Playwright Page object
        event_type: Event type (e.g., 'issue.repo_prompt', 'issue.created')
        payload: Event payload dictionary
    """
    page.evaluate(f"""
        window.__canvasBus.emit('{event_type}', 'canvas-issue', {json.dumps(payload)})
    """)


# =============================================================================
# Web Fallback URL Generation
# =============================================================================


def generate_fallback_url(repo: str, title: str, body: str) -> str:
    """
    Generate github.com/new issue URL for web fallback.

    Used when gh CLI is not available or fails.

    Args:
        repo: Repository in "owner/repo" format
        title: Issue title
        body: Issue body (will be truncated to ~1800 chars for URL safety)

    Returns:
        URL to github.com issue creation form with pre-filled data
    """
    base = f"https://github.com/{repo}/issues/new"
    # Truncate body to ~1800 chars for URL safety
    truncated_body = body[:1800] + "..." if len(body) > 1800 else body
    params = urlencode({"title": title, "body": truncated_body})
    return f"{base}?{params}"


# =============================================================================
# Event Handlers
# =============================================================================


def handle_button_click(page: Any) -> None:
    """
    Handle the issue button click event.

    Checks if a GitHub repo is configured:
    - If not configured: emits 'issue.repo_prompt' to show repo input modal
    - If configured: emits 'issue.create_modal' to show issue creation form

    Args:
        page: Playwright Page object
    """
    repo = get_github_repo()

    if not repo:
        # No repo configured - prompt user to enter one
        emit_event(page, "issue.repo_prompt", {"existing": None})
    else:
        # Repo configured - show issue creation modal with suggested title
        emit_event(
            page,
            "issue.create_modal",
            {
                "suggestedTitle": "Design QA: ",
                "repo": repo,
            },
        )


def handle_repo_configured(page: Any, repo: str) -> None:
    """
    Handle the repo configuration event.

    Saves the repo to config and then shows the issue creation modal.

    Args:
        page: Playwright Page object
        repo: Repository in "owner/repo" format
    """
    try:
        set_github_repo(repo)
        # After saving, show the issue creation modal
        emit_event(
            page,
            "issue.create_modal",
            {
                "suggestedTitle": "Design QA: ",
                "repo": repo,
            },
        )
    except ValueError as e:
        # Invalid repo format
        emit_event(
            page,
            "issue.failed",
            {
                "error": str(e),
                "fallbackUrl": None,
            },
        )


def handle_create_requested(
    page: Any,
    title: str,
    description: str,
    session_data: Dict[str, Any],
) -> None:
    """
    Handle the issue creation request.

    Full creation flow:
    1. Emit 'issue.creating' with status "uploading_screenshots"
    2. Upload screenshots to gist (if gh available and screenshots exist)
    3. Generate issue body via generate_issue_body()
    4. Emit 'issue.creating' with status "creating_issue"
    5. Create issue via 'gh issue create' or generate web fallback URL
    6. Emit 'issue.created' or 'issue.failed'

    Args:
        page: Playwright Page object
        title: Issue title
        description: User-provided issue description
        session_data: Session data dictionary with selections, screenshots, etc.
    """
    repo = get_github_repo()
    if not repo:
        emit_event(
            page,
            "issue.failed",
            {
                "error": "No repository configured",
                "fallbackUrl": None,
            },
        )
        return

    # Step 1: Check gh status
    gh_status = get_gh_status()
    gh_available = gh_status.get("authenticated", False)

    # Step 2: Upload screenshots if gh is available
    screenshot_urls: Dict[str, str] = {}

    if gh_available:
        # Emit uploading status
        emit_event(page, "issue.creating", {"status": "uploading_screenshots"})

        # Collect screenshot paths from session data
        screenshot_paths: List[str] = []

        # Check for before screenshot
        before_path = session_data.get("beforeScreenshotPath")
        if before_path and Path(before_path).exists():
            screenshot_paths.append(before_path)

        # Check for selection screenshots
        for selection in session_data.get("events", {}).get("selections", []):
            screenshot_info = selection.get("screenshot", {})
            path = screenshot_info.get("path")
            if path and Path(path).exists():
                screenshot_paths.append(path)

        # Upload to gist if we have screenshots
        if screenshot_paths:
            gist_result = upload_to_gist(screenshot_paths)
            if not gist_result.get("error"):
                # Map local paths to raw URLs
                for local_path in screenshot_paths:
                    filename = Path(local_path).name
                    file_info = gist_result.get("files", {}).get(filename, {})
                    raw_url = file_info.get("raw_url")
                    if raw_url:
                        screenshot_urls[local_path] = raw_url

    # Step 3: Generate issue body
    body = generate_issue_body(
        session_data,
        user_description=description,
        screenshot_urls=screenshot_urls,
    )

    # Step 4: Create issue or generate fallback URL
    if gh_available:
        emit_event(page, "issue.creating", {"status": "creating_issue"})

        # Try to create issue via gh CLI
        try:
            result = subprocess.run(
                [
                    "gh",
                    "issue",
                    "create",
                    "--repo",
                    repo,
                    "--title",
                    title,
                    "--body",
                    body,
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode == 0:
                # Success - stdout contains issue URL
                issue_url = result.stdout.strip()
                emit_event(page, "issue.created", {"url": issue_url})
            else:
                # Failed - provide fallback
                fallback_url = generate_fallback_url(repo, title, body)
                emit_event(
                    page,
                    "issue.failed",
                    {
                        "error": result.stderr.strip() or "Failed to create issue",
                        "fallbackUrl": fallback_url,
                    },
                )

        except subprocess.TimeoutExpired:
            fallback_url = generate_fallback_url(repo, title, body)
            emit_event(
                page,
                "issue.failed",
                {
                    "error": "Issue creation timed out",
                    "fallbackUrl": fallback_url,
                },
            )

        except Exception as e:
            fallback_url = generate_fallback_url(repo, title, body)
            emit_event(
                page,
                "issue.failed",
                {
                    "error": str(e),
                    "fallbackUrl": fallback_url,
                },
            )
    else:
        # gh not available - provide web fallback
        fallback_url = generate_fallback_url(repo, title, body)
        emit_event(page, "issue.created", {"url": fallback_url})


# =============================================================================
# Main Event Dispatcher
# =============================================================================


def handle_issue_event(
    page: Any,
    event: Dict[str, Any],
    session_id: str,
    selections: List[Dict[str, Any]],
) -> None:
    """
    Main dispatcher for issue-related events.

    Dispatches to the appropriate handler based on event type:
    - issue.button_clicked -> handle_button_click
    - issue.repo_configured -> handle_repo_configured
    - issue.create_requested -> handle_create_requested

    Args:
        page: Playwright Page object
        event: Event dictionary with 'type' and 'payload'
        session_id: Current session ID
        selections: List of all selection events from the session
    """
    event_type = event.get("type", "")
    payload = event.get("payload", {})

    if event_type == "issue.button_clicked":
        handle_button_click(page)

    elif event_type == "issue.repo_configured":
        repo = payload.get("repo", "")
        handle_repo_configured(page, repo)

    elif event_type == "issue.create_requested":
        title = payload.get("title", "")
        description = payload.get("description", "")

        # Build session data from available information
        # The caller (agent_canvas.py) has access to session_dir and can pass
        # full session data. For now, we construct a minimal session dict.
        session_data = {
            "sessionId": session_id,
            "url": payload.get("url", ""),
            "events": {
                "selections": selections,
            },
            # Note: beforeScreenshotPath would need to be passed via payload
            # or we need to read from session.json
            "beforeScreenshotPath": payload.get("beforeScreenshotPath"),
        }

        handle_create_requested(page, title, description, session_data)
