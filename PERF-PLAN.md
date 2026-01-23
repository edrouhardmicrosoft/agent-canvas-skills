# Agent Canvas Performance Optimization Plan

> **Version**: 1.2  
> **Created**: 2026-01-22  
> **Last Updated**: 2026-01-23  
> **Status**: Draft  
> **Target**: Reduce agent prompt context to <80K tokens

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Problem Statement](#problem-statement)
   - [Current State Analysis](#current-state-analysis)
   - [Token Usage Breakdown](#token-usage-breakdown)
   - [Root Causes](#root-causes)
3. [Target Goals](#target-goals)
4. [Proposed Solution Architecture](#proposed-solution-architecture)
   - [Part 1: Compact Output Mode](#part-1-compact-output-mode-quick-win)
   - [Part 2: Sub-Agent Architecture](#part-2-sub-agent-architecture-scalable-solution)
5. [Implementation Plan](#implementation-plan)
   - [Phase 1: Compact Flag for agent_eyes.py](#phase-1-compact-flag-for-agent_eyespy)
   - [Phase 2: Remove Base64 from Session Storage](#phase-2-remove-base64-from-session-storage)
   - [Phase 3: Compact Flag for design_review.py](#phase-3-compact-flag-for-design_reviewpy)
   - [Phase 3.5: CSS Selector Output & Markdown Export](#phase-35-css-selector-output--markdown-export)
   - [Phase 4: Create Sub-Agent Wrapper Scripts](#phase-4-create-sub-agent-wrapper-scripts)
   - [Phase 5: Update Documentation](#phase-5-update-documentation)
   - [Phase 6: Token Budget Tracking](#phase-6-token-budget-tracking)
6. [Design Decisions](#design-decisions)
7. [Technical Specifications](#technical-specifications)
   - [Compact Mode API](#compact-mode-api)
   - [Sub-Agent Communication Protocol](#sub-agent-communication-protocol)
   - [Token Budget Utilities](#token-budget-utilities)
8. [Visual Design Guidelines](#visual-design-guidelines)
   - [Color Palette](#color-palette)
   - [Annotation Visual Style](#annotation-visual-style)
   - [Annotated Screenshot Layout](#annotated-screenshot-layout)
   - [Review Output Format](#review-output-format)
   - [Accessibility Considerations](#accessibility-considerations)
   - [Integration with Implementation Phases](#integration-with-implementation-phases)
9. [Success Metrics](#success-metrics)
10. [File Structure After Implementation](#file-structure-after-implementation)
11. [Risk Assessment](#risk-assessment)
12. [Next Steps](#next-steps)

---

## Executive Summary

The Agent Canvas design-review tool currently generates prompts that frequently exceed LLM context windows. Analysis of actual sessions reveals the primary culprit: **base64-encoded screenshots embedded directly in session.json**, which can consume 100K-470K tokens for a single image.

This document outlines a two-part solution:
1. **Quick Win**: Add `--compact` flags to reduce output size by 90%+
2. **Scalable Solution**: Decompose into specialized sub-agents with controlled token budgets

**Expected Outcome**: All agent interactions stay under **80K tokens** while maintaining full functionality.

---

## Problem Statement

### Current State Analysis

The agent-canvas-review (design-review skill) tool captures comprehensive web page data:

| Data Type | Current Storage | Source |
|-----------|-----------------|--------|
| Screenshots | Base64 in session.json | `agent_eyes.py:take_screenshot()` |
| DOM Snapshots | Full tree in session.json | `agent_eyes.py:get_dom_snapshot()` |
| Accessibility Results | Full axe-core output | `agent_eyes.py:run_a11y_scan()` |
| Session Event Logs | Array in session.json | `canvas_bus.py:changeLog[]` |

### Token Usage Breakdown

Analysis of actual session files in `.canvas/sessions/`:

| Session ID | Total Tokens | Screenshot Tokens | DOM Tokens | A11y Tokens | Other |
|------------|--------------|-------------------|------------|-------------|-------|
| `ses-8c7492be1187` | **769K** | 471K (61%) | ~150K | ~100K | ~48K |
| `ses-cb26a41c31ef` | **84K** | 52K | ~20K | ~8K | ~4K |
| `ses-77484903fb81` | **52K** | 32K | ~12K | ~5K | ~3K |
| Review sessions | ~850 | 0 | 0 | ~500 | ~350 |

<details>
<summary>Session Analysis Methodology</summary>

Token estimation using the standard `chars/4` heuristic:

```python
def estimate_tokens(text: str) -> int:
    """Rough token estimate: ~4 chars per token for English text."""
    return len(text) // 4
```

For base64 content, the ratio is closer to `chars/3.5` due to the limited character set.

Actual session file from `ses-8c7492be1187`:
- `beforeScreenshot` field: ~1.88MB base64 string
- Token estimate: 1,880,000 / 4 ≈ **470,000 tokens** from one screenshot alone

</details>

### Root Causes

1. **Base64 Screenshot Embedding (MAJOR - 61% of tokens)**
   - Location: `agent_canvas.py:write_session_artifact()` stores `before_screenshot_base64`
   - Location: Selection events store `screenshot.base64` in payload
   - Impact: A single full-page screenshot can be 500KB-3MB base64, consuming 100K-470K tokens

2. **Unbounded DOM Snapshots (~20% of tokens)**
   - Location: `agent_eyes.py:get_dom_snapshot()` 
   - Current limits: `depth=5`, `max_children=20`, text truncated to 100 chars
   - Issue: Complex pages (React SPAs, web components) generate massive trees despite limits

3. **Full Accessibility Trees (~13% of tokens)**
   - Location: `agent_eyes.py:run_a11y_scan()` returns full axe-core results
   - Issue: Each violation includes full HTML of affected nodes

4. **Session Event Logs (~6% of tokens)**
   - Location: `canvas_bus.py:changeLog[]` accumulates all events
   - Issue: Long interactive sessions can have hundreds of events

5. **No Token Budget Management**
   - No awareness of context limits when constructing prompts
   - No truncation or summarization strategies

---

## Target Goals

| Metric | Current State | Target |
|--------|---------------|--------|
| Maximum session tokens | 769K | **<80K** |
| Average review tokens | ~50K | **<20K** |
| Screenshot in context | 471K tokens | **0** (file ref only) |
| DOM snapshot | Unbounded | **<5K tokens** |
| A11y results | Full tree | **Summary + top 10** |
| Event logs | Unbounded | **Last 20 events** |

---

## Proposed Solution Architecture

### Part 1: Compact Output Mode (Quick Win)

Add `--compact` flag to skills that enforces token-efficient output:

```
┌─────────────────────────────────────────────────────────────────┐
│                    COMPACT MODE GUARANTEES                      │
├─────────────────────────────────────────────────────────────────┤
│  1. Screenshots: File path only (never base64)                  │
│  2. DOM depth: Max 3 levels, 10 children per node               │
│  3. A11y: Counts + top 3 critical issues only                   │
│  4. Events: Last 20 events only                                 │
│  5. Text: Truncated to 50 chars                                 │
└─────────────────────────────────────────────────────────────────┘
```

<details>
<summary>Compact Mode Implementation Example</summary>

```python
# agent_eyes.py - new compact mode

def get_full_context(
    page: "Page",
    selector: Optional[str] = None,
    include_screenshot: bool = True,
    format_type: str = "json",
    compact: bool = False,  # NEW PARAMETER
) -> dict:
    """
    Get comprehensive context including screenshot, a11y, DOM, and description.
    
    When compact=True:
    - Screenshot saved to file, only path returned (not base64)
    - DOM limited to depth=3, max_children=10
    - A11y returns summary + top 3 issues only
    - All text truncated to 50 chars
    """
    if compact:
        return {
            "ok": True,
            "url": page.url,
            "title": page.title(),
            "timestamp": get_timestamp(),
            # File reference instead of base64
            "screenshot_path": _save_screenshot_to_file(page, selector),
            # Compact DOM
            "dom_summary": get_dom_snapshot(page, selector, depth=3, max_children=10),
            # Compact A11y
            "a11y_summary": _get_a11y_summary(page, selector, max_issues=3),
        }
    
    # ... existing full output code ...
```

</details>

**Estimated compact output size**: ~2-5K tokens per skill call

### Part 2: Sub-Agent Architecture (Scalable Solution)

For complex reviews, decompose into specialized sub-agents with controlled token budgets:

```
┌─────────────────────────────────────────────────────────────────┐
│                    ORCHESTRATOR AGENT                           │
│  (Receives compact summaries, coordinates, synthesizes)         │
│  Budget: ~20K tokens for orchestration + final report           │
└─────────────────────────────────────────────────────────────────┘
           │                    │                    │
           ▼                    ▼                    ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│  SCREENSHOT     │  │  ACCESSIBILITY  │  │  DOM STRUCTURE  │
│  SUB-AGENT      │  │  SUB-AGENT      │  │  SUB-AGENT      │
│                 │  │                 │  │                 │
│ • Takes shot    │  │ • Runs axe-core │  │ • Analyzes DOM  │
│ • Saves to file │  │ • Categorizes   │  │ • Finds issues  │
│ • Returns path  │  │ • Top 10 issues │  │ • Maps to code  │
│ • ~1K tokens    │  │ • ~5K tokens    │  │ • ~5K tokens    │
└─────────────────┘  └─────────────────┘  └─────────────────┘
           │                    │                    │
           ▼                    ▼                    ▼
┌─────────────────────────────────────────────────────────────────┐
│                    DESIGN REVIEW SUB-AGENT                      │
│  • Receives summaries from above (not raw data)                 │
│  • Runs spec checks against summaries                           │
│  • Generates issues list                                        │
│  • Budget: ~15K tokens                                          │
└─────────────────────────────────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────────────────────────────┐
│                    REPORT GENERATOR SUB-AGENT                   │
│  • Creates annotated screenshot                                 │
│  • Generates TASKS.md                                           │
│  • Returns final structured output                              │
│  • Budget: ~10K tokens                                          │
└─────────────────────────────────────────────────────────────────┘
```

**Total Budget**: ~20K + 1K + 5K + 5K + 15K + 10K = **~56K tokens** (well under 80K limit)

---

## Implementation Plan

### Phase 1: Compact Flag for agent_eyes.py

**Priority**: High (Quick Win)  
**Effort**: 2-3 hours  
**Impact**: Reduces screenshot bloat by 100%
**Status**: ✅ COMPLETED (2026-01-22)

- [x] Add `--compact` CLI argument to all commands
- [x] Implement `_generate_screenshot_path()` helper (always saves to disk, returns path)
- [x] Add `compact` parameter to `get_full_context()`
- [x] Implement `_get_a11y_summary()` helper
- [x] Modify `get_dom_snapshot()` to accept stricter limits (`max_children`, `max_text_length`)
- [ ] Update tests (deferred - no existing tests found)

**Files Modified**:
- `.claude/skills/agent-eyes/scripts/agent_eyes.py` - Added compact mode to all functions
- `.claude/skills/agent-eyes/SKILL.md` - Updated documentation with compact mode usage

<details>
<summary>agent_eyes.py Changes (Pseudo-diff)</summary>

```diff
 def take_screenshot(
     page: "Page",
     selector: Optional[str] = None,
     output_path: Optional[str] = None,
     as_base64: bool = False,
     capture_mode_aware: bool = True,
+    compact: bool = False,  # NEW
 ) -> dict:
+    # In compact mode, never return base64
+    if compact:
+        as_base64 = False
+        if not output_path:
+            output_path = _generate_screenshot_path()
     ...

 def get_dom_snapshot(
     page: "Page",
     selector: Optional[str] = None,
     depth: int = 5,
+    max_children: int = 20,  # NEW: Make configurable
+    max_text_length: int = 100,  # NEW: Make configurable
 ) -> dict:
     ...

+def _get_a11y_summary(
+    page: "Page",
+    selector: Optional[str] = None,
+    max_issues: int = 10,
+) -> dict:
+    """Return summarized a11y results for compact mode."""
+    full_results = run_a11y_scan(page, selector)
+    if not full_results.get("ok"):
+        return full_results
+    
+    violations = full_results.get("violations", [])
+    by_severity = {"critical": 0, "serious": 0, "moderate": 0, "minor": 0}
+    for v in violations:
+        impact = v.get("impact", "minor")
+        by_severity[impact] = by_severity.get(impact, 0) + 1
+    
+    return {
+        "ok": True,
+        "total_violations": len(violations),
+        "by_severity": by_severity,
+        "top_issues": [
+            {
+                "id": v.get("id"),
+                "impact": v.get("impact"),
+                "description": v.get("description"),
+                "affected_count": len(v.get("nodes", [])),
+            }
+            for v in violations[:max_issues]
+        ],
+    }
```

</details>

### Phase 2: Remove Base64 from Session Storage

**Priority**: High (Major Impact)  
**Effort**: 1-2 hours  
**Impact**: Eliminates 471K tokens from session files  
**Status**: ✅ **COMPLETED** (2026-01-23)

- [x] Add `_save_screenshot_to_session()` helper function
- [x] Modify `agent_canvas.py:write_session_artifact()` to store screenshot path only
- [x] Update session schema to use `beforeScreenshotPath` instead of `beforeScreenshot`
- [x] Modify selection event handling to store screenshot path, not base64
- [x] Add backward compatibility in `session_parser.py` and `canvas_verify.py`
- [x] Bump schema version to `1.1`

**Files Modified**:
- `.claude/skills/agent-canvas/scripts/agent_canvas.py` - Main session storage
- `.claude/skills/canvas-apply/scripts/session_parser.py` - Backward-compatible parsing
- `.claude/skills/canvas-verify/scripts/canvas_verify.py` - Backward-compatible verification

**Breaking Change**: New sessions use `beforeScreenshotPath` (path string) instead of `beforeScreenshot` (base64). Old sessions are still readable via backward-compatible accessors.

<details>
<summary>Session Schema Changes</summary>

**Before** (current session.json):
```json
{
  "sessionId": "ses-8c7492be1187",
  "beforeScreenshot": "iVBORw0KGgoAAAANSUhEUgAAA...(471K chars)...",
  "events": {
    "selections": [
      {
        "screenshot": {
          "base64": "iVBORw0KGgoAAAANSUhEUgAAA...(443K chars)...",
          "size": 443281
        }
      }
    ]
  }
}
```

**After** (compact session.json):
```json
{
  "sessionId": "ses-8c7492be1187",
  "beforeScreenshotPath": ".canvas/sessions/ses-8c7492be1187/before.png",
  "events": {
    "selections": [
      {
        "screenshot": {
          "path": ".canvas/sessions/ses-8c7492be1187/selection_001.png",
          "size": 443281
        }
      }
    ]
  }
}
```

**Token savings**: ~900K tokens per session with screenshots

</details>

### Phase 3: Compact Flag for design_review.py ✅ COMPLETED

**Priority**: Medium  
**Effort**: 2-3 hours  
**Impact**: Reduces review output size
**Status**: ✅ Completed

- [x] Add `--compact` CLI argument (both `review` and `compare` subcommands)
- [x] Implement compact review output format
- [x] Truncate issue details in compact mode (100 char max)
- [x] Add `truncate_issue_for_compact()` helper function
- [x] Compact mode skips saving full report/session files

**Files Modified**:
- `.claude/skills/design-review/scripts/design_review.py`

**Implementation Details**:
- Added `--compact` flag to both `review` and `compare` subcommands
- `truncate_issue_for_compact()` helper keeps: id, checkId, severity, element, description (truncated to 100 chars)
- Removes: pillar, details, nodes, recommendation, sourceFile, editableContext
- Compact mode returns immediately after output, skipping session/report file writes
- Compare compact mode includes `diffRegionCount` instead of full `diffRegions` array

<details>
<summary>Compact Review Output Format</summary>

**Standard output** (~10K+ tokens):
```json
{
  "ok": true,
  "summary": {"blocking": 1, "major": 3, "minor": 2},
  "issues": [
    {
      "id": 1,
      "checkId": "color-contrast",
      "pillar": "Quality Craft",
      "severity": "major",
      "element": ".subtitle-text",
      "description": "Contrast ratio 3.2:1 (minimum 4.5:1 required)",
      "recommendation": "Darken text to #595959 or darker",
      "details": [...], // Full axe-core violation data
      "nodes": ["<div class='subtitle-text'>...</div>", ...] // Full HTML
    }
  ],
  "editableContext": {...},  // Full framework detection
  "artifacts": {...}
}
```

**Compact output** (~2K tokens):
```json
{
  "ok": true,
  "summary": {"blocking": 1, "major": 3, "minor": 2},
  "issues": [
    {
      "id": 1,
      "checkId": "color-contrast", 
      "severity": "major",
      "element": ".subtitle-text",
      "description": "Contrast 3.2:1 < 4.5:1"
    }
  ],
  "artifacts": {
    "screenshot": "path/to/file.png",
    "report": "path/to/report.json"
  }
}
```

</details>

### Phase 3.5: CSS Selector Output & Markdown Export

**Priority**: Medium  
**Effort**: 3-4 hours  
**Impact**: Improves actionability of review output for AI agents and developers

#### Feature Overview

Enhance the design review annotation system to include CSS selectors in the output, inspired by [agentation.dev](https://agentation.dev). This feature bridges the gap between visual issues and source code location, enabling faster AI-assisted fixes.

**Three components**:
1. **Enhanced Legend**: Add CSS selectors to annotated screenshot legend
2. **Markdown Export**: Generate companion `issues.md` with full selector details
3. **CLI Flag**: Add `--markdown` flag for agent-agnostic output format

#### Rationale

| Benefit | Description |
|---------|-------------|
| **Faster AI fixes** | Agents can use exact element references (e.g., `.sidebar > button.primary`) instead of searching |
| **Visual → Code bridge** | Directly connects annotation markers to source code locations |
| **Universal compatibility** | Markdown export works with any AI tool (Claude Code, Cursor, Windsurf, etc.) |
| **Copy-paste workflow** | Developers can copy selectors directly from issues.md to their editor |

#### Implementation Tasks

- [ ] Modify `annotator.py` to extract and include CSS selectors in legend annotations
- [ ] Create `_generate_css_selector()` helper function for robust selector generation
- [ ] Add `generate_markdown_export()` function to `design_review.py`
- [ ] Add `--markdown` CLI argument to `design_review.py`
- [ ] Generate `issues.md` companion file alongside `annotated.png`
- [ ] Update SKILL.md documentation with new flag and output format
- [ ] Add tests for selector generation edge cases

**Files to Modify**:
- `.claude/skills/design-review/scripts/annotator.py`
- `.claude/skills/design-review/scripts/design_review.py`
- `.claude/skills/design-review/SKILL.md`

<details>
<summary>Enhanced Annotated Screenshot Legend Format</summary>

**Current format** (without selectors):
```
┌────────────────────────────────────┐
│ DESIGN REVIEW ISSUES               │
├────────────────────────────────────┤
│ [1] Color contrast too low         │
│ [2] Missing focus indicator        │
│ [3] Touch target too small         │
└────────────────────────────────────┘
```

**Enhanced format** (with selectors):
```
┌─────────────────────────────────────────────────────────────┐
│ DESIGN REVIEW ISSUES                                        │
├─────────────────────────────────────────────────────────────┤
│ [1] Color contrast too low                                  │
│     → .hero-section > p.subtitle                            │
│                                                             │
│ [2] Missing focus indicator                                 │
│     → nav.main-nav > ul > li:nth-child(3) > a               │
│                                                             │
│ [3] Touch target too small                                  │
│     → .sidebar > button.close-btn                           │
└─────────────────────────────────────────────────────────────┘
```

</details>

<details>
<summary>Markdown Export Format (issues.md)</summary>

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
| **XPath** | `/html/body/main/section[1]/p[2]` |

**Description**: Contrast ratio 3.2:1 does not meet WCAG AA minimum of 4.5:1

**Recommendation**: Darken text color to `#595959` or darker

**Affected Element**:
```html
<p class="subtitle">Your AI-powered analytics dashboard</p>
```

---

## Issue #2: Missing focus indicator

| Property | Value |
|----------|-------|
| **Severity** | major |
| **Pillar** | Quality Craft |
| **Check** | focus-visible |
| **CSS Selector** | `nav.main-nav > ul > li:nth-child(3) > a` |
| **XPath** | `/html/body/header/nav/ul/li[3]/a` |

**Description**: Interactive element has no visible focus indicator

**Recommendation**: Add `outline` or `box-shadow` on `:focus-visible`

**Affected Element**:
```html
<a href="/settings">Settings</a>
```

---

## Issue #3: Touch target too small

| Property | Value |
|----------|-------|
| **Severity** | blocking |
| **Pillar** | Quality Craft |
| **Check** | touch-target-size |
| **CSS Selector** | `.sidebar > button.close-btn` |
| **XPath** | `/html/body/aside/button` |

**Description**: Touch target is 24x24px, minimum is 44x44px

**Recommendation**: Increase button padding or add touch-action area

**Affected Element**:
```html
<button class="close-btn" aria-label="Close sidebar">×</button>
```

---

## Quick Fix Reference

Copy these selectors for your AI assistant:

```
.hero-section > p.subtitle
nav.main-nav > ul > li:nth-child(3) > a
.sidebar > button.close-btn
```
```

</details>

<details>
<summary>CSS Selector Generation Implementation</summary>

```python
# annotator.py - CSS selector generation

def _generate_css_selector(element_info: dict) -> str:
    """
    Generate a unique CSS selector for an element.
    
    Prioritizes:
    1. ID selector (if unique): #my-id
    2. Class chain: .parent > .child.specific
    3. Tag + attributes: button[aria-label="Close"]
    4. Nth-child fallback: div > p:nth-child(2)
    
    Args:
        element_info: Dict with tag, id, classes, attributes, parent chain
        
    Returns:
        CSS selector string (e.g., ".sidebar > button.close-btn")
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


def _is_utility_class(class_name: str) -> bool:
    """Check if class is a utility/framework class to skip."""
    utility_patterns = [
        "flex", "grid", "p-", "m-", "text-", "bg-", "w-", "h-",  # Tailwind
        "col-", "row-", "d-",  # Bootstrap
        "css-",  # Emotion/styled-components
    ]
    return any(class_name.startswith(p) for p in utility_patterns)


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

</details>

<details>
<summary>Markdown Export CLI Usage</summary>

```bash
# Generate annotated screenshot with markdown export
uv run design_review.py review http://localhost:3000 --annotate --markdown

# Markdown-only (no annotated screenshot)
uv run design_review.py review http://localhost:3000 --markdown

# Compact mode with markdown (optimal for AI agents)
uv run design_review.py review http://localhost:3000 --compact --markdown

# Output files generated:
# .canvas/reviews/<sessionId>/
# ├── annotated.png      # Screenshot with issue markers + selector legend
# ├── issues.md          # Full markdown report with selectors
# ├── report.json        # Structured data (existing)
# └── session.json       # Session metadata (existing)
```

</details>

<details>
<summary>Integration with Compact Mode</summary>

The `--markdown` flag works independently and combines well with `--compact`:

| Mode | Output | Use Case |
|------|--------|----------|
| `--annotate` | `annotated.png` with legend | Visual review |
| `--markdown` | `issues.md` with selectors | AI agent consumption |
| `--annotate --markdown` | Both files | Complete output |
| `--compact --markdown` | Minimal JSON + `issues.md` | Token-efficient AI workflow |

**Compact mode JSON enhancement**:
```json
{
  "ok": true,
  "summary": {"blocking": 1, "major": 2},
  "issues": [
    {
      "id": 1,
      "checkId": "color-contrast",
      "severity": "major",
      "selector": ".hero-section > p.subtitle",  // NEW
      "description": "Contrast 3.2:1 < 4.5:1"
    }
  ],
  "artifacts": {
    "screenshot": "path/to/annotated.png",
    "markdown": "path/to/issues.md"  // NEW
  }
}
```

</details>

### Phase 4: Create Sub-Agent Wrapper Scripts ✅ COMPLETED

**Priority**: Medium  
**Effort**: 4-6 hours  
**Impact**: Enables orchestrated reviews with controlled budgets
**Status**: ✅ Completed (core agents created, orchestrator deferred)

- [x] Create `screenshot_agent.py` - Takes screenshots, returns paths only (~1K tokens)
- [x] Create `a11y_agent.py` - Runs scans, returns summaries (~5K tokens)
- [x] Create `dom_agent.py` - Analyzes DOM, returns compact structure (~5K tokens)
- [ ] Create `orchestrator.py` - Coordinates sub-agents, enforces budgets (DEFERRED)
- [ ] Add budget tracking to each sub-agent (DEFERRED)

**Files Created**:
- `.claude/skills/design-review/scripts/agents/__init__.py`
- `.claude/skills/design-review/scripts/agents/screenshot_agent.py`
- `.claude/skills/design-review/scripts/agents/a11y_agent.py`
- `.claude/skills/design-review/scripts/agents/dom_agent.py`

**Implementation Details**:
- All agents have CLI interfaces and can be imported as classes
- ScreenshotAgent: Returns path + dimensions + size (no base64)
- A11yAgent: Returns aggregated violations by severity/category + top N issues
- DomAgent: Returns compact DOM tree with configurable depth/children limits

<details>
<summary>Sub-Agent Implementation Examples</summary>

**screenshot_agent.py**:
```python
#!/usr/bin/env python3
"""
Screenshot Sub-Agent - Captures screenshots with minimal token overhead.

Output Budget: ~1K tokens
"""

import json
import sys
from pathlib import Path

# Import from parent skill
sys.path.insert(0, str(Path(__file__).parent.parent))
from agent_eyes import take_screenshot

def capture(url: str, selector: str = None, session_dir: str = None) -> dict:
    """
    Capture screenshot and return path reference only.
    
    Returns:
        {
            "ok": True,
            "path": ".canvas/sessions/.../screenshot.png",
            "size_bytes": 443281,
            "dimensions": {"width": 1280, "height": 720}
        }
    """
    # Implementation here
    pass

if __name__ == "__main__":
    # CLI interface
    pass
```

**a11y_agent.py**:
```python
#!/usr/bin/env python3
"""
Accessibility Sub-Agent - Runs axe-core and returns compact summary.

Output Budget: ~5K tokens
"""

def scan(url: str, selector: str = None, max_issues: int = 10) -> dict:
    """
    Run accessibility scan and return summarized results.
    
    Returns:
        {
            "ok": True,
            "total_violations": 15,
            "by_severity": {"critical": 2, "serious": 5, "moderate": 6, "minor": 2},
            "by_category": {"color": 3, "aria": 5, "keyboard": 2, ...},
            "top_issues": [
                {"id": "color-contrast", "impact": "serious", "count": 3},
                ...
            ]
        }
    """
    pass
```

**orchestrator.py**:
```python
#!/usr/bin/env python3
"""
Review Orchestrator - Coordinates sub-agents with token budget management.

Total Budget: ~56K tokens
- Orchestrator overhead: ~20K
- Screenshot agent: ~1K
- A11y agent: ~5K  
- DOM agent: ~5K
- Review agent: ~15K
- Report agent: ~10K
"""

from dataclasses import dataclass
from typing import Optional

@dataclass
class TokenBudget:
    """Track and enforce token budgets."""
    limit: int
    used: int = 0
    
    def can_spend(self, tokens: int) -> bool:
        return self.used + tokens <= self.limit
    
    def spend(self, tokens: int) -> None:
        self.used += tokens
        if self.used > self.limit:
            raise TokenBudgetExceeded(f"Budget exceeded: {self.used}/{self.limit}")

class ReviewOrchestrator:
    def __init__(self, total_budget: int = 80000):
        self.budgets = {
            "orchestrator": TokenBudget(20000),
            "screenshot": TokenBudget(1000),
            "a11y": TokenBudget(5000),
            "dom": TokenBudget(5000),
            "review": TokenBudget(15000),
            "report": TokenBudget(10000),
        }
    
    def run_review(self, url: str, spec: str = "default") -> dict:
        """Execute full review with budget tracking."""
        pass
```

</details>

### Phase 5: Update Documentation ✅ COMPLETED

**Priority**: Low  
**Effort**: 1 hour  
**Impact**: Developer experience
**Status**: ✅ Completed

- [x] Update `docs/AGENTS.md` with compact mode usage
- [x] Add design-review skill documentation
- [x] Document agent-eyes compact mode
- [x] Add sub-agent usage info

**Files Modified**:
- `docs/AGENTS.md`

### Phase 6: Token Budget Tracking ✅ COMPLETED

**Priority**: Low  
**Effort**: 2 hours  
**Impact**: Preventive guardrails
**Status**: ✅ Completed

- [x] Create `token_budget.py` utility module
- [x] Add budget estimation function (`chars/4` heuristic)
- [x] Add warning when approaching limit
- [x] Add preset budgets for common scenarios
- [x] CLI interface for testing

**Files Created**:
- `.claude/skills/shared/token_budget.py`

**Features**:
- `estimate_tokens()`: Simple chars/4 heuristic (conservative)
- `estimate_json_tokens()`: For JSON-serializable objects
- `estimate_file_tokens()`: For file contents
- `TokenBudget` class: Category-based tracking with warnings
- `TokenBudgetExceeded` exception
- Preset budgets: compact_review (20K), full_review (80K), sub_agent (10K), etc.
- CLI: `python token_budget.py --list-budgets` or estimate from text/file

<details>
<summary>Token Budget Utility Implementation</summary>

```python
#!/usr/bin/env python3
"""
Token Budget Utilities - Estimate and track token usage.

Based on industry patterns from:
- LangChain TextSplitter
- LlamaIndex TreeSummarize
- OpenAI Cookbook recommendations
"""

import json
from dataclasses import dataclass, field
from typing import Any, Optional

# Conservative estimate: ~4 chars per token for English
CHARS_PER_TOKEN = 4

# For base64, slightly lower ratio due to limited charset
BASE64_CHARS_PER_TOKEN = 3.5


def estimate_tokens(text: str, is_base64: bool = False) -> int:
    """
    Estimate token count from text length.
    
    Args:
        text: Input text to estimate
        is_base64: True if content is base64 encoded
        
    Returns:
        Estimated token count
    """
    if not text:
        return 0
    ratio = BASE64_CHARS_PER_TOKEN if is_base64 else CHARS_PER_TOKEN
    return int(len(text) / ratio)


def estimate_json_tokens(obj: Any) -> int:
    """Estimate tokens for a JSON-serializable object."""
    return estimate_tokens(json.dumps(obj, indent=2))


@dataclass
class TokenBudget:
    """
    Track token usage against a budget.
    
    Usage:
        budget = TokenBudget(limit=80000, warn_at=0.8)
        budget.add("screenshot", 1000)
        budget.add("dom", 5000)
        
        if budget.is_exceeded:
            raise TokenBudgetExceeded(budget.summary)
    """
    limit: int
    warn_at: float = 0.8  # Warn when 80% consumed
    usage: dict = field(default_factory=dict)
    
    @property
    def total_used(self) -> int:
        return sum(self.usage.values())
    
    @property
    def remaining(self) -> int:
        return max(0, self.limit - self.total_used)
    
    @property
    def utilization(self) -> float:
        return self.total_used / self.limit if self.limit > 0 else 0
    
    @property
    def is_exceeded(self) -> bool:
        return self.total_used > self.limit
    
    @property
    def should_warn(self) -> bool:
        return self.utilization >= self.warn_at
    
    def add(self, category: str, tokens: int) -> None:
        """Add token usage for a category."""
        self.usage[category] = self.usage.get(category, 0) + tokens
    
    def can_afford(self, tokens: int) -> bool:
        """Check if we can afford to spend more tokens."""
        return self.total_used + tokens <= self.limit
    
    @property
    def summary(self) -> dict:
        """Get budget summary."""
        return {
            "limit": self.limit,
            "used": self.total_used,
            "remaining": self.remaining,
            "utilization": f"{self.utilization:.1%}",
            "breakdown": self.usage,
            "exceeded": self.is_exceeded,
        }


class TokenBudgetExceeded(Exception):
    """Raised when token budget is exceeded."""
    pass


# Preset budgets for common scenarios
BUDGETS = {
    "compact_review": TokenBudget(limit=20000),
    "full_review": TokenBudget(limit=80000),
    "sub_agent": TokenBudget(limit=10000),
}
```

</details>

---

## Design Decisions

### Decision 1: Compact Flag vs Always-Compact

**Choice**: Add `--compact` flag (backwards compatible)

**Rationale**:
- Preserves existing behavior for users who need full output
- Allows gradual migration
- Can later change default if compact proves reliable
- Explicit opt-in reduces surprise behavior changes

**Alternatives Considered**:
- Always compact: Would break existing workflows
- Auto-detect based on token count: Complex to implement, unpredictable

### Decision 2: Sub-Agent Granularity

**Choice**: One sub-agent per concern (screenshot, a11y, dom, review, report)

**Rationale**:
- Maximum parallelism potential
- Clear separation of concerns
- Each agent stays well under token budget independently
- Easier to debug and maintain individual components
- Can run sub-agents independently for specific tasks

**Alternatives Considered**:
- Single monolithic agent: Doesn't solve the token problem
- Two-agent split (capture vs analyze): Still too large for complex pages

### Decision 3: Screenshot Handling

**Choice**: Always save to file, never embed base64 in JSON output

**Rationale**:
- Simplest and most reliable approach
- Eliminates the #1 source of token bloat (471K tokens per screenshot!)
- File references are tiny (~50-100 chars vs 500K+ chars)
- Screenshots are still accessible via file path
- Consistent behavior regardless of compact mode

**Alternatives Considered**:
- Thumbnail base64: Still adds tokens, quality loss
- On-demand loading: Complex, requires state management
- External storage (S3/CDN): Over-engineering for local use case

### Decision 4: DOM Snapshot Limits

**Choice**: Configurable limits with sensible compact defaults (depth=3, max_children=10)

**Rationale**:
- Current defaults (depth=5, max_children=20) produce trees too large for complex React apps
- Depth 3 captures most meaningful structure without noise
- 10 children per node is usually sufficient to understand layout
- Configurable allows tuning for specific use cases

**Alternatives Considered**:
- Fixed strict limits: Too inflexible
- Smart pruning (remove invisible): Complex, edge cases
- CSS selector targeting only: Loses context

### Decision 5: A11y Result Summarization

**Choice**: Return counts by severity + top N issues with truncated details

**Rationale**:
- Full axe-core output includes enormous HTML snippets
- Severity counts give quick overview
- Top N issues prioritize what to fix first
- Truncated details still provide enough context for fixes
- Full report available in artifacts file

**Alternatives Considered**:
- IDs only: Loses context for fixes
- Categories only: Can't identify specific elements
- Full tree with depth limit: Still too large

### Decision 6: CSS Selector Output (Option C)

**Choice**: Add CSS selectors to annotation legend + companion markdown export file

**Rationale**:
- Inspired by [agentation.dev](https://agentation.dev) approach to AI-friendly output
- CSS selectors provide exact element references for AI agents and developers
- Markdown export enables universal compatibility (Claude Code, Cursor, Windsurf, etc.)
- Copy-paste workflow: selectors can be used directly in code or AI prompts
- Enhances existing annotation system without breaking changes
- Optional `--markdown` flag maintains backward compatibility

**Implementation Choice** (Option C selected over alternatives):
- **Option A** (selector in legend only): Limited - no structured export for AI tools
- **Option B** (markdown only): Loses visual context of annotated screenshot
- **Option C** (both): Best of both worlds - visual + structured output ✓

**Alternatives Considered**:
- JSON-only selectors: Less human-readable, harder to copy-paste
- Inline code comments: Requires source file access, not always available
- Browser extension: Additional install burden, not agent-friendly

---

## Technical Specifications

### Compact Mode API

#### agent_eyes.py CLI

```bash
# Standard mode (existing behavior)
uv run agent_eyes.py context <url>

# Compact mode (new)
uv run agent_eyes.py context <url> --compact

# Compact with custom limits
uv run agent_eyes.py context <url> --compact --dom-depth 2 --max-children 5 --max-issues 5
```

#### agent_eyes.py Library API

```python
# Standard mode
result = get_full_context(page, selector=".hero")

# Compact mode
result = get_full_context(page, selector=".hero", compact=True)

# Compact mode with custom limits
result = get_full_context(
    page, 
    selector=".hero",
    compact=True,
    dom_depth=2,
    max_children=5,
    max_a11y_issues=5,
)
```

#### Compact Output Schema

```typescript
interface CompactContext {
  ok: boolean;
  url: string;
  title: string;
  timestamp: string;
  
  // File path instead of base64
  screenshot_path: string;
  
  // Compact DOM
  dom_summary: {
    tag: string;
    id?: string;
    class?: string;
    children?: DOMSummaryNode[];  // Max depth=3, max_children=10
  };
  
  // Compact A11y
  a11y_summary: {
    total_violations: number;
    by_severity: {
      critical: number;
      serious: number;
      moderate: number;
      minor: number;
    };
    top_issues: Array<{
      id: string;
      impact: string;
      description: string;  // Truncated to 100 chars
      affected_count: number;
    }>;
  };
}
```

### Sub-Agent Communication Protocol

Sub-agents communicate via JSON files in the session directory:

```
.canvas/reviews/<sessionId>/
├── screenshot_result.json    # From screenshot_agent
├── a11y_result.json          # From a11y_agent  
├── dom_result.json           # From dom_agent
├── review_result.json        # From review_agent (issues)
├── report_result.json        # From report_agent (final)
├── budget_tracking.json      # Token budget status
└── orchestrator_log.json     # Coordination log
```

Each result file follows the schema:
```typescript
interface SubAgentResult {
  agent: string;
  timestamp: string;
  tokens_used: number;
  tokens_budget: number;
  result: any;  // Agent-specific payload
}
```

### Token Budget Utilities

```python
# Usage in sub-agents
from shared.token_budget import TokenBudget, estimate_tokens

budget = TokenBudget(limit=5000)  # 5K for a11y agent

# Before returning results
result_tokens = estimate_tokens(json.dumps(result))
if not budget.can_afford(result_tokens):
    result = truncate_result(result, budget.remaining)

budget.add("a11y_result", result_tokens)
```

---

## Visual Design Guidelines

This section establishes the visual design standards for Agent Canvas annotation UI, ensuring consistent, professional, and accessible visual output across all design review features.

### Design Philosophy

**Core Principles**:
- **Simple**: Black and white UI that doesn't distract from the content being reviewed
- **Focused**: Red annotations draw attention to issues without overwhelming
- **Accessible**: Fall back to high-contrast alternatives when needed
- **Professional**: Clean, consistent styling inspired by technical redline documentation

### Color Palette

#### Primary UI Colors

| Role | Color | Hex | Usage |
|------|-------|-----|-------|
| Background | White | `#FFFFFF` | Legend background, clean canvas |
| Text | Black | `#000000` | Primary text, descriptions, labels |
| Border | Light Gray | `#E0E0E0` | Legend borders, separators |
| Secondary Background | Light Gray | `#F8F9FA` | Legend panel background |

#### Annotation Colors

| Role | Color | Hex | Usage |
|------|-------|-----|-------|
| Primary Annotation | Red | `#DC3545` | Issue markers, borders, redlines |
| Accessibility Fallback | Black | `#000000` | When red contrast < 3:1 against background |
| Marker Text | White | `#FFFFFF` | Numbers inside red markers |
| Marker Border | White | `#FFFFFF` | 2px border around markers for visibility |

#### Severity Indicator Colors

Aligned with the CoreAI design review approach, using emoji status indicators in reports and color-coded markers on screenshots:

| Severity | Emoji | Marker Color | Hex | Usage |
|----------|-------|--------------|-----|-------|
| Pass | 🟢 | Green | `#28A745` | Compliant items (reports only) |
| Minor | 🟡 | Yellow | `#FFC107` | Low-priority polish issues |
| Major | 🟠 | Orange | `#FF9100` | Should fix, significant impact |
| Blocking | ⚫ | Red | `#DC3545` | Must fix before shipping |

<details>
<summary>Color Rationale</summary>

**Why Black and White UI?**
- Minimizes visual noise on annotated screenshots
- Creates clear separation between content and annotations
- Works well with any website color scheme
- Professional appearance suitable for sharing with stakeholders

**Why Red for Annotations?**
- Industry-standard "redline" convention for design review
- High visibility on most backgrounds
- Clear association with "issues to fix"
- Consistent with traditional design markup practices

**Why Black Fallback for Accessibility?**
- Some backgrounds (red/orange/brown) have insufficient contrast with red annotations
- Black provides maximum contrast on virtually any background
- Maintains visibility for colorblind users (protanopia, deuteranopia)
- WCAG requires 3:1 minimum contrast for UI components

</details>

### Annotation Visual Style

#### Issue Markers

Numbered circles placed at the top-right corner of problematic elements:

```
┌──────────────────────────────────────────────────────────────────┐
│                                                                  │
│  ┌─────────────────────────────────────────────┐                 │
│  │                                          ┌──┴──┐              │
│  │  [Element with issue]                    │  1  │ ← Marker     │
│  │                                          └─────┘              │
│  └─────────────────────────────────────────────────┘             │
│     ↑ Red border (3px) around element                            │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

**Marker Specifications**:
- Shape: Filled circle with white 2px border
- Size: 32px diameter (16px radius)
- Font: System sans-serif, 18px bold, white text
- Position: Top-right of element bounding box, offset by radius
- Numbering: Sequential integers (1, 2, 3...)
- Overflow: For numbers > 20, use parenthetical format: (21), (22)

**Element Border Specifications**:
- Width: 3px
- Style: Solid
- Color: Matches severity (default: red `#DC3545`)
- Position: Hugs the element bounding box

#### Legend Box Style

Clean, readable legend at the bottom of annotated screenshots:

```
┌────────────────────────────────────────────────────────────────────────────┐
│                                                                            │
│                         [SCREENSHOT CONTENT]                               │
│                                                                            │
├────────────────────────────────────────────────────────────────────────────┤
│  DESIGN REVIEW ISSUES                                                      │
├────────────────────────────────────────────────────────────────────────────┤
│  ⚫ #1: Color contrast too low (3.2:1 < 4.5:1)                             │
│     → .hero-section > p.subtitle                                          │
│                                                                            │
│  🟠 #2: Missing focus indicator                                           │
│     → nav.main-nav > ul > li:nth-child(3) > a                             │
│                                                                            │
│  🟡 #3: Touch target too small (24x24px < 44x44px)                        │
│     → .sidebar > button.close-btn                                          │
└────────────────────────────────────────────────────────────────────────────┘
```

**Legend Specifications**:
- Background: Light gray (`#F8F9FA`)
- Border: 2px gray (`#C8C8C8`) separator line at top
- Padding: 20px all sides
- Header: "DESIGN REVIEW ISSUES" or "Issues Found:" in bold
- Line height: 28px per issue
- Max description length: 60 characters (truncate with "...")

**Issue Entry Format**:
```
[severity_emoji] #[id]: [description_truncated]
   → [css_selector]
```

#### CSS Selector Display

Selectors displayed in monospace for easy copy-paste:

| Element | Font | Size | Color |
|---------|------|------|-------|
| Selector text | `SF Mono`, `Monaco`, `Consolas`, monospace | 12px | `#6C757D` (gray) |
| Arrow indicator | System font | 12px | `#6C757D` |

### Annotated Screenshot Layout

#### Full-Page Layout

```
┌─────────────────────────────────────────────────┐
│                                                 │ ← Original screenshot
│              WEBPAGE CONTENT                    │    dimensions preserved
│                                                 │
│    ┌─────────────────────┐ ①                    │ ← Markers at issue
│    │ [Issue element 1]   │                      │    locations
│    └─────────────────────┘                      │
│                                                 │
│         ┌───────────────────────┐ ②             │
│         │ [Issue element 2]    │               │
│         └───────────────────────┘               │
│                                                 │
├─────────────────────────────────────────────────┤ ← Gray separator (2px)
│  DESIGN REVIEW ISSUES                           │
│                                                 │ ← Legend (auto-height)
│  ⚫ #1: Issue description...                    │
│     → .css-selector                             │
│                                                 │
│  🟠 #2: Issue description...                    │
│     → .css-selector                             │
└─────────────────────────────────────────────────┘
```

**Layout Specifications**:
- Screenshot: Original dimensions, no scaling
- Legend position: Below screenshot (appended)
- Legend height: Dynamic based on issue count (padding + header + issues × line_height)
- Total image height: `screenshot_height + legend_height`
- Total image width: Same as screenshot width

#### Marker Positioning Algorithm

```python
# Marker placement priority (top-right of element)
marker_x = min(
    element.x + element.width + MARKER_RADIUS,
    screenshot_width - MARKER_RADIUS - 5  # Keep within bounds
)
marker_y = max(
    element.y - MARKER_RADIUS,
    MARKER_RADIUS + 5  # Keep within bounds
)
```

#### Spacing Standards

| Element | Value | Notes |
|---------|-------|-------|
| Legend padding | 20px | All sides |
| Legend line height | 28px | Per issue entry |
| Selector indent | 24px | Left padding for "→ .selector" line |
| Marker radius | 16px | Circle radius |
| Border width | 3px | Element highlight border |
| Max legend width | 400px | Text wrap point (description) |

### Review Output Format

Structured review output aligned with CoreAI design review pillars and severity system:

#### Pillar Assessment Table

For markdown/report output, use this format for pillar-level summaries:

```markdown
## Pillar Assessment

| Pillar | Grade | Pass | Attention | Blocking |
|--------|-------|------|-----------|----------|
| Frictionless Insight to Action | 🟢 B | 3 | 1 | 0 |
| Progressive Clarity | 🟢 A | 4 | 0 | 0 |
| Quality Craft | 🟠 C | 2 | 2 | 1 |
| Trustworthy Building | 🟢 B | 3 | 1 | 0 |
```

**Grading Scale** (inspired by CoreAI):
- **A** (🟢): All checks pass, exemplary implementation
- **B** (🟢): Minor issues only, no major concerns
- **C** (🟠): Has major issues, needs attention
- **F** (⚫): Has blocking issues, must fix before shipping

#### Issue Categorization

```markdown
## Issue Summary

**Blocking (must fix)**: 1
**Major (should fix)**: 3
**Minor (nice to fix)**: 2

---

## Blocking Issues

### #1: Missing AI disclaimer
- **Pillar**: Trustworthy Building
- **Check**: ai-disclaimer
- **Element**: `.ai-response-container`
- **Selector**: `section.chat-output > div.message.ai`
- **Description**: AI-generated content lacks required disclaimer
- **Recommendation**: Add "(AI-generated)" label with appropriate styling

---

## Major Issues
...
```

#### JSON Output Schema

```typescript
interface ReviewOutput {
  ok: boolean;
  url: string;
  timestamp: string;
  specUsed: string;
  
  // Summary counts
  summary: {
    blocking: number;
    major: number;
    minor: number;
    passing: number;
  };
  
  // Pillar-level grades
  pillarGrades: {
    [pillarName: string]: {
      grade: "A" | "B" | "C" | "F";
      passing: number;
      attention: number;  // major issues
      blocking: number;
    };
  };
  
  // Individual issues
  issues: Array<{
    id: number;
    severity: "blocking" | "major" | "minor";
    checkId: string;
    pillar: string;
    element: string;
    selector: string;           // NEW: CSS selector
    xpath?: string;             // Optional XPath
    description: string;
    recommendation?: string;
    boundingBox?: {
      x: number;
      y: number;
      width: number;
      height: number;
    };
  }>;
  
  // File artifacts
  artifacts: {
    screenshot: string;
    annotated?: string;
    markdown?: string;          // NEW: issues.md path
    report: string;
  };
}
```

### Accessibility Considerations

#### Contrast Requirements

| Element | Minimum Contrast | Against | Standard |
|---------|-----------------|---------|----------|
| Red markers | 3:1 | Any background | WCAG 2.1 AA (UI components) |
| Marker text (white on red) | 4.5:1 | Red fill | WCAG 2.1 AA (text) |
| Legend text | 4.5:1 | Legend background | WCAG 2.1 AA (text) |
| Selector text | 4.5:1 | Legend background | WCAG 2.1 AA (text) |

#### When to Fall Back to Black

Use black (`#000000`) instead of red (`#DC3545`) when:

1. **Background is red/orange/brown**: Contrast ratio < 3:1
2. **Background is very dark**: Red appears muddy or invisible
3. **User preference**: System high-contrast mode detected

```python
def get_annotation_color(background_rgb: tuple[int, int, int]) -> str:
    """
    Determine annotation color based on background contrast.
    
    Args:
        background_rgb: Background color as (R, G, B) tuple
        
    Returns:
        Hex color string for annotation (#DC3545 red or #000000 black)
    """
    red = (220, 53, 69)  # #DC3545
    black = (0, 0, 0)    # #000000
    
    red_contrast = calculate_contrast_ratio(red, background_rgb)
    
    if red_contrast >= 3.0:
        return "#DC3545"  # Red meets contrast requirement
    else:
        return "#000000"  # Fall back to black
```

#### Screen Reader Considerations

For generated markdown reports (`issues.md`), ensure:

1. **Proper heading hierarchy**: H1 → H2 → H3, no skipped levels
2. **Alt text for images**: Include issue count in alt text
3. **Tables have headers**: Use proper markdown table syntax
4. **Link text is descriptive**: Avoid "click here"

```markdown
<!-- Good -->
![Annotated screenshot showing 3 issues marked on the homepage](annotated.png)

<!-- Avoid -->
![Screenshot](annotated.png)
```

#### Colorblind-Safe Design

The severity color system accounts for common color vision deficiencies:

| Deficiency | Red (#DC3545) | Orange (#FF9100) | Yellow (#FFC107) | Solution |
|------------|---------------|------------------|------------------|----------|
| Protanopia | Appears brown | Appears yellow | Visible | Use emoji indicators |
| Deuteranopia | Appears brown | Appears yellow | Visible | Use emoji indicators |
| Tritanopia | Visible | Visible | Appears pink | Acceptable |

**Mitigation**: Always pair color with:
- Emoji indicators (⚫ 🟠 🟡 🟢) which are always visible
- Numeric severity in legend text
- Severity label in markdown output

### Integration with Implementation Phases

#### Phase 3.5: CSS Selector Output

Apply visual guidelines to:
- **annotator.py**: Update legend format to include CSS selectors
- **Font choice**: Use monospace for selectors in legend
- **Indentation**: 24px indent with "→" arrow prefix

```python
# annotator.py - Enhanced legend entry
def format_legend_entry(issue: Issue) -> str:
    """Format a legend entry with severity, description, and selector."""
    emoji = SEVERITY_EMOJI[issue.severity]  # ⚫, 🟠, 🟡
    desc = truncate(issue.description, 60)
    selector = issue.selector or issue.element
    
    return f"{emoji} #{issue.id}: {desc}\n   → {selector}"
```

#### Phase 4: Sub-Agents

Apply visual guidelines to:
- **Report Generator Sub-Agent**: Use structured output format
- **Pillar grades**: Include in orchestrator's final summary
- **Artifact paths**: Consistent naming (screenshot.png, annotated.png, issues.md)

#### annotator.py Implementation Updates

Current state vs. target visual guidelines:

| Aspect | Current | Target |
|--------|---------|--------|
| Severity colors | Red/Orange/Yellow | Same, with fallback logic |
| Legend format | Description only | Description + CSS selector |
| Selector font | N/A | Monospace, gray |
| Emoji indicators | None | Add to legend entries |
| Contrast fallback | None | Black when red < 3:1 |

**Files to Update**:
- `.claude/skills/design-review/scripts/annotator.py` - Add selector display, emoji indicators, contrast fallback
- `.claude/skills/design-review/scripts/design_review.py` - Pass selector data to annotator
- `.claude/skills/design-review/scripts/markdown_export.py` - (NEW) Generate issues.md with proper accessibility

---

## Success Metrics

### Primary Metrics

| Metric | Current | Phase 1 Target | Phase 4 Target |
|--------|---------|----------------|----------------|
| Max session tokens | 769K | <100K | <80K |
| Avg review tokens | ~50K | <20K | <15K |
| Screenshot tokens | 471K | 0 | 0 |
| DOM snapshot tokens | ~150K | <5K | <3K |
| A11y result tokens | ~100K | <2K | <1K |

### Secondary Metrics

| Metric | Target |
|--------|--------|
| Compact mode execution time | <10% slower than standard |
| Sub-agent orchestration overhead | <20% of total time |
| File I/O for screenshots | <500ms per screenshot |
| Budget tracking accuracy | Within 10% of actual tokens |

### Validation Tests

```bash
# Test 1: Compact mode produces <20K tokens
SESSION=$(uv run design_review.py review https://microsoft.com --compact --generate-tasks)
TOKENS=$(cat .canvas/reviews/$SESSION/session.json | wc -c)
[ $((TOKENS / 4)) -lt 20000 ] && echo "PASS" || echo "FAIL"

# Test 2: No base64 in session.json
grep -q "base64" .canvas/reviews/$SESSION/session.json && echo "FAIL" || echo "PASS"

# Test 3: Sub-agent budget respected
cat .canvas/reviews/$SESSION/budget_tracking.json | jq '.exceeded' | grep -q "false" && echo "PASS"
```

---

## File Structure After Implementation

```
.claude/skills/
├── agent-eyes/
│   ├── scripts/
│   │   └── agent_eyes.py          # Updated with --compact, configurable limits
│   └── SKILL.md                   # Updated docs
│
├── agent-canvas/
│   ├── scripts/
│   │   └── agent_canvas.py        # Updated: no base64 in session storage
│   └── SKILL.md
│
├── design-review/
│   ├── scripts/
│   │   ├── design_review.py       # Updated with --compact, --markdown
│   │   ├── agents/                # NEW: Sub-agent wrappers
│   │   │   ├── __init__.py
│   │   │   ├── screenshot_agent.py
│   │   │   ├── a11y_agent.py
│   │   │   ├── dom_agent.py
│   │   │   ├── review_agent.py
│   │   │   └── orchestrator.py
│   │   ├── annotator.py           # Updated: CSS selector extraction + legend
│   │   ├── markdown_export.py     # NEW: issues.md generation
│   │   ├── image_comparator.py
│   │   └── spec_loader.py
│   └── SKILL.md                   # Updated docs
│
├── shared/
│   ├── __init__.py
│   ├── canvas_bus.py              # Updated: event log limits
│   └── token_budget.py            # NEW: Budget tracking utility
│
└── ...

docs/
└── AGENTS.md                      # Updated with sub-agent patterns, compact mode

.canvas/reviews/<sessionId>/       # Review session artifacts
├── session.json
├── report.json
├── screenshot.png
├── annotated.png                  # Enhanced: legend includes CSS selectors
└── issues.md                      # NEW: Markdown export with full selector details
```

---

## Risk Assessment

### High Risk

| Risk | Mitigation |
|------|------------|
| Breaking existing workflows | Backward-compatible `--compact` flag, not changing defaults |
| Sub-agent coordination failures | Robust error handling, fallback to monolithic mode |
| Token estimates inaccurate | Conservative estimates, 20% buffer in budgets |

### Medium Risk

| Risk | Mitigation |
|------|------------|
| File I/O bottleneck for screenshots | Async writes, parallel sub-agents |
| DOM truncation loses important info | Configurable limits, full output available |
| A11y summary misses critical issues | Sort by severity, configurable max |

### Low Risk

| Risk | Mitigation |
|------|------------|
| Documentation out of sync | Update docs in same PR as code |
| Performance regression | Benchmark before/after in CI |

---

## Next Steps

### Immediate (This Week)

- [ ] Review and approve this plan
- [ ] Create GitHub issues for Phases 1-3
- [ ] Implement Phase 1 (compact flag for agent_eyes.py)
- [ ] Implement Phase 2 (remove base64 from sessions)

### Short-term (Next 2 Weeks)

- [ ] Implement Phase 3 (compact flag for design_review.py)
- [ ] Test with real-world pages (microsoft.com, complex SPAs)
- [ ] Measure actual token reduction

### Medium-term (Next Month)

- [ ] Implement Phase 4 (sub-agent architecture)
- [ ] Implement Phase 5 (documentation updates)
- [ ] Implement Phase 6 (token budget tracking)
- [ ] Performance benchmarking

### Validation Checkpoints

1. **After Phase 1-2**: Verify sessions stay under 100K tokens
2. **After Phase 3**: Verify review output under 20K tokens
3. **After Phase 4**: Verify orchestrated reviews under 80K tokens
4. **Final**: Run full test suite on complex pages

---

## Appendix: Research References

### Industry Patterns Used

1. **Hierarchical Summarization** (LlamaIndex TreeSummarize pattern)
   - Sub-agents produce summaries → orchestrator synthesizes
   - Each level reduces token count while preserving key info

2. **Token Budgeting** (LangChain TextSplitter pattern)
   - Enforce chunk sizes at construction time
   - Validate: `chunk_overlap <= chunk_size`

3. **Reference Pattern** (RAG-style)
   - Store full data in files
   - Pass only references and summaries to agents
   - Load full data on-demand when needed

4. **Progressive Disclosure** (UI pattern applied to data)
   - Start with summary
   - Expand to details only when requested
   - Never load full tree by default

### Related OpenAI Cookbook Examples

- [How to count tokens](https://cookbook.openai.com/examples/how_to_count_tokens_with_tiktoken)
- [Long document summarization](https://cookbook.openai.com/examples/summarizing_long_documents)
- [Function calling with large outputs](https://cookbook.openai.com/examples/how_to_call_functions_with_chat_models)

---

*Document maintained by the Agent Canvas team. Last updated: 2026-01-23 (v1.2 - Added Visual Design Guidelines)*
