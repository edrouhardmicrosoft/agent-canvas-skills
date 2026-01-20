---
name: canvas-edit
description: Floating DevTools-like panel for live UI editing including text and styles. Provides text editing (inline or via textarea), color pickers, typography controls, and spacing adjustments. Uses Shadow DOM to be invisible to agent-eyes screenshots. Emits save_request events for the agent to update code files. Triggers on "edit text", "change content", "edit styles", "change colors", "adjust spacing", "tweak UI", or any visual editing task.
---

# Canvas Edit

Floating DevTools-like panel that lets users visually edit element styles AND text content. Changes are applied live to the page and streamed as JSON events for the AI agent to implement in code.

**Key features:**
- **Live text editing** - Edit text directly on the page or via textarea
- **Style controls** - Colors, typography, spacing
- **Shadow DOM** - Panel is invisible to agent-eyes screenshots
- **Save to Code** - One-click to emit all changes for agent implementation

## Prerequisites

- Python 3.10+
- `uv` package manager
- Playwright browsers: `playwright install chromium`

## Commands

```bash
SKILL_DIR=".claude/skills/canvas-edit/scripts"
```

### Standalone Edit Session

```bash
# Open page with edit panel
uv run $SKILL_DIR/canvas_edit.py edit http://localhost:3000

# Save all changes to file
uv run $SKILL_DIR/canvas_edit.py edit http://localhost:3000 --output ./changes.json
```

### Integrated with Agent Canvas (Recommended)

```bash
# Full workflow: picker + edit panel + agent-eyes
uv run .claude/skills/agent-canvas/scripts/agent_canvas.py pick http://localhost:3000 --with-edit --with-eyes
```

## Panel Controls

The floating panel provides:

**Text Content**
- Textarea for editing selected element's text
- Toggle switch to enable direct on-page editing (contenteditable)
- Changes sync bidirectionally (textarea ↔ page)

**Colors**
- Background color (picker + hex input)
- Text color (picker + hex input)

**Typography**
- Font size (8-72px slider)
- Font weight (100-900 slider)

**Spacing**
- Padding (0-64px slider)
- Border radius (0-50px slider)

**Actions**
- **Reset**: Revert to original styles
- **Apply & Log**: Commit style changes and emit event
- **Save All to Code**: Emit save_request with ALL changes (styles + text)

## User Workflow

1. Click an element to select it
2. Edit text via textarea OR toggle "Edit text directly on page" for inline editing
3. Adjust styles using the panel controls (changes apply live)
4. Click **Apply & Log** to log individual style changes
5. When done, click **Save All to Code** to emit all changes
6. Close the browser window to end the session

## Streamed Output

### Style Changes
```json
{"event": "style_change", "timestamp": "...", "selector": "h1.title", "property": "backgroundColor", "oldValue": "rgba(0,0,0,0)", "newValue": "#ff0000"}
```

### Save Request (all changes bundled)
```json
{
  "event": "save_request",
  "timestamp": "...",
  "changes": {
    "styles": [
      {"selector": "h1.title", "property": "fontSize", "oldValue": "36px", "newValue": "48px"}
    ],
    "texts": [
      {"selector": "h1.title", "oldText": "Hello World", "newText": "Welcome!"}
    ]
  },
  "summary": {"styleChanges": 1, "textChanges": 1}
}
```

## Agent Implementation Workflow

When the agent receives a `save_request` event:

1. **Parse the changes** - Extract style and text modifications
2. **Find source files** - Use selectors to locate elements in code (JSX, HTML, etc.)
3. **Apply text changes** - Update string literals in the source
4. **Apply style changes** - Update CSS/Tailwind classes or inline styles
5. **Hot reload** - Changes appear live in the browser (Next.js/Vite)
6. **Verify with agent-eyes** - Take screenshot to confirm changes match intent

### Example: Updating a Next.js component

Given this `save_request`:
```json
{
  "changes": {
    "texts": [{"selector": "h1.text-4xl", "oldText": "Hello", "newText": "Welcome"}],
    "styles": [{"selector": "h1.text-4xl", "property": "color", "newValue": "#ff0000"}]
  }
}
```

Agent would:
1. Find `<h1 className="text-4xl">Hello</h1>` in the code
2. Change text to `Welcome`
3. Add `text-red-500` or `style={{color: '#ff0000'}}`
4. Save file → Hot reload → Verify

## Shadow DOM Isolation

The edit panel is rendered inside a closed Shadow DOM, meaning:

- `document.querySelector()` cannot find panel elements
- DOM snapshots (agent-eyes) don't include the panel
- Screenshots show only the actual page content
- The agent sees what the final user would see

## Notes

- Panel is draggable (grab the header)
- Direct edit mode shows a dashed purple outline on the element
- Text changes are tracked per-selector (latest change wins)
- Save All bundles everything logged so far
