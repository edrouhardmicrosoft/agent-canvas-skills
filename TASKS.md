# Next Session Tasks: Phase 1 Foundation

## Current State Assessment

**Where we are:** Working prototype of three skills (agent-eyes, agent-canvas, canvas-edit) that function individually but don't close the loop. The workflow ends at "emit JSON" with no path to actual code changes.

**Development stage:** Core functionality - individual tools work, but end-to-end value proposition is incomplete.

**Target fidelity:** Personal tool → alpha transition.

---

## Session Goal

Implement session artifacts so the workflow produces durable, structured output that future skills (`canvas-apply`, `canvas-verify`) can consume.

---

## Tasks for AI Coding Agent

| # | Task | Description | Effort | Status |
|---|------|-------------|--------|--------|
| 1 | **Add session artifact output to agent-canvas** | When session ends, write `.canvas/sessions/<sessionId>/` with `session.json` (full event log) and `before.png` (initial screenshot) | Short | [x] |
| 2 | **Enhance save_request payload** | Bundle: changes + selectors + alternatives + confidence + beforeScreenshot reference | Short | [x] |
| 3 | **Create session directory structure** | Ensure `.canvas/sessions/` exists, generate proper session IDs with timestamps | Quick | [x] |

### Implementation Details

#### Task 1: Session Artifact Output

**Modify:** `.claude/skills/agent-canvas/scripts/agent_canvas.py`

**Changes:**
1. At session start, create `.canvas/sessions/<sessionId>/` directory
2. Take initial screenshot and save as `before.png`
3. At session end, write `session.json` with:
   - All events (selections + edits)
   - Session metadata (url, start time, end time, features enabled)
   - Reference to `before.png`

#### Task 2: Enhanced save_request

**Modify:** `.claude/skills/canvas-edit/scripts/canvas_edit.py`

**Changes:**
1. When emitting `save_request`, include:
   - `selectorConfidence` for each change
   - `selectorAlternatives` for each change
   - Reference to session (so apply can find before screenshot)

#### Task 3: Session Directory Structure

**Expected output:**
```
.canvas/sessions/
├── ses_20260121_153045/
│   ├── session.json       # Full event log + metadata
│   ├── before.png         # Initial screenshot
│   └── changes.json       # Extracted save_request (if user clicked Save)
```

---

## Tasks for Human (Erik)

| # | Task | Description | Why You |
|---|------|-------------|---------|
| 1 | **Decide on session ID format** | `ses_20260121_153045` vs `ses_<uuid>` vs something else? | Design decision |
| 2 | **Test current workflow end-to-end** | Run `agent-canvas pick http://localhost:3000 --with-edit --with-eyes`, make edits, close browser, verify JSON output | Only you can evaluate UX |
| 3 | **Answer: Screenshot storage format?** | Base64 in JSON (portable) or separate PNG file (smaller JSON)? | Design decision |

### Design Decisions Needed

Before AI agent proceeds:

- [x] **Session ID format:** `ses-<uuid>` (12 char hex) ✓
- [x] **Screenshot storage:** Base64 in JSON (portable) ✓
- [x] **Run dev server first?** Should AI test current state before modifying? ✓

---

## Session End Checklist

After implementation:
- [x] Update PLAN.md to mark Phase 1 tasks as complete
- [x] Update README.md with new session artifact behavior
- [x] Test: Run a full session, verify `.canvas/sessions/` is created with expected files
- [x] Document any learnings or issues encountered

---

## Learnings & Notes (Phase 1)

### What Worked Well
- Session artifact structure using directory-per-session (`ses-<id>/`) allows for future expansion (e.g., separate `after.png` for verification)
- Base64 screenshots in JSON keeps sessions self-contained and portable
- Event log captures full interaction history for debugging and replay

### Design Decisions Made
- **Session ID format**: `ses-<12-char-hex>` - short enough to type, long enough to be unique
- **Screenshot storage**: Base64 in JSON (not separate PNG files) - prioritizes portability over file size
- **Artifact location**: `.canvas/sessions/` at project root - easy to gitignore, doesn't pollute source

### Notes for Phase 2 (canvas-apply)
- `save_request` now includes `selectorConfidence` and `selectorAlternatives` - use these for file matching heuristics
- Session artifacts reference screenshots by session ID, not embedded in `changes.json`
- Consider adding `changes.json` extraction on browser close (currently only written on "Save All" click)

---

## What This Unlocks

Once session artifacts exist:
- **Next session:** Build `canvas-apply` that reads session JSON
- **After that:** Build `canvas-verify` that compares before/after
- **Result:** Complete the "UI Patch Workflow" (Path A from PLAN.md)

---

## Commands for Testing

```bash
# Start the dev server
npm run dev

# Run a full canvas session (in another terminal)
uv run .claude/skills/agent-canvas/scripts/agent_canvas.py pick http://localhost:3000 --with-edit --with-eyes

# After closing browser, check for session artifacts
ls -la .canvas/sessions/
```
