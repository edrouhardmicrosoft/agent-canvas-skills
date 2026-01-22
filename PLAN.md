# Canvas Skills Evolution Plan

## Current State Assessment

We have four AI agent skills for visual web development that work together:

| Skill | Purpose | Current State |
|-------|---------|---------------|
| **agent-eyes** | Visual context analyzer (screenshots, a11y, DOM) | ✅ Works well |
| **agent-canvas** | Interactive element picker with overlay | ✅ Works well |
| **canvas-edit** | Live style/text editor panel | ✅ Works well |
| **canvas-apply** | Convert visual edits to code changes | ✅ Complete |

**Completed:** The core workflow from visual edit to code change is functional.

---

## Identity & Positioning

### What This IS (Elevator Pitch)

> **"DevTools for shipping UI changes with AI"**

**One-sentence pitch:**
> "Inspect, select, and live-edit a real web UI—then turn those edits into a reviewable code patch and verify visually."

### Naming Recommendation

- **Suite name:** "UI Patch Kit" or "Canvas Patch Kit"
- Rename skills to clarify roles:
  - agent-eyes → **"snapshot"** (visual + a11y + DOM context)
  - agent-canvas → **"picker"** (interactive selection/targeting)
  - canvas-edit → **"editor"** (live intent capture + change recording)

### How It Differs From Alternatives

| Tool | What It Does | How We Differ |
|------|--------------|---------------|
| **DevTools** | Ephemeral edits, no handoff | We produce a **repeatable change request** with artifacts |
| **Figma Dev Mode** | Design intent | We operate on **what shipped** with real CSS quirks |
| **Pencil.dev** | Generate code from designs | We **surgically change production UI** |

---

## Critical Missing Features (Ranked)

| Rank | Feature | Gap | Solution |
|------|---------|-----|----------|
| **1** | **Patch Application Layer** | We emit `save_request` but don't convert it to code changes | Add `canvas-apply`: JSON → file candidates → proposed edits → git diff |
| **2** | **Diff + Approval Trust Layer** | Engineers won't trust "AI changed the UI" | Generate reviewable diff + before/after screenshots |
| **3** | **DOM→Code Mapping Hints** | No connection from selector to source file | Heuristics using `id`, `data-testid`, `className`, text anchors |
| **4** | **Verification Loop** | No way to prove changes worked | apply → reload → screenshot + a11y rerun |
| **5** | **Style Translation** (optional) | Raw CSS values, not Tailwind | Detect Tailwind → suggest classes |

---

## Strategic Paths Forward

| Path | Description | Pros | Cons |
|------|-------------|------|------|
| **A: UI Patch Workflow** | Inspection → selection → edit → **apply+diff+verify** | Clearest ROI, closest to current assets | DOM→code mapping is messy |
| **B: Accessibility Fix Loop** | agent-eyes finds issues → picker targets → editor fixes → verify re-runs axe | Crisp value, measurable outcomes | Narrower market |
| **C: Visual Diff + Suggestions** | AI proposes changes, previews visually, user approves | Strong "aha moment", designer-friendly | Harder to build, trust issues |

**Recommendation:** Start with **Path A**, add **Path C** later once apply+verify is solid.

---

## Designer Value Proposition

**Simple pitch:**
> "Open the real site, click what you mean, tweak it visually, and hand engineering a shareable change request that includes before/after screenshots *and* an exact diff."

**Designer "aha moment":**
> "Point at the real thing, propose a change, engineering applies with confidence—no ambiguity."

---

## Quick Wins (Do These First)

### 1. Session Artifact
Always write `.canvas/sessions/<sessionId>.json` with:
- Screenshots (before state)
- Change log (all edits)
- Selector confidence data

### 2. Patch Preview Output
On "Save All to Code", generate:
- File candidates (with confidence)
- Suggested edits
- Unified diff preview (even if not auto-applied)

### 3. Verify Command
```bash
canvas verify <url> --baseline <session>
```
- Captures after-screenshot
- Re-runs a11y scan
- Produces "did it work?" summary

---

## Action Plan (Prioritized)

### Phase 1: Foundation (1-2 days) ✅ COMPLETE
- [x] Define the "UI Patch" contract (what `save_request` must contain to be appliable)
- [x] Add session artifact output (`.canvas/sessions/<id>/session.json`)
- [x] Bundle intent: changes + selectors + alternatives + confidence + screenshots

### Phase 2: Apply MVP (2-3 days) ✅ COMPLETE
- [x] Build `canvas-apply` skill
  - [x] Parse session JSON (`session_parser.py`)
  - [x] Propose file candidates with confidence (`file_finder.py`)
  - [x] Generate unified diff (`diff_generator.py`)
  - [x] CLI with --diff, --apply, --verbose flags (`canvas_apply.py`)
  - [x] Conservative by default: show diff, require --apply flag

### Phase 3: Verification Loop (1 day) ✅ COMPLETE
- [x] Add `canvas verify` command
- [x] Before/after screenshot comparison
- [x] A11y rerun to prove fixes

### Phase 4: UX Unification (1 day) ✅ COMPLETE
- [x] Extended `agent-canvas pick` with new flags instead of new command
- [x] Added `--interactive` flag for post-session prompts
- [x] Added `--auto-apply` flag for automatic apply (CI mode)
- [x] Added `--auto-verify` flag for automatic verify (CI mode)
- [x] Integrated apply/verify workflows from sibling skills

### Phase 5: Enhancements (Later)
- [ ] Tailwind class detection and suggestion
- [ ] Design token inference
- [ ] Richer component boundary detection

---

## New Skills to Build

### canvas-apply
**Purpose:** Convert `save_request` JSON into code changes

**Input:**
```json
{
  "changes": {
    "styles": [{"selector": "h1.title", "property": "color", "newValue": "#ff0000"}],
    "texts": [{"selector": "h1.title", "oldText": "Hello", "newText": "Welcome"}]
  },
  "context": {
    "beforeScreenshot": "base64...",
    "selectorConfidence": "high",
    "alternatives": ["#main-title", "h1:first-child"]
  }
}
```

**Output:**
- File candidates with confidence scores
- Proposed edits (search/replace or AST-based)
- Unified diff for review
- Optional: auto-apply to files

### canvas-verify
**Purpose:** Prove that applied changes worked

**Input:** URL + baseline session ID

**Output:**
- After screenshot
- Visual diff (before/after)
- A11y delta (violations fixed? new ones introduced?)
- Pass/fail summary

---

## Architecture Notes

### Session Artifact Structure
```
.canvas/sessions/
├── ses_20260121_153045/
│   ├── session.json       # Full event log
│   ├── before.png         # Initial screenshot
│   ├── changes.json       # Extracted save_request
│   └── patch-preview.diff # Generated diff (if any)
```

### Event Flow
```
User clicks element → picker emits selection.changed
User edits styles → editor emits style.changed  
User clicks "Save" → editor emits save_request
                   → session artifact written
                   → patch preview generated
User runs apply → canvas-apply reads session
               → proposes file changes
               → generates diff
               → optionally applies
User runs verify → canvas-verify screenshots
                → runs a11y
                → compares to baseline
```

---

## Success Metrics

1. **Time to code change:** How long from "I want to change this color" to "code is updated"
2. **Confidence in changes:** Can engineer review exactly what will change before applying?
3. **Verification coverage:** Can we prove the change worked without manual checking?
4. **Designer adoption:** Would a designer use this instead of marking up screenshots?

---

## Open Questions

1. How to handle framework-specific code patterns (React className vs Vue :class vs Svelte class:)?
2. Should we support CSS-in-JS (styled-components, emotion)?
3. How deep should component boundary detection go?
4. Should `canvas-apply` be conservative (propose only) or aggressive (auto-apply)?
