# Canvas Edit Toolbar Redesign

**Status**: Blocked - needs design decision  
**Created**: 2026-01-24  
**Related Files**:
- `.claude/skills/agent-canvas/scripts/agent_canvas.py` (--with-edit flag)
- `.claude/skills/canvas-edit/scripts/annotation_toolbar.js` (current toolbar)
- `.claude/skills/canvas-edit/scripts/canvas_edit.py`

---

## Problem Statement

The `--with-edit` flag on `agent-canvas pick` promises "live style editing" but actually injects a **design-review annotation toolbar** that is non-functional without pre-loaded issues.

### Current Behavior

When running:
```bash
uv run agent_canvas.py pick https://example.com --with-edit --with-eyes
```

A floating toolbar appears with:
| Button | Icon | Expected | Actual |
|--------|------|----------|--------|
| Drag handle | ☰ | Drag to reposition | Works |
| Eye | 👁 | Toggle annotation visibility | Does nothing (no annotations exist) |
| Camera | 📸 | Capture screenshot | Emits event but no handler responds |
| Filter | ⚙ | Filter issues by severity | Does nothing (no issues loaded) |
| Orientation | ↕ | Toggle horizontal/vertical | Works |
| Dismiss | ✕ | Close toolbar | Works |

**Root Cause**: The `annotation_toolbar.js` was designed for the **design-review workflow** where issues are pre-loaded. The `--with-edit` flag incorrectly reuses this toolbar expecting it to provide live editing capabilities.

### User Impact

- Confusing UI that looks interactive but isn't
- Counter shows "0 Issues" with no way to add issues
- Eye/camera buttons appear clickable but do nothing
- Breaks user trust in the tool

---

## Temporary Fix Applied

The `--with-edit` toolbar injection has been **commented out** in `agent_canvas.py`:

```python
# NOTE: --with-edit toolbar temporarily disabled
# See plans/toolbar-update.md for the redesign plan.
```

The `--with-edit` flag still exists but now has no effect. The `features.edit` field in session artifacts is set to `false`.

---

## Design Options

### Option A: Remove --with-edit Entirely

**Effort**: Low  
**Impact**: Breaking change for anyone using the flag

Simply remove the flag and document that live editing is not supported. The picker workflow would be:
1. Select elements
2. Get element info (selector, styles, bounding box)
3. Agent makes code changes based on selection data

**Pros**: Clean, no misleading UI  
**Cons**: Loses the vision of live visual editing

---

### Option B: Build Actual Edit Panel

**Effort**: High  
**Impact**: New feature

Create a proper editing panel that allows:
- Color pickers for background/text colors
- Spacing controls (margin, padding)
- Typography controls (font-size, font-weight)
- Live preview of changes
- "Save to Code" button that emits changes for `canvas-apply`

**Architecture**:
```
┌─────────────────────────────────────────┐
│  Edit Panel (Shadow DOM)                │
├─────────────────────────────────────────┤
│  Selected: button#submit                │
├─────────────────────────────────────────┤
│  Background  [#3b82f6] [picker]         │
│  Text Color  [#ffffff] [picker]         │
│  Font Size   [14px   ] [-][+]           │
│  Padding     [8px 16px] [    ]          │
├─────────────────────────────────────────┤
│  [Reset] [Preview] [Save to Code]       │
└─────────────────────────────────────────┘
```

**Event Flow**:
1. User selects element via picker
2. Edit panel populates with current computed styles
3. User adjusts values, changes apply live to DOM
4. "Save to Code" emits `save_request` event with all changes
5. `canvas-apply` skill maps DOM changes to source code edits

**Pros**: Full visual editing workflow  
**Cons**: Significant development effort, needs source mapping

---

### Option C: Repurpose Existing Toolbar for Picker Context

**Effort**: Medium  
**Impact**: Improved UX

Modify `annotation_toolbar.js` to have a **picker mode** vs **review mode**:

**Picker Mode** (when loaded via agent-canvas):
- Shows selection count instead of issue count
- Eye button toggles picker overlay visibility
- Camera button captures screenshot of page
- No filter/severity controls (irrelevant)

**Review Mode** (when loaded via design-review):
- Current behavior with issues, severities, filters

**Implementation**:
```javascript
const mode = window.__canvasBus?.state?.activeTools?.has('picker') ? 'picker' : 'review';

if (mode === 'picker') {
    // Show: drag, selection count, screenshot, orientation, dismiss
    // Hide: eye toggle, filter, severity badges
}
```

**Pros**: Reuses existing code, contextually appropriate UI  
**Cons**: Toolbar becomes overloaded with mode logic

---

## Recommendation

**Start with Option A** (remove the flag) for now, then implement **Option B** (proper edit panel) as a separate focused effort.

The live editing workflow is compelling but requires:
1. Proper UI design for the edit panel
2. Source mapping to convert DOM changes to code edits
3. Integration with `canvas-apply` for the actual file modifications

This is a feature, not a bug fix, and deserves dedicated design attention.

---

## Action Items

- [x] Disable `--with-edit` toolbar injection (temporary fix)
- [ ] Decide on design direction (A, B, or C)
- [ ] If Option B: Create detailed UI spec for edit panel
- [ ] If Option B: Design source mapping strategy (selector -> file location)
- [ ] Update SKILL.md documentation to reflect current state
- [ ] Consider deprecation warning if --with-edit is used

---

## Related Context

### Existing canvas-apply workflow

The `canvas-apply` skill already handles mapping DOM changes to source code:

```
session.json (with save_request) 
    → parse_session() 
    → generate_diffs() 
    → file modifications
```

A proper edit panel would feed into this same workflow, emitting `save_request` events with style/text changes that `canvas-apply` can process.

### Design-review integration

The annotation toolbar works well for design-review because issues are structured data with:
- Selector (where)
- Severity (priority)  
- Description (what's wrong)
- Pillar (category)

An edit panel would need similar structure for changes:
- Selector (where)
- Property (what)
- Old value (was)
- New value (now)
