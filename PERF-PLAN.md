# Agent Canvas Performance Optimization Plan

> **Version**: 1.0  
> **Created**: 2026-01-22  
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
   - [Phase 4: Create Sub-Agent Wrapper Scripts](#phase-4-create-sub-agent-wrapper-scripts)
   - [Phase 5: Update Documentation](#phase-5-update-documentation)
   - [Phase 6: Token Budget Tracking](#phase-6-token-budget-tracking)
6. [Design Decisions](#design-decisions)
7. [Technical Specifications](#technical-specifications)
   - [Compact Mode API](#compact-mode-api)
   - [Sub-Agent Communication Protocol](#sub-agent-communication-protocol)
   - [Token Budget Utilities](#token-budget-utilities)
8. [Success Metrics](#success-metrics)
9. [File Structure After Implementation](#file-structure-after-implementation)
10. [Risk Assessment](#risk-assessment)
11. [Next Steps](#next-steps)

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

- [ ] Modify `agent_canvas.py:write_session_artifact()` to store screenshot path only
- [ ] Update session schema to use `beforeScreenshotPath` instead of `beforeScreenshot`
- [ ] Modify selection event handling to store screenshot path, not base64
- [ ] Add migration note for existing sessions

**Files to Modify**:
- `.claude/skills/agent-canvas/scripts/agent_canvas.py`
- `.claude/skills/shared/canvas_bus.py`

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

### Phase 3: Compact Flag for design_review.py

**Priority**: Medium  
**Effort**: 2-3 hours  
**Impact**: Reduces review output size

- [ ] Add `--compact` CLI argument
- [ ] Implement compact review output format
- [ ] Truncate issue details in compact mode
- [ ] Update `generate_tasks_file()` for compact mode

**Files to Modify**:
- `.claude/skills/design-review/scripts/design_review.py`
- `.claude/skills/design-review/SKILL.md`

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

### Phase 4: Create Sub-Agent Wrapper Scripts

**Priority**: Medium  
**Effort**: 4-6 hours  
**Impact**: Enables orchestrated reviews with controlled budgets

- [ ] Create `screenshot_agent.py` - Takes screenshots, returns paths only
- [ ] Create `a11y_agent.py` - Runs scans, returns summaries
- [ ] Create `dom_agent.py` - Analyzes DOM, returns compact structure
- [ ] Create `orchestrator.py` - Coordinates sub-agents, enforces budgets
- [ ] Add budget tracking to each sub-agent

**Files to Create**:
- `.claude/skills/design-review/scripts/agents/__init__.py`
- `.claude/skills/design-review/scripts/agents/screenshot_agent.py`
- `.claude/skills/design-review/scripts/agents/a11y_agent.py`
- `.claude/skills/design-review/scripts/agents/dom_agent.py`
- `.claude/skills/design-review/scripts/agents/orchestrator.py`

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

### Phase 5: Update Documentation

**Priority**: Low  
**Effort**: 1 hour  
**Impact**: Developer experience

- [ ] Update `docs/AGENTS.md` with compact mode usage
- [ ] Update skill SKILL.md files with `--compact` flag
- [ ] Add sub-agent workflow documentation
- [ ] Document token budget guidelines

**Files to Modify**:
- `docs/AGENTS.md`
- `.claude/skills/design-review/SKILL.md`
- `.claude/skills/agent-eyes/SKILL.md`

### Phase 6: Token Budget Tracking

**Priority**: Low  
**Effort**: 2 hours  
**Impact**: Preventive guardrails

- [ ] Create `token_budget.py` utility module
- [ ] Add budget estimation function (`chars/4` heuristic)
- [ ] Add warning when approaching limit
- [ ] Integrate with orchestrator

**Files to Create**:
- `.claude/skills/shared/token_budget.py`

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
│   │   ├── design_review.py       # Updated with --compact
│   │   ├── agents/                # NEW: Sub-agent wrappers
│   │   │   ├── __init__.py
│   │   │   ├── screenshot_agent.py
│   │   │   ├── a11y_agent.py
│   │   │   ├── dom_agent.py
│   │   │   ├── review_agent.py
│   │   │   └── orchestrator.py
│   │   ├── annotator.py
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

*Document maintained by the Agent Canvas team. Last updated: 2026-01-22*
