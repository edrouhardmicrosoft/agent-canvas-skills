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
captures selection info and optionally takes a screenshot via agent-eyes.

Usage:
    uv run agent_canvas.py pick <url> [--with-eyes] [--with-edit] [--output PATH]
    uv run agent_canvas.py watch <url> [--interval SECONDS]
"""

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from playwright.sync_api import sync_playwright, Page


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

    try:
        # Call the script's get-js command via uv run to get the JS string
        # This ensures PEP 723 dependencies are available
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


PICKER_OVERLAY_JS = """
(() => {
    if (window.__agentCanvasActive) return;
    window.__agentCanvasActive = true;
    
    // Event queue for streaming selections
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
    
    function getSelector(el) {
        if (el.id) return `#${el.id}`;
        if (el.className && typeof el.className === 'string') {
            const classes = el.className.trim().split(/\\s+/).filter(c => c && !c.startsWith('__'));
            if (classes.length) return `${el.tagName.toLowerCase()}.${classes.join('.')}`;
        }
        return el.tagName.toLowerCase();
    }
    
    function getElementInfo(el) {
        const rect = el.getBoundingClientRect();
        const styles = window.getComputedStyle(el);
        return {
            tag: el.tagName.toLowerCase(),
            id: el.id || null,
            className: el.className || null,
            selector: getSelector(el),
            text: el.textContent?.trim().slice(0, 100) || null,
            boundingBox: {
                x: Math.round(rect.x),
                y: Math.round(rect.y),
                width: Math.round(rect.width),
                height: Math.round(rect.height)
            },
            styles: {
                backgroundColor: styles.backgroundColor,
                color: styles.color,
                fontSize: styles.fontSize,
                display: styles.display,
                position: styles.position
            }
        };
    }
    
    function updateOverlay(el) {
        if (!el || el.id?.startsWith('__agent_canvas') || el.id?.startsWith('__canvas_edit')) {
            overlay.style.display = 'none';
            label.style.display = 'none';
            return;
        }
        
        const rect = el.getBoundingClientRect();
        overlay.style.display = 'block';
        overlay.style.top = rect.top + 'px';
        overlay.style.left = rect.left + 'px';
        overlay.style.width = rect.width + 'px';
        overlay.style.height = rect.height + 'px';
        
        label.style.display = 'block';
        label.style.top = (rect.top - 28) + 'px';
        label.style.left = rect.left + 'px';
        label.textContent = getSelector(el);
        
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
        
        const info = getElementInfo(e.target);
        selectionCount++;
        
        // Push to event queue
        window.__agentCanvasEvents.push({
            event: 'selection',
            index: selectionCount,
            timestamp: new Date().toISOString(),
            element: info
        });
        
        // Visual feedback - flash green then back to blue
        overlay.style.borderColor = '#34C759';
        overlay.style.background = 'rgba(52, 199, 89, 0.3)';
        label.style.background = '#34C759';
        counter.textContent = `Selections: ${selectionCount}`;
        counter.style.background = '#34C759';
        
        setTimeout(() => {
            overlay.style.borderColor = '#007AFF';
            overlay.style.background = 'rgba(0, 122, 255, 0.1)';
            label.style.background = '#007AFF';
            counter.style.background = '#007AFF';
        }, 300);
    }, true);
})();
"""


def get_timestamp() -> str:
    return datetime.utcnow().strftime("%Y-%m-%dT%H-%M-%S-%f")[:-3] + "Z"


def run_agent_eyes(
    url: str, selector: Optional[str] = None, command: str = "describe"
) -> dict:
    """Call agent-eyes script for visual context."""
    skill_dir = Path(__file__).parent.parent.parent / "agent-eyes" / "scripts"
    script_path = skill_dir / "agent_eyes.py"

    if not script_path.exists():
        return {"ok": False, "error": "agent-eyes skill not found"}

    cmd = ["uv", "run", str(script_path), command, url]
    if selector:
        cmd.extend(["--selector", selector])

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return json.loads(result.stdout)
    except Exception as e:
        return {"ok": False, "error": str(e)}


def pick_element(
    url: str,
    with_eyes: bool = False,
    with_edit: bool = False,
    output_path: Optional[str] = None,
    stream: bool = False,
) -> dict:
    """Launch browser with element picker, stream selection events until window closes."""

    all_selections = []
    all_edit_events = []

    with sync_playwright() as p:
        # Launch visible browser for interaction
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        try:
            page.goto(url, wait_until="networkidle", timeout=30000)

            # Inject picker overlay
            page.evaluate(PICKER_OVERLAY_JS)

            # Inject edit panel if requested
            if with_edit:
                edit_js = get_canvas_edit_js()
                if edit_js:
                    page.evaluate(edit_js)

            # Emit session start
            start_event = {
                "event": "session_started",
                "url": url,
                "timestamp": get_timestamp(),
                "features": {
                    "picker": True,
                    "eyes": with_eyes,
                    "edit": with_edit and get_canvas_edit_js() is not None,
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

                    # Drain selection event queue
                    events = page.evaluate("""
                        () => {
                            const events = window.__agentCanvasEvents || [];
                            window.__agentCanvasEvents = [];
                            return events;
                        }
                    """)

                    for event in events:
                        all_selections.append(event)

                        # Enrich with agent-eyes if requested
                        if with_eyes and event.get("element", {}).get("selector"):
                            selector = event["element"]["selector"]
                            eyes_result = run_agent_eyes(url, selector, "describe")
                            if eyes_result.get("ok"):
                                event["eyes"] = eyes_result

                            screenshot_result = run_agent_eyes(
                                url, selector, "screenshot"
                            )
                            if screenshot_result.get("ok"):
                                event["screenshot"] = screenshot_result

                        # Stream event to stdout
                        print(json.dumps(event))
                        sys.stdout.flush()

                    # Drain edit event queue if edit panel is active
                    if with_edit:
                        edit_events = page.evaluate("""
                            () => {
                                const events = window.__canvasEditEvents || [];
                                window.__canvasEditEvents = [];
                                return events;
                            }
                        """)

                        for event in edit_events:
                            all_edit_events.append(event)
                            print(json.dumps(event))
                            sys.stdout.flush()

                    time.sleep(0.1)

                except Exception:
                    # Page likely closed
                    break

            # Emit session end
            end_event = {
                "event": "session_ended",
                "timestamp": get_timestamp(),
                "total_selections": len(all_selections),
                "total_edits": len(all_edit_events),
            }
            print(json.dumps(end_event))
            sys.stdout.flush()

            result = {
                "ok": True,
                "url": url,
                "selections": all_selections,
                "edits": all_edit_events,
                "total_selections": len(all_selections),
                "total_edits": len(all_edit_events),
            }

            # Save to file if requested
            if output_path:
                Path(output_path).parent.mkdir(parents=True, exist_ok=True)
                Path(output_path).write_text(json.dumps(result, indent=2))

            return result

        except Exception as e:
            error_result = {"ok": False, "error": str(e)}
            print(json.dumps({"event": "error", "error": str(e)}), file=sys.stderr)
            sys.stderr.flush()
            return error_result
        finally:
            browser.close()


def watch_page(
    url: str,
    interval: float = 2.0,
    output_dir: Optional[str] = None,
) -> None:
    """Watch page for changes, reporting via agent-eyes."""

    output_path = Path(output_dir or ".canvas/watch")
    output_path.mkdir(parents=True, exist_ok=True)

    print(json.dumps({"event": "watch_started", "url": url, "interval": interval}))
    sys.stdout.flush()

    last_snapshot = None
    iteration = 0

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        try:
            page.goto(url, wait_until="networkidle", timeout=30000)

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

                    # Take screenshot via agent-eyes
                    screenshot_result = run_agent_eyes(url)

                    change_event = {
                        "event": "change_detected",
                        "iteration": iteration,
                        "timestamp": timestamp,
                        "screenshot": screenshot_result.get("path")
                        if screenshot_result.get("ok")
                        else None,
                    }

                    print(json.dumps(change_event))
                    sys.stdout.flush()

                    last_snapshot = snapshot

                time.sleep(interval)

        except KeyboardInterrupt:
            print(json.dumps({"event": "watch_stopped"}))
        except Exception as e:
            print(json.dumps({"event": "error", "error": str(e)}))
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
        help="Get visual context from agent-eyes after selection",
    )
    pick_parser.add_argument(
        "--with-edit",
        action="store_true",
        help="Load canvas-edit panel for live style editing",
    )
    pick_parser.add_argument("--output", "-o", help="Save result to file")

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
