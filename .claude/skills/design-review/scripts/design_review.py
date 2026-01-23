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


class EditableContext:
    """
    Detects if we're in a context where code changes can be applied.

    Checks for:
    1. Local dev server (localhost, 127.0.0.1)
    2. Source files present in the project
    3. Known frameworks (Next.js, Vite, Create React App, etc.)
    4. Git repository (for safe changes)
    """

    def __init__(self, url: str, project_root: Optional[Path] = None):
        self.url = url
        self.project_root = project_root or Path.cwd()
        self._analysis: Optional[dict] = None

    def analyze(self) -> dict:
        """Analyze the context and return detailed information."""
        if self._analysis is not None:
            return self._analysis

        from urllib.parse import urlparse

        parsed = urlparse(self.url)
        hostname = parsed.hostname or ""
        port = parsed.port

        result = {
            "editable": False,
            "reasons": [],
            "framework": None,
            "source_dirs": [],
            "has_git": False,
            "confidence": "low",
        }

        # Check 1: Is this a local dev server?
        is_local = hostname in ["localhost", "127.0.0.1", "0.0.0.0", "::1"]
        common_dev_ports = [3000, 3001, 5173, 5174, 8080, 8000, 4200, 4321]
        is_dev_port = port in common_dev_ports if port else False

        if is_local:
            result["reasons"].append("Local development server detected")
            if is_dev_port:
                result["reasons"].append(f"Common dev port {port}")

        # Check 2: Detect framework
        framework = self._detect_framework()
        if framework:
            result["framework"] = framework
            result["reasons"].append(f"Framework detected: {framework}")

        # Check 3: Find source directories
        source_dirs = self._find_source_dirs()
        result["source_dirs"] = [str(d) for d in source_dirs]
        if source_dirs:
            result["reasons"].append(f"Source directories found: {len(source_dirs)}")

        # Check 4: Git repository
        git_dir = self.project_root / ".git"
        result["has_git"] = git_dir.exists()
        if result["has_git"]:
            result["reasons"].append("Git repository (changes can be tracked)")

        # Determine if editable
        if is_local and (source_dirs or framework):
            result["editable"] = True
            result["confidence"] = (
                "high"
                if (framework and source_dirs and result["has_git"])
                else "medium"
            )
        elif source_dirs and framework:
            result["editable"] = True
            result["confidence"] = "low"
            result["reasons"].append(
                "Warning: Not a local server, changes may not reflect"
            )

        self._analysis = result
        return result

    def _detect_framework(self) -> Optional[str]:
        """Detect the web framework being used."""
        # Check package.json for framework indicators
        package_json = self.project_root / "package.json"
        if package_json.exists():
            try:
                pkg = json.loads(package_json.read_text())
                deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}

                if "next" in deps:
                    return "Next.js"
                elif "vite" in deps:
                    return "Vite"
                elif "react-scripts" in deps:
                    return "Create React App"
                elif "@angular/core" in deps:
                    return "Angular"
                elif "vue" in deps:
                    return "Vue"
                elif "svelte" in deps:
                    return "Svelte"
                elif "astro" in deps:
                    return "Astro"
                elif "nuxt" in deps:
                    return "Nuxt"
                elif "gatsby" in deps:
                    return "Gatsby"
                elif "remix" in deps:
                    return "Remix"
            except (json.JSONDecodeError, IOError):
                pass

        # Check for framework-specific files
        framework_indicators = {
            "next.config.js": "Next.js",
            "next.config.ts": "Next.js",
            "next.config.mjs": "Next.js",
            "vite.config.js": "Vite",
            "vite.config.ts": "Vite",
            "angular.json": "Angular",
            "vue.config.js": "Vue",
            "svelte.config.js": "Svelte",
            "astro.config.mjs": "Astro",
            "nuxt.config.js": "Nuxt",
            "nuxt.config.ts": "Nuxt",
            "gatsby-config.js": "Gatsby",
            "remix.config.js": "Remix",
        }

        for filename, framework in framework_indicators.items():
            if (self.project_root / filename).exists():
                return framework

        return None

    def _find_source_dirs(self) -> list[Path]:
        """Find directories containing source files."""
        potential_dirs = [
            "src",
            "app",
            "pages",
            "components",
            "lib",
            "src/components",
            "app/components",
        ]

        found = []
        for dir_name in potential_dirs:
            dir_path = self.project_root / dir_name
            if dir_path.exists() and dir_path.is_dir():
                # Check if it contains source files
                extensions = [".tsx", ".jsx", ".vue", ".svelte", ".ts", ".js"]
                has_source = any(
                    list(dir_path.rglob(f"*{ext}"))[:1]  # Just check if any exist
                    for ext in extensions
                )
                if has_source:
                    found.append(dir_path)

        return found

    @property
    def is_editable(self) -> bool:
        """Quick check if context is editable."""
        return self.analyze()["editable"]

    def get_summary(self) -> str:
        """Get a human-readable summary of the context."""
        analysis = self.analyze()
        if analysis["editable"]:
            framework = analysis["framework"] or "Unknown"
            return f"Editable ({framework}, {analysis['confidence']} confidence)"
        else:
            return "Read-only (not a local dev environment)"


def generate_todowrite_output(
    issues: list[dict], result: dict, source_mapper: Optional["SourceMapper"] = None
) -> dict:
    """
    Generate output in a format compatible with the todowrite tool.

    Returns a dict with:
    - todos: list of todo items in todowrite format
    - summary: issue counts
    - metadata: session info
    """
    todos = []

    for issue in issues:
        issue_id = issue.get("id", 0)
        check_id = issue.get("checkId", "unknown")
        severity = issue.get("severity", "minor")
        description = issue.get("description", "")
        element = issue.get("element", "")
        pillar = issue.get("pillar", "")
        recommendation = issue.get("recommendation", "")

        # Map severity to priority
        priority_map = {
            "blocking": "high",
            "major": "high",
            "minor": "medium",
        }
        priority = priority_map.get(severity, "medium")

        # Build todo content
        content_parts = [f"[{check_id}] {description}"]
        if element:
            content_parts.append(f"Element: {element}")
        if recommendation:
            content_parts.append(f"Fix: {recommendation}")

        # Get source file mapping
        source_info = None
        if source_mapper and element:
            source_info = source_mapper.find_source_file(element)

        todo = {
            "id": f"design-review-{issue_id}",
            "content": " | ".join(content_parts),
            "status": "pending",
            "priority": priority,
            # Extended metadata for integration
            "_metadata": {
                "checkId": check_id,
                "severity": severity,
                "pillar": pillar,
                "element": element,
                "sourceFile": source_info["path"] if source_info else None,
                "sourceConfidence": source_info["confidence"] if source_info else None,
            },
        }

        todos.append(todo)

    return {
        "ok": True,
        "format": "todowrite",
        "todos": todos,
        "summary": result.get("summary", {}),
        "metadata": {
            "sessionId": result.get("sessionId"),
            "url": result.get("url"),
            "spec": result.get("spec"),
            "timestamp": get_timestamp(),
        },
    }


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


def truncate_issue_for_compact(issue: dict, max_desc_len: int = 100) -> dict:
    """
    Truncate an issue for compact output mode.

    Keeps: id, checkId, severity, element, description (truncated)
    Removes: pillar, details, nodes, recommendation, sourceFile, etc.
    """
    desc = issue.get("description", "")
    if len(desc) > max_desc_len:
        desc = desc[: max_desc_len - 3] + "..."

    return {
        "id": issue.get("id"),
        "checkId": issue.get("checkId"),
        "severity": issue.get("severity"),
        "element": issue.get("element"),
        "description": desc,
    }


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


def extract_element_info(page: "Page", selector: str) -> Optional[dict[str, Any]]:
    """
    Extract element metadata for CSS selector generation.

    Captures:
    - tag: element tag name
    - id: element ID (if any)
    - classes: array of class names
    - parent_chain: array of parent element info (up to 3 levels)
    """
    try:
        element_info = page.evaluate(
            """(selector) => {
            const el = document.querySelector(selector);
            if (!el) return null;
            
            function getElementInfo(element) {
                return {
                    tag: element.tagName.toLowerCase(),
                    id: element.id || null,
                    classes: Array.from(element.classList)
                };
            }
            
            // Get parent chain (up to 3 levels)
            const parentChain = [];
            let parent = el.parentElement;
            let depth = 0;
            while (parent && depth < 3 && parent !== document.body) {
                parentChain.push(getElementInfo(parent));
                parent = parent.parentElement;
                depth++;
            }
            
            return {
                tag: el.tagName.toLowerCase(),
                id: el.id || null,
                classes: Array.from(el.classList),
                parent_chain: parentChain
            };
        }""",
            selector,
        )
        return element_info
    except Exception:
        return None


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
                            # Extract element info for CSS selector generation
                            element_info = extract_element_info(page, selector)
                            issue_dict: dict[str, Any] = {
                                "id": issue_id,
                                "checkId": check.id,
                                "pillar": pillar.name,
                                "severity": check.severity,
                                "element": selector,
                                "description": f"Contrast ratio {contrast['ratio']}:1 (minimum {contrast['minimum']}:1)",
                                "recommendation": "Increase contrast by darkening text or lightening background",
                                "boundingBox": element_data.get("boundingBox"),
                            }
                            if element_info:
                                issue_dict["elementInfo"] = element_info
                            issues.append(issue_dict)

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

    # Detect editable context
    editable_ctx = EditableContext(args.url, project_root)
    ctx_analysis = editable_ctx.analyze()

    # Initialize source mapper if we have source directories
    source_mapper: Optional[SourceMapper] = None
    if ctx_analysis["source_dirs"]:
        source_mapper = SourceMapper(project_root)

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
            "editableContext": ctx_analysis,
        },
    )

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
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

    # Enhance issues with source file mapping
    if source_mapper:
        for issue in issues:
            element = issue.get("element", "")
            if element:
                source_info = source_mapper.find_source_file(element)
                if source_info:
                    issue["sourceFile"] = source_info["path"]
                    issue["sourceConfidence"] = source_info["confidence"]
                    issue["sourceReason"] = source_info["reason"]

    # Calculate summary
    summary = {"blocking": 0, "major": 0, "minor": 0}
    for issue in issues:
        severity = issue.get("severity", "minor")
        if severity in summary:
            summary[severity] += 1

    # Check for compact mode
    compact_mode = getattr(args, "compact", False)

    # Build result object
    if compact_mode:
        # Compact output: truncated issues, minimal artifacts, no editableContext
        compact_issues = [truncate_issue_for_compact(issue) for issue in issues]
        result = {
            "ok": True,
            "sessionId": session_id,
            "summary": summary,
            "issues": compact_issues,
            "artifacts": {
                "screenshot": str(screenshot_path),
            },
        }
    else:
        result = {
            "ok": True,
            "url": args.url,
            "spec": spec.name,
            "specPath": str(spec_path),
            "sessionId": session_id,
            "summary": summary,
            "issues": issues,
            "editableContext": ctx_analysis,
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
        generate_tasks_file(result, tasks_path, annotated_path, source_mapper)
        result["artifacts"]["tasks"] = str(tasks_path)
        log_event("tasks_file_generated", {"path": str(tasks_path)})

    # Generate markdown export if requested
    if args.markdown and issues:
        md_path = session_dir / "issues.md"
        md_result = generate_markdown_export(
            review_result=result,
            output_path=md_path,
            url=args.url,
            spec_name=args.spec or "default.md",
        )
        if md_result.get("ok"):
            result["artifacts"]["markdown"] = str(md_path)
            log_event(
                "markdown_export_created",
                {
                    "path": str(md_path),
                    "issueCount": md_result.get("issueCount", 0),
                    "selectorCount": md_result.get("selectorCount", 0),
                },
            )
        else:
            log_event("markdown_export_error", {"error": md_result.get("error")})

    # Handle todowrite output format
    todowrite_mode = getattr(args, "todowrite", False)
    if todowrite_mode:
        todowrite_output = generate_todowrite_output(issues, result, source_mapper)

        # Save todowrite JSON
        todowrite_path = session_dir / "todowrite.json"
        todowrite_path.write_text(json.dumps(todowrite_output, indent=2))
        result["artifacts"]["todowrite"] = str(todowrite_path)
        log_event("todowrite_output_generated", {"path": str(todowrite_path)})

        # Output in todowrite format instead of standard format
        json_output(todowrite_output)
        return

    # In compact mode, skip saving full report/session and output directly
    if compact_mode:
        json_output(result)
        return

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
        "editableContext": ctx_analysis,
        "summary": summary,
        "events": session_events,
    }
    session_file = session_dir / "session.json"
    session_file.write_text(json.dumps(session_data, indent=2))

    json_output(result)


def generate_tasks_file(
    result: dict,
    output_path: Path,
    annotated_path: Optional[Path] = None,
    source_mapper: Optional["SourceMapper"] = None,
) -> None:
    """Generate DESIGN-REVIEW-TASKS.md from review results.

    Enhanced version with:
    - Annotated screenshot reference
    - Better formatting with issue numbers matching visual annotations
    - Source file location hints (when detectable from element selectors)
    - Suggested fixes with code examples where applicable
    - Editable context information
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

            # Source file info - first check if already computed in issue
            source_file = issue.get("sourceFile")
            source_confidence = issue.get("sourceConfidence")
            source_reason = issue.get("sourceReason")

            # Fallback to source_mapper or detect_source_file
            if not source_file and source_mapper and element:
                source_info = source_mapper.find_source_file(element)
                if source_info:
                    source_file = source_info["path"]
                    source_confidence = source_info["confidence"]
                    source_reason = source_info["reason"]
            elif not source_file:
                source_hint = detect_source_file(element)
                if source_hint:
                    source_file = source_hint
                    source_confidence = "low"

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

            # Show enhanced source file info
            if source_file:
                confidence_badge = ""
                if source_confidence == "high":
                    confidence_badge = " ✅"
                elif source_confidence == "medium":
                    confidence_badge = " 🔶"
                else:
                    confidence_badge = " ❓"
                lines.append(f"| **Source File** | `{source_file}`{confidence_badge} |")
                if source_reason:
                    lines.append(f"| **Detection** | {source_reason} |")

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


def generate_markdown_export(
    review_result: dict,
    output_path: Path,
    url: str,
    spec_name: str,
) -> dict:
    """
    Generate issues.md companion file with full issue details.

    Returns:
        dict with ok, path keys
    """
    from annotator import _generate_css_selector

    try:
        issues = review_result.get("issues", [])
        summary = review_result.get("summary", {})
        timestamp = get_timestamp()

        # Calculate summary counts
        blocking_count = summary.get("blocking", 0)
        major_count = summary.get("major", 0)
        minor_count = summary.get("minor", 0)
        total_count = blocking_count + major_count + minor_count

        # Build summary string
        summary_parts = []
        if blocking_count > 0:
            summary_parts.append(f"{blocking_count} blocking")
        if major_count > 0:
            summary_parts.append(f"{major_count} major")
        if minor_count > 0:
            summary_parts.append(f"{minor_count} minor")
        summary_str = ", ".join(summary_parts) if summary_parts else "none"

        lines = [
            "# Design Review Issues",
            "",
            f"**URL**: {url}  ",
            f"**Reviewed**: {timestamp}  ",
            f"**Spec**: {spec_name}  ",
            f"**Total Issues**: {total_count} ({summary_str})",
            "",
            "---",
            "",
        ]

        # Collect all selectors for the quick reference section
        all_selectors: list[str] = []

        for issue in issues:
            issue_id = issue.get("id", "?")
            severity = issue.get("severity", "minor")
            pillar = issue.get("pillar", "")
            check_id = issue.get("checkId", "unknown")
            description = issue.get("description", "")
            recommendation = issue.get("recommendation", "")
            element = issue.get("element", "")

            # Get or generate CSS selector
            css_selector = issue.get("cssSelector", "")
            if not css_selector and issue.get("elementInfo"):
                css_selector = _generate_css_selector(issue["elementInfo"])

            if css_selector:
                all_selectors.append(css_selector)

            lines.append(
                f"## Issue #{issue_id}: {description[:50]}{'...' if len(description) > 50 else ''}"
            )
            lines.append("")
            lines.append("| Property | Value |")
            lines.append("|----------|-------|")
            lines.append(f"| **Severity** | {severity} |")
            if pillar:
                lines.append(f"| **Pillar** | {pillar} |")
            lines.append(f"| **Check** | {check_id} |")
            if css_selector:
                lines.append(f"| **CSS Selector** | `{css_selector}` |")
            if element:
                lines.append(f"| **Element** | `{element}` |")
            lines.append("")

            lines.append(f"**Description**: {description}")
            lines.append("")

            if recommendation:
                lines.append(f"**Recommendation**: {recommendation}")
                lines.append("")

            lines.append("---")
            lines.append("")

        # Add Quick Fix Reference section
        if all_selectors:
            lines.append("## Quick Fix Reference")
            lines.append("")
            lines.append("Copy these selectors for your AI assistant:")
            lines.append("")
            lines.append("```")
            for selector in all_selectors:
                lines.append(selector)
            lines.append("```")
            lines.append("")

        # Write the file
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("\n".join(lines))

        return {
            "ok": True,
            "path": str(output_path),
            "issueCount": len(issues),
            "selectorCount": len(all_selectors),
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


class SourceMapper:
    """
    Maps DOM elements/selectors to source files in the project.

    Uses multiple strategies:
    1. data-testid attributes
    2. Component-like class names (PascalCase)
    3. Common UI patterns (hero, header, footer, etc.)
    4. Source map lookup (if available)
    5. Glob-based file search in common directories
    """

    def __init__(self, project_root: Optional[Path] = None):
        self.project_root = project_root or Path.cwd()
        self._file_cache: dict[str, list[Path]] = {}
        self._build_file_index()

    def _build_file_index(self) -> None:
        """Build an index of component files in the project."""
        # Common component directories to search
        search_dirs = [
            "components",
            "src/components",
            "app/components",
            "lib/components",
            "src",
            "app",
            "pages",
        ]

        extensions = [".tsx", ".jsx", ".vue", ".svelte", ".astro"]

        for search_dir in search_dirs:
            dir_path = self.project_root / search_dir
            if dir_path.exists():
                for ext in extensions:
                    for file_path in dir_path.rglob(f"*{ext}"):
                        # Index by lowercase filename without extension
                        key = file_path.stem.lower()
                        if key not in self._file_cache:
                            self._file_cache[key] = []
                        self._file_cache[key].append(file_path)

    def find_source_file(
        self, selector: str, element_info: Optional[dict] = None
    ) -> Optional[dict]:
        """
        Find the likely source file for an element.

        Returns a dict with:
        - path: relative path to source file
        - confidence: 'high', 'medium', or 'low'
        - reason: explanation of how it was found
        - line_hint: optional line number hint
        """
        if not selector:
            return None

        import re

        # Strategy 1: data-testid attribute
        testid_match = re.search(
            r'data-testid[=~*\^$]*["\']?([A-Za-z][a-zA-Z0-9_-]+)', selector
        )
        if testid_match:
            name = testid_match.group(1)
            # Convert kebab-case to PascalCase for component lookup
            component_name = "".join(word.capitalize() for word in name.split("-"))
            found = self._lookup_component(component_name)
            if found:
                return {
                    "path": str(found.relative_to(self.project_root)),
                    "confidence": "high",
                    "reason": f"data-testid='{name}' matches component file",
                    "line_hint": None,
                }

        # Strategy 2: PascalCase class names (React/component patterns)
        class_match = re.search(r"\.([A-Z][a-zA-Z0-9]+)", selector)
        if class_match:
            component_name = class_match.group(1)
            found = self._lookup_component(component_name)
            if found:
                return {
                    "path": str(found.relative_to(self.project_root)),
                    "confidence": "medium",
                    "reason": f"PascalCase class '.{component_name}' suggests component",
                    "line_hint": None,
                }

        # Strategy 3: CSS Module patterns (ComponentName_className__hash)
        module_match = re.search(r"\.([A-Z][a-zA-Z0-9]+)_", selector)
        if module_match:
            component_name = module_match.group(1)
            found = self._lookup_component(component_name)
            if found:
                return {
                    "path": str(found.relative_to(self.project_root)),
                    "confidence": "high",
                    "reason": "CSS Module pattern detected",
                    "line_hint": None,
                }

        # Strategy 4: Common UI pattern names
        ui_patterns = {
            "hero": ["Hero", "HeroSection", "HeroBanner"],
            "header": ["Header", "AppHeader", "SiteHeader", "Navbar"],
            "footer": ["Footer", "AppFooter", "SiteFooter"],
            "nav": ["Nav", "Navigation", "Navbar", "NavMenu"],
            "sidebar": ["Sidebar", "SideNav", "SideMenu"],
            "modal": ["Modal", "Dialog", "Popup"],
            "card": ["Card", "CardComponent"],
            "button": ["Button", "Btn"],
            "form": ["Form", "FormComponent"],
            "input": ["Input", "TextField", "TextInput"],
            "menu": ["Menu", "DropdownMenu", "MenuList"],
            "toast": ["Toast", "Notification", "Alert"],
            "badge": ["Badge", "Tag", "Chip"],
            "avatar": ["Avatar", "UserAvatar"],
            "table": ["Table", "DataTable"],
            "list": ["List", "ListView"],
        }

        selector_lower = selector.lower()
        for pattern, component_names in ui_patterns.items():
            if pattern in selector_lower:
                for component_name in component_names:
                    found = self._lookup_component(component_name)
                    if found:
                        return {
                            "path": str(found.relative_to(self.project_root)),
                            "confidence": "low",
                            "reason": f"UI pattern '{pattern}' in selector",
                            "line_hint": None,
                        }

        # Strategy 5: Extract class/id and search files
        identifiers = re.findall(r"[.#]([a-zA-Z][a-zA-Z0-9_-]+)", selector)
        for ident in identifiers:
            # Convert kebab-case to possible component name
            possible_name = "".join(word.capitalize() for word in ident.split("-"))
            found = self._lookup_component(possible_name)
            if found:
                return {
                    "path": str(found.relative_to(self.project_root)),
                    "confidence": "low",
                    "reason": f"Identifier '{ident}' may correspond to component",
                    "line_hint": None,
                }

        return None

    def _lookup_component(self, name: str) -> Optional[Path]:
        """Look up a component by name in the file index."""
        key = name.lower()
        if key in self._file_cache:
            # Return first match (prefer .tsx over .jsx, etc.)
            files = self._file_cache[key]
            tsx_files = [f for f in files if f.suffix == ".tsx"]
            if tsx_files:
                return tsx_files[0]
            return files[0]
        return None


def detect_source_file(selector: str) -> Optional[str]:
    """Attempt to detect likely source file from element selector.

    Heuristics:
    - data-testid="ComponentName" → components/ComponentName.tsx
    - .className with component-like name → components/ClassName.tsx
    - #id patterns → look for matching component

    Note: For more advanced source mapping, use SourceMapper class.
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
            # Signal completion to emit review.completed event
            page.evaluate(
                "() => window.__designReviewComplete && window.__designReviewComplete()"
            )
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
    """Compare page against reference image or Figma frame."""
    from playwright.sync_api import sync_playwright

    # Validate inputs
    if not args.reference and not args.figma:
        error_output("Either --reference or --figma is required")
        sys.exit(1)

    if args.figma:
        # Figma integration placeholder
        error_output(
            "Figma integration not yet implemented. "
            "Export your Figma frame as PNG and use --reference instead."
        )
        sys.exit(1)

    # Resolve reference image path
    reference_path = resolve_reference_image(args.reference)
    if not reference_path:
        error_output(f"Reference image not found: {args.reference}")
        sys.exit(1)

    session_id = generate_session_id()
    session_dir = ensure_reviews_dir(session_id)

    # Session event logging
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
            "reference": str(reference_path),
            "mode": "compare",
        },
    )

    # Capture current screenshot
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
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

        # Take screenshot
        screenshot_path = session_dir / "screenshot.png"
        page.screenshot(path=str(screenshot_path), full_page=not args.viewport_only)
        log_event("screenshot_captured", {"path": str(screenshot_path)})

        browser.close()
        log_event("browser_closed", {})

    # Run image comparison
    from image_comparator import compare_images, CompareMethod

    comparison_result = compare_images(
        reference=reference_path,
        current=screenshot_path,
        output_diff=session_dir / "diff.png",
        method=CompareMethod.HYBRID,
        pixel_threshold=args.threshold,
        ssim_threshold=args.ssim_threshold,
        diff_style=args.diff_style,
    )

    log_event(
        "comparison_completed",
        {
            "match": comparison_result.match,
            "pixelDiffPercent": comparison_result.pixel_diff_percent,
            "ssimScore": comparison_result.ssim_score,
            "diffRegions": len(comparison_result.diff_regions),
        },
    )

    # Build result
    compact_mode = getattr(args, "compact", False)

    if compact_mode:
        # Compact output: minimal comparison info, no full diffRegions
        result = {
            "ok": comparison_result.ok,
            "sessionId": session_id,
            "match": comparison_result.match,
            "comparison": {
                "pixelDiffPercent": comparison_result.pixel_diff_percent,
                "ssimScore": comparison_result.ssim_score,
            },
            "diffRegionCount": len(comparison_result.diff_regions),
            "artifacts": {
                "screenshot": str(screenshot_path),
            },
        }
        if comparison_result.diff_path:
            result["artifacts"]["diff"] = comparison_result.diff_path
        json_output(result)
        return

    result = {
        "ok": comparison_result.ok,
        "url": args.url,
        "sessionId": session_id,
        "mode": "compare",
        "reference": str(reference_path),
        "match": comparison_result.match,
        "comparison": {
            "method": comparison_result.method,
            "pixelDiffPercent": comparison_result.pixel_diff_percent,
            "ssimScore": comparison_result.ssim_score,
            "pixelThreshold": comparison_result.pixel_threshold,
            "ssimThreshold": comparison_result.ssim_threshold,
            "sizeMismatch": comparison_result.size_mismatch,
            "referenceSize": comparison_result.reference_size,
            "currentSize": comparison_result.current_size,
        },
        "diffRegions": [r.to_dict() for r in comparison_result.diff_regions],
        "artifacts": {
            "screenshot": str(screenshot_path),
            "reference": str(reference_path),
            "sessionDir": str(session_dir),
        },
    }

    if comparison_result.diff_path:
        result["artifacts"]["diff"] = comparison_result.diff_path

    # Generate annotated screenshot if there are differences
    if not comparison_result.match and comparison_result.diff_regions:
        from annotator import annotate_screenshot

        # Convert diff regions to issue format for annotator
        issues = []
        for i, region in enumerate(comparison_result.diff_regions, 1):
            issues.append(
                {
                    "id": i,
                    "severity": region.severity,
                    "description": f"Visual difference ({region.width}x{region.height}px)",
                    "boundingBox": {
                        "x": region.x,
                        "y": region.y,
                        "width": region.width,
                        "height": region.height,
                    },
                }
            )

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
                {"path": str(annotated_path)},
            )

    # Generate tasks file if requested and there are differences
    if args.generate_tasks and not comparison_result.match:
        tasks_path = Path("DESIGN-REVIEW-TASKS.md")
        generate_compare_tasks_file(result, tasks_path)
        result["artifacts"]["tasks"] = str(tasks_path)
        log_event("tasks_file_generated", {"path": str(tasks_path)})

    # Generate markdown export if requested and there are differences
    if args.markdown and not comparison_result.match and comparison_result.diff_regions:
        # Build issues from diff regions for markdown export
        compare_issues = []
        for i, region in enumerate(comparison_result.diff_regions, 1):
            compare_issues.append(
                {
                    "id": i,
                    "severity": region.severity,
                    "description": f"Visual difference ({region.width}x{region.height}px)",
                    "boundingBox": {
                        "x": region.x,
                        "y": region.y,
                        "width": region.width,
                        "height": region.height,
                    },
                }
            )
        md_path = session_dir / "issues.md"
        md_result = generate_markdown_export(
            review_result={"issues": compare_issues, "summary": {}},
            output_path=md_path,
            url=args.url,
            spec_name="visual-comparison",
        )
        if md_result.get("ok"):
            result["artifacts"]["markdown"] = str(md_path)
            log_event(
                "markdown_export_created",
                {
                    "path": str(md_path),
                    "issueCount": md_result.get("issueCount", 0),
                    "selectorCount": md_result.get("selectorCount", 0),
                },
            )
        else:
            log_event("markdown_export_error", {"error": md_result.get("error")})

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
        "mode": "compare",
        "reference": str(reference_path),
        "match": comparison_result.match,
        "comparison": result["comparison"],
        "events": session_events,
    }
    session_file = session_dir / "session.json"
    session_file.write_text(json.dumps(session_data, indent=2))

    json_output(result)


def resolve_reference_image(ref_arg: str) -> Optional[Path]:
    """
    Resolve reference image path.

    Checks:
    1. Absolute path
    2. Relative to current directory
    3. In imgs/ directory of the skill
    """
    ref_path = Path(ref_arg)

    # Absolute path
    if ref_path.is_absolute() and ref_path.exists():
        return ref_path

    # Relative to cwd
    if ref_path.exists():
        return ref_path.resolve()

    # In imgs/ directory
    imgs_path = IMGS_DIR / ref_arg
    if imgs_path.exists():
        return imgs_path

    # Try with common extensions
    for ext in [".png", ".jpg", ".jpeg", ".webp"]:
        for base_path in [ref_path, imgs_path]:
            with_ext = base_path.with_suffix(ext)
            if with_ext.exists():
                return with_ext

    return None


def generate_compare_tasks_file(result: dict, output_path: Path) -> None:
    """Generate DESIGN-REVIEW-TASKS.md from comparison results."""
    severity_icons = {
        "minor": "🟡",
        "moderate": "🟠",
        "major": "🔴",
    }

    lines = [
        "# Visual Comparison Tasks",
        "",
        f"> **Generated**: {get_timestamp()}  ",
        f"> **URL**: {result['url']}  ",
        f"> **Reference**: {result['reference']}  ",
        f"> **Session**: `{result['sessionId']}`",
        "",
    ]

    # Comparison summary
    comparison = result.get("comparison", {})
    match_status = "✅ MATCH" if result.get("match") else "❌ MISMATCH"

    lines.extend(
        [
            "## Comparison Summary",
            "",
            f"**Status**: {match_status}",
            "",
            "| Metric | Value | Threshold |",
            "|--------|-------|-----------|",
        ]
    )

    if comparison.get("pixelDiffPercent") is not None:
        lines.append(
            f"| Pixel Difference | {comparison['pixelDiffPercent']}% | {comparison['pixelThreshold']}% |"
        )

    if comparison.get("ssimScore") is not None:
        lines.append(
            f"| SSIM Score | {comparison['ssimScore']} | {comparison['ssimThreshold']} |"
        )

    if comparison.get("sizeMismatch"):
        lines.append(
            f"| Size Mismatch | ⚠️ Yes | Reference: {comparison['referenceSize']}, Current: {comparison['currentSize']} |"
        )

    lines.append("")

    # Diff regions
    diff_regions = result.get("diffRegions", [])
    if diff_regions:
        lines.extend(
            [
                "## Difference Regions",
                "",
                f"Found **{len(diff_regions)}** regions with visual differences:",
                "",
            ]
        )

        for i, region in enumerate(diff_regions, 1):
            icon = severity_icons.get(region.get("severity", "moderate"), "🟠")
            lines.append(
                f"### {icon} Region {i}",
            )
            lines.append("")
            lines.append(f"- **Location**: ({region['x']}, {region['y']})")
            lines.append(f"- **Size**: {region['width']}x{region['height']}px")
            lines.append(f"- **Severity**: {region.get('severity', 'unknown')}")
            lines.append("")

    # Artifacts
    artifacts = result.get("artifacts", {})
    lines.extend(
        [
            "## 📁 Artifacts",
            "",
            "| File | Path |",
            "|------|------|",
            f"| Current Screenshot | `{artifacts.get('screenshot', 'N/A')}` |",
            f"| Reference Image | `{artifacts.get('reference', 'N/A')}` |",
        ]
    )

    if artifacts.get("diff"):
        lines.append(f"| Visual Diff | `{artifacts['diff']}` |")

    if artifacts.get("annotated"):
        lines.append(f"| Annotated Screenshot | `{artifacts['annotated']}` |")

    lines.extend(
        [
            "",
            "---",
            "",
            "*Review the diff image to identify specific changes.*  ",
            "*Update your implementation to match the reference design.*",
        ]
    )

    output_path.write_text("\n".join(lines))


def parse_user_intent(user_input: str) -> dict[str, Any]:
    """
    Parse natural language input to determine review type and parameters.

    Returns a dict with:
    - command: 'review', 'interactive', 'compare', or 'accessibility'
    - spec_hints: list of spec-related keywords found
    - selector_hint: selector if user mentioned specific element
    - focus_areas: list of areas to focus on
    """
    user_input_lower = user_input.lower()

    result = {
        "command": "review",  # default
        "spec_hints": [],
        "selector_hint": None,
        "focus_areas": [],
    }

    # Detect command type
    if any(
        word in user_input_lower
        for word in ["compare", "reference", "design image", "figma", "mockup"]
    ):
        result["command"] = "compare"
    elif any(
        word in user_input_lower
        for word in ["interactive", "pick", "select", "browse", "explore"]
    ):
        result["command"] = "interactive"
    elif any(
        word in user_input_lower
        for word in ["accessibility", "a11y", "wcag", "screen reader", "aria"]
    ):
        result["command"] = "accessibility"

    # Detect focus areas
    focus_keywords = {
        "contrast": ["contrast", "color contrast", "text contrast", "readable"],
        "typography": ["font", "typography", "text size", "font-size", "typeface"],
        "spacing": ["spacing", "margin", "padding", "whitespace", "gap"],
        "brand": ["brand", "brand colors", "brand guidelines", "style guide"],
        "buttons": ["button", "buttons", "cta", "call to action", "primary action"],
        "navigation": ["navigation", "nav", "menu", "breadcrumb"],
        "forms": ["form", "input", "field", "validation"],
        "accessibility": ["accessibility", "a11y", "keyboard", "focus", "aria"],
        "images": ["image", "images", "alt text", "alt", "icons"],
        "responsive": ["responsive", "mobile", "tablet", "breakpoint"],
    }

    for area, keywords in focus_keywords.items():
        if any(kw in user_input_lower for kw in keywords):
            result["focus_areas"].append(area)

    # Detect specific element mentions (common patterns)
    import re

    selector_patterns = [
        r"\.[\w-]+",  # .class-name
        r"#[\w-]+",  # #id
        r"the\s+(\w+)\s+(?:section|component|button|header|footer|nav)",  # "the hero section"
    ]

    for pattern in selector_patterns:
        match = re.search(pattern, user_input)
        if match:
            result["selector_hint"] = match.group(0)
            break

    return result


def cmd_prompt(args: argparse.Namespace) -> None:
    """
    Interactive prompt mode - ask user what they want to review.

    This is triggered when the user runs `design_review.py <url>` without a command.
    """
    url = args.url

    # Display prompt menu
    menu = """
🎨 Design Review - What would you like to check?

  1. Full page review (check entire page against spec)
  2. Specific element (select an element to review)
  3. Compare to reference (compare against design image)
  4. Accessibility audit (deep-dive a11y checks)
  5. Custom (describe what you're looking for)

Enter choice [1-5] or describe your goal: """

    try:
        choice = input(menu).strip()
    except (EOFError, KeyboardInterrupt):
        print("\nCancelled.")
        sys.exit(0)

    if not choice:
        print("No input provided. Running full page review.")
        choice = "1"

    # Handle numeric choices
    if choice == "1":
        # Full page review
        args.spec = None
        args.selector = None
        args.annotate = True
        args.generate_tasks = True
        cmd_review(args)
    elif choice == "2":
        # Interactive mode
        args.spec = None
        cmd_interactive(args)
    elif choice == "3":
        # Compare mode - prompt for reference
        ref = input(
            "Enter reference image path (or press Enter to list available): "
        ).strip()
        if not ref:
            # List available images
            if IMGS_DIR.exists():
                images = list(IMGS_DIR.glob("*.png")) + list(IMGS_DIR.glob("*.jpg"))
                if images:
                    print("\nAvailable reference images:")
                    for i, img in enumerate(images, 1):
                        print(f"  {i}. {img.name}")
                    ref_choice = input("Enter number or path: ").strip()
                    if ref_choice.isdigit() and 1 <= int(ref_choice) <= len(images):
                        ref = str(images[int(ref_choice) - 1])
                    else:
                        ref = ref_choice
                else:
                    print("No reference images found in imgs/ directory.")
                    ref = input("Enter reference image path: ").strip()
            else:
                ref = input("Enter reference image path: ").strip()

        if not ref:
            print("No reference image specified. Cannot proceed with comparison.")
            sys.exit(1)

        args.reference = ref
        args.figma = None
        args.frame = None
        args.threshold = 5.0
        args.ssim_threshold = 0.95
        args.diff_style = "overlay"
        args.viewport_only = False
        args.generate_tasks = True
        cmd_compare(args)
    elif choice == "4":
        # Accessibility audit - review with accessibility focus
        args.spec = None
        args.selector = None
        args.annotate = True
        args.generate_tasks = True
        # TODO: Add accessibility-focused spec or mode
        cmd_review(args)
    elif choice == "5" or not choice.isdigit():
        # Custom - parse natural language
        if choice == "5":
            custom_input = input("Describe what you want to check: ").strip()
        else:
            custom_input = choice

        intent = parse_user_intent(custom_input)

        print(f"\nUnderstood: Running {intent['command']} mode")
        if intent["focus_areas"]:
            print(f"Focus areas: {', '.join(intent['focus_areas'])}")
        if intent["selector_hint"]:
            print(f"Target element: {intent['selector_hint']}")
        print()

        if intent["command"] == "interactive":
            args.spec = None
            cmd_interactive(args)
        elif intent["command"] == "compare":
            print("Note: Compare mode requires a reference image.")
            ref = input("Enter reference image path: ").strip()
            if not ref:
                print("No reference image. Falling back to full page review.")
                args.spec = None
                args.selector = intent["selector_hint"]
                args.annotate = True
                args.generate_tasks = True
                cmd_review(args)
            else:
                args.reference = ref
                args.figma = None
                args.frame = None
                args.threshold = 5.0
                args.ssim_threshold = 0.95
                args.diff_style = "overlay"
                args.viewport_only = False
                args.generate_tasks = True
                cmd_compare(args)
        else:
            # Default to review
            args.spec = None
            args.selector = intent["selector_hint"]
            args.annotate = True
            args.generate_tasks = True
            cmd_review(args)
    else:
        print(f"Invalid choice: {choice}")
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Design Review - Spec-driven design QA"
    )
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Prompt mode (default when only URL provided)
    prompt_parser = subparsers.add_parser(
        "prompt", help="Interactive prompt to choose review type"
    )
    prompt_parser.add_argument("url", help="URL to review")

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
    review_parser.add_argument(
        "--todowrite",
        action="store_true",
        help="Output in todowrite-compatible JSON format",
    )
    review_parser.add_argument(
        "--compact",
        action="store_true",
        help="Token-efficient output: truncate descriptions, omit details/nodes/editableContext",
    )
    review_parser.add_argument(
        "--markdown",
        action="store_true",
        help="Generate issues.md companion file with full selector details",
    )

    interactive_parser = subparsers.add_parser(
        "interactive", help="Interactive review mode"
    )
    interactive_parser.add_argument("url", help="URL to review")
    interactive_parser.add_argument("--spec", help="Spec file (default: default.md)")

    compare_parser = subparsers.add_parser(
        "compare", help="Compare page against reference image"
    )
    compare_parser.add_argument("url", help="URL to compare")
    compare_parser.add_argument(
        "--reference", "-r", help="Reference image path (in imgs/ or absolute/relative)"
    )
    compare_parser.add_argument("--figma", help="Figma file URL (not yet implemented)")
    compare_parser.add_argument("--frame", help="Figma frame name (for --figma)")
    compare_parser.add_argument(
        "--threshold",
        "-t",
        type=float,
        default=5.0,
        help="Pixel diff threshold percentage (default: 5.0)",
    )
    compare_parser.add_argument(
        "--ssim-threshold",
        type=float,
        default=0.95,
        help="SSIM similarity threshold (default: 0.95)",
    )
    compare_parser.add_argument(
        "--diff-style",
        choices=["overlay", "sidebyside", "heatmap"],
        default="overlay",
        help="Diff visualization style (default: overlay)",
    )
    compare_parser.add_argument(
        "--viewport-only",
        action="store_true",
        help="Capture only viewport (not full page)",
    )
    compare_parser.add_argument(
        "--generate-tasks",
        action="store_true",
        help="Generate DESIGN-REVIEW-TASKS.md",
    )
    compare_parser.add_argument(
        "--compact",
        action="store_true",
        help="Token-efficient output: reduced diff regions, minimal artifacts",
    )
    compare_parser.add_argument(
        "--markdown",
        action="store_true",
        help="Generate issues.md companion file with full selector details",
    )

    specs_parser = subparsers.add_parser("specs", help="Manage specs")
    specs_parser.add_argument(
        "--list", action="store_true", help="List available specs"
    )
    specs_parser.add_argument("--validate", help="Validate a spec file")
    specs_parser.add_argument("--show", help="Show spec details")

    args = parser.parse_args()

    # Handle case where user provides just a URL (no subcommand)
    # argparse will have command=None, so we check if there's a positional arg that looks like a URL
    if not args.command:
        # Check if there's a URL-like argument
        remaining = sys.argv[1:]
        if remaining and (
            remaining[0].startswith("http") or remaining[0].startswith("localhost")
        ):
            # Treat as prompt mode
            args.url = remaining[0]
            args.command = "prompt"
        else:
            parser.print_help()
            sys.exit(1)

    if args.command == "prompt":
        cmd_prompt(args)
    elif args.command == "review":
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
