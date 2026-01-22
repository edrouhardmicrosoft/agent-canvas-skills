#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "playwright",
#     "pyyaml",
#     "pillow",
# ]
# ///
"""
Design Review - Spec-driven design quality assurance.

Reviews web pages against design specs, generates annotated screenshots,
and creates actionable task lists.

CLI Usage:
    uv run design_review.py review <url> [--spec SPEC] [--selector SELECTOR]
    uv run design_review.py interactive <url>
    uv run design_review.py compare <url> --reference <image>
    uv run design_review.py specs --list | --validate <spec> | --show <spec>
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from playwright.sync_api import Page

SCRIPT_DIR = Path(__file__).parent
SPECS_DIR = SCRIPT_DIR.parent / "specs"
IMGS_DIR = SCRIPT_DIR.parent / "imgs"
REVIEWS_DIR = Path(".canvas") / "reviews"


def get_timestamp() -> str:
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def generate_session_id() -> str:
    ts = datetime.utcnow().strftime("%Y%m%d%H%M%S%f")[:-3]
    return f"review_{ts}"


def ensure_reviews_dir(session_id: str) -> Path:
    session_dir = REVIEWS_DIR / session_id
    session_dir.mkdir(parents=True, exist_ok=True)
    return session_dir


def json_output(data: dict) -> None:
    print(json.dumps(data, indent=2))


def error_output(message: str) -> None:
    json_output({"ok": False, "error": message})


def run_accessibility_scan(page: "Page") -> dict[str, Any]:
    """Run axe-core accessibility scan on the page."""
    try:
        from axe_playwright_python.sync_playwright import Axe

        axe = Axe()
        results = axe.run(page)
        return {
            "violations": results.get("violations", []),
            "passes": len(results.get("passes", [])),
            "incomplete": len(results.get("incomplete", [])),
        }
    except ImportError:
        return {
            "violations": [],
            "passes": 0,
            "incomplete": 0,
            "error": "axe-playwright-python not installed",
        }


def analyze_element(page: "Page", selector: str) -> dict[str, Any]:
    """Analyze a specific element for design compliance."""
    try:
        element = page.query_selector(selector)
        if not element:
            return {"error": f"Element not found: {selector}"}

        box = element.bounding_box()
        styles = page.evaluate(
            """(selector) => {
            const el = document.querySelector(selector);
            if (!el) return null;
            const styles = window.getComputedStyle(el);
            return {
                color: styles.color,
                backgroundColor: styles.backgroundColor,
                fontSize: styles.fontSize,
                fontWeight: styles.fontWeight,
                fontFamily: styles.fontFamily,
                padding: styles.padding,
                margin: styles.margin,
                borderRadius: styles.borderRadius,
                display: styles.display,
                position: styles.position
            };
        }""",
            selector,
        )

        return {
            "selector": selector,
            "boundingBox": box,
            "styles": styles,
            "isVisible": element.is_visible(),
        }
    except Exception as e:
        return {"error": str(e)}


def check_color_contrast(
    color: str, background: str, minimum_ratio: float = 4.5
) -> dict[str, Any]:
    """Check if color contrast meets WCAG requirements."""

    def parse_rgb(color_str: str) -> Optional[tuple[int, int, int]]:
        import re

        match = re.match(r"rgba?\((\d+),\s*(\d+),\s*(\d+)", color_str)
        if match:
            return int(match.group(1)), int(match.group(2)), int(match.group(3))
        return None

    def luminance(r: int, g: int, b: int) -> float:
        def channel(c: int) -> float:
            c_norm = c / 255
            return (
                c_norm / 12.92
                if c_norm <= 0.03928
                else ((c_norm + 0.055) / 1.055) ** 2.4
            )

        return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)

    fg = parse_rgb(color)
    bg = parse_rgb(background)

    if not fg or not bg:
        return {"pass": True, "ratio": None, "note": "Could not parse colors"}

    l1 = luminance(*fg)
    l2 = luminance(*bg)
    ratio = (max(l1, l2) + 0.05) / (min(l1, l2) + 0.05)

    return {
        "pass": ratio >= minimum_ratio,
        "ratio": round(ratio, 2),
        "minimum": minimum_ratio,
        "foreground": color,
        "background": background,
    }


def run_spec_checks(
    page: "Page", spec: "DesignSpec", selector: Optional[str] = None
) -> list[dict]:
    """Run all spec checks against the page."""
    issues: list[dict] = []
    issue_id = 0

    a11y_results = run_accessibility_scan(page)

    for pillar in spec.pillars:
        for check in pillar.checks:
            result = None

            if check.id == "accessibility-grade":
                violation_count = len(a11y_results.get("violations", []))
                min_grade = check.config.get("minimum_grade", "C")
                grade_thresholds = {"A": 0, "B": 2, "C": 5, "D": 10}
                threshold = grade_thresholds.get(min_grade, 5)

                if violation_count > threshold:
                    issue_id += 1
                    issues.append(
                        {
                            "id": issue_id,
                            "checkId": check.id,
                            "pillar": pillar.name,
                            "severity": check.severity,
                            "description": f"Found {violation_count} accessibility violations (max {threshold} for grade {min_grade})",
                            "details": a11y_results.get("violations", [])[:5],
                        }
                    )

            elif check.id == "color-contrast":
                if selector:
                    element_data = analyze_element(page, selector)
                    if "styles" in element_data:
                        styles = element_data["styles"]
                        contrast = check_color_contrast(
                            styles.get("color", ""),
                            styles.get("backgroundColor", ""),
                            check.config.get("minimum_ratio", 4.5),
                        )
                        if not contrast["pass"]:
                            issue_id += 1
                            issues.append(
                                {
                                    "id": issue_id,
                                    "checkId": check.id,
                                    "pillar": pillar.name,
                                    "severity": check.severity,
                                    "element": selector,
                                    "description": f"Contrast ratio {contrast['ratio']}:1 (minimum {contrast['minimum']}:1)",
                                    "recommendation": "Increase contrast by darkening text or lightening background",
                                }
                            )

            elif check.id == "keyboard-navigation":
                for violation in a11y_results.get("violations", []):
                    if violation.get("id") in ["focus-order-semantics", "tabindex"]:
                        issue_id += 1
                        issues.append(
                            {
                                "id": issue_id,
                                "checkId": check.id,
                                "pillar": pillar.name,
                                "severity": check.severity,
                                "description": violation.get(
                                    "description", "Keyboard navigation issue"
                                ),
                                "nodes": [
                                    n.get("html", "")
                                    for n in violation.get("nodes", [])[:3]
                                ],
                            }
                        )

            elif check.id == "focus-indicators":
                for violation in a11y_results.get("violations", []):
                    if "focus" in violation.get("id", "").lower():
                        issue_id += 1
                        issues.append(
                            {
                                "id": issue_id,
                                "checkId": check.id,
                                "pillar": pillar.name,
                                "severity": check.severity,
                                "description": violation.get(
                                    "description", "Focus indicator issue"
                                ),
                                "nodes": [
                                    n.get("html", "")
                                    for n in violation.get("nodes", [])[:3]
                                ],
                            }
                        )

    return issues


def cmd_review(args: argparse.Namespace) -> None:
    """Review a page against design specs."""
    from spec_loader import load_spec, resolve_spec

    from playwright.sync_api import sync_playwright

    project_root = Path.cwd()
    spec_path = resolve_spec(args.spec, project_root)
    try:
        spec = load_spec(spec_path, SPECS_DIR)
    except FileNotFoundError:
        error_output(f"Spec not found: {spec_path}")
        sys.exit(1)

    session_id = generate_session_id()
    session_dir = ensure_reviews_dir(session_id)

    # Initialize session event log
    session_events: list[dict] = []
    session_start = get_timestamp()

    def log_event(event_type: str, data: dict) -> None:
        session_events.append(
            {
                "timestamp": get_timestamp(),
                "type": event_type,
                "data": data,
            }
        )

    log_event(
        "session_start",
        {
            "sessionId": session_id,
            "url": args.url,
            "spec": str(spec_path),
            "selector": args.selector,
            "annotate": args.annotate,
            "generateTasks": args.generate_tasks,
        },
    )

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 720})

        log_event("browser_launched", {"viewport": {"width": 1280, "height": 720}})

        try:
            page.goto(args.url, wait_until="networkidle")
            log_event("page_loaded", {"url": args.url})
        except Exception as e:
            log_event("page_load_error", {"error": str(e)})
            error_output(f"Failed to load URL: {e}")
            browser.close()
            sys.exit(1)

        # Take original screenshot
        screenshot_path = session_dir / "screenshot.png"
        page.screenshot(path=str(screenshot_path), full_page=True)
        log_event("screenshot_captured", {"path": str(screenshot_path)})

        # Run spec checks
        issues = run_spec_checks(page, spec, args.selector)
        log_event(
            "spec_checks_completed",
            {
                "checkCount": len(spec.get_all_checks()),
                "issueCount": len(issues),
            },
        )

        browser.close()
        log_event("browser_closed", {})

    # Calculate summary
    summary = {"blocking": 0, "major": 0, "minor": 0}
    for issue in issues:
        severity = issue.get("severity", "minor")
        if severity in summary:
            summary[severity] += 1

    # Build result object
    result = {
        "ok": True,
        "url": args.url,
        "spec": spec.name,
        "specPath": str(spec_path),
        "sessionId": session_id,
        "summary": summary,
        "issues": issues,
        "artifacts": {
            "screenshot": str(screenshot_path),
            "sessionDir": str(session_dir),
        },
    }

    # Generate annotated screenshot if requested
    annotated_path: Optional[Path] = None
    if args.annotate and issues:
        from annotator import annotate_screenshot

        annotated_path = session_dir / "annotated.png"
        annotate_result = annotate_screenshot(
            screenshot_path=screenshot_path,
            issues=issues,
            output_path=annotated_path,
            include_legend=True,
        )

        if annotate_result.get("ok"):
            result["artifacts"]["annotated"] = str(annotated_path)
            log_event(
                "annotated_screenshot_created",
                {
                    "path": str(annotated_path),
                    "annotatedIssues": annotate_result.get("annotatedIssues", []),
                },
            )
        else:
            log_event("annotate_error", {"error": annotate_result.get("error")})

    # Generate tasks file if requested
    if args.generate_tasks and issues:
        tasks_path = Path("DESIGN-REVIEW-TASKS.md")
        generate_tasks_file(result, tasks_path, annotated_path)
        result["artifacts"]["tasks"] = str(tasks_path)
        log_event("tasks_file_generated", {"path": str(tasks_path)})

    # Save report.json (structured issue data)
    report_file = session_dir / "report.json"
    report_file.write_text(json.dumps(result, indent=2))
    log_event("report_saved", {"path": str(report_file)})

    # Save session.json (full event log + metadata)
    session_data = {
        "sessionId": session_id,
        "startTime": session_start,
        "endTime": get_timestamp(),
        "url": args.url,
        "spec": {
            "name": spec.name,
            "path": str(spec_path),
            "pillars": len(spec.pillars),
            "checks": len(spec.get_all_checks()),
        },
        "options": {
            "selector": args.selector,
            "annotate": args.annotate,
            "generateTasks": args.generate_tasks,
        },
        "summary": summary,
        "events": session_events,
    }
    session_file = session_dir / "session.json"
    session_file.write_text(json.dumps(session_data, indent=2))

    json_output(result)


def generate_tasks_file(
    result: dict, output_path: Path, annotated_path: Optional[Path] = None
) -> None:
    """Generate DESIGN-REVIEW-TASKS.md from review results.

    Enhanced version with:
    - Annotated screenshot reference
    - Better formatting with issue numbers matching visual annotations
    - Source file location hints (when detectable from element selectors)
    - Suggested fixes with code examples where applicable
    """
    severity_icons = {
        "blocking": "🔴",
        "major": "🟠",
        "minor": "🟡",
    }
    severity_labels = {
        "blocking": "Blocking",
        "major": "Major",
        "minor": "Minor",
    }

    lines = [
        "# Design Review Tasks",
        "",
        f"> **Generated**: {get_timestamp()}  ",
        f"> **URL**: {result['url']}  ",
        f"> **Spec**: {result['spec']}  ",
        f"> **Session**: `{result['sessionId']}`",
        "",
    ]

    # Add annotated screenshot reference if available
    if annotated_path and annotated_path.exists():
        lines.extend(
            [
                "## 📸 Annotated Screenshot",
                "",
                f"![Annotated Screenshot]({annotated_path})",
                "",
                "*Issue numbers in the screenshot correspond to the issues below.*",
                "",
            ]
        )

    # Summary section
    lines.extend(
        [
            "## Summary",
            "",
            "| Severity | Count |",
            "|----------|-------|",
            f"| {severity_icons['blocking']} Blocking | {result['summary']['blocking']} |",
            f"| {severity_icons['major']} Major | {result['summary']['major']} |",
            f"| {severity_icons['minor']} Minor | {result['summary']['minor']} |",
            "",
        ]
    )

    severity_order = ["blocking", "major", "minor"]

    for severity in severity_order:
        severity_issues = [i for i in result["issues"] if i.get("severity") == severity]
        if not severity_issues:
            continue

        icon = severity_icons[severity]
        label = severity_labels[severity]
        lines.append(f"## {icon} {label} Issues")
        lines.append("")

        for issue in severity_issues:
            issue_id = issue.get("id", "?")
            check_id = issue.get("checkId", "unknown")
            pillar = issue.get("pillar", "")
            description = issue.get("description", "")
            element = issue.get("element", "")
            recommendation = issue.get("recommendation", "")
            nodes = issue.get("nodes", [])
            details = issue.get("details", [])

            # Issue header with circled number for visual reference
            circled_num = get_circled_number(issue_id)
            lines.append(f"### {circled_num} Issue #{issue_id}: {check_id}")
            lines.append("")

            # Metadata table for clean formatting
            lines.append("| Property | Value |")
            lines.append("|----------|-------|")
            lines.append(f"| **Pillar** | {pillar} |")
            lines.append(f"| **Severity** | {icon} {severity.capitalize()} |")
            if element:
                lines.append(f"| **Element** | `{element}` |")

            # Detect potential source file from selector
            source_hint = detect_source_file(element)
            if source_hint:
                lines.append(f"| **Likely Source** | `{source_hint}` |")

            lines.append("")

            # Issue description
            lines.append(f"**Issue**: {description}")
            lines.append("")

            # Show affected nodes if available (from axe-core)
            if nodes:
                lines.append("**Affected Elements**:")
                lines.append("```html")
                for node in nodes[:3]:  # Limit to 3
                    lines.append(node)
                lines.append("```")
                lines.append("")

            # Show detailed violations if available
            if details:
                lines.append("<details>")
                lines.append("<summary>View Details</summary>")
                lines.append("")
                for detail in details[:3]:
                    if isinstance(detail, dict):
                        lines.append(
                            f"- **{detail.get('id', 'Unknown')}**: {detail.get('description', '')}"
                        )
                lines.append("")
                lines.append("</details>")
                lines.append("")

            # Recommendation / suggested fix
            if recommendation:
                lines.append(f"**Suggested Fix**: {recommendation}")
                lines.append("")

                # Add code example for common fixes
                code_example = get_fix_code_example(check_id, issue)
                if code_example:
                    lines.append("```tsx")
                    lines.append(code_example)
                    lines.append("```")
                    lines.append("")

            lines.append("---")
            lines.append("")

    # Reference section
    lines.extend(
        [
            "## 📁 Reference",
            "",
            "| Artifact | Path |",
            "|----------|------|",
            f"| Session Directory | `.canvas/reviews/{result['sessionId']}/` |",
            f"| Original Screenshot | `.canvas/reviews/{result['sessionId']}/screenshot.png` |",
        ]
    )

    if annotated_path:
        lines.append(f"| Annotated Screenshot | `{annotated_path}` |")

    lines.extend(
        [
            f"| Full Report (JSON) | `.canvas/reviews/{result['sessionId']}/report.json` |",
            "",
            "---",
            "",
            "*To fix these issues, review each task above and update your code accordingly.*  ",
            "*Re-run the design review after making changes to verify fixes.*",
        ]
    )

    output_path.write_text("\n".join(lines))


def get_circled_number(n: int) -> str:
    """Get circled number character for visual reference."""
    circled = [
        "①",
        "②",
        "③",
        "④",
        "⑤",
        "⑥",
        "⑦",
        "⑧",
        "⑨",
        "⑩",
        "⑪",
        "⑫",
        "⑬",
        "⑭",
        "⑮",
        "⑯",
        "⑰",
        "⑱",
        "⑲",
        "⑳",
    ]
    if isinstance(n, int) and 1 <= n <= len(circled):
        return circled[n - 1]
    return f"({n})"


def detect_source_file(selector: str) -> Optional[str]:
    """Attempt to detect likely source file from element selector.

    Heuristics:
    - data-testid="ComponentName" → components/ComponentName.tsx
    - .className with component-like name → components/ClassName.tsx
    - #id patterns → look for matching component
    """
    if not selector:
        return None

    import re

    # Check for data-testid pattern
    testid_match = re.search(
        r'data-testid[=~*\^$]*["\']?([A-Z][a-zA-Z0-9-]+)', selector
    )
    if testid_match:
        name = testid_match.group(1)
        return f"components/{name}.tsx (inferred from data-testid)"

    # Check for component-like class names (PascalCase or kebab-case with prefix)
    class_match = re.search(r"\.([A-Z][a-zA-Z0-9]+)", selector)
    if class_match:
        name = class_match.group(1)
        return f"components/{name}.tsx (inferred from class name)"

    # Check for common container patterns
    container_patterns = {
        ".hero": "components/Hero.tsx",
        ".header": "components/Header.tsx",
        ".footer": "components/Footer.tsx",
        ".nav": "components/Nav.tsx",
        ".sidebar": "components/Sidebar.tsx",
        ".modal": "components/Modal.tsx",
        ".card": "components/Card.tsx",
        ".button": "components/Button.tsx",
    }

    for pattern, file in container_patterns.items():
        if pattern in selector.lower():
            return f"{file} (inferred from pattern)"

    return None


def get_fix_code_example(check_id: str, issue: dict) -> Optional[str]:
    """Generate code example for common fix patterns."""

    examples = {
        "color-contrast": """// Increase text contrast
// Before: color: #767676 (3.2:1 ratio)
// After: color: #595959 (7.0:1 ratio)
<Text style={{ color: '#595959' }}>Your text here</Text>""",
        "ai-disclaimer": """// Add AI-generated content disclaimer
<MessageBar intent="warning" className="ai-disclaimer">
  AI-generated content may contain inaccuracies
</MessageBar>""",
        "focus-indicators": """// Add visible focus indicator
.interactive-element:focus-visible {
  outline: 2px solid #0078D4;
  outline-offset: 2px;
}""",
        "keyboard-navigation": """// Ensure keyboard accessibility
<button
  tabIndex={0}
  onKeyDown={(e) => e.key === 'Enter' && handleClick()}
>
  Accessible Button
</button>""",
        "single-primary-action": """// Use Button variants for visual hierarchy
<Button appearance="primary">Main Action</Button>
<Button appearance="secondary">Secondary Action</Button>
<Button appearance="subtle">Tertiary Action</Button>""",
        "touch-targets": """// Ensure 44x44px minimum touch target
.touch-target {
  min-width: 44px;
  min-height: 44px;
  padding: 12px;
}""",
        "destructive-confirmation": """// Add confirmation for destructive actions
const handleDelete = () => {
  if (confirm('Are you sure you want to delete this item?')) {
    performDelete();
  }
};""",
    }

    return examples.get(check_id)


def cmd_specs(args: argparse.Namespace) -> None:
    """Manage design specs."""
    from spec_loader import find_project_spec, list_specs, load_spec, resolve_spec

    if args.list:
        specs = list_specs(SPECS_DIR)
        project_spec = find_project_spec(Path.cwd())
        result = {"ok": True, "specs": specs}
        if project_spec:
            result["projectSpec"] = str(project_spec)
        json_output(result)
    elif args.validate:
        project_root = Path.cwd()
        spec_path = resolve_spec(args.validate, project_root)
        try:
            spec = load_spec(spec_path, SPECS_DIR)
            checks = spec.get_all_checks()
            json_output(
                {
                    "ok": True,
                    "valid": True,
                    "name": spec.name,
                    "pillars": len(spec.pillars),
                    "checks": len(checks),
                    "formatType": spec.format_type,
                }
            )
        except Exception as e:
            json_output({"ok": False, "valid": False, "error": str(e)})
    elif args.show:
        project_root = Path.cwd()
        spec_path = resolve_spec(args.show, project_root)
        try:
            spec = load_spec(spec_path, SPECS_DIR)
            json_output({"ok": True, "spec": spec.to_dict()})
        except Exception as e:
            error_output(str(e))
            sys.exit(1)
    else:
        error_output("Specify --list, --validate, or --show")
        sys.exit(1)


def cmd_interactive(args: argparse.Namespace) -> None:
    """Interactive design review mode.

    Launches a browser with a review overlay. User can hover over elements
    to see compliance status, click to see full compliance report, and
    add elements to the review. On browser close, generates annotated
    screenshot and tasks file.
    """
    import time

    from spec_loader import load_spec, resolve_spec

    from playwright.sync_api import sync_playwright

    # Load spec
    project_root = Path.cwd()
    spec_path = resolve_spec(getattr(args, "spec", None), project_root)
    try:
        spec = load_spec(spec_path, SPECS_DIR)
    except FileNotFoundError:
        error_output(f"Spec not found: {spec_path}")
        sys.exit(1)

    session_id = generate_session_id()
    session_dir = ensure_reviews_dir(session_id)
    session_start = get_timestamp()

    # Load overlay JS
    overlay_js_path = SCRIPT_DIR / "review_overlay.js"
    if not overlay_js_path.exists():
        error_output(f"Review overlay not found: {overlay_js_path}")
        sys.exit(1)
    overlay_js = overlay_js_path.read_text()

    # Load shared canvas bus if available
    canvas_bus_js = ""
    shared_path = SCRIPT_DIR.parent.parent / "shared"
    canvas_bus_path = shared_path / "canvas_bus.py"
    if canvas_bus_path.exists():
        # Import canvas_bus to get the JS
        if str(shared_path) not in sys.path:
            sys.path.insert(0, str(shared_path))
        try:
            from canvas_bus import CANVAS_BUS_JS

            canvas_bus_js = CANVAS_BUS_JS
        except ImportError:
            pass

    # Prepare spec data for the overlay
    spec_data = {
        "name": spec.name,
        "checks": [
            {
                "id": check.id,
                "pillar": check.pillar,
                "severity": check.severity,
                "description": check.description,
                "config": check.config,
            }
            for check in spec.get_all_checks()
        ],
    }

    # Session events for logging
    session_events: list[dict] = []

    def log_event(event_type: str, data: dict) -> None:
        session_events.append(
            {
                "timestamp": get_timestamp(),
                "type": event_type,
                "data": data,
            }
        )

    log_event(
        "session_start",
        {
            "sessionId": session_id,
            "url": args.url,
            "spec": str(spec_path),
            "mode": "interactive",
        },
    )

    # Emit session start event
    start_event = {
        "schemaVersion": "1.0",
        "sessionId": session_id,
        "type": "review.session_started",
        "source": "design-review",
        "timestamp": session_start,
        "payload": {
            "url": args.url,
            "spec": spec.name,
            "mode": "interactive",
        },
    }
    print(json.dumps(start_event))
    sys.stdout.flush()

    review_results = None

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page(viewport={"width": 1280, "height": 800})

        log_event("browser_launched", {"viewport": {"width": 1280, "height": 800}})

        try:
            page.goto(args.url, wait_until="networkidle", timeout=30000)
            log_event("page_loaded", {"url": args.url})
        except Exception as e:
            log_event("page_load_error", {"error": str(e)})
            error_output(f"Failed to load URL: {e}")
            browser.close()
            sys.exit(1)

        # Inject canvas bus first if available
        if canvas_bus_js:
            page.evaluate(canvas_bus_js)

        # Inject review overlay
        page.evaluate(overlay_js)

        # Initialize overlay with spec data
        page.evaluate(
            f"window.__designReviewInit && window.__designReviewInit({json.dumps(spec_data)})"
        )

        log_event("overlay_injected", {"spec": spec.name})

        # Poll for events until browser closes
        while True:
            try:
                if page.is_closed():
                    break

                # Drain review events
                events = page.evaluate("""
                    () => {
                        const events = window.__designReviewEvents || [];
                        window.__designReviewEvents = [];
                        return events;
                    }
                """)

                for event in events:
                    log_event("review_event", event)
                    print(json.dumps(event))
                    sys.stdout.flush()

                time.sleep(0.1)

            except Exception:
                # Page likely closed
                break

        # Get final review results before browser closes
        try:
            review_results = page.evaluate(
                "() => window.__designReviewGetResults && window.__designReviewGetResults()"
            )
        except Exception:
            review_results = None

        browser.close()
        log_event("browser_closed", {})

    # Take screenshot after browser closes - need to reopen headless
    screenshot_path = session_dir / "screenshot.png"
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 800})
        try:
            page.goto(args.url, wait_until="networkidle", timeout=30000)
            page.screenshot(path=str(screenshot_path), full_page=True)
            log_event("screenshot_captured", {"path": str(screenshot_path)})
        except Exception as e:
            log_event("screenshot_error", {"error": str(e)})
        finally:
            browser.close()

    # Process review results
    issues: list[dict] = []
    summary = {"blocking": 0, "major": 0, "minor": 0}

    if review_results and review_results.get("issues"):
        issue_id = 0
        for reviewed_item in review_results["issues"]:
            for rule in reviewed_item.get("rules", []):
                issue_id += 1
                severity = rule.get("severity", "minor")
                issues.append(
                    {
                        "id": issue_id,
                        "checkId": rule.get("id", "unknown"),
                        "pillar": "",  # Could be populated from spec lookup
                        "severity": severity,
                        "element": reviewed_item.get("selector", ""),
                        "description": rule.get("message", ""),
                        "recommendation": get_recommendation_for_check(
                            rule.get("id", "")
                        ),
                    }
                )
                if severity in summary:
                    summary[severity] += 1

        # Also add summary counts from overlay if no individual issues
        if not issues and review_results.get("summary"):
            summary = review_results["summary"]

    # Build result
    result = {
        "ok": True,
        "url": args.url,
        "spec": spec.name,
        "specPath": str(spec_path),
        "sessionId": session_id,
        "mode": "interactive",
        "summary": summary,
        "issues": issues,
        "reviewedElements": review_results.get("reviewedElements", [])
        if review_results
        else [],
        "artifacts": {
            "screenshot": str(screenshot_path),
            "sessionDir": str(session_dir),
        },
    }

    # Generate annotated screenshot if there are issues
    annotated_path: Optional[Path] = None
    if issues:
        from annotator import annotate_screenshot

        annotated_path = session_dir / "annotated.png"
        annotate_result = annotate_screenshot(
            screenshot_path=screenshot_path,
            issues=issues,
            output_path=annotated_path,
            include_legend=True,
        )

        if annotate_result.get("ok"):
            result["artifacts"]["annotated"] = str(annotated_path)
            log_event(
                "annotated_screenshot_created",
                {
                    "path": str(annotated_path),
                    "annotatedIssues": annotate_result.get("annotatedIssues", []),
                },
            )

    # Generate tasks file
    if issues:
        tasks_path = Path("DESIGN-REVIEW-TASKS.md")
        generate_tasks_file(result, tasks_path, annotated_path)
        result["artifacts"]["tasks"] = str(tasks_path)
        log_event("tasks_file_generated", {"path": str(tasks_path)})

    # Save report.json
    report_file = session_dir / "report.json"
    report_file.write_text(json.dumps(result, indent=2))
    log_event("report_saved", {"path": str(report_file)})

    # Save session.json
    session_data = {
        "sessionId": session_id,
        "startTime": session_start,
        "endTime": get_timestamp(),
        "url": args.url,
        "mode": "interactive",
        "spec": {
            "name": spec.name,
            "path": str(spec_path),
            "pillars": len(spec.pillars),
            "checks": len(spec.get_all_checks()),
        },
        "summary": summary,
        "reviewedElements": review_results.get("reviewedElements", [])
        if review_results
        else [],
        "events": session_events,
    }
    session_file = session_dir / "session.json"
    session_file.write_text(json.dumps(session_data, indent=2))

    # Emit session end event
    end_event = {
        "schemaVersion": "1.0",
        "sessionId": session_id,
        "type": "review.session_ended",
        "source": "design-review",
        "timestamp": get_timestamp(),
        "payload": {
            "summary": summary,
            "issueCount": len(issues),
            "artifacts": result["artifacts"],
        },
    }
    print(json.dumps(end_event))
    sys.stdout.flush()

    json_output(result)


def get_recommendation_for_check(check_id: str) -> str:
    """Get a recommendation string for a check ID."""
    recommendations = {
        "color-contrast": "Increase contrast by darkening text or lightening background",
        "touch-targets": "Increase the interactive element size to at least 44x44px",
        "focus-indicators": "Add visible focus indicator using outline or box-shadow",
        "alt-text": "Add descriptive alt text that conveys the image content",
        "keyboard-navigation": "Ensure element is focusable and responds to keyboard events",
    }
    return recommendations.get(check_id, "")


def cmd_compare(args: argparse.Namespace) -> None:
    """Compare page against reference image."""
    error_output("Compare mode not yet implemented. Use 'review' command.")
    sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Design Review - Spec-driven design QA"
    )
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    review_parser = subparsers.add_parser(
        "review", help="Review page against design specs"
    )
    review_parser.add_argument("url", help="URL to review")
    review_parser.add_argument("--spec", help="Spec file (default: default.md)")
    review_parser.add_argument("--selector", help="CSS selector for specific element")
    review_parser.add_argument(
        "--annotate", action="store_true", help="Generate annotated screenshot"
    )
    review_parser.add_argument(
        "--generate-tasks", action="store_true", help="Generate DESIGN-REVIEW-TASKS.md"
    )

    interactive_parser = subparsers.add_parser(
        "interactive", help="Interactive review mode"
    )
    interactive_parser.add_argument("url", help="URL to review")
    interactive_parser.add_argument("--spec", help="Spec file (default: default.md)")

    compare_parser = subparsers.add_parser("compare", help="Compare against reference")
    compare_parser.add_argument("url", help="URL to compare")
    compare_parser.add_argument("--reference", help="Reference image path")
    compare_parser.add_argument("--figma", help="Figma file URL")
    compare_parser.add_argument("--frame", help="Figma frame name")

    specs_parser = subparsers.add_parser("specs", help="Manage specs")
    specs_parser.add_argument(
        "--list", action="store_true", help="List available specs"
    )
    specs_parser.add_argument("--validate", help="Validate a spec file")
    specs_parser.add_argument("--show", help="Show spec details")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "review":
        cmd_review(args)
    elif args.command == "interactive":
        cmd_interactive(args)
    elif args.command == "compare":
        cmd_compare(args)
    elif args.command == "specs":
        cmd_specs(args)


if __name__ == "__main__":
    main()


from spec_loader import DesignSpec
