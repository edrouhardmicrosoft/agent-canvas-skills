# Canvas CLI Demo

A Next.js project with AI agent visual analysis and editing skills for web development workflows.

## Getting Started

First, run the development server:

```bash
npm run dev
# or
yarn dev
# or
pnpm dev
# or
bun dev
```

Open [http://localhost:3000](http://localhost:3000) with your browser to see the result.

---

## AI Agent Skills

This project includes three visual analysis and editing skills for AI agents located in `.claude/skills/`. These tools enable AI agents to "see" web pages, let users select elements interactively, and make live style/text edits.

### Prerequisites

All skills require:

- Python 3.10+
- `uv` package manager
- Playwright browsers: `playwright install chromium`

---

### Agent Eyes

Visual context analyzer for AI agents. Provides screenshots, accessibility scans, DOM snapshots, and element descriptions.

**Use when:** You need to see what a web page looks like, analyze accessibility issues, inspect DOM structure, or get detailed element information.

#### Commands

```bash
SKILL_DIR=".claude/skills/agent-eyes/scripts"

# Screenshot (full page)
uv run $SKILL_DIR/agent_eyes.py screenshot http://localhost:3000

# Screenshot (specific element)
uv run $SKILL_DIR/agent_eyes.py screenshot http://localhost:3000 --selector ".hero"

# Accessibility scan (WCAG 2.1 AA)
uv run $SKILL_DIR/agent_eyes.py a11y http://localhost:3000

# DOM snapshot
uv run $SKILL_DIR/agent_eyes.py dom http://localhost:3000

# Describe element (styles, bounding box, attributes)
uv run $SKILL_DIR/agent_eyes.py describe http://localhost:3000 --selector ".hero-button"

# Full context bundle (screenshot + a11y + DOM + description)
uv run $SKILL_DIR/agent_eyes.py context http://localhost:3000
```

---

### Agent Canvas

Interactive element picker that opens a browser with a DevTools-like selection overlay. Users hover to highlight elements and click to select.

**Use when:** You need to let users visually select DOM elements, identify element selectors, or get detailed element information interactively.

#### Commands

```bash
SKILL_DIR=".claude/skills/agent-canvas/scripts"

# Basic pick - opens browser, streams selections as JSON lines
uv run $SKILL_DIR/agent_canvas.py pick http://localhost:3000

# Pick with agent-eyes integration (screenshot + detailed styles per selection)
uv run $SKILL_DIR/agent_canvas.py pick http://localhost:3000 --with-eyes

# Pick with edit panel (floating DevTools for live style editing)
uv run $SKILL_DIR/agent_canvas.py pick http://localhost:3000 --with-edit

# Full workflow: picker + edit panel + agent-eyes (recommended)
uv run $SKILL_DIR/agent_canvas.py pick http://localhost:3000 --with-edit --with-eyes

# Watch for DOM changes
uv run $SKILL_DIR/agent_canvas.py watch http://localhost:3000
```

#### User Interaction Flow

1. Browser opens with blue highlight overlay
2. Hover over elements to see selector labels
3. Click to select (overlay flashes green, counter increments)
4. Keep clicking to select more elements
5. Close browser window when done

---

### Canvas Edit

Floating DevTools-like panel for live UI editing (text and styles). Changes apply live to the page and stream as JSON events for AI agent implementation.

**Use when:** You need to edit text content, adjust colors, typography, or spacing on elements visually.

#### Commands

```bash
SKILL_DIR=".claude/skills/canvas-edit/scripts"

# Open page with edit panel
uv run $SKILL_DIR/canvas_edit.py edit http://localhost:3000

# Save all changes to file
uv run $SKILL_DIR/canvas_edit.py edit http://localhost:3000 --output ./changes.json
```

#### Panel Controls

- **Text Content**: Textarea for editing selected element's text, or toggle for direct on-page editing
- **Colors**: Background and text color pickers
- **Typography**: Font size (8-72px) and font weight (100-900)
- **Spacing**: Padding (0-64px) and border radius (0-50px)
- **Actions**: Reset, Apply & Log, Save All to Code

#### User Workflow

1. Click an element to select it
2. Edit text via textarea OR toggle "Edit text directly on page"
3. Adjust styles using panel controls (changes apply live)
4. Click **Apply & Log** to log individual style changes
5. Click **Save All to Code** to emit all changes for agent implementation
6. Close browser window to end session

---

### Recommended Workflow

For the best experience combining all three skills:

```bash
# Full visual editing workflow
uv run .claude/skills/agent-canvas/scripts/agent_canvas.py pick http://localhost:3000 --with-edit --with-eyes
```

This gives users:
- Element selection with visual highlighting
- Live style editing with preview
- Screenshots and detailed element info for the AI agent
- JSON event stream of all changes for code implementation

---

### Session Artifacts

When running a canvas session with `--with-edit`, all interactions are recorded to `.canvas/sessions/` for later use by `canvas-apply` and `canvas-verify`.

#### Directory Structure

```
.canvas/sessions/
├── ses-a1b2c3d4e5f6/           # 12-char hex session ID
│   ├── session.json            # Full event log + metadata
│   └── changes.json            # Extracted save_request (if "Save All" clicked)
```

#### Session ID Format

Session IDs use the format `ses-<12-char-hex>` (e.g., `ses-a1b2c3d4e5f6`).

#### Session JSON Structure

```json
{
  "sessionId": "ses-a1b2c3d4e5f6",
  "url": "http://localhost:3000",
  "startTime": "2026-01-21T15:30:45.123Z",
  "endTime": "2026-01-21T15:35:12.456Z",
  "features": {
    "withEdit": true,
    "withEyes": true
  },
  "beforeScreenshot": "data:image/png;base64,...",
  "events": [
    {"type": "selection.changed", "timestamp": "...", "data": {...}},
    {"type": "style.changed", "timestamp": "...", "data": {...}},
    {"type": "save_request", "timestamp": "...", "data": {...}}
  ]
}
```

#### Screenshot Storage

Screenshots are stored as **base64-encoded data URIs** within the JSON for portability. This keeps all session data self-contained in a single file.

#### What Gets Recorded

| Event Type | Description |
|------------|-------------|
| `selection.changed` | User clicked to select an element |
| `style.changed` | User modified a style property |
| `text.changed` | User edited element text |
| `save_request` | User clicked "Save All to Code" |

---

## Learn More

To learn more about Next.js, take a look at the following resources:

- [Next.js Documentation](https://nextjs.org/docs) - learn about Next.js features and API.
- [Learn Next.js](https://nextjs.org/learn) - an interactive Next.js tutorial.

## Deploy on Vercel

The easiest way to deploy your Next.js app is to use the [Vercel Platform](https://vercel.com/new?utm_medium=default-template&filter=next.js&utm_source=create-next-app&utm_campaign=create-next-app-readme) from the creators of Next.js.

Check out our [Next.js deployment documentation](https://nextjs.org/docs/app/building-your-application/deploying) for more details.
