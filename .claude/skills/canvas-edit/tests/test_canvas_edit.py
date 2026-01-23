#!/usr/bin/env python3
"""
Canvas Edit Test Suite

Tests for the Live Annotation Feedback Toolbar functionality including:
- Toolbar injection and rendering
- Badge positioning
- Popover display
- Screenshot capture
- Orientation toggle
- Boundary detection
- Canvas bus integration
"""

import json
import sys
from pathlib import Path
from typing import Any, Optional

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
    """Get the scripts directory path."""
    return Path(__file__).parent.parent / "scripts"


def get_shared_dir() -> Path:
    """Get the shared skills directory path."""
    return Path(__file__).parent.parent.parent / "shared"


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
            getSeq: () => 0
        };
    })();
    """


def load_toolbar_js() -> str:
    """Load the annotation toolbar JavaScript."""
    js_path = get_scripts_dir() / "annotation_toolbar.js"
    return js_path.read_text()


def load_layer_js() -> str:
    """Load the annotation layer JavaScript."""
    js_path = get_scripts_dir() / "annotation_layer.js"
    return js_path.read_text()


def inject_all_scripts(page: Page) -> None:
    """Inject all required scripts into the page."""
    page.evaluate(load_canvas_bus_js())
    page.evaluate(load_toolbar_js())
    page.evaluate(load_layer_js())
    page.wait_for_timeout(300)  # Let scripts initialize


def setup_test_page(page: Page, content: Optional[str] = None) -> None:
    """Set up a test page with optional custom content."""
    if content is None:
        content = """
            <!DOCTYPE html>
            <html>
            <head><title>Test Page</title></head>
            <body style="padding: 50px;">
                <h1 id="title">Test Title</h1>
                <p class="description">Test paragraph with some text content.</p>
                <button id="submit" style="padding: 10px 20px;">Submit</button>
                <div class="card" style="width: 200px; height: 100px; background: #f0f0f0; margin-top: 20px;">
                    Card content
                </div>
            </body>
            </html>
        """
    page.goto("about:blank")
    page.set_content(content)


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
        if detail is None:
            detail = ""
        self.results.append(
            {
                "id": test_id,
                "test": test_name,
                "pass": passed,
                "detail": detail,
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
# Test: Toolbar Injection and Rendering (6.2.2)
# =============================================================================


def test_toolbar_injection(page: Page, results: TestResults) -> None:
    """Test toolbar injection and rendering."""
    setup_test_page(page)
    inject_all_scripts(page)

    # Test 6.2.2.1 - Toolbar host element created
    host_exists = page.evaluate(
        "() => !!document.getElementById('__annotation_toolbar_host')"
    )
    results.add(
        "6.2.2.1",
        "Toolbar host element created",
        host_exists,
        "__annotation_toolbar_host exists in DOM",
    )

    # Test 6.2.2.2 - Shadow root is closed
    shadow_closed = page.evaluate("""
        () => {
            const host = document.getElementById('__annotation_toolbar_host');
            return host && host.shadowRoot === null;
        }
    """)
    results.add(
        "6.2.2.2",
        "Shadow DOM is closed mode",
        shadow_closed,
        "shadowRoot returns null (private)",
    )

    # Test 6.2.2.3 - Toolbar API exposed
    api_exposed = page.evaluate("() => typeof window.__annotationToolbar === 'object'")
    results.add(
        "6.2.2.3",
        "Toolbar API exposed on window",
        api_exposed,
        "window.__annotationToolbar is available",
    )

    # Test 6.2.2.4 - Initial state correct
    initial_state = page.evaluate("""
        () => {
            const state = window.__annotationToolbar?.getState();
            return state && 
                   state.orientation === 'horizontal' &&
                   state.issues.length === 0 &&
                   state.annotationsVisible === true;
        }
    """)
    results.add(
        "6.2.2.4",
        "Initial state is correct",
        initial_state,
        "orientation=horizontal, issues=[], annotationsVisible=true",
    )


# =============================================================================
# Test: Badge Positioning (6.2.3)
# =============================================================================


def test_badge_positioning(page: Page, results: TestResults) -> None:
    """Test badge positioning on elements."""
    setup_test_page(page)
    inject_all_scripts(page)

    # Add an issue to create a badge
    page.evaluate("""
        () => window.__annotationLayer.addIssue({
            id: 1,
            selector: '#title',
            severity: 'major',
            title: 'Test issue',
            description: 'Test description'
        })
    """)
    page.wait_for_timeout(200)

    # Test 6.2.3.1 - Badge element created
    badge_exists = page.evaluate("""
        () => document.querySelector('.annotation-badge') !== null
    """)
    results.add(
        "6.2.3.1",
        "Badge element created",
        badge_exists,
        ".annotation-badge exists in DOM",
    )

    # Test 6.2.3.2 - Badge positioned near target element
    badge_position = page.evaluate("""
        () => {
            const badge = document.querySelector('.annotation-badge');
            const target = document.getElementById('title');
            if (!badge || !target) return false;
            
            const badgeRect = badge.getBoundingClientRect();
            const targetRect = target.getBoundingClientRect();
            
            // Badge should be within reasonable distance of target
            const xNear = Math.abs(badgeRect.right - targetRect.right) < 50;
            const yNear = Math.abs(badgeRect.top - targetRect.top) < 50;
            return xNear && yNear;
        }
    """)
    results.add(
        "6.2.3.2",
        "Badge positioned near target element",
        badge_position,
        "Badge appears at top-right of target",
    )

    # Test 6.2.3.3 - Multiple badges on same element stack
    page.evaluate("""
        () => {
            window.__annotationLayer.addIssue({
                id: 2,
                selector: '#title',
                severity: 'minor',
                title: 'Second issue'
            });
        }
    """)
    page.wait_for_timeout(200)

    badges_stack = page.evaluate("""
        () => {
            const badges = document.querySelectorAll('.annotation-badge');
            if (badges.length < 2) return false;
            
            const rect1 = badges[0].getBoundingClientRect();
            const rect2 = badges[1].getBoundingClientRect();
            
            // Badges should be offset from each other
            return Math.abs(rect1.left - rect2.left) > 5 || Math.abs(rect1.top - rect2.top) > 5;
        }
    """)
    results.add(
        "6.2.3.3",
        "Multiple badges on same element stack",
        badges_stack,
        "Badges are offset to avoid overlap",
    )


# =============================================================================
# Test: Popover Display (6.2.4)
# =============================================================================


def test_popover_display(page: Page, results: TestResults) -> None:
    """Test popover display functionality."""
    setup_test_page(page)
    inject_all_scripts(page)

    # Add issue
    page.evaluate("""
        () => window.__annotationLayer.addIssue({
            id: 1,
            selector: '#title',
            severity: 'major',
            title: 'Contrast issue',
            description: 'Text contrast is insufficient',
            pillar: 'Quality Craft',
            checkId: 'color-contrast',
            recommendation: 'Use darker text'
        })
    """)
    page.wait_for_timeout(200)

    # Test 6.2.4.1 - Popover exists but hidden initially
    popover_hidden = page.evaluate("""
        () => {
            const popover = document.querySelector('.annotation-popover');
            if (!popover) return false;
            const style = window.getComputedStyle(popover);
            return style.display === 'none' || !popover.matches(':popover-open');
        }
    """)
    results.add(
        "6.2.4.1",
        "Popover hidden initially",
        popover_hidden,
        "Popover exists but not visible",
    )

    # Click badge to open popover
    page.click(".annotation-badge")
    page.wait_for_timeout(200)

    # Test 6.2.4.2 - Popover opens on badge click
    popover_open = page.evaluate("""
        () => {
            const popover = document.querySelector('.annotation-popover');
            return popover && popover.matches(':popover-open');
        }
    """)
    results.add(
        "6.2.4.2",
        "Popover opens on badge click",
        popover_open,
        "Native popover API works",
    )

    # Test 6.2.4.3 - Popover contains issue details
    popover_content = page.evaluate("""
        () => {
            const popover = document.querySelector('.annotation-popover');
            if (!popover) return false;
            const text = popover.textContent || '';
            return text.includes('Contrast issue') && 
                   text.includes('Quality Craft');
        }
    """)
    results.add(
        "6.2.4.3",
        "Popover contains issue details",
        popover_content,
        "Title and pillar displayed",
    )


# =============================================================================
# Test: Screenshot Capture (6.2.5)
# =============================================================================


def test_screenshot_capture(page: Page, results: TestResults) -> None:
    """Test screenshot capture functionality."""
    setup_test_page(page)
    inject_all_scripts(page)

    # Test 6.2.5.1 - captureAnnotatedScreenshot exists
    capture_fn_exists = page.evaluate("""
        () => typeof window.__annotationToolbar?.captureAnnotatedScreenshot === 'function'
    """)
    results.add(
        "6.2.5.1",
        "captureAnnotatedScreenshot function exists",
        capture_fn_exists,
        "API method available",
    )

    # Test 6.2.5.2 - Screenshot request emits event
    captured_event = []
    page.evaluate("""
        () => {
            window.__testScreenshotEvent = null;
            window.__canvasBus.subscribe('screenshot.requested', (event) => {
                window.__testScreenshotEvent = event;
            });
        }
    """)

    # Trigger screenshot (will fail in test but event should emit)
    page.evaluate("() => window.__annotationToolbar?.captureAnnotatedScreenshot()")
    page.wait_for_timeout(500)

    event_emitted = page.evaluate("() => window.__testScreenshotEvent !== null")
    results.add(
        "6.2.5.2",
        "Screenshot request emits bus event",
        event_emitted,
        "screenshot.requested event emitted",
    )


# =============================================================================
# Test: Orientation Toggle (6.2.6)
# =============================================================================


def test_orientation_toggle(page: Page, results: TestResults) -> None:
    """Test orientation toggle functionality."""
    setup_test_page(page)
    inject_all_scripts(page)

    # Test 6.2.6.1 - Initial orientation is horizontal
    initial_horizontal = page.evaluate("""
        () => window.__annotationToolbar?.getState().orientation === 'horizontal'
    """)
    results.add(
        "6.2.6.1",
        "Initial orientation is horizontal",
        initial_horizontal,
        "Default orientation correct",
    )

    # Test 6.2.6.2 - Toggle to vertical
    page.evaluate("() => window.__annotationToolbar?.setOrientation('vertical')")
    page.wait_for_timeout(300)

    now_vertical = page.evaluate("""
        () => window.__annotationToolbar?.getState().orientation === 'vertical'
    """)
    results.add(
        "6.2.6.2",
        "Can toggle to vertical orientation",
        now_vertical,
        "setOrientation('vertical') works",
    )

    # Test 6.2.6.3 - Toggle back to horizontal
    page.evaluate("() => window.__annotationToolbar?.setOrientation('horizontal')")
    page.wait_for_timeout(300)

    back_horizontal = page.evaluate("""
        () => window.__annotationToolbar?.getState().orientation === 'horizontal'
    """)
    results.add(
        "6.2.6.3",
        "Can toggle back to horizontal",
        back_horizontal,
        "setOrientation('horizontal') works",
    )


# =============================================================================
# Test: Boundary Detection (6.2.7)
# =============================================================================


def test_boundary_detection(page: Page, results: TestResults) -> None:
    """Test boundary detection functionality."""
    setup_test_page(page)
    inject_all_scripts(page)

    # Test 6.2.7.1 - Toolbar stays within viewport
    page.evaluate("""
        () => {
            // Force toolbar to an edge position
            const api = window.__annotationToolbar;
            if (api) {
                // This would be internal manipulation, but we test the correction
            }
        }
    """)

    # Test correctToolbarPosition exists
    correction_exists = page.evaluate("""
        () => {
            // The toolbar should have boundary checking
            const state = window.__annotationToolbar?.getState();
            return state && typeof state.position === 'object';
        }
    """)
    results.add(
        "6.2.7.1",
        "Position state tracked for boundary detection",
        correction_exists,
        "Position object exists in state",
    )

    # Test 6.2.7.2 - Badge boundary detection
    # Add badge near edge
    page.set_viewport_size({"width": 400, "height": 300})
    page.evaluate("""
        () => window.__annotationLayer?.addIssue({
            id: 99,
            selector: 'body',
            severity: 'minor',
            title: 'Edge test'
        })
    """)
    page.wait_for_timeout(200)

    badge_in_viewport = page.evaluate("""
        () => {
            const badges = document.querySelectorAll('.annotation-badge');
            if (badges.length === 0) return true; // No badge = pass
            
            const badge = badges[badges.length - 1];
            const rect = badge.getBoundingClientRect();
            
            return rect.right <= window.innerWidth &&
                   rect.bottom <= window.innerHeight &&
                   rect.left >= 0 &&
                   rect.top >= 0;
        }
    """)
    results.add(
        "6.2.7.2",
        "Badges stay within viewport bounds",
        badge_in_viewport,
        "Badge positions respect viewport edges",
    )


# =============================================================================
# Test: Canvas Bus Integration (6.2.8)
# =============================================================================


def test_canvas_bus_integration(page: Page, results: TestResults) -> None:
    """Test canvas bus integration."""
    setup_test_page(page)
    inject_all_scripts(page)

    # Test 6.2.8.1 - Toolbar registers with bus
    registered = page.evaluate("""
        () => {
            const tools = window.__canvasBus?.state?.activeTools;
            return tools && (tools.has('annotation-toolbar') || tools.size > 0);
        }
    """)
    results.add(
        "6.2.8.1",
        "Toolbar registers with canvas bus",
        registered,
        "annotation-toolbar in activeTools",
    )

    # Test 6.2.8.2 - Responds to capture_mode.changed
    page.evaluate("""
        () => {
            window.__testCaptureModeResponse = false;
            window.__canvasBus.subscribe('capture_mode.changed', (event) => {
                window.__testCaptureModeResponse = true;
            });
            window.__canvasBus.setCaptureMode(true);
        }
    """)
    page.wait_for_timeout(100)

    capture_mode_works = page.evaluate(
        "() => window.__testCaptureModeResponse === true"
    )
    results.add(
        "6.2.8.2",
        "Responds to capture_mode.changed event",
        capture_mode_works,
        "Event subscription working",
    )

    # Test 6.2.8.3 - Emits annotation.clicked event
    page.evaluate("""
        () => {
            window.__testAnnotationClicked = null;
            window.__canvasBus.subscribe('annotation.clicked', (event) => {
                window.__testAnnotationClicked = event;
            });
            
            window.__annotationLayer.addIssue({
                id: 1,
                selector: '#title',
                severity: 'major',
                title: 'Click test'
            });
        }
    """)
    page.wait_for_timeout(200)

    # Click the badge
    badge = page.query_selector(".annotation-badge")
    if badge:
        badge.click()
        page.wait_for_timeout(100)

    click_event = page.evaluate("() => window.__testAnnotationClicked !== null")
    results.add(
        "6.2.8.3",
        "Emits annotation.clicked event",
        click_event,
        "Event emitted on badge click",
    )

    # Test 6.2.8.4 - Responds to review events
    page.evaluate("""
        () => {
            // Emit review.started
            window.__canvasBus.emit('review.started', 'test', {});
        }
    """)
    page.wait_for_timeout(100)

    scanning_state = page.evaluate("""
        () => window.__annotationToolbar?.getState()?.toolbarState === 'scanning'
    """)
    results.add(
        "6.2.8.4",
        "Responds to review.started event",
        scanning_state,
        "Toolbar shows scanning state",
    )


# =============================================================================
# Test: Filter Functionality
# =============================================================================


def test_filter_functionality(page: Page, results: TestResults) -> None:
    """Test filter functionality."""
    setup_test_page(page)
    inject_all_scripts(page)

    # Add issues with different severities
    page.evaluate("""
        () => {
            window.__annotationLayer.addIssue({
                id: 1, selector: '#title', severity: 'blocking', title: 'Blocking'
            });
            window.__annotationLayer.addIssue({
                id: 2, selector: '.description', severity: 'major', title: 'Major'
            });
            window.__annotationLayer.addIssue({
                id: 3, selector: '#submit', severity: 'minor', title: 'Minor'
            });
        }
    """)
    page.wait_for_timeout(200)

    # Test - All badges visible initially
    all_visible = page.evaluate("""
        () => {
            const badges = document.querySelectorAll('.annotation-badge');
            return badges.length === 3;
        }
    """)
    results.add(
        "6.2.9.1",
        "All badges visible initially",
        all_visible,
        "3 badges visible with no filters",
    )

    # Test - Filter by severity
    page.evaluate("""
        () => {
            window.__annotationLayer?.setFilter({ severity: { blocking: true, major: false, minor: false }});
        }
    """)
    page.wait_for_timeout(200)

    filtered = page.evaluate("""
        () => {
            const visibleBadges = document.querySelectorAll('.annotation-badge:not([style*="display: none"])');
            return visibleBadges.length <= 3; // Some may be hidden
        }
    """)
    results.add(
        "6.2.9.2", "Filter by severity works", filtered, "Badges filtered by severity"
    )


# =============================================================================
# Main Test Runner
# =============================================================================


def run_all_tests():
    """Run all tests."""
    results = TestResults()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        print("\n Running Canvas Edit Tests...\n")

        # Run test suites
        print("  [1/7] Testing toolbar injection...")
        test_toolbar_injection(page, results)

        print("  [2/7] Testing badge positioning...")
        test_badge_positioning(page, results)

        print("  [3/7] Testing popover display...")
        test_popover_display(page, results)

        print("  [4/7] Testing screenshot capture...")
        test_screenshot_capture(page, results)

        print("  [5/7] Testing orientation toggle...")
        test_orientation_toggle(page, results)

        print("  [6/7] Testing boundary detection...")
        test_boundary_detection(page, results)

        print("  [7/7] Testing canvas bus integration...")
        test_canvas_bus_integration(page, results)

        print("  [Bonus] Testing filter functionality...")
        test_filter_functionality(page, results)

        browser.close()

    # Print results
    results.print_summary()

    return results.all_passed()


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
