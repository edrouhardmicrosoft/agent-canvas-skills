#!/usr/bin/env python3
"""
Accessibility Sub-Agent - Runs axe-core and returns compact summary.

Output Budget: ~5K tokens

Usage:
    python a11y_agent.py <url> [--selector SELECTOR] [--max-issues N]
"""

import argparse
import json
import sys
from collections import Counter
from typing import Optional


class A11yAgent:
    """
    Token-efficient accessibility scanning agent.

    Returns summarized results instead of full axe-core output,
    keeping output under ~5K tokens.
    """

    def scan(
        self,
        url: str,
        selector: Optional[str] = None,
        max_issues: int = 10,
        viewport: tuple[int, int] = (1280, 720),
    ) -> dict:
        """
        Run accessibility scan and return summarized results.

        Args:
            url: URL to scan
            selector: Optional CSS selector to scope the scan
            max_issues: Maximum number of top issues to include
            viewport: Viewport dimensions (width, height)

        Returns:
            {
                "ok": True,
                "totalViolations": 15,
                "bySeverity": {"critical": 2, "serious": 5, "moderate": 6, "minor": 2},
                "byCategory": {"color": 3, "aria": 5, "keyboard": 2, ...},
                "topIssues": [
                    {"id": "color-contrast", "impact": "serious", "count": 3, "description": "..."},
                    ...
                ]
            }
        """
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            return {
                "ok": False,
                "error": "Playwright not installed. Run: pip install playwright && playwright install chromium",
            }

        try:
            from axe_playwright_python.sync_playwright import Axe
        except ImportError:
            return {
                "ok": False,
                "error": "axe-playwright-python not installed. Run: pip install axe-playwright-python",
            }

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=False)
                page = browser.new_page(
                    viewport={"width": viewport[0], "height": viewport[1]}
                )

                page.goto(url, wait_until="networkidle")

                # Force browser window to foreground (critical for subprocess execution)
                page.bring_to_front()

                # Run axe-core scan
                axe = Axe()

                if selector:
                    # Scope scan to specific element
                    results = axe.run(page, context=selector)
                else:
                    results = axe.run(page)

                browser.close()

            violations = results.get("violations", [])

            # Count by severity
            severity_counts = Counter()
            for v in violations:
                impact = v.get("impact", "minor")
                severity_counts[impact] += len(v.get("nodes", []))

            # Count by category (using tags)
            category_counts = Counter()
            category_map = {
                "wcag2a": "wcag-a",
                "wcag2aa": "wcag-aa",
                "wcag2aaa": "wcag-aaa",
                "color-contrast": "color",
                "aria": "aria",
                "keyboard": "keyboard",
                "forms": "forms",
                "semantics": "semantics",
            }

            for v in violations:
                tags = v.get("tags", [])
                categorized = False
                for tag in tags:
                    for key, category in category_map.items():
                        if key in tag:
                            category_counts[category] += 1
                            categorized = True
                            break
                    if categorized:
                        break
                if not categorized:
                    category_counts["other"] += 1

            # Get top issues (aggregated by rule id)
            issue_counts = Counter()
            issue_info = {}
            for v in violations:
                rule_id = v.get("id", "unknown")
                node_count = len(v.get("nodes", []))
                issue_counts[rule_id] += node_count
                if rule_id not in issue_info:
                    desc = v.get("description", "")
                    if len(desc) > 80:
                        desc = desc[:77] + "..."
                    issue_info[rule_id] = {
                        "impact": v.get("impact", "minor"),
                        "description": desc,
                    }

            top_issues = []
            for rule_id, count in issue_counts.most_common(max_issues):
                info = issue_info.get(rule_id, {})
                top_issues.append(
                    {
                        "id": rule_id,
                        "impact": info.get("impact", "minor"),
                        "count": count,
                        "description": info.get("description", ""),
                    }
                )

            return {
                "ok": True,
                "totalViolations": sum(severity_counts.values()),
                "uniqueRules": len(violations),
                "bySeverity": dict(severity_counts),
                "byCategory": dict(category_counts),
                "topIssues": top_issues,
            }

        except Exception as e:
            return {"ok": False, "error": str(e)}


def main():
    parser = argparse.ArgumentParser(
        description="Accessibility Sub-Agent - Token-efficient a11y scanning"
    )
    parser.add_argument("url", help="URL to scan")
    parser.add_argument("--selector", "-s", help="CSS selector to scope the scan")
    parser.add_argument(
        "--max-issues",
        "-m",
        type=int,
        default=10,
        help="Max top issues to include (default: 10)",
    )
    parser.add_argument(
        "--width", type=int, default=1280, help="Viewport width (default: 1280)"
    )
    parser.add_argument(
        "--height", type=int, default=720, help="Viewport height (default: 720)"
    )

    args = parser.parse_args()

    agent = A11yAgent()
    result = agent.scan(
        url=args.url,
        selector=args.selector,
        max_issues=args.max_issues,
        viewport=(args.width, args.height),
    )

    print(json.dumps(result, indent=2))
    sys.exit(0 if result.get("ok") else 1)


if __name__ == "__main__":
    main()
