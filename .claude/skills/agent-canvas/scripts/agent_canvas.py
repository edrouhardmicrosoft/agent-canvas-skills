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
from datetime import datetime
from pathlib import Path
from typing import Optional

from playwright.sync_api import sync_playwright, Page


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


def write_session_artifact(
    session_dir: Path,
    session_id: str,
    url: str,
    start_time: str,
    end_time: str,
    features: dict,
    selections: list,
    edits: list,
    before_screenshot_base64: Optional[str] = None,
) -> Path:
    """
    Write the complete session artifact to disk.

    Returns the path to session.json.
    """
    artifact = {
        "schemaVersion": "1.0",
        "sessionId": session_id,
        "url": url,
        "startTime": start_time,
        "endTime": end_time,
        "features": features,
        "beforeScreenshot": before_screenshot_base64,
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
    
    // Create overlay elements
    const overlay = document.createElement('div');
    overlay.id = '__agent_canvas_overlay';
    overlay.style.cssText = `
        position: fixed;
        pointer-events: none;
        border: 2px solid #007AFF;
        background: rgba(0, 122, 255, 0.1);
        z-index: 999999;
        transition: all 0.05s ease-out;
        display: none;
    `;
    
    const label = document.createElement('div');
    label.id = '__agent_canvas_label';
    label.style.cssText = `
        position: fixed;
        background: #007AFF;
        color: white;
        padding: 4px 8px;
        font-size: 12px;
        font-family: -apple-system, BlinkMacSystemFont, sans-serif;
        border-radius: 4px;
        z-index: 1000000;
        pointer-events: none;
        display: none;
        max-width: 300px;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    `;
    
    const instructions = document.createElement('div');
    instructions.id = '__agent_canvas_instructions';
    instructions.style.cssText = `
        position: fixed;
        top: 10px;
        left: 50%;
        transform: translateX(-50%);
        background: rgba(0, 0, 0, 0.8);
        color: white;
        padding: 12px 20px;
        font-size: 14px;
        font-family: -apple-system, BlinkMacSystemFont, sans-serif;
        border-radius: 8px;
        z-index: 1000001;
        pointer-events: none;
    `;
    instructions.textContent = 'Click elements to select. Close window when done.';
    
    // Selection counter badge
    const counter = document.createElement('div');
    counter.id = '__agent_canvas_counter';
    counter.style.cssText = `
        position: fixed;
        top: 10px;
        right: 10px;
        background: #007AFF;
        color: white;
        padding: 8px 16px;
        font-size: 14px;
        font-family: -apple-system, BlinkMacSystemFont, sans-serif;
        border-radius: 8px;
        z-index: 1000001;
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
        
        // Add confidence indicator
        if (selectorInfo.confidence === 'high') {
            label.style.background = '#34C759';  // Green for high confidence
        } else if (selectorInfo.confidence === 'medium') {
            label.style.background = '#FF9500';  // Orange for medium
        } else {
            label.style.background = '#007AFF';  // Blue for low
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
        
        // Visual feedback - flash green then back
        overlay.style.borderColor = '#34C759';
        overlay.style.background = 'rgba(52, 199, 89, 0.3)';
        counter.textContent = `Selections: ${selectionCount}`;
        counter.style.background = '#34C759';
        
        setTimeout(() => {
            overlay.style.borderColor = '#007AFF';
            overlay.style.background = 'rgba(0, 122, 255, 0.1)';
            counter.style.background = '#007AFF';
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

    # Generate our own session ID for artifact tracking
    session_id = generate_session_id()
    session_dir = get_session_dir(session_id)
    start_time = get_timestamp()
    before_screenshot_base64 = None

    with sync_playwright() as p:
        # Launch visible browser for interaction
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        try:
            page.goto(url, wait_until="networkidle", timeout=30000)

            # Capture "before" screenshot immediately (as base64 for portability)
            if HAS_AGENT_EYES:
                before_result = take_screenshot(page, as_base64=True)
                if before_result.get("ok"):
                    before_screenshot_base64 = before_result.get("base64")

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

            # Inject edit panel if requested
            if with_edit:
                edit_js = get_canvas_edit_js()
                if edit_js:
                    page.evaluate(edit_js)

            # Define features for this session
            features = {
                "picker": True,
                "eyes": with_eyes and HAS_AGENT_EYES,
                "edit": with_edit and get_canvas_edit_js() is not None,
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
            print(json.dumps(start_event))
            sys.stdout.flush()

            # Poll for events until browser closes
            while True:
                try:
                    # Check if page is still open
                    if page.is_closed():
                        break

                    # Drain events from the canvas bus (preferred) or legacy queue
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

                                        screenshot_result = take_screenshot(
                                            page,
                                            selector,
                                            as_base64=True,
                                            capture_mode_aware=False,  # We already set it
                                        )
                                        if screenshot_result.get("ok"):
                                            event["screenshot"] = screenshot_result
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
                        print(json.dumps(event))
                        sys.stdout.flush()

                    # Also check legacy edit event queue for backward compatibility
                    if with_edit:
                        edit_events = page.evaluate("""
                            () => {
                                const events = window.__canvasEditEvents || [];
                                window.__canvasEditEvents = [];
                                return events;
                            }
                        """)

                        for event in edit_events:
                            # Avoid duplicates from bus
                            if not any(
                                e.get("timestamp") == event.get("timestamp")
                                for e in all_edit_events
                            ):
                                all_edit_events.append(event)
                                print(json.dumps(event))
                                sys.stdout.flush()

                    time.sleep(0.1)

                except Exception:
                    # Page likely closed
                    break

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
                before_screenshot_base64=before_screenshot_base64,
            )

            # Emit session end
            end_event = {
                "schemaVersion": "1.0",
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
            print(json.dumps(end_event))
            sys.stdout.flush()

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
            print(
                json.dumps(
                    {
                        "schemaVersion": "1.0",
                        "sessionId": session_id,
                        "type": "session.error",
                        "source": "picker",
                        "timestamp": get_timestamp(),
                        "payload": {"error": str(e)},
                    }
                ),
                file=sys.stderr,
            )
            sys.stderr.flush()
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
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        try:
            page.goto(url, wait_until="networkidle", timeout=30000)

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
