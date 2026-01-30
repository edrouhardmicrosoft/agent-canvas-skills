# Phase 3: Interactive Mode - Agent Canvas

## TL;DR

> **Quick Summary**: Wire existing components to enable automatic page scanning and badge display on page load, with keyboard navigation through detected issues.
> 
> **Deliverables**:
> - Pre-scan page on load with automatic issue detection
> - Numbered badges on elements with issues (using existing annotation_layer.js)
> - Enhanced "Next Issue" navigation through pre-scanned issues
> - Report generation on browser close includes all issues
> - Integration tests for interactive mode
> 
> **Estimated Effort**: Medium (mostly wiring, ~270 lines new code)
> **Parallel Execution**: YES - 2 waves
> **Critical Path**: Task 1 → Task 2 → Task 3 → Task 4 → Task 5 → Task 6 → Task 7

---

## Context

### Original Request
Implement Phase 3 (Interactive Mode) of the Agent Canvas project - the spec-driven design QA system. Phases 1-2 (Core Review Engine, Annotation & Output) are complete.

### Interview Summary
**Key Discussions**:
- Agent Canvas reviews UI against design specs, generates annotated screenshots
- Interactive mode should scan page on load, show badges, enable navigation
- Reuse existing annotation_layer.js badge system rather than building new
- 7 tasks identified covering CLI wiring through integration tests

**Research Findings**:
- `cmd_interactive()` already substantial (lines 1485-1799) - loads spec, launches browser, injects overlay
- `review_overlay.js` has 4 hardcoded checks: color-contrast, touch-targets, focus-indicators, alt-text
- `annotation_layer.js` has full badge system subscribing to `review.issue_found` events
- **Gap**: annotation_layer.js NOT currently injected in interactive mode
- Test pattern exists in `test_canvas_edit.py` (custom runner with Playwright, NOT pytest)

### Metis Review
**Identified Gaps** (addressed):
- Pre-scan scope unclear → Default to common element types (buttons, inputs, images, links, landmarks)
- Badge display policy unclear → Progressive animation with batch limit
- Annotation layer not injected → Task 1 now includes injection
- Navigation only works with user-added issues → Task 5 fixes this
- Edge cases (empty page, huge pages) → Added scan limits and empty state handling

---

## Work Objectives

### Core Objective
Enable automatic page scanning on load with visual issue highlighting, making design review feedback immediate and navigable without requiring manual element selection.

### Concrete Deliverables
- Modified `design_review.py`: injects annotation_layer.js, triggers pre-scan
- New `preScanPage()` function in `review_overlay.js`
- Updated `navigateIssue()` to work with pre-scanned issues
- Report includes all pre-scanned issues (not just user-added)
- `test_interactive_mode.py` integration test file

### Definition of Done
- [ ] `design_review.py interactive --url <test_url>` shows badges automatically on page load
- [ ] Pressing 'N' navigates through issues without manual "Add to Review"
- [ ] Browser close generates report.json with all issues
- [ ] All integration tests pass headless

### Must Have
- Pre-scan executes on page load
- Badges appear via existing annotation_layer.js
- Keyboard navigation through issues (N key)
- Report generation includes all issues
- Tests for critical paths

### Must NOT Have (Guardrails)
- NO new badge implementation (use annotation_layer.js)
- NO new spec check implementations (use existing 4 checks)
- NO changes to canvas_bus.py (shared dependency)
- NO blocking UI during scan (use chunked traversal)
- NO CLI flags for scan depth/timeout/filters (hardcode sensible defaults)
- NO iframe or Shadow DOM traversal (keep simple)
- NO re-scan on navigation/AJAX (out of scope for Phase 3)

---

## Verification Strategy (MANDATORY)

### Test Decision
- **Infrastructure exists**: YES (test_canvas_edit.py exists with patterns)
- **User wants tests**: YES (Task 7 is explicitly integration tests)
- **Framework**: Custom Python runner with Playwright (matches test_canvas_edit.py pattern - NOT pytest)

### Automated Verification Only (NO User Intervention)

**CRITICAL ARCHITECTURE NOTE**: The integration tests use Playwright DIRECTLY (not via external attachment). Tests follow the `test_canvas_edit.py` pattern:
1. Create a Playwright browser/page in the test
2. Load test HTML content
3. Inject scripts via `page.evaluate()`
4. Assert results via `page.evaluate()`

This is NOT the same as trying to "attach" to a browser launched by `design_review.py interactive`. The tests are self-contained.

**By Deliverable Type:**

| Type | Verification Tool | Automated Procedure |
|------|------------------|---------------------|
| **Browser/UI** | Self-contained Playwright test | Test creates browser, injects scripts, asserts JS state |
| **Python CLI** | Bash subprocess with JSON output parsing | Run command, capture JSON output, validate fields |
| **Report files** | Bash + jq | Parse JSON, validate fields |

---

## Critical Data Model Definition

### Issue Object Shape (MUST match `addToReview()` pattern)

Pre-scanned issues MUST use the same shape as `addToReview()` creates (see `review_overlay.js:834-840`):

```javascript
{
    selector: string,              // CSS selector from bus.generateSelector(el)
    timestamp: string,             // ISO timestamp
    element: {                     // From bus.getElementInfo(el) or { tag: el.tagName }
        tag: string,
        boundingBox?: { x, y, width, height }
    },
    compliance: object,            // Full compliance result
    rules: [                       // Non-passing rules (status !== 'pass')
        {
            id: string,            // Check ID (e.g., 'touch-targets')
            name: string,          // Human-readable name
            status: string,        // 'fail' or 'warning'
            severity: string,      // 'blocking', 'major', 'minor'
            message: string,       // Description of issue
            pillar?: string        // Design pillar (optional)
        }
    ]
}
```

### Warning Inclusion Policy (CRITICAL DECISION)

**INCLUDE warnings in pre-scan results.** Rationale:
- Matches existing `addToReview()` behavior: `rules: compliance.rules.filter(r => r.status !== 'pass')` includes both 'fail' AND 'warning'
- Users should see all potential issues, not just failures
- Warnings have lower severity ('minor') so they sort appropriately
- Consistency with manual "Add to Review" flow is essential

**DO NOT filter out warnings** - this maintains behavioral consistency.

### Duplicate Prevention (CRITICAL)

Pre-scan MUST update `reviewState.reviewedElements` for each scanned element with issues to prevent duplicates:

```javascript
// In preScanPage(), after creating issue:
reviewState.reviewedElements.add(selector);  // Prevents duplicate from manual "Add to Review"
```

This matches the deduplication mechanism in `addToReview()` at line 829.

**Python report processing expects** (see `design_review.py:1682-1700`):
- `review_results["issues"]` = array of issue objects
- Each issue has `selector` and `rules` array
- `rules` contains objects with `id`, `severity`, `message`

**Navigation expects** (see `review_overlay.js:894-900`):
- `reviewState.issues[i].selector` resolvable via `document.querySelector()`

### Browser Close Results Capture (CRITICAL FIX)

**PROBLEM**: Current code at lines 1647-1657 tries to call `page.evaluate()` AFTER `page.is_closed()` becomes true, causing `review_results = None`.

**SOLUTION**: Modify the event polling loop to periodically snapshot results BEFORE browser closes:

```python
# In cmd_interactive() event polling loop (around line 1621-1645)
last_results = None  # Add this before the while loop

while True:
    try:
        if page.is_closed():
            break
        
        # Periodically snapshot results while page is still open
        try:
            last_results = page.evaluate(
                "() => window.__designReviewGetResults && window.__designReviewGetResults()"
            )
        except Exception:
            pass  # Ignore evaluation errors during polling
        
        # ... existing event drain code ...
        
        time.sleep(0.1)
    except Exception:
        break

# Use last_results instead of trying to evaluate after close
review_results = last_results
```

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 1 (Start Immediately):
├── Task 1: Inject annotation_layer.js in cmd_interactive [no dependencies]
└── Task 2: Pass spec checks to overlay dynamically [no dependencies]

Wave 2 (After Wave 1):
├── Task 3: Add preScanPage() function [depends: 1, 2]
├── Task 4: Wire pre-scan trigger in cmd_interactive [depends: 3]
└── Task 5: Update navigateIssue() for pre-scanned issues [depends: 3]

Wave 3 (After Wave 2):
└── Task 6: Fix browser-close results capture + include all issues [depends: 4, 5]

Wave 4 (After Wave 3):
└── Task 7: Integration tests [depends: 6]

Critical Path: 1 → 3 → 4 → 6 → 7
Parallel Speedup: ~30% faster than sequential
```

### Dependency Matrix

| Task | Depends On | Blocks | Can Parallelize With |
|------|------------|--------|---------------------|
| 1 | None | 3, 4 | 2 |
| 2 | None | 3 | 1 |
| 3 | 1, 2 | 4, 5 | None |
| 4 | 3 | 6 | 5 |
| 5 | 3 | 6 | 4 |
| 6 | 4, 5 | 7 | None |
| 7 | 6 | None | None (final) |

### Agent Dispatch Summary

| Wave | Tasks | Recommended Agents |
|------|-------|-------------------|
| 1 | 1, 2 | delegate_task(category="quick", load_skills=["playwright"], run_in_background=true) × 2 |
| 2 | 3, 4, 5 | delegate_task(category="unspecified-low", load_skills=["playwright"]) - sequential due to shared file |
| 3 | 6 | delegate_task(category="quick", load_skills=["playwright"]) |
| 4 | 7 | delegate_task(category="unspecified-low", load_skills=["playwright"]) |

---

## TODOs

- [ ] 1. Inject annotation_layer.js in cmd_interactive

  **What to do**:
  - Load `annotation_layer.js` content in `cmd_interactive()` similar to how `review_overlay.js` is loaded
  - Inject it after canvas_bus_js but BEFORE review_overlay.js
  - Verify annotation layer initializes and subscribes to `review.issue_found` events

  **Must NOT do**:
  - Do NOT modify annotation_layer.js itself
  - Do NOT change the injection order of canvas_bus (must be first)

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Single file modification, straightforward code addition
  - **Skills**: [`playwright`]
    - `playwright`: Needed to verify browser-side injection works
  - **Skills Evaluated but Omitted**:
    - `frontend-ui-ux`: Not UI design work, just Python wiring

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Task 2)
  - **Blocks**: Tasks 3, 4
  - **Blocked By**: None (can start immediately)

  **References**:

  **Pattern References** (existing code to follow):
  - `.claude/skills/design-review/scripts/design_review.py:1512-1517` - How `overlay_js_path` is defined and read
  - `.claude/skills/design-review/scripts/design_review.py:1519-1532` - How canvas_bus.py is imported and CANVAS_BUS_JS extracted
  - `.claude/skills/design-review/scripts/design_review.py:1607-1612` - Injection order: canvas_bus first, then overlay

  **File References** (files to modify/read):
  - `.claude/skills/design-review/scripts/design_review.py` - Add annotation_layer.js loading around line 1512
  - `.claude/skills/canvas-edit/scripts/annotation_layer.js` - Source file to inject (DO NOT MODIFY)

  **Why Each Reference Matters**:
  - Lines 1512-1517: Shows pattern for loading JS file: `Path / "filename.js"`, `.read_text()`
  - Lines 1519-1532: Shows how to import from relative skill path
  - Lines 1607-1612: Shows injection via `page.evaluate(js_content)` - add annotation_layer between canvas_bus and review_overlay
  - Annotation layer path: `SCRIPT_DIR.parent.parent / "canvas-edit" / "scripts" / "annotation_layer.js"`

  **Acceptance Criteria**:

  **Automated Verification (Self-contained Playwright test):**
  ```python
  # In test file, create browser and verify injection:
  from playwright.sync_api import sync_playwright
  
  with sync_playwright() as p:
      browser = p.chromium.launch(headless=True)
      page = browser.new_page()
      page.set_content("<button>Test</button>")
      
      # Load scripts in correct order (simulating what cmd_interactive does)
      page.evaluate(canvas_bus_js)
      page.evaluate(annotation_layer_js)  # NEW - should be injected
      page.evaluate(review_overlay_js)
      
      # Assert annotation layer initialized
      result = page.evaluate("() => window.__annotationLayerActive === true")
      assert result == True, "Annotation layer not initialized"
      
      browser.close()
  ```

  **Evidence to Capture:**
  - [ ] Test output showing `window.__annotationLayerActive === true`
  - [ ] No console errors during injection

  **Commit**: YES
  - Message: `feat(design-review): inject annotation layer in interactive mode`
  - Files: `design_review.py`
  - Pre-commit: `python -c "import sys; sys.path.insert(0, '.claude/skills/design-review/scripts'); from design_review import *"` (syntax check)

---

- [ ] 2. Verify spec checks pass to overlay correctly

  **What to do**:
  - Verify `spec_data` in `cmd_interactive()` at line 1535-1547 contains full check details
  - Verify `__designReviewInit(spec_data)` at line 1614-1617 passes checks correctly
  - In `review_overlay.js`, verify `reviewState.spec` is populated by `__designReviewInit()` 
  - NOTE: The spec is ALREADY being passed - this task is VERIFICATION and minor fixes if needed

  **Must NOT do**:
  - Do NOT add new check types
  - Do NOT implement new check logic
  - Do NOT change check execution from JS to Python

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Primarily verification, may need small fixes
  - **Skills**: [`playwright`]
    - `playwright`: Needed to verify spec data arrives in browser
  - **Skills Evaluated but Omitted**:
    - `frontend-ui-ux`: Not UI work

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Task 1)
  - **Blocks**: Task 3
  - **Blocked By**: None (can start immediately)

  **References**:

  **Pattern References** (existing code to follow):
  - `.claude/skills/design-review/scripts/design_review.py:1535-1547` - spec_data construction with check details
  - `.claude/skills/design-review/scripts/design_review.py:1614-1617` - `__designReviewInit(spec_data)` call
  - `.claude/skills/design-review/scripts/review_overlay.js:24-32` - reviewState object with spec field

  **Spec References** (data format):
  - `.claude/skills/design-review/specs/default.md` - Default spec format with checks

  **Why Each Reference Matters**:
  - Lines 1535-1547: spec_data already includes `name` and `checks` array with id, pillar, severity, description, config
  - Lines 1614-1617: Shows the init call that passes spec_data to the overlay
  - Lines 24-32: Shows `reviewState.spec = null` - needs to be set by `__designReviewInit()`

  **Acceptance Criteria**:

  **Automated Verification (Self-contained Playwright test):**
  ```python
  # In test file:
  TEST_SPEC = {
      "name": "test-spec",
      "checks": [
          {"id": "touch-targets", "pillar": "Quality Craft", "severity": "major", "description": "Touch targets", "config": {"minimum_size": 44}}
      ]
  }
  
  with sync_playwright() as p:
      browser = p.chromium.launch(headless=True)
      page = browser.new_page()
      page.set_content("<button>Test</button>")
      
      # Inject scripts
      page.evaluate(canvas_bus_js)
      page.evaluate(review_overlay_js)
      
      # Initialize with test spec data
      page.evaluate(f"window.__designReviewInit({json.dumps(TEST_SPEC)})")
      
      # Assert spec is stored
      spec = page.evaluate("() => window.__designReviewState.spec")
      assert spec["name"] == "test-spec"
      assert len(spec["checks"]) == 1
      assert spec["checks"][0]["id"] == "touch-targets"
      
      browser.close()
  ```

  **Evidence to Capture:**
  - [ ] JSON output of `window.__designReviewState.spec` showing check details
  - [ ] Verify check count matches spec file (21 checks in default.md)

  **Commit**: YES (if changes needed)
  - Message: `feat(design-review): ensure spec checks passed to overlay correctly`
  - Files: `review_overlay.js` (if __designReviewInit needs to store spec)
  - Pre-commit: `node --check .claude/skills/design-review/scripts/review_overlay.js`

---

- [ ] 3. Add preScanPage() function to review_overlay.js

  **What to do**:
  - Create `preScanPage()` function (expose as `window.__designReviewPreScan`) that:
    1. Selects scannable elements: `button, a, input, select, textarea, img, [role], h1-h6, nav, main, header, footer`
    2. Limits to first 500 elements (performance guard)
    3. Iterates elements, calls `checkElementCompliance(el)` on each
    4. For each element with non-passing rules (fail OR warning), creates issue object matching `addToReview()` shape
    5. Updates `reviewState.reviewedElements.add(selector)` to prevent duplicates from manual "Add to Review"
    6. Pushes issue to `reviewState.issues`
    7. Emits `review.issue_found` via canvas bus for each non-passing rule (both fail AND warning - per Warning Inclusion Policy)
    8. Uses `setTimeout` chunking (process 50 elements per frame) to avoid blocking UI
  - After scan completes, push scan completion event to `window.__designReviewEvents` array (for Python logging):
    ```javascript
    window.__designReviewEvents.push({
        type: 'review.scan_complete',
        source: 'design-review',
        timestamp: new Date().toISOString(),
        payload: { issueCount: reviewState.issues.length, elementsScanned: count }
    });
    ```
  - If no issues found, still push the scan_complete event with issueCount: 0

  **Must NOT do**:
  - Do NOT scan ALL elements (use selector list above)
  - Do NOT block UI during scan
  - Do NOT traverse iframes or Shadow DOM
  - Do NOT add new check implementations

  **Recommended Agent Profile**:
  - **Category**: `unspecified-low`
    - Reason: Moderate complexity, new function but following existing patterns
  - **Skills**: [`playwright`, `frontend-ui-ux`]
    - `playwright`: For testing scan behavior
    - `frontend-ui-ux`: For non-blocking UI pattern (setTimeout chunking)
  - **Skills Evaluated but Omitted**:
    - `git-master`: Not complex git operations

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 2 (sequential after Wave 1)
  - **Blocks**: Tasks 4, 5
  - **Blocked By**: Tasks 1, 2

  **References**:

  **Pattern References** (existing code to follow):
  - `.claude/skills/design-review/scripts/review_overlay.js:550-641` - `checkElementCompliance(el)` function to call per element
  - `.claude/skills/design-review/scripts/review_overlay.js:834-840` - Issue object shape created by `addToReview()`
  - `.claude/skills/design-review/scripts/review_overlay.js:856-866` - How to emit `review.issue_found` events via bus

  **API References** (event contracts):
  - Canvas bus `review.issue_found` event shape (see lines 857-865):
    ```javascript
    {
        id: `${selector}-${rule.id}`,  // Unique ID
        checkId: rule.id,               // e.g., 'touch-targets'
        severity: rule.severity,        // 'blocking', 'major', 'minor'
        element: selector,              // CSS selector string
        description: rule.message,      // Human-readable message
        pillar: rule.pillar || '',      // Design pillar
        boundingBox: issue.element?.boundingBox  // For badge positioning
    }
    ```
  - Annotation layer listens at `.claude/skills/canvas-edit/scripts/annotation_layer.js:1015-1017` (subscribes to `review.issue_found`)

  **Why Each Reference Matters**:
  - Lines 550-641: This is the exact function to call; returns `{ status, rules }` where rules have pass/fail status
  - Lines 834-840: Issue shape MUST match this for navigation and report generation to work
  - Lines 856-866: Event emission pattern that triggers badge creation in annotation_layer

  **Acceptance Criteria**:

  **Automated Verification (Self-contained Playwright test):**
  ```python
  # Test page with intentional violations:
  TEST_HTML = """
  <html>
    <button style="width:20px;height:20px">X</button>
    <img src="test.png">
    <a href="#">Link</a>
  </html>
  """
  
  # Minimum spec payload for tests (checks that preScanPage can evaluate):
  TEST_SPEC = {
      "name": "test-spec",
      "checks": [
          {"id": "touch-targets", "pillar": "Quality Craft", "severity": "major", "description": "Touch target size", "config": {"minimum_size": 44}},
          {"id": "alt-text", "pillar": "Quality Craft", "severity": "major", "description": "Alt text", "config": {}},
          {"id": "focus-indicators", "pillar": "Quality Craft", "severity": "minor", "description": "Focus indicators", "config": {}},
          {"id": "color-contrast", "pillar": "Quality Craft", "severity": "major", "description": "Color contrast", "config": {"minimum_ratio": 4.5}}
      ]
  }
  
  with sync_playwright() as p:
      browser = p.chromium.launch(headless=True)
      page = browser.new_page()
      page.set_content(TEST_HTML)
      
      # Inject all scripts
      page.evaluate(canvas_bus_js)
      page.evaluate(annotation_layer_js)
      page.evaluate(review_overlay_js)
      page.evaluate(f"window.__designReviewInit({json.dumps(TEST_SPEC)})")
      
      # Trigger pre-scan
      page.evaluate("window.__designReviewPreScan && window.__designReviewPreScan()")
      page.wait_for_timeout(2000)  # Wait for async scan
      
      # Assert issues were found
      issues_count = page.evaluate("() => window.__designReviewState.issues.length")
      assert issues_count >= 1, f"Expected at least 1 issue, got {issues_count}"
      
      # Assert badges appeared (annotation layer creates these with class .annotation-badge)
      badges = page.evaluate("() => document.querySelectorAll('.annotation-badge').length")
      assert badges >= 1, f"Expected badges, got {badges}"
      
      browser.close()
  ```

  **Evidence to Capture:**
  - [ ] Test output showing issues found count
  - [ ] Test output showing badge count > 0

  **Commit**: YES
  - Message: `feat(design-review): add preScanPage() for automatic issue detection`
  - Files: `review_overlay.js`
  - Pre-commit: `node --check .claude/skills/design-review/scripts/review_overlay.js`

---

- [ ] 4. Wire pre-scan trigger in cmd_interactive

  **What to do**:
  - After `window.__designReviewInit(spec_data)` call at line 1614-1617, add call to trigger pre-scan
  - Add: `page.evaluate("window.__designReviewPreScan && window.__designReviewPreScan()")`
  - Ensure proper sequencing: canvas_bus → annotation_layer → review_overlay → init → preScan
  - Add brief wait after preScan for async completion: `page.wait_for_timeout(1000)`
  - Log scan start/complete events to session

  **Must NOT do**:
  - Do NOT call preScan before overlay is fully initialized
  - Do NOT add excessive timeout/retry logic (keep simple)

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: 5-10 lines of code addition
  - **Skills**: [`playwright`]
    - `playwright`: To understand page.evaluate patterns
  - **Skills Evaluated but Omitted**:
    - `frontend-ui-ux`: Not UI work

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Task 5)
  - **Parallel Group**: Wave 2
  - **Blocks**: Task 6
  - **Blocked By**: Task 3

  **References**:

  **Pattern References** (existing code to follow):
  - `.claude/skills/design-review/scripts/design_review.py:1607-1617` - Current injection and init sequence
  - `.claude/skills/design-review/scripts/design_review.py:1619` - `log_event()` call pattern

  **Why Each Reference Matters**:
  - Lines 1607-1617: Shows exact location to add preScan call (after line 1617)
  - Line 1619: Shows `log_event("overlay_injected", {...})` pattern for logging

  **Acceptance Criteria**:

  **Automated Verification (Code review + self-contained Playwright test):**
  
  1. **Code review**: Verify `design_review.py` has preScan call after __designReviewInit:
     ```python
     # Around line 1617, should see:
     page.evaluate(f"window.__designReviewInit && window.__designReviewInit({json.dumps(spec_data)})")
     page.evaluate("window.__designReviewPreScan && window.__designReviewPreScan()")
     ```
  
  2. **Self-contained test** (same pattern as Task 3/5 - tests full injection sequence):
     ```python
     # Simulates the injection sequence from cmd_interactive()
     with sync_playwright() as p:
         browser = p.chromium.launch(headless=True)
         page = browser.new_page()
         page.set_content("<button style='width:10px'>X</button>")
         
         # Injection sequence matching cmd_interactive():
         page.evaluate(canvas_bus_js)
         page.evaluate(annotation_layer_js)  # NEW in this phase
         page.evaluate(review_overlay_js)
         page.evaluate(f"window.__designReviewInit({json.dumps(TEST_SPEC)})")
         page.evaluate("window.__designReviewPreScan()")  # NEW in this phase
         page.wait_for_timeout(2000)
         
         # Assert scan completed (issues populated)
         issues = page.evaluate("() => window.__designReviewState.issues.length")
         assert issues >= 1, "PreScan should have found issues"
         
         browser.close()
     ```

  **Evidence to Capture:**
  - [ ] Code diff showing preScan call added after init
  - [ ] JSON output showing scan events logged

  **Commit**: YES (group with Task 5)
  - Message: `feat(design-review): trigger pre-scan on page load`
  - Files: `design_review.py`
  - Pre-commit: `python -c "import sys; sys.path.insert(0, '.claude/skills/design-review/scripts'); from design_review import *"`

---

- [ ] 5. Update navigateIssue() for pre-scanned issues

  **What to do**:
  - Review `navigateIssue(direction)` at lines 883-910 in review_overlay.js
  - Currently it ALREADY navigates through `reviewState.issues` array (line 894)
  - Since preScanPage() will populate `reviewState.issues`, navigation should work automatically
  - VERIFY this works, fix if needed:
    - Ensure `document.querySelector(issue.selector)` works for pre-scanned issues
    - Ensure `showCompliancePanel(el)` is called after navigation (already at line 900)

  **Must NOT do**:
  - Do NOT remove existing navigation behavior
  - Do NOT change keyboard shortcuts

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Likely just verification, minimal changes needed
  - **Skills**: [`playwright`]
    - `playwright`: To verify keyboard navigation works
  - **Skills Evaluated but Omitted**:
    - `frontend-ui-ux`: Not visual design work

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Task 4)
  - **Parallel Group**: Wave 2
  - **Blocks**: Task 6
  - **Blocked By**: Task 3

  **References**:

  **Pattern References** (existing code to follow):
  - `.claude/skills/design-review/scripts/review_overlay.js:883-910` - `navigateIssue(direction)` implementation
  - `.claude/skills/design-review/scripts/review_overlay.js:894-900` - Element lookup and scrollIntoView
  - `.claude/skills/design-review/scripts/review_overlay.js:773-809` - `showCompliancePanel(el)` function

  **Why Each Reference Matters**:
  - Lines 883-910: Shows navigation already uses `reviewState.issues` - should work with pre-scanned issues
  - Lines 894-900: Shows `document.querySelector(issue.selector)` - must ensure selectors are valid
  - Lines 773-809: Compliance panel display - already called at line 900

  **Acceptance Criteria**:

  **Automated Verification (Self-contained Playwright test):**
  ```python
  # Multi-issue test page
  TEST_HTML = """
  <html><body style="height:2000px">
    <button id="btn1" style="width:10px">A</button>
    <div style="height:500px"></div>
    <button id="btn2" style="width:10px">B</button>
    <div style="height:500px"></div>
    <img id="img1" src="x.png">
  </body></html>
  """
  
  # Spec with checks that will trigger on test elements
  TEST_SPEC = {
      "name": "test-spec",
      "checks": [
          {"id": "touch-targets", "pillar": "Quality Craft", "severity": "major", "description": "Touch targets", "config": {"minimum_size": 44}},
          {"id": "alt-text", "pillar": "Quality Craft", "severity": "major", "description": "Alt text", "config": {}}
      ]
  }
  
  with sync_playwright() as p:
      browser = p.chromium.launch(headless=True)
      page = browser.new_page()
      page.set_content(TEST_HTML)
      
      # Inject and initialize
      page.evaluate(canvas_bus_js)
      page.evaluate(annotation_layer_js)
      page.evaluate(review_overlay_js)
      page.evaluate(f"window.__designReviewInit({json.dumps(TEST_SPEC)})")
      page.evaluate("window.__designReviewPreScan()")
      page.wait_for_timeout(2000)
      
      # Get initial scroll position
      initial_scroll = page.evaluate("() => window.scrollY")
      
      # Press 'N' to navigate
      page.keyboard.press('n')
      page.wait_for_timeout(500)
      
      # Assert scroll changed (element scrolled into view)
      new_scroll = page.evaluate("() => window.scrollY")
      # Note: May or may not scroll depending on which issue is first
      
      # Assert currentIssueIndex changed
      index = page.evaluate("() => window.__designReviewState.currentIssueIndex")
      assert index >= 0, "Navigation did not update currentIssueIndex"
      
      browser.close()
  ```

  **Evidence to Capture:**
  - [ ] Test output showing navigation works
  - [ ] currentIssueIndex changes on 'N' key press

  **Commit**: YES (group with Task 4)
  - Message: `feat(design-review): verify navigation works with pre-scanned issues`
  - Files: `review_overlay.js` (if fixes needed)
  - Pre-commit: `node --check .claude/skills/design-review/scripts/review_overlay.js`

---

- [ ] 6. Fix browser-close results capture + include all issues in report

  **What to do**:
  - **CRITICAL FIX**: Modify event polling loop (lines 1621-1645) to periodically snapshot results WHILE page is still open
  - Add `last_results = None` before the while loop
  - Inside the loop, before `time.sleep(0.1)`, add snapshot: `last_results = page.evaluate("() => window.__designReviewGetResults && window.__designReviewGetResults()")`
  - After loop exits, use `review_results = last_results` instead of trying to evaluate on closed page
  - Verify `__designReviewGetResults()` at line 994-1004 returns all issues (it returns `reviewState.issues` which includes pre-scanned)

  **Must NOT do**:
  - Do NOT change report.json schema
  - Do NOT add new fields to report
  - Do NOT try to evaluate JS after page is closed

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Targeted fix to specific code section
  - **Skills**: [`playwright`]
    - `playwright`: To understand page lifecycle
  - **Skills Evaluated but Omitted**:
    - `frontend-ui-ux`: Not visual work

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 3 (sequential)
  - **Blocks**: Task 7
  - **Blocked By**: Tasks 4, 5

  **References**:

  **Pattern References** (existing code to follow):
  - `.claude/skills/design-review/scripts/design_review.py:1621-1645` - Event polling loop (FIX HERE)
  - `.claude/skills/design-review/scripts/design_review.py:1647-1657` - Current (broken) results capture
  - `.claude/skills/design-review/scripts/design_review.py:1680-1700` - Report processing expects `review_results["issues"]`
  - `.claude/skills/design-review/scripts/review_overlay.js:994-1004` - `__designReviewGetResults()` returns `reviewState.issues`

  **Output References** (expected format):
  - `.canvas/reviews/<sessionId>/report.json` - Final report location
  - `.canvas/reviews/<sessionId>/annotated.png` - Annotated screenshot

  **Why Each Reference Matters**:
  - Lines 1621-1645: This is where periodic snapshotting must be added
  - Lines 1647-1657: Current code tries to evaluate after close - this fails and causes `review_results = None`
  - Lines 1680-1700: Shows what format report processing expects - must not break this
  - Lines 994-1004: Shows `__designReviewGetResults()` already returns `reviewState.issues` - no changes needed there

  **Acceptance Criteria**:

  **Automated Verification (Self-contained Playwright test for results capture):**
  ```python
  # This test verifies __designReviewGetResults() returns issues correctly
  # The actual browser-close fix in design_review.py is verified by code review
  
  TEST_HTML = "<button style='width:10px'>X</button><img src='x.png'>"
  TEST_SPEC = {
      "name": "test-spec",
      "checks": [
          {"id": "touch-targets", "pillar": "Quality Craft", "severity": "major", "description": "Touch targets", "config": {"minimum_size": 44}},
          {"id": "alt-text", "pillar": "Quality Craft", "severity": "major", "description": "Alt text", "config": {}}
      ]
  }
  
  with sync_playwright() as p:
      browser = p.chromium.launch(headless=True)
      page = browser.new_page()
      page.set_content(TEST_HTML)
      
      # Full injection sequence
      page.evaluate(canvas_bus_js)
      page.evaluate(annotation_layer_js)
      page.evaluate(review_overlay_js)
      page.evaluate(f"window.__designReviewInit({json.dumps(TEST_SPEC)})")
      page.evaluate("window.__designReviewPreScan()")
      page.wait_for_timeout(2000)
      
      # Get results (simulating what design_review.py does)
      results = page.evaluate("() => window.__designReviewGetResults()")
      
      # Assert results structure
      assert "issues" in results, "Results should have 'issues' key"
      assert len(results["issues"]) >= 1, "Should have at least 1 issue"
      
      # Assert issue shape matches what Python expects
      issue = results["issues"][0]
      assert "selector" in issue, "Issue should have 'selector'"
      assert "rules" in issue, "Issue should have 'rules'"
      
      browser.close()
  ```
  
  **Code review checklist for browser-close fix:**
  - [ ] `last_results = None` added before while loop (around line 1621)
  - [ ] Inside loop: `last_results = page.evaluate("() => window.__designReviewGetResults && window.__designReviewGetResults()")` 
  - [ ] After loop: `review_results = last_results` (replace lines 1647-1657)

  **Evidence to Capture:**
  - [ ] Code diff showing periodic snapshot in polling loop
  - [ ] report.json content showing issues array populated

  **Commit**: YES
  - Message: `fix(design-review): capture results before browser close, include all pre-scanned issues`
  - Files: `design_review.py`
  - Pre-commit: `python -c "import sys; sys.path.insert(0, '.claude/skills/design-review/scripts'); from design_review import *"`

---

- [ ] 7. Integration tests for interactive mode

  **What to do**:
  - Create `.claude/skills/design-review/tests/test_interactive_mode.py` following `test_canvas_edit.py` pattern (custom runner, NOT pytest)
  - **Test runner pattern** (see `test_canvas_edit.py:1-100`):
    - Direct Playwright usage (not pytest-playwright)
    - Helper functions: `get_scripts_dir()`, `load_canvas_bus_js()`, `inject_all_scripts()`
    - Test functions that create browser, run assertions, return pass/fail
    - `main()` function that runs all tests and reports results
  - Test cases:
    1. `test_overlay_injection`: Verifies annotation layer and review overlay are injected
    2. `test_spec_loading`: Verifies spec is passed to overlay correctly
    3. `test_prescan_execution`: Verifies issues are detected on page load
    4. `test_badge_display`: Verifies badges appear for detected issues
    5. `test_keyboard_navigation`: Verifies 'N' key navigates issues
    6. `test_results_capture`: Verifies `__designReviewGetResults()` returns issues
  - Use data: URLs or `page.set_content()` with intentional violations for test pages
  - Run headless (default)

  **Must NOT do**:
  - Do NOT use pytest (use custom runner like test_canvas_edit.py)
  - Do NOT require external test URLs (use inline HTML)
  - Do NOT add new dependencies

  **Recommended Agent Profile**:
  - **Category**: `unspecified-low`
    - Reason: New file creation, multiple test cases, follows existing patterns closely
  - **Skills**: [`playwright`]
    - `playwright`: Primary skill for browser testing
  - **Skills Evaluated but Omitted**:
    - `frontend-ui-ux`: Not UI design work

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 4 (final)
  - **Blocks**: None
  - **Blocked By**: Task 6

  **References**:

  **Pattern References** (existing code to follow):
  - `.claude/skills/canvas-edit/tests/test_canvas_edit.py:1-27` - Imports and module docstring
  - `.claude/skills/canvas-edit/tests/test_canvas_edit.py:34-89` - Helper functions (`get_scripts_dir`, `load_*_js`, `inject_all_scripts`)
  - `.claude/skills/canvas-edit/tests/test_canvas_edit.py:84-89` - `inject_all_scripts(page)` pattern
  - `.claude/skills/canvas-edit/tests/test_canvas_edit.py:92-114` - `setup_test_page()` with default HTML

  **Test Data References** (inline HTML for tests):
  - Touch-target violation: `<button style="width:10px;height:10px">X</button>`
  - Alt-text violation: `<img src="test.png">`
  - Pass case: `<button style="width:48px;height:48px">OK</button>`

  **Why Each Reference Matters**:
  - Lines 1-27: Shows import structure for Playwright sync API
  - Lines 34-89: Shows script loading helpers to adapt for design-review
  - Lines 84-89: Shows `inject_all_scripts()` calling `page.evaluate()` for each script
  - Lines 92-114: Shows test page setup with default content

  **Acceptance Criteria**:

  **Automated Verification (Run test file):**
  ```bash
  cd .claude/skills/design-review
  python tests/test_interactive_mode.py
  
  # Expected output:
  # Running test_overlay_injection... PASS
  # Running test_spec_loading... PASS
  # Running test_prescan_execution... PASS
  # Running test_badge_display... PASS
  # Running test_keyboard_navigation... PASS
  # Running test_results_capture... PASS
  # 
  # Results: 6/6 tests passed
  ```

  **Evidence to Capture:**
  - [ ] Full test output showing all tests pass
  - [ ] Test file location: `.claude/skills/design-review/tests/test_interactive_mode.py`

  **Commit**: YES
  - Message: `test(design-review): add integration tests for interactive mode`
  - Files: `tests/test_interactive_mode.py`
  - Pre-commit: `python .claude/skills/design-review/tests/test_interactive_mode.py` (run tests)

---

## Commit Strategy

| After Task | Message | Files | Verification |
|------------|---------|-------|--------------|
| 1 | `feat(design-review): inject annotation layer in interactive mode` | design_review.py | syntax check |
| 2 | `feat(design-review): ensure spec checks passed to overlay correctly` | review_overlay.js | syntax check |
| 3 | `feat(design-review): add preScanPage() for automatic issue detection` | review_overlay.js | syntax check |
| 4+5 | `feat(design-review): trigger pre-scan and verify navigation` | design_review.py, review_overlay.js | syntax check |
| 6 | `fix(design-review): capture results before browser close` | design_review.py | syntax check |
| 7 | `test(design-review): add integration tests for interactive mode` | test_interactive_mode.py | run tests |

---

## Success Criteria

### Verification Commands
```bash
# Run integration tests (primary verification)
cd .claude/skills/design-review
python tests/test_interactive_mode.py
# Expected: 6/6 tests pass

# Manual smoke test (optional)
python scripts/design_review.py interactive --url "data:text/html,<button style='width:10px'>X</button>"
# Expected: Browser opens, badge appears on button, 'N' navigates, close generates report
```

### Final Checklist
- [ ] All "Must Have" present:
  - [ ] Pre-scan executes on page load
  - [ ] Badges appear via annotation_layer.js (`.annotation-badge` elements)
  - [ ] 'N' key navigates issues
  - [ ] Report includes all issues (captured before browser close)
  - [ ] Tests pass (6/6)
- [ ] All "Must NOT Have" absent:
  - [ ] No new badge implementation
  - [ ] No new check implementations
  - [ ] No canvas_bus.py changes
  - [ ] No UI blocking during scan
  - [ ] No new CLI flags
- [ ] All tests pass headless
