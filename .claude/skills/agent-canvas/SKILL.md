---
name: agent-canvas
description: Interactive element picker for web pages. Opens a browser with click-to-select UI overlay. Use when you need to let users visually select DOM elements, identify element selectors, or get detailed element information interactively. Triggers on "select an element", "pick element", "let me choose", "which element", or any interactive element selection task. Integrates with agent-eyes for visual context.
---

# Agent Canvas

Interactive element picker that opens a browser window with a DevTools-like selection overlay. Users hover to highlight elements and click to select. Returns detailed element info including selector, bounding box, and computed styles.

## First-Time Setup

**Before first use**, verify dependencies are installed:

```bash
uv run .claude/skills/agent-canvas-setup/scripts/check_setup.py check
```

If checks fail, ask user which installation scope they prefer and run:

```bash
# Recommended: minimal footprint, uv manages deps on-demand
uv run .claude/skills/agent-canvas-setup/scripts/check_setup.py install --scope temporary

# Alternative: create .venv in project
uv run .claude/skills/agent-canvas-setup/scripts/check_setup.py install --scope local
```

See `agent-canvas-setup` skill for full details on installation options.

## Commands

```bash
SKILL_DIR=".claude/skills/agent-canvas/scripts"
```

### Pick Element

Open browser with element picker overlay. Streams selection events as JSON lines until window is closed:

```bash
# Basic pick - opens browser, streams selections as JSON lines
uv run $SKILL_DIR/agent_canvas.py pick http://localhost:3000

# Pick with agent-eyes integration (adds screenshot + detailed styles per selection)
uv run $SKILL_DIR/agent_canvas.py pick http://localhost:3000 --with-eyes

# Pick with edit panel (floating DevTools for live style editing)
uv run $SKILL_DIR/agent_canvas.py pick http://localhost:3000 --with-edit

# Full workflow: picker + edit panel + agent-eyes (recommended)
uv run $SKILL_DIR/agent_canvas.py pick http://localhost:3000 --with-edit --with-eyes

# Save all selections and edits to file when done
uv run $SKILL_DIR/agent_canvas.py pick http://localhost:3000 --with-edit --output ./session.json
```

**User interaction:**
1. Browser opens with blue highlight overlay
2. Hover over elements to see selector labels
3. Click to select (overlay flashes green, counter increments)
4. Keep clicking to select more elements
5. Close browser window when done

**Streamed output (JSON lines):**
```json
{"event": "session_started", "url": "http://localhost:3000", "timestamp": "...", "features": {"picker": true, "eyes": true, "edit": true}}
{"event": "selection", "index": 1, "timestamp": "...", "element": {"tag": "button", "selector": "#submit", ...}}
{"event": "style_change", "timestamp": "...", "selector": "#submit", "property": "backgroundColor", "newValue": "#ff0000"}
{"event": "session_ended", "timestamp": "...", "total_selections": 1, "total_edits": 1}
```

With `--with-eyes`, each selection event also includes `eyes` (detailed styles) and `screenshot` fields.
With `--with-edit`, style changes made in the floating panel are emitted as `style_change` events.

### Watch for Changes

Monitor page for DOM changes, capture screenshots on each change:

```bash
# Watch with default 2s interval
uv run $SKILL_DIR/agent_canvas.py watch http://localhost:3000

# Custom interval
uv run $SKILL_DIR/agent_canvas.py watch http://localhost:3000 --interval 5

# Custom output directory
uv run $SKILL_DIR/agent_canvas.py watch http://localhost:3000 --output-dir ./snapshots
```

Outputs JSON events to stdout:
```json
{"event": "watch_started", "url": "http://localhost:3000", "interval": 2.0}
{"event": "change_detected", "iteration": 1, "timestamp": "...", "screenshot": ".canvas/screenshots/..."}
```

## Typical Workflow

1. **Let user select element:**
   ```bash
   uv run $SKILL_DIR/agent_canvas.py pick http://localhost:3000 --with-eyes
   ```

2. **Use returned selector for further analysis:**
   ```bash
   # Get accessibility info for selected element
   uv run .claude/skills/agent-eyes/scripts/agent_eyes.py a11y http://localhost:3000 --selector "#selected-element"
   ```

3. **Make changes to the element's styles/content**

4. **Verify changes with agent-eyes:**
   ```bash
   uv run .claude/skills/agent-eyes/scripts/agent_eyes.py screenshot http://localhost:3000
   ```

## Integration with Agent Eyes

When `--with-eyes` flag is used, agent-canvas calls agent-eyes to:
1. Get detailed element description (computed styles, attributes, visibility)
2. Take a screenshot of the selected element

This provides comprehensive visual context for the AI agent to understand and modify the selected element.

## Integration with Canvas Edit

When `--with-edit` flag is used, agent-canvas loads the canvas-edit floating panel:
1. Users can visually adjust styles (colors, typography, spacing) 
2. Changes apply live to the page for preview
3. Style change events stream alongside selection events
4. The panel uses Shadow DOM, so it's invisible to agent-eyes screenshots

**Recommended workflow:**
```bash
uv run $SKILL_DIR/agent_canvas.py pick http://localhost:3000 --with-edit --with-eyes
```
This gives users full control to select elements, preview style changes, while the agent receives both the visual context and the specific CSS changes to implement.

## Notes

- Browser launches in **visible mode** for `pick` command (user interaction required)
- Browser runs **headless** for `watch` command
- Selection events stream as JSON lines to stdout in real-time
- Close the browser window to end the session
- Overlay elements are excluded from selection
