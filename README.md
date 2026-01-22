<p align="center">
  <img src="Agent Canvas Logo.png" alt="Agent Canvas" width="600">
</p>

# Agent Canvas Skills

> **DevTools for shipping UI changes with AI**

Inspect, select, and live-edit a real web UI—then turn those edits into a reviewable code patch and verify visually.

## Overview

A suite of 6 AI agent skills for visual web development. Works with **any web page**.

| Skill | Role | Docs |
|-------|------|------|
| [agent-canvas-setup](.claude/skills/agent-canvas-setup/SKILL.md) | Dependency installer | First-time setup |
| [agent-eyes](.claude/skills/agent-eyes/SKILL.md) | Visual context | Screenshots, a11y, DOM |
| [agent-canvas](.claude/skills/agent-canvas/SKILL.md) | Element picker | Interactive selection |
| [canvas-edit](.claude/skills/canvas-edit/SKILL.md) | Live editing | Style/text changes |
| [canvas-apply](.claude/skills/canvas-apply/SKILL.md) | Code generation | Visual edits → code |
| [canvas-verify](.claude/skills/canvas-verify/SKILL.md) | Verification | Before/after comparison |

### Workflow

```
PICK ──▶ EDIT ──▶ APPLY ──▶ VERIFY
```

1. **Pick**: Select elements visually in the browser
2. **Edit**: Change text, colors, spacing live
3. **Apply**: Convert edits to code changes
4. **Verify**: Confirm with screenshots + a11y

---

## Prerequisites

- Python 3.10+
- `uv` package manager
- Playwright: `playwright install chromium`

### First-Time Setup

```bash
uv run .claude/skills/agent-canvas-setup/scripts/check_setup.py check

# If checks fail:
uv run .claude/skills/agent-canvas-setup/scripts/check_setup.py install --scope temporary
```

---

## Quick Start

### Full Workflow

```bash
uv run .claude/skills/agent-canvas/scripts/agent_canvas.py pick <url> --with-edit --with-eyes
```

1. Browser opens → click elements to select
2. Edit in floating panel → changes apply live
3. Click "Save All to Code" → close browser

### Modes

```bash
# Interactive: prompts for apply/verify
... pick <url> --with-edit --with-eyes --interactive

# Auto: applies and verifies automatically
... pick <url> --with-edit --with-eyes --auto-apply --auto-verify
```

---

## Skills

### agent-canvas-setup

Dependency checker and installer. **Run this first.**

```bash
uv run .claude/skills/agent-canvas-setup/scripts/check_setup.py check
```

→ [Full docs](.claude/skills/agent-canvas-setup/SKILL.md)

### agent-eyes

Screenshots, accessibility scans, DOM snapshots.

```bash
uv run .claude/skills/agent-eyes/scripts/agent_eyes.py screenshot <url>
uv run .claude/skills/agent-eyes/scripts/agent_eyes.py a11y <url>
```

→ [Full docs](.claude/skills/agent-eyes/SKILL.md)

### agent-canvas

Interactive element picker with browser overlay.

```bash
uv run .claude/skills/agent-canvas/scripts/agent_canvas.py pick <url> --with-edit --with-eyes
```

→ [Full docs](.claude/skills/agent-canvas/SKILL.md)

### canvas-edit

Floating panel for live text and style editing.

```bash
uv run .claude/skills/canvas-edit/scripts/canvas_edit.py edit <url>
```

→ [Full docs](.claude/skills/canvas-edit/SKILL.md)

### canvas-apply

Convert visual edit sessions to code changes.

```bash
python3 .claude/skills/canvas-apply/scripts/canvas_apply.py --list
python3 .claude/skills/canvas-apply/scripts/canvas_apply.py <sessionId> --apply
```

→ [Full docs](.claude/skills/canvas-apply/SKILL.md)

### canvas-verify

Verify changes with before/after comparison.

```bash
uv run .claude/skills/canvas-verify/scripts/canvas_verify.py <url> --session <sessionId>
```

→ [Full docs](.claude/skills/canvas-verify/SKILL.md)

---

## For AI Agents

See **[docs/AGENTS.md](docs/AGENTS.md)** for:
- Skill selection guide
- Trigger phrases
- Command reference
- Workflow sequences
- Output parsing
- Error handling

---

## Session Artifacts

Sessions are saved to `.canvas/sessions/<sessionId>/`:

```
session.json   # Full event log + metadata
changes.json   # Extracted save_request
```

---

## Try It Out (Optional Demo)

This repo includes a Next.js demo app to test the skills:

```bash
# 1. Start the demo server
npm run dev

# 2. Run canvas skills against it
uv run .claude/skills/agent-canvas/scripts/agent_canvas.py pick http://localhost:3000 --with-edit --with-eyes
```

The skills work with any web page—the demo is just a convenient starting point.

---

## Project Structure

```
.claude/skills/
├── agent-canvas-setup/    # Dependency installer
├── agent-eyes/            # Visual context
├── agent-canvas/          # Element picker
├── canvas-edit/           # Style editor
├── canvas-apply/          # Code generator
├── canvas-verify/         # Verification
└── shared/                # Shared utilities

docs/
└── AGENTS.md              # AI agent reference
```
