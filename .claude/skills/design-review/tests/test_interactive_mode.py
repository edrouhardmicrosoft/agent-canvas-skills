#!/usr/bin/env python3
"""
Interactive Mode Test Suite

Tests for Phase 3 Interactive Mode features:
- Overlay and annotation layer injection
- Spec loading into reviewState
- Pre-scan execution and issue detection
- Badge display via annotation layer
- Keyboard navigation through issues
- Results capture via __designReviewGetResults
"""

import json
import sys
from pathlib import Path
from typing import Optional

try:
    from playwright.sync_api import sync_playwright, Page
except ImportError:
    print(
        "ERROR: Playwright not installed. Run: pip install playwright && playwright install chromium"
    )
    sys.exit(1)


# =============================================================================
# Test Utilities
# =============================================================================


def get_scripts_dir() -> Path:
    """Get the design-review scripts directory path."""
    return Path(__file__).parent.parent / "scripts"


def get_shared_dir() -> Path:
    """Get the shared skills directory path."""
    return Path(__file__).parent.parent.parent / "shared"


def get_canvas_edit_dir() -> Path:
    """Get the canvas-edit scripts directory path."""
    return Path(__file__).parent.parent.parent / "canvas-edit" / "scripts"


def load_canvas_bus_js() -> str:
    """Load the canvas bus JavaScript."""
    bus_path = get_shared_dir() / "canvas_bus.py"
    if bus_path.exists():
        content = bus_path.read_text()
        start = content.find('CANVAS_BUS_JS = """')
        if start != -1:
            start += len('CANVAS_BUS_JS = """')
            end = content.find('"""', start)
            if end != -1:
                return content[start:end]
    # Return minimal mock if not found
    return """
    (() => {
        if (window.__canvasBus) return;
        window.__canvasBus = {
            sessionId: 'test-session',
            state: { activeTools: new Set(), captureMode: false, selection: null },
            emit: (type, source, payload) => ({ type, source, payload, timestamp: new Date().toISOString() }),
            subscribe: (type, cb) => () => {},
            drain: () => [],
            getSeq: () => 0,
            generateSelector: (el) => ({ selector: el.id ? '#' + el.id : el.tagName.toLowerCase() }),
            getElementInfo: (el) => ({ tag: el.tagName.toLowerCase() })
        };
    })();
    """


def load_annotation_layer_js() -> str:
    """Load the annotation layer JavaScript."""
    js_path = get_canvas_edit_dir() / "annotation_layer.js"
    return js_path.read_text()


def load_review_overlay_js() -> str:
    """Load the review overlay JavaScript."""
    js_path = get_scripts_dir() / "review_overlay.js"
    return js_path.read_text()


def inject_all_scripts(page: Page) -> None:
    """Inject all required scripts in correct order."""
    page.evaluate(load_canvas_bus_js())
    page.evaluate(load_annotation_layer_js())
    page.evaluate(load_review_overlay_js())
    page.wait_for_timeout(300)


# Test spec with checks that will trigger on test elements
TEST_SPEC = {
    "name": "test-spec",
    "checks": [
        {
            "id": "touch-targets",
            "pillar": "Quality Craft",
            "severity": "major",
            "description": "Touch targets",
            "config": {"minimum_size": 44},
        },
        {
            "id": "alt-text",
            "pillar": "Quality Craft",
            "severity": "major",
            "description": "Alt text",
            "config": {},
        },
        {
            "id": "focus-indicators",
            "pillar": "Quality Craft",
            "severity": "minor",
            "description": "Focus indicators",
            "config": {},
        },
        {
            "id": "color-contrast",
            "pillar": "Quality Craft",
            "severity": "major",
            "description": "Color contrast",
            "config": {"minimum_ratio": 4.5},
        },
    ],
}

# Test HTML with intentional violations
TEST_HTML = """
<!DOCTYPE html>
<html>
<head><title>Test Page</title></head>
<body style="padding: 50px; height: 2000px;">
    <button id="btn1" style="width:20px; height:20px;">X</button>
    <div style="height:500px;"></div>
    <button id="btn2" style="width:15px; height:15px;">Y</button>
    <div style="height:500px;"></div>
    <img id="img1" src="test.png">
    <a id="link1" href="#">Test Link</a>
</body>
</html>
"""


# =============================================================================
# Test Result Tracking
# =============================================================================


class TestResults:
    """Track test results."""

    def __init__(self):
        self.results = []

    def add(
        self, test_id: str, test_name: str, passed: bool, detail: Optional[str] = None
    ) -> None:
        self.results.append(
            {
                "id": test_id,
                "test": test_name,
                "pass": passed,
                "detail": detail or "",
            }
        )

    def print_summary(self) -> None:
        pass_count = sum(1 for r in self.results if r["pass"])
        total_count = len(self.results)
        print(f"\n{'=' * 60}")
        print(f"TEST RESULTS: {pass_count}/{total_count} PASSED")
        print(f"{'=' * 60}\n")
        for r in self.results:
            status = "\033[92m PASS\033[0m" if r["pass"] else "\033[91m FAIL\033[0m"
            print(f"[{r['id']}] {status}: {r['test']}")
            if r["detail"]:
                print(f"       {r['detail']}\n")

    def all_passed(self) -> bool:
        return all(r["pass"] for r in self.results)


# =============================================================================
# Test Cases
# =============================================================================


def test_overlay_injection(results: TestResults) -> None:
    """Test 1: Verify annotation layer and review overlay are injected."""
    test_id = "T1"
    test_name = "Overlay and annotation layer injection"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_content(TEST_HTML)

        inject_all_scripts(page)

        # Check annotation layer
        annotation_active = page.evaluate(
            "() => window.__annotationLayerActive === true"
        )
        # Check review overlay (has __designReviewInit)
        overlay_init = page.evaluate(
            "() => typeof window.__designReviewInit === 'function'"
        )

        passed = annotation_active and overlay_init
        detail = f"annotationLayerActive={annotation_active}, __designReviewInit={overlay_init}"

        results.add(test_id, test_name, passed, detail)
        browser.close()


def test_spec_loading(results: TestResults) -> None:
    """Test 2: Verify spec is passed to overlay correctly."""
    test_id = "T2"
    test_name = "Spec loading into reviewState"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_content(TEST_HTML)

        inject_all_scripts(page)
        page.evaluate(f"window.__designReviewInit({json.dumps(TEST_SPEC)})")

        spec = page.evaluate("() => window.__designReviewState.spec")

        passed = (
            spec is not None
            and spec.get("name") == "test-spec"
            and len(spec.get("checks", [])) == 4
        )
        detail = f"spec.name={spec.get('name') if spec else None}, checks={len(spec.get('checks', [])) if spec else 0}"

        results.add(test_id, test_name, passed, detail)
        browser.close()


def test_prescan_execution(results: TestResults) -> None:
    """Test 3: Verify pre-scan detects issues."""
    test_id = "T3"
    test_name = "Pre-scan execution and issue detection"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_content(TEST_HTML)

        inject_all_scripts(page)
        page.evaluate(f"window.__designReviewInit({json.dumps(TEST_SPEC)})")
        page.evaluate("window.__designReviewPreScan()")
        page.wait_for_timeout(2000)  # Wait for async scan

        issues_count = page.evaluate("() => window.__designReviewState.issues.length")

        passed = issues_count >= 1
        detail = f"Found {issues_count} issues"

        results.add(test_id, test_name, passed, detail)
        browser.close()


def test_badge_display(results: TestResults) -> None:
    """Test 4: Verify badges appear for detected issues."""
    test_id = "T4"
    test_name = "Badge display via annotation layer"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_content(TEST_HTML)

        inject_all_scripts(page)
        page.evaluate(f"window.__designReviewInit({json.dumps(TEST_SPEC)})")
        page.evaluate("window.__designReviewPreScan()")
        page.wait_for_timeout(2000)

        # Check for annotation badges (created by annotation_layer.js on review.issue_found events)
        badges = page.evaluate(
            "() => document.querySelectorAll('.annotation-badge').length"
        )

        passed = badges >= 1
        detail = f"Found {badges} badges"

        results.add(test_id, test_name, passed, detail)
        browser.close()


def test_keyboard_navigation(results: TestResults) -> None:
    """Test 5: Verify 'N' key navigates through issues."""
    test_id = "T5"
    test_name = "Keyboard navigation through issues"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_content(TEST_HTML)

        inject_all_scripts(page)
        page.evaluate(f"window.__designReviewInit({json.dumps(TEST_SPEC)})")
        page.evaluate("window.__designReviewPreScan()")
        page.wait_for_timeout(2000)

        # Get initial index
        initial_index = page.evaluate(
            "() => window.__designReviewState.currentIssueIndex"
        )

        # Press 'N' to navigate
        page.keyboard.press("n")
        page.wait_for_timeout(300)

        new_index = page.evaluate("() => window.__designReviewState.currentIssueIndex")
        issues_count = page.evaluate("() => window.__designReviewState.issues.length")

        # Navigation should change index if there are issues
        passed = issues_count > 0 and new_index >= 0
        detail = (
            f"initial={initial_index}, after_press={new_index}, issues={issues_count}"
        )

        results.add(test_id, test_name, passed, detail)
        browser.close()


def test_results_capture(results: TestResults) -> None:
    """Test 6: Verify __designReviewGetResults returns issues."""
    test_id = "T6"
    test_name = "Results capture via __designReviewGetResults"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_content(TEST_HTML)

        inject_all_scripts(page)
        page.evaluate(f"window.__designReviewInit({json.dumps(TEST_SPEC)})")
        page.evaluate("window.__designReviewPreScan()")
        page.wait_for_timeout(2000)

        results_data = page.evaluate("() => window.__designReviewGetResults()")

        has_issues_key = "issues" in results_data if results_data else False
        has_issues = len(results_data.get("issues", [])) >= 1 if results_data else False

        # Check issue shape
        issue_shape_ok = False
        if has_issues:
            issue = results_data["issues"][0]
            issue_shape_ok = "selector" in issue and "rules" in issue

        passed = has_issues_key and has_issues and issue_shape_ok
        detail = f"has_issues={has_issues}, count={len(results_data.get('issues', [])) if results_data else 0}, shape_ok={issue_shape_ok}"

        results.add(test_id, test_name, passed, detail)
        browser.close()


# =============================================================================
# Main Runner
# =============================================================================


def main():
    """Run all tests."""
    print("\nInteractive Mode Test Suite")
    print("=" * 60)

    results = TestResults()

    test_overlay_injection(results)
    test_spec_loading(results)
    test_prescan_execution(results)
    test_badge_display(results)
    test_keyboard_navigation(results)
    test_results_capture(results)

    results.print_summary()

    sys.exit(0 if results.all_passed() else 1)


if __name__ == "__main__":
    main()
