#!/usr/bin/env -S python3 -u
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "playwright",
# ]
# ///
"""
Canvas Edit - Live Annotation Feedback Toolbar

Injects an annotation toolbar onto web pages that displays design review findings.
Numbered badges appear on elements with issues, with severity indicators and
popovers showing issue details.

The toolbar uses Shadow DOM to be invisible to agent-eyes screenshots.

Features:
- Inject annotation toolbar with issues from design-review
- Numbered badges on elements with issues
- Severity filtering and issue counts
- Screenshot capture (annotations visible, toolbar hidden)
- Integration with canvas bus for cross-skill coordination

Usage:
    uv run canvas_edit.py inject <url> --issues <json_file>
    uv run canvas_edit.py inject <url> --issues - (read from stdin)
"""

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

from playwright.sync_api import sync_playwright, Page


# =============================================================================
# Shared module imports (with fallback for standalone operation)
# =============================================================================


def _setup_shared_imports():
    """Add shared module to path for imports."""
    shared_path = Path(__file__).parent.parent.parent / "shared"
    if shared_path.exists() and str(shared_path) not in sys.path:
        sys.path.insert(0, str(shared_path))


_setup_shared_imports()

try:
    from canvas_bus import (
        CANVAS_BUS_JS,
        drain_bus_events,
        inject_canvas_bus,
    )

    HAS_CANVAS_BUS = True
except ImportError:
    HAS_CANVAS_BUS = False
    CANVAS_BUS_JS = ""

    def inject_canvas_bus(page):
        return {"sessionId": "standalone", "seq": 0}

    def drain_bus_events(page):
        return []


# =============================================================================
# Utilities
# =============================================================================


def get_timestamp() -> str:
    """Generate ISO timestamp."""
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def get_scripts_dir() -> Path:
    """Get the scripts directory path."""
    return Path(__file__).parent


def load_js_file(filename: str) -> str:
    """Load a JavaScript file from the scripts directory."""
    js_path = get_scripts_dir() / filename
    if not js_path.exists():
        raise FileNotFoundError(f"JavaScript file not found: {js_path}")
    return js_path.read_text()


def load_toolbar_js() -> str:
    """Load the annotation toolbar JavaScript."""
    return load_js_file("annotation_toolbar.js")


def load_layer_js() -> str:
    """Load the annotation layer JavaScript."""
    return load_js_file("annotation_layer.js")


def ensure_screenshots_dir() -> Path:
    """Ensure screenshots directory exists and return its path."""
    screenshots_dir = Path.cwd() / ".canvas" / "screenshots"
    screenshots_dir.mkdir(parents=True, exist_ok=True)
    return screenshots_dir


def generate_screenshot_filename(issue_count: int) -> str:
    """Generate screenshot filename per convention."""
    timestamp = datetime.utcnow().strftime("%Y-%m-%dT%H-%M-%S")
    return f"{timestamp}_{issue_count}-issues.png"


# =============================================================================
# Core Functions
# =============================================================================


def inject_annotation_toolbar(
    page: Page, issues: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Inject the annotation toolbar and layer into a page.

    Args:
        page: Playwright page object
        issues: List of issue dictionaries with id, selector, severity, title, etc.

    Returns:
        Dictionary with session info and issue count
    """
    # Inject canvas bus first (for cross-skill coordination)
    session_info = inject_canvas_bus(page)

    # Inject annotation toolbar
    toolbar_js = load_toolbar_js()
    page.evaluate(toolbar_js)

    # Inject annotation layer
    layer_js = load_layer_js()
    page.evaluate(layer_js)

    # Wait for initialization
    page.wait_for_timeout(300)

    # Add each issue as a badge
    for issue in issues:
        page.evaluate(
            """
            (issue) => {
                if (window.__annotationLayer) {
                    window.__annotationLayer.addIssue(issue);
                }
            }
        """,
            issue,
        )

    # Update toolbar counts
    page.evaluate("""
        () => {
            if (window.__annotationToolbar) {
                window.__annotationToolbar.setComplete();
            }
        }
    """)

    return {
        "sessionId": session_info.get("sessionId", "standalone"),
        "issueCount": len(issues),
    }


def capture_annotated_screenshot(page: Page, issue_count: int) -> str:
    """
    Capture a screenshot with annotations visible but toolbar hidden.

    Args:
        page: Playwright page object
        issue_count: Number of issues (for filename)

    Returns:
        Path to saved screenshot
    """
    screenshots_dir = ensure_screenshots_dir()
    filename = generate_screenshot_filename(issue_count)
    screenshot_path = screenshots_dir / filename

    # Hide toolbar for screenshot
    page.evaluate("""
        () => {
            const host = document.getElementById('__annotation_toolbar_host');
            if (host) host.style.display = 'none';
        }
    """)

    # Capture screenshot
    page.screenshot(path=str(screenshot_path), full_page=True)

    # Restore toolbar
    page.evaluate("""
        () => {
            const host = document.getElementById('__annotation_toolbar_host');
            if (host) host.style.display = '';
        }
    """)

    return str(screenshot_path)


def run_inject_session(
    url: str,
    issues: List[Dict[str, Any]],
    auto_screenshot: bool = False,
    interactive: bool = True,
) -> Dict[str, Any]:
    """
    Launch browser with annotation toolbar.

    Args:
        url: URL to open
        issues: List of issues to display
        auto_screenshot: Capture screenshot immediately after injection
        interactive: Keep browser open for user interaction

    Returns:
        Result dictionary with session info and artifacts
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        try:
            # Navigate to URL
            page.goto(url, wait_until="networkidle", timeout=30000)

            # Force browser window to foreground (critical for subprocess execution)
            page.bring_to_front()

            # Inject annotation toolbar
            session_info = inject_annotation_toolbar(page, issues)

            result = {
                "ok": True,
                "url": url,
                "sessionId": session_info["sessionId"],
                "issueCount": session_info["issueCount"],
                "artifacts": {},
            }

            # Emit session start
            start_event = {
                "event": "session.started",
                "sessionId": session_info["sessionId"],
                "timestamp": get_timestamp(),
                "url": url,
                "issueCount": session_info["issueCount"],
            }
            print(json.dumps(start_event))
            sys.stdout.flush()

            # Auto-screenshot if requested
            if auto_screenshot:
                screenshot_path = capture_annotated_screenshot(
                    page, session_info["issueCount"]
                )
                result["artifacts"]["screenshot"] = screenshot_path

                screenshot_event = {
                    "event": "screenshot.captured",
                    "sessionId": session_info["sessionId"],
                    "timestamp": get_timestamp(),
                    "path": screenshot_path,
                    "issueCount": session_info["issueCount"],
                }
                print(json.dumps(screenshot_event))
                sys.stdout.flush()

            # Interactive mode: keep browser open
            if interactive:
                all_events = []

                # Poll for events until browser closes
                while True:
                    try:
                        if page.is_closed():
                            break

                        # Check for screenshot requests
                        events = drain_bus_events(page)
                        for event in events:
                            all_events.append(event)

                            # Handle screenshot.requested events
                            if event.get("type") == "screenshot.requested":
                                payload = event.get("payload", {})
                                screenshot_path = capture_annotated_screenshot(
                                    page, payload.get("issueCount", 0)
                                )

                                # Emit captured event
                                captured_event = {
                                    "event": "screenshot.captured",
                                    "sessionId": session_info["sessionId"],
                                    "timestamp": get_timestamp(),
                                    "path": screenshot_path,
                                    "issueCount": payload.get("issueCount", 0),
                                }
                                print(json.dumps(captured_event))
                                sys.stdout.flush()

                                # Update result
                                result["artifacts"]["screenshot"] = screenshot_path
                            else:
                                # Stream other events
                                print(json.dumps(event))
                                sys.stdout.flush()

                        time.sleep(0.1)

                    except Exception:
                        break

                result["events"] = all_events

            # Emit session end
            end_event = {
                "event": "session.ended",
                "sessionId": session_info["sessionId"],
                "timestamp": get_timestamp(),
            }
            print(json.dumps(end_event))
            sys.stdout.flush()

            return result

        except Exception as e:
            return {"ok": False, "error": str(e)}

        finally:
            browser.close()


def load_issues_from_file(path: str) -> List[Dict[str, Any]]:
    """Load issues from a JSON file or stdin."""
    if path == "-":
        # Read from stdin
        return json.load(sys.stdin)
    else:
        with open(path, "r") as f:
            return json.load(f)


# =============================================================================
# API for other skills
# =============================================================================


def get_toolbar_js() -> str:
    """Return combined JS for toolbar injection."""
    parts = []
    if HAS_CANVAS_BUS:
        parts.append(CANVAS_BUS_JS)
    parts.append(load_toolbar_js())
    parts.append(load_layer_js())
    return "\n".join(parts)


# =============================================================================
# CLI
# =============================================================================


def main():
    parser = argparse.ArgumentParser(
        description="Canvas Edit - Live Annotation Feedback Toolbar",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Inject command
    inject_parser = subparsers.add_parser(
        "inject", help="Inject annotation toolbar with issues"
    )
    inject_parser.add_argument("url", help="URL to annotate")
    inject_parser.add_argument(
        "--issues",
        "-i",
        required=True,
        help="Path to issues JSON file, or '-' for stdin",
    )
    inject_parser.add_argument(
        "--screenshot",
        "-s",
        action="store_true",
        help="Capture screenshot immediately after injection",
    )
    inject_parser.add_argument(
        "--headless",
        action="store_true",
        help="Run in headless mode (no visible browser)",
    )

    # Get JS command (for integration)
    subparsers.add_parser("get-js", help="Output toolbar injection JS")

    args = parser.parse_args()

    if args.command == "inject":
        # Load issues
        try:
            issues = load_issues_from_file(args.issues)
        except json.JSONDecodeError as e:
            print(json.dumps({"ok": False, "error": f"Invalid JSON: {e}"}))
            sys.exit(1)
        except FileNotFoundError as e:
            print(json.dumps({"ok": False, "error": f"File not found: {e}"}))
            sys.exit(1)

        # Run session (visible by default, headless only if explicitly requested)
        result = run_inject_session(
            url=args.url,
            issues=issues,
            auto_screenshot=args.screenshot,
            interactive=not args.headless,
        )

        # Print final result
        print(json.dumps(result))
        sys.exit(0 if result.get("ok") else 1)

    elif args.command == "get-js":
        print(get_toolbar_js())


if __name__ == "__main__":
    main()
