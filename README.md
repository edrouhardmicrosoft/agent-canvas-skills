# Agent Canvas Skills

> **DevTools for shipping UI changes with AI**

Inspect, select, and live-edit a real web UI—then turn those edits into a reviewable code patch and verify visually.

---

## Overview

Agent Canvas Skills is a suite of 6 interconnected AI agent skills for visual web development. These tools work with **any web page** to let AI agents "see" the UI, let users select and edit elements visually, and convert those edits into actual code changes.

| Skill | Role | Description |
|-------|------|-------------|
| **agent-canvas-setup** | Installation | Dependency checker and installer |
| **agent-eyes** | Visual context | Screenshots, accessibility scans, DOM snapshots |
| **agent-canvas** | Element picker | Interactive browser overlay to select elements |
| **canvas-edit** | Live editing | Floating DevTools panel for style/text changes |
| **canvas-apply** | Code generation | Convert visual edits to actual code changes |
| **canvas-verify** | Verification | Before/after screenshots + a11y comparison |

### The Complete Workflow

```
┌─────────┐     ┌─────────┐     ┌─────────┐     ┌─────────┐
│  PICK   │ ──▶ │  EDIT   │ ──▶ │  APPLY  │ ──▶ │ VERIFY  │
│         │     │         │     │         │     │         │
│ Select  │     │ Change  │     │ Generate│     │ Confirm │
│ element │     │ styles  │     │ code    │     │ it works│
└─────────┘     └─────────┘     └─────────┘     └─────────┘
```

1. **Pick**: User visually selects elements in the browser
2. **Edit**: User makes visual changes (text, colors, spacing)
3. **Apply**: AI converts visual edits to actual code changes
4. **Verify**: Screenshots + a11y scans prove it worked

---

## Prerequisites

- Python 3.10+
- `uv` package manager
- Playwright browsers: `playwright install chromium`

### First-Time Setup

Run the setup checker before using any canvas skill:

```bash
uv run .claude/skills/agent-canvas-setup/scripts/check_setup.py check
```

If checks fail, install dependencies:

```bash
# Recommended: minimal footprint
uv run .claude/skills/agent-canvas-setup/scripts/check_setup.py install --scope temporary
```

---

## Quick Start

### Full Visual Editing Workflow

```bash
uv run .claude/skills/agent-canvas/scripts/agent_canvas.py pick http://localhost:3000 --with-edit --with-eyes
```

This opens a browser where you can:
1. Click elements to select them
2. Edit text and styles in the floating panel
3. Click "Save All to Code" when done
4. Close the browser to end the session

### Interactive vs Auto Modes

```bash
# Interactive mode - prompts for apply/verify after editing
uv run .claude/skills/agent-canvas/scripts/agent_canvas.py pick <url> --with-edit --with-eyes --interactive

# CI/Auto mode - automatically applies and verifies
uv run .claude/skills/agent-canvas/scripts/agent_canvas.py pick <url> --with-edit --with-eyes --auto-apply --auto-verify
```

---

## Skills Reference

### agent-canvas-setup

Checks and installs dependencies for all canvas skills.

**Trigger phrases:** "setup agent canvas", "install canvas dependencies", "canvas not working", "playwright not found"

**Key commands:**

```bash
SKILL_DIR=".claude/skills/agent-canvas-setup/scripts"

# Check if dependencies are installed
uv run $SKILL_DIR/check_setup.py check

# Install with minimal footprint (recommended)
uv run $SKILL_DIR/check_setup.py install --scope temporary

# Install with project-local .venv
uv run $SKILL_DIR/check_setup.py install --scope local
```

See `.claude/skills/agent-canvas-setup/SKILL.md` for full documentation.

---

### agent-eyes

Visual context analyzer. Provides AI agents with the ability to "see" web pages.

**Trigger phrases:** "take a screenshot", "check accessibility", "what does this page look like", "analyze the UI", "inspect this element"

**Key commands:**

```bash
SKILL_DIR=".claude/skills/agent-eyes/scripts"

# Screenshot (full page)
uv run $SKILL_DIR/agent_eyes.py screenshot http://localhost:3000

# Accessibility scan (WCAG 2.1 AA)
uv run $SKILL_DIR/agent_eyes.py a11y http://localhost:3000

# Full context bundle (screenshot + a11y + DOM)
uv run $SKILL_DIR/agent_eyes.py context http://localhost:3000
```

See `.claude/skills/agent-eyes/SKILL.md` for full documentation.

---

### agent-canvas

Interactive element picker with DevTools-like selection overlay.

**Trigger phrases:** "select an element", "pick element", "let me choose", "which element"

**Key commands:**

```bash
SKILL_DIR=".claude/skills/agent-canvas/scripts"

# Basic pick - streams selections as JSON
uv run $SKILL_DIR/agent_canvas.py pick http://localhost:3000

# Full workflow: picker + edit panel + visual context
uv run $SKILL_DIR/agent_canvas.py pick http://localhost:3000 --with-edit --with-eyes

# Watch for DOM changes
uv run $SKILL_DIR/agent_canvas.py watch http://localhost:3000
```

See `.claude/skills/agent-canvas/SKILL.md` for full documentation.

---

### canvas-edit

Floating DevTools panel for live text and style editing.

**Trigger phrases:** "edit text", "change content", "edit styles", "change colors", "adjust spacing", "tweak UI"

**Key commands:**

```bash
SKILL_DIR=".claude/skills/canvas-edit/scripts"

# Open page with edit panel
uv run $SKILL_DIR/canvas_edit.py edit http://localhost:3000

# Save changes to file
uv run $SKILL_DIR/canvas_edit.py edit http://localhost:3000 --output ./changes.json
```

**Panel controls:**
- **Text**: Textarea or direct on-page editing
- **Colors**: Background and text color pickers
- **Typography**: Font size (8-72px) and weight (100-900)
- **Spacing**: Padding (0-64px) and border radius (0-50px)

See `.claude/skills/canvas-edit/SKILL.md` for full documentation.

---

### canvas-apply

Convert visual edit sessions into actual code changes.

**Trigger phrases:** "apply canvas changes", "apply session", "convert edits to code", "apply visual edits"

**Key commands:**

```bash
SKILL_DIR=".claude/skills/canvas-apply/scripts"

# List available sessions
python3 $SKILL_DIR/canvas_apply.py --list

# Preview changes
python3 $SKILL_DIR/canvas_apply.py <sessionId>

# Show unified diff
python3 $SKILL_DIR/canvas_apply.py <sessionId> --diff

# Apply changes to files
python3 $SKILL_DIR/canvas_apply.py <sessionId> --apply
```

**Confidence scoring:** The tool maps DOM selectors to source files using ID attributes (~95%), data-testid (~90%), className+tag (65-95%), and text content (60-80%).

See `.claude/skills/canvas-apply/SKILL.md` for full documentation.

---

### canvas-verify

Verify that applied changes worked by comparing screenshots and accessibility.

**Trigger phrases:** "verify canvas changes", "verify session", "check if changes worked", "compare before and after"

**Key commands:**

```bash
SKILL_DIR=".claude/skills/canvas-verify/scripts"

# Full verification (visual + a11y)
uv run $SKILL_DIR/canvas_verify.py <url> --session <sessionId>

# Visual comparison only
uv run $SKILL_DIR/canvas_verify.py <url> --session <sessionId> --visual

# Accessibility comparison only
uv run $SKILL_DIR/canvas_verify.py <url> --session <sessionId> --a11y
```

See `.claude/skills/canvas-verify/SKILL.md` for full documentation.

---

## Session Artifacts

Canvas sessions are recorded to `.canvas/sessions/` for use by canvas-apply and canvas-verify.

### Directory Structure

```
.canvas/sessions/
└── ses-a1b2c3d4e5f6/           # 12-char hex session ID
    ├── session.json            # Full event log + metadata
    └── changes.json            # Extracted save_request (if "Save All" clicked)
```

### Session JSON Structure

```json
{
  "sessionId": "ses-a1b2c3d4e5f6",
  "url": "http://localhost:3000",
  "startTime": "2026-01-21T15:30:45.123Z",
  "endTime": "2026-01-21T15:35:12.456Z",
  "features": { "withEdit": true, "withEyes": true },
  "beforeScreenshot": "data:image/png;base64,...",
  "events": [...]
}
```

### Event Types

| Event Type | Description |
|------------|-------------|
| `selection.changed` | User clicked to select an element |
| `style.changed` | User modified a style property |
| `text.changed` | User edited element text |
| `save_request` | User clicked "Save All to Code" |

---

## For AI Agents

Skills are located in `.claude/skills/` and follow a consistent structure:

```
.claude/skills/<skill-name>/
├── SKILL.md              # Documentation with trigger phrases
└── scripts/              # Python scripts to execute
```

### Trigger Phrase Reference

| Skill | Trigger Phrases |
|-------|-----------------|
| agent-canvas-setup | "setup agent canvas", "install dependencies", "canvas not working" |
| agent-eyes | "take screenshot", "check accessibility", "analyze UI" |
| agent-canvas | "select element", "pick element", "let me choose" |
| canvas-edit | "edit text", "change colors", "adjust spacing" |
| canvas-apply | "apply changes", "convert to code", "apply session" |
| canvas-verify | "verify changes", "compare before after", "check if worked" |

---

## Project Structure

```
.claude/skills/
├── agent-canvas-setup/    # Dependency installer
├── agent-eyes/            # Visual context analyzer
├── agent-canvas/          # Element picker
├── canvas-edit/           # Live style editor
├── canvas-apply/          # Code generator
├── canvas-verify/         # Verification tool
└── shared/                # Shared utilities
```

---

## Notes

- Skills work with **any web page**, not just the included demo
- All tools output JSON for easy parsing by AI agents
- Screenshots are stored as base64 data URIs for portability
- The edit panel uses Shadow DOM, so it's invisible to screenshots
