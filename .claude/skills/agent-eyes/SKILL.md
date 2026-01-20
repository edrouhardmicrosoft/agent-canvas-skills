---
name: agent-eyes
description: Visual context analyzer for AI agents. Provides screenshots, accessibility scans, DOM snapshots, and element descriptions for web pages. Use when you need to see what a web page looks like, analyze accessibility issues, inspect DOM structure, or get detailed element information. Triggers on requests like "take a screenshot", "check accessibility", "what does this page look like", "analyze the UI", "inspect this element", or any visual/UI analysis task.
---

# Agent Eyes

Visual context analyzer for web pages. Provides AI agents with the ability to "see" web applications through screenshots, accessibility scans, DOM snapshots, and element descriptions.

## Prerequisites

- Python 3.10+
- `uv` package manager (recommended)
- Playwright browsers installed: `playwright install chromium`

## Commands

All commands use `uv run` for automatic dependency management:

```bash
SKILL_DIR=".claude/skills/agent-eyes/scripts"
```

### Screenshot

Capture full page or element screenshots:

```bash
# Full page screenshot (saves to .canvas/screenshots/)
uv run $SKILL_DIR/agent_eyes.py screenshot http://localhost:3000

# Element screenshot
uv run $SKILL_DIR/agent_eyes.py screenshot http://localhost:3000 --selector ".hero"

# Save to specific path
uv run $SKILL_DIR/agent_eyes.py screenshot http://localhost:3000 --output ./tmp/page.png

# Get as base64 (for inline context)
uv run $SKILL_DIR/agent_eyes.py screenshot http://localhost:3000 --base64
```

### Accessibility Scan

Run axe-core accessibility analysis:

```bash
# Full page scan (WCAG 2.1 AA)
uv run $SKILL_DIR/agent_eyes.py a11y http://localhost:3000

# Scoped to element
uv run $SKILL_DIR/agent_eyes.py a11y http://localhost:3000 --selector "main"

# WCAG AAA level
uv run $SKILL_DIR/agent_eyes.py a11y http://localhost:3000 --level AAA
```

### DOM Snapshot

Get simplified DOM tree:

```bash
# Full page DOM
uv run $SKILL_DIR/agent_eyes.py dom http://localhost:3000

# Subtree only
uv run $SKILL_DIR/agent_eyes.py dom http://localhost:3000 --selector ".content"

# Control depth
uv run $SKILL_DIR/agent_eyes.py dom http://localhost:3000 --depth 3
```

### Describe Element

Get detailed element information (styles, bounding box, attributes):

```bash
uv run $SKILL_DIR/agent_eyes.py describe http://localhost:3000 --selector ".hero-button"
```

### Full Context

Get comprehensive context bundle (screenshot + a11y + DOM + description):

```bash
# Full context for page
uv run $SKILL_DIR/agent_eyes.py context http://localhost:3000

# Focused on element
uv run $SKILL_DIR/agent_eyes.py context http://localhost:3000 --selector ".hero"

# Without screenshot (smaller output)
uv run $SKILL_DIR/agent_eyes.py context http://localhost:3000 --no-screenshot
```

## Output Format

All commands return JSON to stdout:

```json
{
  "ok": true,
  "...": "command-specific fields"
}
```

On error:

```json
{
  "ok": false,
  "error": "Error description"
}
```

## Typical Agent Workflow

1. **Start dev server** (if not running):
   ```bash
   npm run dev &
   ```

2. **Take initial screenshot** to see current state:
   ```bash
   uv run $SKILL_DIR/agent_eyes.py screenshot http://localhost:3000
   ```

3. **Run accessibility scan** to find issues:
   ```bash
   uv run $SKILL_DIR/agent_eyes.py a11y http://localhost:3000
   ```

4. **Inspect specific element** for details:
   ```bash
   uv run $SKILL_DIR/agent_eyes.py describe http://localhost:3000 --selector ".problematic-button"
   ```

5. **Get full context** for comprehensive analysis:
   ```bash
   uv run $SKILL_DIR/agent_eyes.py context http://localhost:3000 --selector ".hero"
   ```

## Example: Analyze and Fix A11y Issues

```bash
# 1. Get accessibility violations
uv run $SKILL_DIR/agent_eyes.py a11y http://localhost:3000

# Output shows violations like:
# {
#   "ok": true,
#   "violations": [
#     {
#       "id": "color-contrast",
#       "impact": "serious",
#       "description": "Elements must have sufficient color contrast",
#       "nodes": [{"html": "<button class='cta'>..."}]
#     }
#   ]
# }

# 2. Describe the element to understand current styles
uv run $SKILL_DIR/agent_eyes.py describe http://localhost:3000 --selector ".cta"

# 3. Make code changes to fix the contrast issue

# 4. Re-run a11y to verify fix
uv run $SKILL_DIR/agent_eyes.py a11y http://localhost:3000
```

## Notes

- Screenshots are saved to `.canvas/screenshots/` by default with ISO timestamps
- The tool runs headless Chromium via Playwright
- All commands wait for `networkidle` before capturing
- DOM snapshots are simplified to reduce output size
- A11y scans use axe-core, the industry standard accessibility testing engine
