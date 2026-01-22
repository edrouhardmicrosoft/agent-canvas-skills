# Agent Canvas Skills - AI Agent Reference

Quick reference for AI agents to navigate and use canvas skills effectively.

---

## Skill Selection Guide

| User Intent | Skill to Use | Command |
|-------------|--------------|---------|
| See the page / take screenshot | `agent-eyes` | `uv run .claude/skills/agent-eyes/scripts/agent_eyes.py screenshot <url>` |
| Check accessibility issues | `agent-eyes` | `uv run .claude/skills/agent-eyes/scripts/agent_eyes.py a11y <url>` |
| Select an element interactively | `agent-canvas` | `uv run .claude/skills/agent-canvas/scripts/agent_canvas.py pick <url>` |
| Edit styles/text visually | `agent-canvas` | `uv run .claude/skills/agent-canvas/scripts/agent_canvas.py pick <url> --with-edit` |
| Apply visual edits to code | `canvas-apply` | `python3 .claude/skills/canvas-apply/scripts/canvas_apply.py <sessionId> --apply` |
| Verify changes worked | `canvas-verify` | `uv run .claude/skills/canvas-verify/scripts/canvas_verify.py <url> --session <sessionId>` |
| Skills not working / first use | `agent-canvas-setup` | `uv run .claude/skills/agent-canvas-setup/scripts/check_setup.py check` |

---

## Trigger Phrases

### agent-canvas-setup
- "setup agent canvas"
- "install canvas dependencies"
- "canvas not working"
- "playwright not found"
- "first time setup"

### agent-eyes
- "take a screenshot"
- "check accessibility"
- "what does this page look like"
- "analyze the UI"
- "inspect this element"
- "run a11y scan"
- "get DOM snapshot"

### agent-canvas
- "select an element"
- "pick element"
- "let me choose"
- "which element"
- "interactive selection"

### canvas-edit
- "edit text"
- "change content"
- "edit styles"
- "change colors"
- "adjust spacing"
- "tweak UI"

### canvas-apply
- "apply canvas changes"
- "apply session"
- "convert edits to code"
- "apply visual edits"

### canvas-verify
- "verify canvas changes"
- "verify session"
- "check if changes worked"
- "compare before and after"
- "run verification"

---

## Command Quick Reference

### agent-canvas-setup

```bash
# Check dependencies
uv run .claude/skills/agent-canvas-setup/scripts/check_setup.py check

# Install (recommended scope)
uv run .claude/skills/agent-canvas-setup/scripts/check_setup.py install --scope temporary
```

**Exit codes:** `0` = ready, `1` = needs setup

---

### agent-eyes

```bash
# Screenshot
uv run .claude/skills/agent-eyes/scripts/agent_eyes.py screenshot <url>

# Accessibility scan
uv run .claude/skills/agent-eyes/scripts/agent_eyes.py a11y <url>

# Full context (screenshot + a11y + DOM)
uv run .claude/skills/agent-eyes/scripts/agent_eyes.py context <url>

# Element description
uv run .claude/skills/agent-eyes/scripts/agent_eyes.py describe <url> --selector "<selector>"
```

**Output format:**
```json
{
  "ok": true,
  "screenshot": "path/to/file.png",
  "violations": [...],
  "dom": {...}
}
```

---

### agent-canvas

```bash
# Basic pick
uv run .claude/skills/agent-canvas/scripts/agent_canvas.py pick <url>

# Full workflow (RECOMMENDED)
uv run .claude/skills/agent-canvas/scripts/agent_canvas.py pick <url> --with-edit --with-eyes

# Auto-apply after editing
uv run .claude/skills/agent-canvas/scripts/agent_canvas.py pick <url> --with-edit --with-eyes --auto-apply --auto-verify
```

**Output format (JSON lines):**
```json
{"event": "session_started", "sessionId": "ses-abc123", "url": "..."}
{"event": "selection", "index": 1, "element": {"tag": "button", "selector": "#submit"}}
{"event": "style_change", "selector": "#submit", "property": "color", "newValue": "#ff0000"}
{"event": "save_request", "changes": {...}}
{"event": "session_ended", "total_selections": 1, "total_edits": 2}
```

---

### canvas-apply

```bash
# List sessions
python3 .claude/skills/canvas-apply/scripts/canvas_apply.py --list

# Preview changes
python3 .claude/skills/canvas-apply/scripts/canvas_apply.py <sessionId>

# Show diff
python3 .claude/skills/canvas-apply/scripts/canvas_apply.py <sessionId> --diff

# Apply changes
python3 .claude/skills/canvas-apply/scripts/canvas_apply.py <sessionId> --apply

# Force apply (ignore low confidence)
python3 .claude/skills/canvas-apply/scripts/canvas_apply.py <sessionId> --apply --force
```

**Output format (--json):**
```json
{
  "sessionId": "ses-abc123",
  "fileDiffs": [
    {"filePath": "app/page.tsx", "confidence": 0.95, "changes": [...]}
  ],
  "unmappedChanges": [],
  "warnings": []
}
```

**Confidence thresholds:** `<70%` = warning, use `--force` to override

---

### canvas-verify

```bash
# Full verification
uv run .claude/skills/canvas-verify/scripts/canvas_verify.py <url> --session <sessionId>

# Visual only
uv run .claude/skills/canvas-verify/scripts/canvas_verify.py <url> --session <sessionId> --visual

# A11y only
uv run .claude/skills/canvas-verify/scripts/canvas_verify.py <url> --session <sessionId> --a11y

# List sessions
uv run .claude/skills/canvas-verify/scripts/canvas_verify.py --list
```

**Output format (--json):**
```json
{
  "ok": true,
  "sessionId": "ses-abc123",
  "verification": {
    "visual": {"status": "pass", "diffPercentage": 2.3},
    "a11y": {"status": "pass", "fixed": [...], "introduced": []}
  },
  "overallStatus": "pass"
}
```

**Exit codes:** `0` = pass, `1` = fail

---

## Workflow Sequences

### Workflow 1: Full Visual Edit Cycle

```bash
# 1. Check setup (first time only)
uv run .claude/skills/agent-canvas-setup/scripts/check_setup.py check

# 2. Pick element and edit visually
uv run .claude/skills/agent-canvas/scripts/agent_canvas.py pick http://localhost:3000 --with-edit --with-eyes
# User makes changes, clicks "Save All to Code", closes browser
# Output includes sessionId (e.g., ses-abc123)

# 3. Apply changes to source files
python3 .claude/skills/canvas-apply/scripts/canvas_apply.py ses-abc123 --apply

# 4. Verify changes worked
uv run .claude/skills/canvas-verify/scripts/canvas_verify.py http://localhost:3000 --session ses-abc123
```

### Workflow 2: Accessibility Analysis

```bash
# 1. Scan for violations
uv run .claude/skills/agent-eyes/scripts/agent_eyes.py a11y http://localhost:3000

# 2. Parse violations array, make code fixes

# 3. Re-scan to verify fixes
uv run .claude/skills/agent-eyes/scripts/agent_eyes.py a11y http://localhost:3000
```

### Workflow 3: Quick Screenshot for Context

```bash
uv run .claude/skills/agent-eyes/scripts/agent_eyes.py screenshot http://localhost:3000
```

### Workflow 4: Automated CI Pipeline

```bash
# Full automation - opens browser, applies, verifies
uv run .claude/skills/agent-canvas/scripts/agent_canvas.py pick http://localhost:3000 \
  --with-edit --with-eyes --auto-apply --auto-verify
```

---

## Output Parsing Guide

### Key Fields to Check

| Field | Meaning | Action |
|-------|---------|--------|
| `ok: true/false` | Command success | If false, check `error` field |
| `sessionId` | Session identifier | Pass to canvas-apply and canvas-verify |
| `violations[]` | A11y issues found | Parse and fix each violation |
| `confidence` | Match certainty (0-1) | Warn user if <0.70 |
| `overallStatus` | Verification result | "pass" or "fail" |
| `diffPercentage` | Visual change amount | Higher = more changed |

### Parsing Examples

**Check if command succeeded:**
```python
result = json.loads(output)
if not result.get("ok", False):
    print(f"Error: {result.get('error')}")
```

**Extract sessionId from agent-canvas:**
```python
for line in output.splitlines():
    event = json.loads(line)
    if event.get("event") == "session_started":
        session_id = event["sessionId"]
```

**Check verification passed:**
```python
result = json.loads(output)
if result["overallStatus"] == "pass":
    print("Changes verified successfully")
```

---

## Error Handling

| Error | Cause | Solution |
|-------|-------|----------|
| `Playwright not found` | Missing browser | Run `agent-canvas-setup` |
| `Session not found` | Invalid sessionId | Use `--list` to find valid sessions |
| `Low confidence warning` | Uncertain file match | Use `--force` or improve selectors |
| `No beforeScreenshot` | Incomplete session | Re-run canvas session with `--with-eyes` |
| `uv not found` | Missing package manager | Install uv: `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| `Connection refused` | Dev server not running | Start with `npm run dev` |

---

## Best Practices for Agents

1. **Always check setup first** - Run `check_setup.py check` before first canvas operation
2. **Use full flags for context** - `--with-edit --with-eyes` provides maximum information
3. **Parse JSON output** - Don't rely on text output; use `--json` flag when available
4. **Track sessionId** - Pass it consistently from agent-canvas to canvas-apply to canvas-verify
5. **Verify after apply** - Always run canvas-verify to confirm changes worked
6. **Watch confidence scores** - Warn users about low-confidence matches (<70%)
7. **Handle errors gracefully** - Check `ok` field and provide helpful messages on failure

---

## Session Artifacts

Sessions are stored in `.canvas/sessions/<sessionId>/`:

```
.canvas/sessions/
└── ses-abc123/
    ├── session.json    # Full event log + metadata
    └── changes.json    # Extracted save_request data
```

**Session JSON structure:**
```json
{
  "sessionId": "ses-abc123",
  "url": "http://localhost:3000",
  "startTime": "2026-01-21T15:30:45.123Z",
  "features": {"withEdit": true, "withEyes": true},
  "beforeScreenshot": "data:image/png;base64,...",
  "events": [...]
}
```

---

## Quick Paths

```bash
# Skills directory
.claude/skills/

# Session artifacts
.canvas/sessions/

# Screenshots
.canvas/screenshots/
```
