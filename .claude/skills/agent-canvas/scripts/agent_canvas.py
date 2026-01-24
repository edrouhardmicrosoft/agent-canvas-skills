#!/usr/bin/env -S python3 -u
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "playwright",
# ]
# ///
"""
Agent Canvas - Interactive element picker for AI agents.

Launches a browser with element picker overlay. When user clicks an element,
captures selection info and optionally enriches with agent-eyes data IN-PROCESS
(no subprocess spawning - uses the same Page object).

Usage:
    uv run agent_canvas.py pick <url> [--with-eyes] [--with-edit] [--output PATH]
    uv run agent_canvas.py pick <url> --with-edit --with-eyes --interactive
    uv run agent_canvas.py pick <url> --with-edit --with-eyes --auto-apply --auto-verify
    uv run agent_canvas.py watch <url> [--interval SECONDS]
"""

import argparse
import json
import sys
import time
import uuid
import signal
from datetime import datetime
from pathlib import Path
from typing import Optional

from playwright.sync_api import (
    sync_playwright,
    Page,
    TimeoutError as PlaywrightTimeoutError,
)


# =============================================================================
# Session Artifact Management
# =============================================================================


def generate_session_id() -> str:
    """Generate a unique session ID using UUID."""
    return f"ses-{uuid.uuid4().hex[:12]}"


def get_session_dir(session_id: str) -> Path:
    """Get the session directory path, creating it if needed."""
    session_dir = Path(".canvas/sessions") / session_id
    session_dir.mkdir(parents=True, exist_ok=True)
    return session_dir


def _save_screenshot_to_session(
    session_dir: Path,
    filename: str,
    page: Optional["Page"] = None,
    selector: Optional[str] = None,
) -> Optional[str]:
    """
    Save screenshot to session directory, return the path.

    Captures directly to file using agent_eyes.take_screenshot().
    Returns None if capture fails.

    Args:
        session_dir: Path to session directory
        filename: Filename for the screenshot (e.g., "before.png", "selection_001.png")
        page: Playwright Page object
        selector: Optional CSS selector for element screenshot

    Returns:
        Path to saved screenshot file, or None if capture failed
    """
    if not HAS_AGENT_EYES:
        return None

    if page is None:
        return None

    screenshot_path = session_dir / filename

    # Use agent_eyes.take_screenshot with output_path to save directly to file
    # This avoids base64 encoding/decoding overhead
    result = take_screenshot(
        page,
        selector=selector,
        output_path=str(screenshot_path),
        as_base64=False,
        capture_mode_aware=True,  # Hides overlays during capture
    )

    if result.get("ok"):
        return str(screenshot_path)

    return None


def _append_event_log(session_dir: Path, event: dict) -> None:
    """Append a single event as JSONL to the session log file."""
    log_path = session_dir / "events.jsonl"
    with log_path.open("a", encoding="utf-8") as log_file:
        log_file.write(json.dumps(event) + "\n")


def _emit_event(event: dict, stream: bool, session_dir: Path) -> bool:
    """Persist event to disk and optionally stream to stdout.

    Returns updated stream flag (False if stdout is broken).
    """
    _append_event_log(session_dir, event)
    if not stream:
        return False
    try:
        print(json.dumps(event))
        sys.stdout.flush()
        return True
    except BrokenPipeError:
        return False


def write_session_artifact(
    session_dir: Path,
    session_id: str,
    url: str,
    start_time: str,
    end_time: str,
    features: dict,
    selections: list,
    edits: list,
    before_screenshot_path: Optional[str] = None,
) -> Path:
    """
    Write the complete session artifact to disk.

    Args:
        session_dir: Path to session directory
        session_id: Unique session identifier
        url: URL that was being edited
        start_time: ISO timestamp of session start
        end_time: ISO timestamp of session end
        features: Dict of enabled features (picker, eyes, edit)
        selections: List of selection events
        edits: List of edit events
        before_screenshot_path: Path to before screenshot file (not base64!)

    Returns the path to session.json.

    Schema version 1.1: Screenshots stored as file paths, not base64.
    """
    artifact = {
        "schemaVersion": "1.1",  # Bumped for path-based screenshots
        "sessionId": session_id,
        "url": url,
        "startTime": start_time,
        "endTime": end_time,
        "features": features,
        "beforeScreenshotPath": before_screenshot_path,  # Path, not base64
        "events": {
            "selections": selections,
            "edits": edits,
        },
        "summary": {
            "totalSelections": len(selections),
            "totalEdits": len(edits),
            "hasSaveRequest": any(
                e.get("type") == "save_request" or e.get("event") == "save_request"
                for e in edits
            ),
        },
    }

    session_file = session_dir / "session.json"
    session_file.write_text(json.dumps(artifact, indent=2))

    # Also extract save_request to separate file if present
    save_requests = [
        e
        for e in edits
        if e.get("type") == "save_request" or e.get("event") == "save_request"
    ]
    if save_requests:
        changes_file = session_dir / "changes.json"
        changes_file.write_text(json.dumps(save_requests[-1], indent=2))

    return session_file


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
        get_canvas_bus_js,
        inject_canvas_bus,
        drain_bus_events,
        set_capture_mode,
        get_bus_state,
    )

    HAS_CANVAS_BUS = True
except ImportError:
    HAS_CANVAS_BUS = False
    CANVAS_BUS_JS = ""


# =============================================================================
# Agent Eyes integration (in-process, no subprocess)
# =============================================================================


def _setup_agent_eyes_imports():
    """Add agent-eyes to path for in-process calls."""
    agent_eyes_path = Path(__file__).parent.parent.parent / "agent-eyes" / "scripts"
    if agent_eyes_path.exists() and str(agent_eyes_path) not in sys.path:
        sys.path.insert(0, str(agent_eyes_path))


_setup_agent_eyes_imports()

try:
    from agent_eyes import (
        take_screenshot,
        describe_element,
        get_full_context,
    )

    HAS_AGENT_EYES = True
except ImportError:
    HAS_AGENT_EYES = False


def get_timestamp() -> str:
    return datetime.utcnow().strftime("%Y-%m-%dT%H-%M-%S-%f")[:-3] + "Z"


# =============================================================================
# Canvas Apply/Verify integration (for interactive mode)
# =============================================================================


def _setup_apply_verify_imports():
    """Add canvas-apply and canvas-verify to path for imports."""
    apply_path = Path(__file__).parent.parent.parent / "canvas-apply" / "scripts"
    verify_path = Path(__file__).parent.parent.parent / "canvas-verify" / "scripts"
    for p in [apply_path, verify_path]:
        if p.exists() and str(p) not in sys.path:
            sys.path.insert(0, str(p))


_setup_apply_verify_imports()

# Lazy imports - only loaded when interactive mode is used
HAS_CANVAS_APPLY = False
HAS_CANVAS_VERIFY = False

try:
    from session_parser import parse_session
    from diff_generator import generate_diffs, result_to_dict

    HAS_CANVAS_APPLY = True
except ImportError:
    pass

try:
    # canvas_verify needs playwright, so we'll call it via subprocess
    HAS_CANVAS_VERIFY = True
except ImportError:
    pass


# =============================================================================
# Design Review Overlay Integration
# =============================================================================


def get_review_overlay_js() -> Optional[str]:
    """Load the design-review overlay JavaScript."""
    review_js_path = (
        Path(__file__).parent.parent.parent
        / "design-review"
        / "scripts"
        / "review_overlay.js"
    )
    if review_js_path.exists():
        return review_js_path.read_text()
    return None


def _safe_stderr_write(payload: dict) -> None:
    try:
        print(json.dumps(payload), file=sys.stderr)
        sys.stderr.flush()
    except BrokenPipeError:
        return


HAS_REVIEW_OVERLAY = get_review_overlay_js() is not None


# =============================================================================
# Interactive mode helpers
# =============================================================================


def prompt_yes_no(question: str, default: bool = False) -> bool:
    """Prompt user for yes/no answer."""
    suffix = " [Y/n] " if default else " [y/N] "
    try:
        answer = input(question + suffix).strip().lower()
        if not answer:
            return default
        return answer in ("y", "yes")
    except (EOFError, KeyboardInterrupt):
        print()
        return False


def run_apply_workflow(session_id: str, auto: bool = False) -> bool:
    """
    Run the apply workflow for a session.

    Returns True if changes were applied successfully.
    """
    if not HAS_CANVAS_APPLY:
        print("⚠️  canvas-apply not available", file=sys.stderr)
        return False

    print(f"\n{'=' * 60}")
    print(f"Session: {session_id}")
    print(f"{'=' * 60}\n")

    # Parse session and generate diffs
    manifest = parse_session(session_id)
    if not manifest:
        print(f"❌ Could not parse session: {session_id}", file=sys.stderr)
        return False

    if not manifest.style_changes and not manifest.text_changes:
        print("ℹ️  No changes to apply (did you click 'Save All to Code'?)")
        return False

    # Generate diffs
    diff_result = generate_diffs(manifest)
    result_dict = result_to_dict(diff_result)

    if not result_dict["fileDiffs"]:
        print("ℹ️  No file changes generated.")
        if result_dict.get("unmappedChanges"):
            print("\nUnmapped changes (couldn't find source location):")
            for change in result_dict["unmappedChanges"]:
                print(f"  - {change}")
        return False

    # Show diff preview
    print(f"Files to modify: {result_dict['summary']['filesModified']}\n")

    for diff in result_dict["fileDiffs"]:
        confidence = diff["confidence"]
        confidence_str = f" (confidence: {confidence:.0%})"

        if confidence < 0.70:
            print(f"⚠️  LOW CONFIDENCE{confidence_str}: {diff['filePath']}")
        else:
            print(f"📝 {diff['filePath']}{confidence_str}")

        print()
        print(diff["unifiedDiff"])
        print()

    # Prompt for apply (unless auto mode)
    if not auto:
        if not prompt_yes_no("Apply these changes?", default=False):
            print("Skipped applying changes.")
            return False

    # Apply changes
    applied = 0
    for file_diff in diff_result.file_diffs:
        try:
            Path(file_diff.file_path).write_text(file_diff.modified_content)
            print(f"✅ Modified: {file_diff.file_path}")
            applied += 1
        except Exception as e:
            print(f"❌ Failed to modify {file_diff.file_path}: {e}", file=sys.stderr)

    if applied > 0:
        print(f"\n✅ Applied changes to {applied} file(s).")
        return True

    return False


def run_verify_workflow(url: str, session_id: str, auto: bool = False) -> bool:
    """
    Run the verify workflow for a session.

    Returns True if verification passed.
    """
    import subprocess

    verify_script = (
        Path(__file__).parent.parent.parent
        / "canvas-verify"
        / "scripts"
        / "canvas_verify.py"
    )

    if not verify_script.exists():
        print("⚠️  canvas-verify not available", file=sys.stderr)
        return False

    print(f"\n{'=' * 60}")
    print("Running verification...")
    print(f"{'=' * 60}\n")

    try:
        result = subprocess.run(
            ["uv", "run", str(verify_script), url, "--session", session_id, "--save"],
            capture_output=False,
            timeout=60,
        )
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        print("❌ Verification timed out", file=sys.stderr)
        return False
    except Exception as e:
        print(f"❌ Verification failed: {e}", file=sys.stderr)
        return False


# =============================================================================
# Canvas Edit panel loading
# =============================================================================


def get_canvas_edit_js() -> Optional[str]:
    """Load the canvas-edit panel JS if available."""
    edit_script = (
        Path(__file__).parent.parent.parent
        / "canvas-edit"
        / "scripts"
        / "canvas_edit.py"
    )
    if not edit_script.exists():
        return None

    # Try to import directly (preferred - no subprocess)
    try:
        edit_scripts_path = edit_script.parent
        if str(edit_scripts_path) not in sys.path:
            sys.path.insert(0, str(edit_scripts_path))

        from canvas_edit import get_panel_js

        return get_panel_js()
    except ImportError:
        pass

    # Fallback: subprocess (for PEP 723 dependency resolution)
    import subprocess

    try:
        result = subprocess.run(
            ["uv", "run", str(edit_script), "get-js"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout
    except Exception:
        pass
    return None


# =============================================================================
# Picker overlay JS - Updated to use canvas bus
# =============================================================================

PICKER_OVERLAY_JS = """
(() => {
    if (window.__agentCanvasActive) return;
    window.__agentCanvasActive = true;
    
    // Ensure canvas bus is available
    const bus = window.__canvasBus;
    if (!bus) {
        console.error('[AgentCanvas] Canvas bus not initialized!');
        return;
    }
    
    // Register this tool
    bus.state.activeTools.add('picker');
    
    // Legacy event queues (for backward compatibility)
    window.__agentCanvasEvents = [];
    window.__agentCanvasClosed = false;
    
    // ==========================================================================
    // Unified Design Tokens (shared with canvas-edit, design-review)
    // ==========================================================================
    const TOKENS = {
        colors: {
            primary: '#58a6ff',
            primaryHover: '#79b8ff',
            primaryLight: 'rgba(88, 166, 255, 0.15)',
            background: {
                panel: '#1f1f1f',
                elevated: '#292929',
                overlay: 'rgba(31, 41, 55, 0.95)',
            },
            border: '#3d3d3d',
            text: {
                primary: '#e0e0e0',
                secondary: '#a0a0a0',
            },
            status: {
                success: '#3fb950',
                warning: '#d29922',
                error: '#f85149',
            },
            highlight: 'rgba(88, 166, 255, 0.2)',
        },
        font: {
            family: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
        },
        radius: {
            md: '4px',
            lg: '6px',
            xl: '8px',
        },
        shadow: {
            md: '0 4px 12px rgba(0, 0, 0, 0.4)',
            lg: '0 4px 16px rgba(0, 0, 0, 0.4), 0 0 0 1px rgba(255, 255, 255, 0.05)',
        },
        zIndex: {
            overlay: 2147483645,
            panel: 2147483646,
            tooltip: 2147483647,
        },
    };
    
    // Create overlay elements with unified tokens
    const overlay = document.createElement('div');
    overlay.id = '__agent_canvas_overlay';
    overlay.style.cssText = `
        position: fixed;
        pointer-events: none;
        border: 2px solid ${TOKENS.colors.primary};
        background: ${TOKENS.colors.highlight};
        z-index: ${TOKENS.zIndex.overlay};
        transition: all 0.1s cubic-bezier(0.33, 0, 0.1, 1);
        display: none;
    `;
    
    const label = document.createElement('div');
    label.id = '__agent_canvas_label';
    label.style.cssText = `
        position: fixed;
        background: ${TOKENS.colors.background.elevated};
        color: ${TOKENS.colors.text.primary};
        padding: 6px 12px;
        font-size: 12px;
        font-family: ${TOKENS.font.family};
        border-radius: ${TOKENS.radius.lg};
        border: 1px solid ${TOKENS.colors.border};
        box-shadow: ${TOKENS.shadow.md};
        z-index: ${TOKENS.zIndex.tooltip};
        pointer-events: none;
        display: none;
        max-width: 350px;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    `;
    
    const instructions = document.createElement('div');
    instructions.id = '__agent_canvas_instructions';
    instructions.style.cssText = `
        position: fixed;
        top: 12px;
        left: 50%;
        transform: translateX(-50%);
        background: ${TOKENS.colors.background.overlay};
        color: ${TOKENS.colors.text.primary};
        padding: 10px 20px;
        font-size: 13px;
        font-family: ${TOKENS.font.family};
        border-radius: ${TOKENS.radius.xl};
        box-shadow: ${TOKENS.shadow.lg};
        z-index: ${TOKENS.zIndex.tooltip};
        pointer-events: none;
    `;
    instructions.textContent = 'Click elements to select. Close window when done.';
    
    // Selection counter badge
    const counter = document.createElement('div');
    counter.id = '__agent_canvas_counter';
    counter.style.cssText = `
        position: fixed;
        top: 12px;
        right: 12px;
        background: ${TOKENS.colors.primary};
        color: #1f1f1f;
        padding: 10px 16px;
        font-size: 13px;
        font-weight: 600;
        font-family: ${TOKENS.font.family};
        border-radius: ${TOKENS.radius.xl};
        box-shadow: ${TOKENS.shadow.lg};
        z-index: ${TOKENS.zIndex.tooltip};
        pointer-events: none;
    `;
    counter.textContent = 'Selections: 0';
    
    document.body.appendChild(overlay);
    document.body.appendChild(label);
    document.body.appendChild(instructions);
    document.body.appendChild(counter);
    
    let currentElement = null;
    let selectionCount = 0;
    
    // Subscribe to capture mode changes (hide overlays during screenshots)
    bus.subscribe('capture_mode.changed', (event) => {
        const hidden = event.payload.enabled;
        overlay.style.display = hidden ? 'none' : (currentElement ? 'block' : 'none');
        label.style.display = hidden ? 'none' : (currentElement ? 'block' : 'none');
        instructions.style.display = hidden ? 'none' : 'block';
        counter.style.display = hidden ? 'none' : 'block';
    });
    
    function updateOverlay(el) {
        if (!el || el.id?.startsWith('__agent_canvas') || el.id?.startsWith('__canvas_edit')) {
            overlay.style.display = 'none';
            label.style.display = 'none';
            return;
        }
        
        // Don't show during capture mode
        if (bus.state.captureMode) {
            overlay.style.display = 'none';
            label.style.display = 'none';
            return;
        }
        
        const rect = el.getBoundingClientRect();
        const selectorInfo = bus.generateSelector(el);
        
        overlay.style.display = 'block';
        overlay.style.top = rect.top + 'px';
        overlay.style.left = rect.left + 'px';
        overlay.style.width = rect.width + 'px';
        overlay.style.height = rect.height + 'px';
        
        label.style.display = 'block';
        label.style.top = (rect.top - 28) + 'px';
        label.style.left = rect.left + 'px';
        label.textContent = selectorInfo.selector;
        
        // Add confidence indicator using unified tokens
        if (selectorInfo.confidence === 'high') {
            label.style.background = TOKENS.colors.status.success;  // Green for high
            label.style.borderColor = TOKENS.colors.status.success;
        } else if (selectorInfo.confidence === 'medium') {
            label.style.background = TOKENS.colors.status.warning;  // Orange for medium
            label.style.borderColor = TOKENS.colors.status.warning;
        } else {
            label.style.background = TOKENS.colors.background.elevated;  // Default elevated bg
            label.style.borderColor = TOKENS.colors.border;
        }
        
        // Adjust label if it goes off screen
        if (rect.top < 30) {
            label.style.top = (rect.bottom + 4) + 'px';
        }
    }
    
    document.addEventListener('mousemove', (e) => {
        const el = document.elementFromPoint(e.clientX, e.clientY);
        if (el !== currentElement) {
            currentElement = el;
            updateOverlay(el);
        }
    }, true);
    
    document.addEventListener('click', (e) => {
        if (e.target.id?.startsWith('__agent_canvas')) return;
        if (e.target.id?.startsWith('__canvas_edit')) return;
        
        e.preventDefault();
        e.stopPropagation();
        
        const elementInfo = bus.getElementInfo(e.target);
        selectionCount++;
        
        // Emit selection through the bus (this updates shared state)
        const event = bus.emit('selection.changed', 'picker', {
            index: selectionCount,
            element: elementInfo
        });
        
        // Also update bus state for cross-tool coordination
        bus.setSelection(elementInfo);
        
        // Legacy: push to old event queue for backward compatibility
        window.__agentCanvasEvents.push({
            event: 'selection',
            index: selectionCount,
            timestamp: event.timestamp,
            element: elementInfo
        });
        
        // Visual feedback - flash success green then restore
        overlay.style.borderColor = TOKENS.colors.status.success;
        overlay.style.background = 'rgba(63, 185, 80, 0.2)';
        counter.textContent = `Selections: ${selectionCount}`;
        counter.style.background = TOKENS.colors.status.success;
        
        setTimeout(() => {
            overlay.style.borderColor = TOKENS.colors.primary;
            overlay.style.background = TOKENS.colors.highlight;
            counter.style.background = TOKENS.colors.primary;
            updateOverlay(currentElement);  // Restore proper label color
        }, 300);
    }, true);
    
    console.log('[AgentCanvas] Picker initialized with session:', bus.sessionId);
})();
"""


def pick_element(
    url: str,
    with_eyes: bool = False,
    with_edit: bool = False,
    with_review: bool = False,
    output_path: Optional[str] = None,
    stream: bool = False,
    interactive: bool = False,
    auto_apply: bool = False,
    auto_verify: bool = False,
) -> dict:
    """
    Launch browser with element picker, stream selection events until window closes.

    When with_eyes=True, enriches selections with agent-eyes data IN-PROCESS
    (using the same Page object - no subprocess spawning).

    Session artifacts are automatically written to .canvas/sessions/<sessionId>/

    Interactive mode (--interactive):
        After browser closes, prompts user to apply changes and verify.

    Auto mode (--auto-apply, --auto-verify):
        Automatically applies and/or verifies without prompting.
    """

    all_selections = []
    all_edit_events = []
    stream_enabled = stream

    # Generate our own session ID for artifact tracking
    session_id = generate_session_id()
    session_dir = get_session_dir(session_id)
    start_time = get_timestamp()
    before_screenshot_path = None

    with sync_playwright() as p:
        # Launch visible browser for interaction
        browser = p.chromium.launch(headless=False)

        def _on_browser_disconnected(_browser):
            _safe_stderr_write({"type": "debug.browser_disconnected"})

        browser.on("disconnected", _on_browser_disconnected)
        context = browser.new_context()
        # Disable default timeout - user controls when to close browser
        context.set_default_timeout(0)
        page = context.new_page()
        page.set_default_timeout(0)
        page.set_default_navigation_timeout(0)

        try:
            page.goto(url, wait_until="networkidle", timeout=30000)

            # Force browser window to foreground (critical for subprocess execution)
            page.bring_to_front()

            # Capture "before" screenshot immediately (as file for token efficiency)
            before_screenshot_path = _save_screenshot_to_session(
                session_dir=session_dir,
                filename="before.png",
                page=page,
            )

            # Inject shared canvas bus FIRST
            session_info = {"sessionId": session_id, "seq": 0}
            if HAS_CANVAS_BUS:
                page.evaluate(CANVAS_BUS_JS)
                # Override the bus session ID to match our artifact session ID
                page.evaluate(
                    f"() => {{ window.__canvasBus.sessionId = '{session_id}'; }}"
                )
                session_info = page.evaluate(
                    "() => ({ sessionId: window.__canvasBus.sessionId, seq: window.__canvasBus.getSeq() })"
                )

            # Inject picker overlay
            page.evaluate(PICKER_OVERLAY_JS)

            # NOTE: --with-edit toolbar temporarily disabled
            # The canvas-edit toolbar was designed for design-review workflow (displaying issues)
            # but was incorrectly wired to --with-edit flag. It shows a non-functional UI
            # with eye/camera/filter buttons that do nothing without pre-loaded issues.
            # See plans/toolbar-update.md for the redesign plan.
            #
            # if with_edit:
            #     edit_js = get_canvas_edit_js()
            #     if edit_js:
            #         page.evaluate(edit_js)

            # Inject design-review overlay if requested (live a11y compliance)
            if with_review:
                review_js = get_review_overlay_js()
                if review_js:
                    page.evaluate(review_js)

            # Define features for this session
            # NOTE: edit feature temporarily disabled - see plans/toolbar-update.md
            features = {
                "picker": True,
                "eyes": with_eyes and HAS_AGENT_EYES,
                "edit": False,  # Disabled: was showing non-functional toolbar
                "review": with_review and HAS_REVIEW_OVERLAY,
            }

            # Emit session start
            start_event = {
                "schemaVersion": "1.0",
                "sessionId": session_id,
                "seq": 0,
                "type": "session.started",
                "source": "picker",
                "timestamp": start_time,
                "payload": {
                    "url": url,
                    "features": features,
                    "artifactDir": str(session_dir),
                },
            }
            stream_enabled = _emit_event(start_event, stream_enabled, session_dir)

            # Poll for events until browser closes
            while True:
                try:
                    if not browser.is_connected():
                        _safe_stderr_write({"type": "debug.browser_disconnected"})
                        break

                    # Check if page is still open
                    if page.is_closed():
                        break

                    # Drain events from the canvas bus (preferred) or legacy queue
                    try:
                        if HAS_CANVAS_BUS:
                            events = drain_bus_events(page)
                        else:
                            events = page.evaluate("""
                                () => {
                                    const events = window.__agentCanvasEvents || [];
                                    window.__agentCanvasEvents = [];
                                    return events;
                                }
                            """)
                    except PlaywrightTimeoutError as e:
                        _safe_stderr_write({"type": "debug.timeout", "message": str(e)})
                        time.sleep(0.2)
                        continue

                    for event in events:
                        # Handle selection events
                        if (
                            event.get("type") == "selection.changed"
                            or event.get("event") == "selection"
                        ):
                            all_selections.append(event)

                            # Enrich with agent-eyes IN-PROCESS if requested
                            if with_eyes and HAS_AGENT_EYES:
                                # Get selector from event
                                element_data = event.get("payload", {}).get(
                                    "element", {}
                                ) or event.get("element", {})
                                selector = element_data.get("selector")

                                if selector:
                                    # Call agent-eyes functions directly with the SAME page
                                    # No subprocess, no separate browser!
                                    try:
                                        # Set capture mode before taking screenshot
                                        if HAS_CANVAS_BUS:
                                            set_capture_mode(page, True)

                                        eyes_result = describe_element(page, selector)
                                        if eyes_result.get("ok"):
                                            event["eyes"] = eyes_result

                                        # Save selection screenshot to file (not base64)
                                        selection_count = len(all_selections)
                                        screenshot_filename = (
                                            f"selection_{selection_count:03d}.png"
                                        )
                                        screenshot_path = _save_screenshot_to_session(
                                            session_dir=session_dir,
                                            filename=screenshot_filename,
                                            page=page,
                                            selector=selector,
                                        )
                                        if screenshot_path:
                                            # Get file size for metadata
                                            screenshot_file = (
                                                session_dir / screenshot_filename
                                            )
                                            event["screenshot"] = {
                                                "path": screenshot_path,
                                                "size": screenshot_file.stat().st_size
                                                if screenshot_file.exists()
                                                else 0,
                                            }
                                    finally:
                                        if HAS_CANVAS_BUS:
                                            set_capture_mode(page, False)

                        # Handle edit events
                        elif (
                            event.get("type", "").startswith("edit.")
                            or event.get("type", "").startswith("style")
                            or event.get("event") == "style_change"
                        ):
                            all_edit_events.append(event)

                        elif (
                            event.get("type") == "save_request"
                            or event.get("event") == "save_request"
                        ):
                            all_edit_events.append(event)

                        # Stream event to stdout
                        stream_enabled = _emit_event(event, stream_enabled, session_dir)

                    # Also check legacy edit event queue for backward compatibility
                    if with_edit:
                        try:
                            edit_events = page.evaluate("""
                                () => {
                                    const events = window.__canvasEditEvents || [];
                                    window.__canvasEditEvents = [];
                                    return events;
                                }
                            """)
                        except PlaywrightTimeoutError as e:
                            _safe_stderr_write(
                                {"type": "debug.timeout", "message": str(e)}
                            )
                            time.sleep(0.2)
                            continue

                        for event in edit_events:
                            # Avoid duplicates from bus
                            if not any(
                                e.get("timestamp") == event.get("timestamp")
                                for e in all_edit_events
                            ):
                                all_edit_events.append(event)
                                stream_enabled = _emit_event(
                                    event, stream_enabled, session_dir
                                )

                    time.sleep(0.1)

                except Exception as e:
                    # Only break if the browser/page is actually closed
                    # Common close indicators: "Target closed", "Browser closed", "Context closed"
                    error_msg = str(e).lower()
                    if any(
                        indicator in error_msg
                        for indicator in [
                            "target closed",
                            "browser closed",
                            "context closed",
                            "connection closed",
                            "target page, context or browser has been closed",
                        ]
                    ):
                        break
                    # For other exceptions, log and continue polling
                    _safe_stderr_write({"type": "debug.error", "message": str(e)})
                    time.sleep(0.5)  # Back off slightly on errors
                    continue

            # Session end time
            end_time = get_timestamp()

            # Write session artifact to disk
            artifact_path = write_session_artifact(
                session_dir=session_dir,
                session_id=session_id,
                url=url,
                start_time=start_time,
                end_time=end_time,
                features=features,
                selections=all_selections,
                edits=all_edit_events,
                before_screenshot_path=before_screenshot_path,
            )

            # Emit session end
            end_event = {
                "schemaVersion": "1.1",  # Matches artifact schema
                "sessionId": session_id,
                "seq": len(all_selections) + len(all_edit_events) + 1,
                "type": "session.ended",
                "source": "picker",
                "timestamp": end_time,
                "payload": {
                    "total_selections": len(all_selections),
                    "total_edits": len(all_edit_events),
                    "artifactPath": str(artifact_path),
                },
            }
            stream_enabled = _emit_event(end_event, stream_enabled, session_dir)

            result = {
                "ok": True,
                "url": url,
                "sessionId": session_id,
                "artifactPath": str(artifact_path),
                "artifactDir": str(session_dir),
                "selections": all_selections,
                "edits": all_edit_events,
                "total_selections": len(all_selections),
                "total_edits": len(all_edit_events),
            }

            # Save to file if requested (in addition to session artifact)
            if output_path:
                Path(output_path).parent.mkdir(parents=True, exist_ok=True)
                Path(output_path).write_text(json.dumps(result, indent=2))

            # Interactive/auto workflow (after browser closes)
            if interactive or auto_apply or auto_verify:
                # Check if there are changes to apply
                has_save_request = any(
                    e.get("type") == "save_request" or e.get("event") == "save_request"
                    for e in all_edit_events
                )

                applied = False

                if has_save_request:
                    if auto_apply:
                        applied = run_apply_workflow(session_id, auto=True)
                    elif interactive:
                        if prompt_yes_no("\nApply changes to code?", default=False):
                            applied = run_apply_workflow(session_id, auto=True)
                        else:
                            print("Skipped applying changes.")
                else:
                    if interactive or auto_apply:
                        print(
                            "\nℹ️  No save_request found (did you click 'Save All to Code'?)"
                        )

                # Verify workflow
                if applied and (auto_verify or interactive):
                    if auto_verify:
                        result["verified"] = run_verify_workflow(
                            url, session_id, auto=True
                        )
                    elif interactive:
                        if prompt_yes_no("\nVerify changes?", default=False):
                            result["verified"] = run_verify_workflow(
                                url, session_id, auto=True
                            )
                        else:
                            print("Skipped verification.")

                result["applied"] = applied

            return result

        except Exception as e:
            error_result = {"ok": False, "error": str(e), "sessionId": session_id}
            error_event = {
                "schemaVersion": "1.0",
                "sessionId": session_id,
                "type": "session.error",
                "source": "picker",
                "timestamp": get_timestamp(),
                "payload": {"error": str(e)},
            }
            _append_event_log(session_dir, error_event)
            _safe_stderr_write(error_event)
            return error_result
        finally:
            browser.close()


def watch_page(
    url: str,
    interval: float = 2.0,
    output_dir: Optional[str] = None,
) -> None:
    """Watch page for changes, using in-process agent-eyes for screenshots."""

    output_path = Path(output_dir or ".canvas/watch")
    output_path.mkdir(parents=True, exist_ok=True)

    print(
        json.dumps(
            {
                "schemaVersion": "1.0",
                "type": "watch.started",
                "source": "picker",
                "timestamp": get_timestamp(),
                "payload": {"url": url, "interval": interval},
            }
        )
    )
    sys.stdout.flush()

    last_snapshot = None
    iteration = 0

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()

        try:
            page.goto(url, wait_until="networkidle", timeout=30000)

            # Force browser window to foreground (critical for subprocess execution)
            page.bring_to_front()

            # Inject canvas bus for utilities
            if HAS_CANVAS_BUS:
                page.evaluate(CANVAS_BUS_JS)

            while True:
                # Get current DOM snapshot
                snapshot = page.evaluate("""
                    () => {
                        return document.body.innerHTML.length.toString() + 
                               Array.from(document.querySelectorAll('*')).length.toString();
                    }
                """)

                if snapshot != last_snapshot:
                    iteration += 1
                    timestamp = get_timestamp()

                    # Take screenshot using in-process agent-eyes if available
                    screenshot_result = {"ok": False}
                    if HAS_AGENT_EYES:
                        screenshot_result = take_screenshot(page)

                    change_event = {
                        "schemaVersion": "1.0",
                        "type": "watch.change_detected",
                        "source": "picker",
                        "timestamp": timestamp,
                        "payload": {
                            "iteration": iteration,
                            "screenshot": screenshot_result.get("path")
                            if screenshot_result.get("ok")
                            else None,
                        },
                    }

                    print(json.dumps(change_event))
                    sys.stdout.flush()

                    last_snapshot = snapshot

                time.sleep(interval)

        except KeyboardInterrupt:
            print(
                json.dumps(
                    {
                        "schemaVersion": "1.0",
                        "type": "watch.stopped",
                        "source": "picker",
                        "timestamp": get_timestamp(),
                        "payload": {},
                    }
                )
            )
        except Exception as e:
            print(
                json.dumps(
                    {
                        "schemaVersion": "1.0",
                        "type": "watch.error",
                        "source": "picker",
                        "timestamp": get_timestamp(),
                        "payload": {"error": str(e)},
                    }
                )
            )
        finally:
            browser.close()


def main():
    signal.signal(signal.SIGPIPE, signal.SIG_IGN)
    parser = argparse.ArgumentParser(
        description="Agent Canvas - Interactive element picker for AI agents",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Pick command
    pick_parser = subparsers.add_parser("pick", help="Pick an element interactively")
    pick_parser.add_argument("url", help="URL to open")
    pick_parser.add_argument(
        "--with-eyes",
        action="store_true",
        help="Get visual context from agent-eyes after selection (in-process)",
    )
    pick_parser.add_argument(
        "--with-edit",
        action="store_true",
        help="Load canvas-edit panel for live style editing",
    )
    pick_parser.add_argument(
        "--with-review",
        action="store_true",
        help="Load design-review overlay with live a11y compliance checking",
    )
    pick_parser.add_argument("--output", "-o", help="Save result to file")
    pick_parser.add_argument(
        "--interactive",
        "-i",
        action="store_true",
        help="Interactive mode: prompt to apply/verify after browser closes",
    )
    pick_parser.add_argument(
        "--auto-apply",
        action="store_true",
        help="Automatically apply changes after browser closes (no prompt)",
    )
    pick_parser.add_argument(
        "--auto-verify",
        action="store_true",
        help="Automatically verify changes after applying (no prompt)",
    )

    # Watch command
    watch_parser = subparsers.add_parser("watch", help="Watch page for changes")
    watch_parser.add_argument("url", help="URL to watch")
    watch_parser.add_argument(
        "--interval",
        "-i",
        type=float,
        default=2.0,
        help="Check interval in seconds (default: 2)",
    )
    watch_parser.add_argument("--output-dir", "-o", help="Directory for screenshots")

    args = parser.parse_args()

    if args.command == "pick":
        result = pick_element(
            args.url,
            with_eyes=args.with_eyes,
            with_edit=args.with_edit,
            with_review=args.with_review,
            output_path=args.output,
            interactive=args.interactive,
            auto_apply=args.auto_apply,
            auto_verify=args.auto_verify,
        )
        # Final summary already streamed, just exit
        sys.exit(0 if result.get("ok") else 1)

    elif args.command == "watch":
        watch_page(
            args.url,
            interval=args.interval,
            output_dir=args.output_dir,
        )


if __name__ == "__main__":
    main()
