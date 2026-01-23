# Phase 3.5: CSS Selector Output & Markdown Export

**Priority**: Medium  
**Estimated Effort**: 3-4 hours  
**Reference**: `PERF-PLAN.md` lines 467-729

## Overview

Enhance design review output with CSS selectors and markdown export to bridge the gap between visual issues and source code location.

**Three components**:
1. CSS selector generation for issue elements
2. Enhanced legend with selectors in annotated screenshots
3. Markdown export with `--markdown` CLI flag

---

## Task Breakdown

### Task 1: Add `_is_utility_class()` helper

**File**: `.claude/skills/design-review/scripts/annotator.py`

**Goal**: Create helper function to identify utility/framework CSS classes that should be skipped when building selectors.

**Implementation**:
```python
def _is_utility_class(class_name: str) -> bool:
    """Check if class is a utility/framework class to skip."""
    utility_patterns = [
        "flex", "grid", "p-", "m-", "text-", "bg-", "w-", "h-",  # Tailwind
        "col-", "row-", "d-",  # Bootstrap
        "css-",  # Emotion/styled-components
    ]
    return any(class_name.startswith(p) for p in utility_patterns)
```

**Verification**:
- [x] Function exists in `annotator.py`
- [x] Returns `True` for utility classes: `flex`, `p-4`, `text-sm`, `bg-blue-500`, `col-6`, `css-abc123`
- [x] Returns `False` for semantic classes: `sidebar`, `header`, `btn-primary`, `card-title`
- [x] `lsp_diagnostics` clean

---

### Task 2: Add `_build_parent_selector()` helper

**File**: `.claude/skills/design-review/scripts/annotator.py`

**Goal**: Create helper to build a CSS selector fragment for a parent element.

**Implementation**:
```python
def _build_parent_selector(parent: dict) -> str:
    """Build selector for a parent element."""
    if parent.get("id"):
        return f"#{parent['id']}"
    
    tag = parent.get("tag", "div")
    classes = parent.get("classes", [])
    
    if classes:
        main_class = next((c for c in classes if not _is_utility_class(c)), None)
        if main_class:
            return f"{tag}.{main_class}"
    
    return tag
```

**Verification**:
- [x] Function exists in `annotator.py`
- [x] Returns `#my-id` for `{"id": "my-id", "tag": "div"}`
- [x] Returns `div.sidebar` for `{"tag": "div", "classes": ["sidebar", "flex"]}`
- [x] Returns `div` for `{"tag": "div", "classes": ["flex", "p-4"]}`
- [x] `lsp_diagnostics` clean

---

### Task 3: Add `_generate_css_selector()` function

**File**: `.claude/skills/design-review/scripts/annotator.py`

**Goal**: Create main CSS selector generation function that combines element info into a unique selector.

**Implementation**:
```python
def _generate_css_selector(element_info: dict) -> str:
    """
    Generate a unique CSS selector for an element.
    
    Prioritizes:
    1. ID selector (if unique): #my-id
    2. Class chain: .parent > .child.specific
    3. Tag + attributes: button[aria-label="Close"]
    4. Nth-child fallback: div > p:nth-child(2)
    """
    # If element has a unique ID, use it
    if element_info.get("id"):
        return f"#{element_info['id']}"
    
    # Build selector from tag and classes
    parts = []
    tag = element_info.get("tag", "div")
    classes = element_info.get("classes", [])
    
    if classes:
        # Use most specific classes (filter out utility classes)
        specific_classes = [c for c in classes if not _is_utility_class(c)]
        if specific_classes:
            selector = f"{tag}.{'.'.join(specific_classes[:2])}"
        else:
            selector = tag
    else:
        selector = tag
    
    # Add parent context for uniqueness
    parent_chain = element_info.get("parent_chain", [])
    for parent in reversed(parent_chain[:3]):  # Max 3 parents
        parent_selector = _build_parent_selector(parent)
        if parent_selector:
            parts.append(parent_selector)
    
    parts.append(selector)
    return " > ".join(parts)
```

**Verification**:
- [x] Function exists in `annotator.py`
- [x] Returns `#unique-id` for element with ID
- [x] Returns `div.sidebar > button.close-btn` for nested element with classes
- [x] Returns `nav > ul > li` for element chain without meaningful classes
- [x] Limits parent chain to 3 levels
- [x] `lsp_diagnostics` clean

---

### Task 4: Update `Issue` dataclass with selector field

**File**: `.claude/skills/design-review/scripts/annotator.py`

**Goal**: Add `css_selector` field to the `Issue` dataclass.

**Changes**:
```python
@dataclass
class Issue:
    """An issue to annotate on the screenshot."""

    id: int
    severity: str
    description: str
    bounding_box: Optional[BoundingBox] = None
    check_id: str = ""
    pillar: str = ""
    element: str = ""
    css_selector: str = ""  # NEW FIELD
    element_info: Optional[dict] = None  # NEW FIELD for raw element data
```

**Verification**:
- [x] `Issue` dataclass has `css_selector` field
- [x] `Issue` dataclass has `element_info` field
- [x] `Issue.from_dict()` parses `cssSelector` and `elementInfo` from input dict
- [x] `lsp_diagnostics` clean

---

### Task 5: Update `draw_legend()` to include selectors

**File**: `.claude/skills/design-review/scripts/annotator.py`

**Goal**: Enhance the legend rendering to show CSS selector on a second line for each issue.

**Current format**:
```
#1: Color contrast too low
```

**New format**:
```
#1: Color contrast too low
    → .hero-section > p.subtitle
```

**Changes to `draw_legend()`**:
- Add selector line below each issue description
- Use gray color for selector (lighter than main text)
- Increase `LEGEND_LINE_HEIGHT` calculation to account for 2-line entries
- Truncate long selectors with `...`

**Verification**:
- [x] Legend shows selector on second line when `css_selector` is present
- [x] Selector line is indented with arrow prefix `→`
- [x] Long selectors are truncated
- [x] Issues without selector show single line (no empty selector line)
- [x] `lsp_diagnostics` clean

---

### Task 6: Update `design_review.py` to extract element info

**File**: `.claude/skills/design-review/scripts/design_review.py`

**Goal**: Modify the review flow to capture element metadata (tag, id, classes, parent chain) from Playwright and pass to annotator.

**Changes**:
1. In the element inspection JavaScript, capture:
   - `tag`: element tag name
   - `id`: element ID (if any)
   - `classes`: array of class names
   - `parent_chain`: array of parent element info (up to 3 levels)

2. Store this in issue dict as `elementInfo`

3. Before calling annotator, generate `cssSelector` using `_generate_css_selector()`

**Verification**:
- [x] Review output includes `elementInfo` for each issue
- [x] Review output includes `cssSelector` for each issue
- [x] `report.json` contains selector data
- [x] `lsp_diagnostics` clean

---

### Task 7: Add `--markdown` CLI flag

**File**: `.claude/skills/design-review/scripts/design_review.py`

**Goal**: Add `--markdown` argument to `review` and `compare` subcommands.

**Changes**:
```python
# In review subparser
parser.add_argument(
    "--markdown",
    action="store_true",
    help="Generate issues.md companion file with full selector details"
)

# In compare subparser (same)
```

**Verification**:
- [x] `--markdown` flag accepted by `review` subcommand
- [x] `--markdown` flag accepted by `compare` subcommand
- [x] `--help` shows the new flag
- [x] `lsp_diagnostics` clean

---

### Task 8: Implement `generate_markdown_export()` function

**File**: `.claude/skills/design-review/scripts/design_review.py`

**Goal**: Create function to generate `issues.md` from review results.

**Signature**:
```python
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
```

**Output format** (see PERF-PLAN.md lines 541-623 for full spec):
```markdown
# Design Review Issues

**URL**: http://localhost:3000  
**Reviewed**: 2026-01-23 14:32:00  
**Spec**: default.md  
**Total Issues**: 3 (1 blocking, 2 major)

---

## Issue #1: Color contrast too low

| Property | Value |
|----------|-------|
| **Severity** | major |
| **Pillar** | Quality Craft |
| **Check** | color-contrast |
| **CSS Selector** | `.hero-section > p.subtitle` |

**Description**: Contrast ratio 3.2:1 does not meet WCAG AA minimum

**Recommendation**: Darken text color to `#595959` or darker

---

## Quick Fix Reference

Copy these selectors for your AI assistant:

```
.hero-section > p.subtitle
nav.main-nav > ul > li:nth-child(3) > a
```
```

**Verification**:
- [x] Function exists in `design_review.py`
- [x] Generates valid markdown format
- [x] Includes all issue fields (severity, pillar, check, selector, description)
- [x] Includes Quick Fix Reference section with all selectors
- [x] Handles issues without selectors gracefully
- [x] `lsp_diagnostics` clean

---

### Task 9: Wire `--markdown` flag to export function

**File**: `.claude/skills/design-review/scripts/design_review.py`

**Goal**: Call `generate_markdown_export()` when `--markdown` flag is passed.

**Changes in `cmd_review()`**:
```python
# After generating report
if args.markdown:
    md_path = session_dir / "issues.md"
    md_result = generate_markdown_export(
        review_result=result,
        output_path=md_path,
        url=args.url,
        spec_name=args.spec or "default.md",
    )
    if md_result.get("ok"):
        result["artifacts"]["markdown"] = str(md_path)
```

**Same changes in `cmd_compare()`**.

**Verification**:
- [x] `uv run design_review.py review <url> --markdown` creates `issues.md`
- [x] `issues.md` appears in session directory alongside other artifacts
- [x] `result["artifacts"]["markdown"]` contains path
- [x] JSON output includes markdown path
- [x] `lsp_diagnostics` clean

---

### Task 10: Update SKILL.md documentation

**File**: `.claude/skills/design-review/SKILL.md`

**Goal**: Document the new `--markdown` flag and enhanced selector output.

**Sections to add/update**:
1. Add `--markdown` to CLI reference
2. Add example usage with `--markdown`
3. Document `issues.md` output format
4. Explain CSS selector generation

**Verification**:
- [x] `--markdown` flag documented
- [x] Example usage included
- [x] Output format explained
- [x] Integration with compact mode mentioned

---

### Task 11: Add unit tests for selector generation

**File**: `.claude/skills/design-review/scripts/test_annotator.py` (new file)

**Goal**: Create test cases for the selector generation helpers.

**Test cases**:
```python
def test_is_utility_class():
    assert _is_utility_class("flex") == True
    assert _is_utility_class("p-4") == True
    assert _is_utility_class("sidebar") == False

def test_build_parent_selector():
    assert _build_parent_selector({"id": "main"}) == "#main"
    assert _build_parent_selector({"tag": "nav", "classes": ["main-nav"]}) == "nav.main-nav"

def test_generate_css_selector():
    # Test ID priority
    assert _generate_css_selector({"id": "unique"}) == "#unique"
    
    # Test class chain
    result = _generate_css_selector({
        "tag": "button",
        "classes": ["close-btn", "flex"],
        "parent_chain": [{"tag": "div", "classes": ["sidebar"]}]
    })
    assert result == "div.sidebar > button.close-btn"
```

**Verification**:
- [x] Test file exists
- [x] All test cases pass: `uv run pytest test_annotator.py`
- [x] Edge cases covered (empty classes, no parents, utility-only classes)

---

## Dependency Graph

```
Task 1 (_is_utility_class)
    ↓
Task 2 (_build_parent_selector) ←── depends on Task 1
    ↓
Task 3 (_generate_css_selector) ←── depends on Task 1, 2
    ↓
Task 4 (Issue dataclass update)
    ↓
Task 5 (draw_legend enhancement) ←── depends on Task 4
    ↓
Task 6 (element info extraction) ←── depends on Task 3, 4
    ↓
Task 7 (--markdown CLI flag)
    ↓
Task 8 (generate_markdown_export)
    ↓
Task 9 (wire flag to export) ←── depends on Task 7, 8
    ↓
Task 10 (documentation) ←── depends on all above
    ↓
Task 11 (unit tests) ←── depends on Task 1, 2, 3
```

## Execution Order

**Batch 1** (no dependencies):
- Task 1: `_is_utility_class()`

**Batch 2** (depends on Batch 1):
- Task 2: `_build_parent_selector()`

**Batch 3** (depends on Batch 2):
- Task 3: `_generate_css_selector()`
- Task 4: Issue dataclass update (parallel)

**Batch 4** (depends on Batch 3):
- Task 5: draw_legend enhancement
- Task 6: element info extraction
- Task 7: --markdown CLI flag (parallel)

**Batch 5** (depends on Batch 4):
- Task 8: generate_markdown_export()

**Batch 6** (depends on Batch 5):
- Task 9: wire flag to export

**Batch 7** (depends on all):
- Task 10: documentation
- Task 11: unit tests

---

## Files Modified

| File | Tasks |
|------|-------|
| `.claude/skills/design-review/scripts/annotator.py` | 1, 2, 3, 4, 5 |
| `.claude/skills/design-review/scripts/design_review.py` | 6, 7, 8, 9 |
| `.claude/skills/design-review/SKILL.md` | 10 |
| `.claude/skills/design-review/scripts/test_annotator.py` (new) | 11 |

---

## Success Criteria

Phase 3.5 is complete when:
- [x] `uv run design_review.py review <url> --annotate` shows selectors in legend
- [x] `uv run design_review.py review <url> --markdown` generates `issues.md`
- [x] Combined: `uv run design_review.py review <url> --compact --annotate --markdown` works
- [x] All unit tests pass
- [x] Documentation updated
- [x] `lsp_diagnostics` clean on all modified files
