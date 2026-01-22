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
    from spec_loader import get_default_spec_path, load_spec

    from playwright.sync_api import sync_playwright

    spec_path = SPECS_DIR / args.spec if args.spec else get_default_spec_path()
    try:
        spec = load_spec(spec_path, SPECS_DIR)
    except FileNotFoundError:
        error_output(f"Spec not found: {spec_path}")
        sys.exit(1)

    session_id = generate_session_id()
    session_dir = ensure_reviews_dir(session_id)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 720})

        try:
            page.goto(args.url, wait_until="networkidle")
        except Exception as e:
            error_output(f"Failed to load URL: {e}")
            browser.close()
            sys.exit(1)

        screenshot_path = session_dir / "screenshot.png"
        page.screenshot(path=str(screenshot_path), full_page=True)

        issues = run_spec_checks(page, spec, args.selector)

        browser.close()

    summary = {"blocking": 0, "major": 0, "minor": 0}
    for issue in issues:
        severity = issue.get("severity", "minor")
        if severity in summary:
            summary[severity] += 1

    result = {
        "ok": True,
        "url": args.url,
        "spec": spec.name,
        "sessionId": session_id,
        "summary": summary,
        "issues": issues,
        "artifacts": {
            "screenshot": str(screenshot_path),
        },
    }

    if args.generate_tasks and issues:
        tasks_path = Path("DESIGN-REVIEW-TASKS.md")
        generate_tasks_file(result, tasks_path)
        result["artifacts"]["tasks"] = str(tasks_path)

    session_file = session_dir / "report.json"
    session_file.write_text(json.dumps(result, indent=2))

    json_output(result)


def generate_tasks_file(result: dict, output_path: Path) -> None:
    """Generate DESIGN-REVIEW-TASKS.md from review results."""
    lines = [
        "# Design Review Tasks",
        "",
        f"> Generated: {get_timestamp()}",
        f"> URL: {result['url']}",
        f"> Spec: {result['spec']}",
        f"> Session: {result['sessionId']}",
        "",
        "## Summary",
        "",
        "| Severity | Count |",
        "|----------|-------|",
        f"| Blocking | {result['summary']['blocking']} |",
        f"| Major | {result['summary']['major']} |",
        f"| Minor | {result['summary']['minor']} |",
        "",
    ]

    severity_order = ["blocking", "major", "minor"]
    severity_icons = {"blocking": "Blocking", "major": "Major", "minor": "Minor"}

    for severity in severity_order:
        severity_issues = [i for i in result["issues"] if i.get("severity") == severity]
        if not severity_issues:
            continue

        lines.append(f"## {severity_icons[severity]} Issues")
        lines.append("")

        for issue in severity_issues:
            lines.append(f"### {issue['id']}. {issue['checkId']}")
            lines.append(f"- **Pillar**: {issue['pillar']}")
            lines.append(f"- **Severity**: {issue['severity']}")
            if "element" in issue:
                lines.append(f"- **Element**: `{issue['element']}`")
            lines.append(f"- **Issue**: {issue['description']}")
            if "recommendation" in issue:
                lines.append(f"- **Fix**: {issue['recommendation']}")
            lines.append("")

    lines.extend(
        [
            "---",
            "",
            f"*Review session: {result['sessionId']}*",
        ]
    )

    output_path.write_text("\n".join(lines))


def cmd_specs(args: argparse.Namespace) -> None:
    """Manage design specs."""
    from spec_loader import list_specs, load_spec

    if args.list:
        specs = list_specs(SPECS_DIR)
        json_output({"ok": True, "specs": specs})
    elif args.validate:
        spec_path = SPECS_DIR / args.validate
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
                }
            )
        except Exception as e:
            json_output({"ok": False, "valid": False, "error": str(e)})
    elif args.show:
        spec_path = SPECS_DIR / args.show
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
    """Interactive design review mode."""
    error_output("Interactive mode not yet implemented. Use 'review' command.")
    sys.exit(1)


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
