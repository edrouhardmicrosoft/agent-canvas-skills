#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "playwright",
#     "axe-playwright-python",
# ]
# ///
"""
Agent Eyes - Visual context analyzer for AI agents.

A CLI tool that provides visual context about web pages including:
- Screenshots (full page or element-specific)
- Accessibility scans (using axe-core)
- DOM snapshots
- Element descriptions (computed styles, bounding box, text content)

Usage:
    uv run agent_eyes.py screenshot <url> [--selector SELECTOR] [--output PATH]
    uv run agent_eyes.py a11y <url> [--selector SELECTOR] [--level AA|AAA]
    uv run agent_eyes.py dom <url> [--selector SELECTOR] [--depth DEPTH]
    uv run agent_eyes.py describe <url> --selector SELECTOR
    uv run agent_eyes.py context <url> [--selector SELECTOR] [--format json|text]
"""

import argparse
import base64
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from playwright.sync_api import sync_playwright, Page, Locator


def get_timestamp() -> str:
    """Generate ISO timestamp for filenames."""
    return datetime.utcnow().strftime("%Y-%m-%dT%H-%M-%S-%f")[:-3] + "Z"


def take_screenshot(
    page: Page,
    selector: Optional[str] = None,
    output_path: Optional[str] = None,
    as_base64: bool = False,
) -> dict:
    """Take a screenshot of the page or a specific element."""
    if selector:
        element = page.locator(selector)
        if element.count() == 0:
            return {"ok": False, "error": f"Selector '{selector}' not found"}
        screenshot_bytes = element.first.screenshot()
    else:
        screenshot_bytes = page.screenshot(full_page=True)

    if output_path:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_path).write_bytes(screenshot_bytes)
        return {"ok": True, "path": output_path, "size": len(screenshot_bytes)}
    elif as_base64:
        return {
            "ok": True,
            "base64": base64.b64encode(screenshot_bytes).decode("utf-8"),
            "size": len(screenshot_bytes),
        }
    else:
        # Default: save to .canvas/screenshots/
        screenshots_dir = Path(".canvas/screenshots")
        screenshots_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{get_timestamp()}.png"
        filepath = screenshots_dir / filename
        filepath.write_bytes(screenshot_bytes)
        return {"ok": True, "path": str(filepath), "size": len(screenshot_bytes)}


def run_a11y_scan(
    page: Page, selector: Optional[str] = None, level: str = "AA"
) -> dict:
    """Run accessibility scan using axe-core."""
    try:
        from axe_playwright_python.sync_playwright import Axe

        axe = Axe()

        if selector:
            # Scope the scan to a specific element
            results = axe.run(page, context=selector)
        else:
            results = axe.run(page)

        # Filter by WCAG level
        violations = results.get("violations", [])
        if level == "AAA":
            # Include all violations
            pass
        else:
            # Filter to AA and below
            violations = [
                v
                for v in violations
                if any(
                    tag in v.get("tags", [])
                    for tag in ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]
                )
            ]

        return {
            "ok": True,
            "violations": violations,
            "violationCount": len(violations),
            "passes": len(results.get("passes", [])),
            "incomplete": len(results.get("incomplete", [])),
        }
    except ImportError:
        return {
            "ok": False,
            "error": "axe-playwright-python not installed. Run: pip install axe-playwright-python",
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


def get_dom_snapshot(
    page: Page, selector: Optional[str] = None, depth: int = 5
) -> dict:
    """Get a simplified DOM snapshot."""
    script = """
    (args) => {
        const { selector, maxDepth } = args;
        
        function serializeNode(node, depth) {
            if (depth > maxDepth) return { truncated: true };
            if (!node) return null;
            
            if (node.nodeType === Node.TEXT_NODE) {
                const text = node.textContent.trim();
                return text ? { type: 'text', content: text.slice(0, 100) } : null;
            }
            
            if (node.nodeType !== Node.ELEMENT_NODE) return null;
            
            const el = node;
            const result = {
                tag: el.tagName.toLowerCase(),
            };
            
            // Include important attributes
            if (el.id) result.id = el.id;
            if (el.className && typeof el.className === 'string') {
                result.class = el.className.split(' ').filter(c => c).slice(0, 5).join(' ');
            }
            if (el.getAttribute('role')) result.role = el.getAttribute('role');
            if (el.getAttribute('aria-label')) result.ariaLabel = el.getAttribute('aria-label');
            if (el.tagName === 'A' && el.href) result.href = el.href;
            if (el.tagName === 'IMG' && el.src) result.src = el.src.slice(0, 100);
            if (el.tagName === 'IMG' && el.alt) result.alt = el.alt;
            if (el.tagName === 'INPUT') {
                result.type = el.type;
                result.name = el.name;
                result.value = el.value?.slice(0, 50);
            }
            
            // Serialize children
            const children = [];
            for (const child of el.childNodes) {
                const serialized = serializeNode(child, depth + 1);
                if (serialized) children.push(serialized);
            }
            if (children.length > 0) result.children = children.slice(0, 20);
            
            return result;
        }
        
        const root = selector ? document.querySelector(selector) : document.body;
        if (!root) return { ok: false, error: `Selector '${selector}' not found` };
        
        return { ok: true, dom: serializeNode(root, 0) };
    }
    """
    result = page.evaluate(script, {"selector": selector, "maxDepth": depth})
    return result


def describe_element(page: Page, selector: str) -> dict:
    """Get detailed description of an element including styles and bounding box."""
    script = """
    (selector) => {
        const el = document.querySelector(selector);
        if (!el) return { ok: false, error: `Selector '${selector}' not found` };
        
        const rect = el.getBoundingClientRect();
        const styles = window.getComputedStyle(el);
        
        return {
            ok: true,
            tag: el.tagName.toLowerCase(),
            id: el.id || null,
            className: el.className || null,
            textContent: el.textContent?.trim().slice(0, 200) || null,
            boundingBox: {
                x: Math.round(rect.x),
                y: Math.round(rect.y),
                width: Math.round(rect.width),
                height: Math.round(rect.height),
            },
            styles: {
                display: styles.display,
                position: styles.position,
                color: styles.color,
                backgroundColor: styles.backgroundColor,
                fontSize: styles.fontSize,
                fontWeight: styles.fontWeight,
                margin: styles.margin,
                padding: styles.padding,
                border: styles.border,
                visibility: styles.visibility,
                opacity: styles.opacity,
            },
            attributes: {
                role: el.getAttribute('role'),
                ariaLabel: el.getAttribute('aria-label'),
                ariaDescribedby: el.getAttribute('aria-describedby'),
                tabindex: el.getAttribute('tabindex'),
                href: el.getAttribute('href'),
                src: el.getAttribute('src'),
                alt: el.getAttribute('alt'),
            },
            isVisible: rect.width > 0 && rect.height > 0 && styles.visibility !== 'hidden' && styles.display !== 'none',
        };
    }
    """
    return page.evaluate(script, selector)


def get_full_context(
    page: Page,
    selector: Optional[str] = None,
    include_screenshot: bool = True,
    format_type: str = "json",
) -> dict:
    """Get comprehensive context including screenshot, a11y, DOM, and description."""
    result = {
        "ok": True,
        "url": page.url,
        "title": page.title(),
        "timestamp": get_timestamp(),
    }

    # DOM snapshot
    dom_result = get_dom_snapshot(page, selector)
    if dom_result.get("ok"):
        result["dom"] = dom_result.get("dom")

    # A11y scan
    a11y_result = run_a11y_scan(page, selector)
    if a11y_result.get("ok"):
        result["a11y"] = {
            "violations": a11y_result.get("violations", [])[:10],  # Limit for context
            "violationCount": a11y_result.get("violationCount"),
        }

    # Element description (if selector provided)
    if selector:
        desc_result = describe_element(page, selector)
        if desc_result.get("ok"):
            result["element"] = desc_result

    # Screenshot (as base64 for inline context)
    if include_screenshot:
        screenshot_result = take_screenshot(page, selector, as_base64=True)
        if screenshot_result.get("ok"):
            result["screenshot"] = {
                "base64": screenshot_result.get("base64"),
                "size": screenshot_result.get("size"),
            }

    return result


def main():
    parser = argparse.ArgumentParser(
        description="Agent Eyes - Visual context analyzer for AI agents",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Screenshot command
    screenshot_parser = subparsers.add_parser("screenshot", help="Take a screenshot")
    screenshot_parser.add_argument("url", help="URL to capture")
    screenshot_parser.add_argument(
        "--selector", "-s", help="CSS selector for element screenshot"
    )
    screenshot_parser.add_argument("--output", "-o", help="Output file path")
    screenshot_parser.add_argument(
        "--base64", action="store_true", help="Output as base64"
    )

    # A11y command
    a11y_parser = subparsers.add_parser("a11y", help="Run accessibility scan")
    a11y_parser.add_argument("url", help="URL to scan")
    a11y_parser.add_argument("--selector", "-s", help="CSS selector to scope the scan")
    a11y_parser.add_argument(
        "--level", choices=["AA", "AAA"], default="AA", help="WCAG level"
    )

    # DOM command
    dom_parser = subparsers.add_parser("dom", help="Get DOM snapshot")
    dom_parser.add_argument("url", help="URL to analyze")
    dom_parser.add_argument("--selector", "-s", help="CSS selector for subtree")
    dom_parser.add_argument(
        "--depth", "-d", type=int, default=5, help="Max depth to traverse"
    )

    # Describe command
    describe_parser = subparsers.add_parser("describe", help="Describe an element")
    describe_parser.add_argument("url", help="URL to analyze")
    describe_parser.add_argument(
        "--selector", "-s", required=True, help="CSS selector (required)"
    )

    # Context command
    context_parser = subparsers.add_parser("context", help="Get full context bundle")
    context_parser.add_argument("url", help="URL to analyze")
    context_parser.add_argument("--selector", "-s", help="CSS selector for focus")
    context_parser.add_argument(
        "--format", "-f", choices=["json", "text"], default="json"
    )
    context_parser.add_argument(
        "--no-screenshot", action="store_true", help="Exclude screenshot"
    )

    args = parser.parse_args()

    # Run with Playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        try:
            # Navigate to URL
            page.goto(args.url, wait_until="networkidle", timeout=30000)

            # Execute command
            if args.command == "screenshot":
                result = take_screenshot(
                    page,
                    selector=args.selector,
                    output_path=args.output,
                    as_base64=args.base64,
                )
            elif args.command == "a11y":
                result = run_a11y_scan(page, selector=args.selector, level=args.level)
            elif args.command == "dom":
                result = get_dom_snapshot(
                    page, selector=args.selector, depth=args.depth
                )
            elif args.command == "describe":
                result = describe_element(page, selector=args.selector)
            elif args.command == "context":
                result = get_full_context(
                    page,
                    selector=args.selector,
                    include_screenshot=not args.no_screenshot,
                    format_type=args.format,
                )
            else:
                result = {"ok": False, "error": f"Unknown command: {args.command}"}

            # Output
            print(json.dumps(result, indent=2))
            sys.exit(0 if result.get("ok") else 1)

        except Exception as e:
            print(json.dumps({"ok": False, "error": str(e)}), file=sys.stderr)
            sys.exit(1)
        finally:
            browser.close()


if __name__ == "__main__":
    main()
