# Canvas Apply Skill

Convert visual UI edit sessions into actual code changes.

## Trigger Phrases

- "apply canvas changes"
- "apply session <sessionId>"
- "convert canvas edits to code"
- "apply visual edits"

## Commands

```bash
SKILL_DIR=".claude/skills/canvas-apply/scripts"

# List available sessions
python3 $SKILL_DIR/canvas_apply.py --list

# Preview changes (default)
python3 $SKILL_DIR/canvas_apply.py <sessionId>

# Show unified diff
python3 $SKILL_DIR/canvas_apply.py <sessionId> --diff

# Apply changes to files
python3 $SKILL_DIR/canvas_apply.py <sessionId> --apply

# Dry run (show what would be applied)
python3 $SKILL_DIR/canvas_apply.py <sessionId> --apply --dry-run

# Verbose mode with confidence scores
python3 $SKILL_DIR/canvas_apply.py <sessionId> --verbose

# JSON output
python3 $SKILL_DIR/canvas_apply.py <sessionId> --json

# Force apply despite low confidence
python3 $SKILL_DIR/canvas_apply.py <sessionId> --apply --force
```

## Workflow

1. **Run a canvas-edit session** to create visual changes:
   ```bash
   uv run .claude/skills/agent-canvas/scripts/agent_canvas.py pick http://localhost:3000 --with-edit
   ```

2. **User makes visual changes** in the browser (text, colors, spacing, etc.)

3. **User clicks "Save All to Code"** to record the changes

4. **Preview the proposed code changes**:
   ```bash
   python3 $SKILL_DIR/canvas_apply.py --list  # Find session ID
   python3 $SKILL_DIR/canvas_apply.py ses-abc123  # Preview
   ```

5. **Apply the changes**:
   ```bash
   python3 $SKILL_DIR/canvas_apply.py ses-abc123 --apply
   ```

## Session Format

Sessions are stored in `.canvas/sessions/<sessionId>/session.json` and contain:

- Selection events (which elements the user clicked on)
- Style changes (color, font-size, padding, etc.)
- Text changes (content edits)
- Save requests (when user clicked "Save All to Code")

## Confidence Scoring

The tool uses a multi-strategy approach to map DOM selectors to source files:

| Strategy | Confidence | Description |
|----------|------------|-------------|
| ID attribute | ~0.95 | `id="myElement"` |
| data-testid | ~0.90 | `data-testid="submit-btn"` |
| className + tag | 0.65-0.95 | `<h1 className="...">` matching classes |
| Text content | 0.60-0.80 | Literal text in JSX |

Changes with confidence below 70% will show a warning. Use `--force` to apply anyway.

## Output Examples

### Preview Mode
```
Session: ses-abc123
Files to modify: 1

📝 app/page.tsx (confidence: 95%)
   Changes:
     - Text: 'hello world' -> 'Hello Canvas!'
     - Style: color: rgb(0, 0, 0) -> rgb(255, 0, 0)

--- a/app/page.tsx
+++ b/app/page.tsx
@@ -3,7 +3,7 @@
     <main>
-      <h1 className="...">hello world</h1>
+      <h1 className="..." style={{ color: "rgb(255, 0, 0)" }}>Hello Canvas!</h1>
     </main>
```

### JSON Output
```json
{
  "sessionId": "ses-abc123",
  "fileDiffs": [
    {
      "filePath": "app/page.tsx",
      "changes": ["Text: ...", "Style: ..."],
      "confidence": 0.95,
      "unifiedDiff": "..."
    }
  ],
  "unmappedChanges": [],
  "warnings": [],
  "summary": {
    "filesModified": 1,
    "unmappedCount": 0,
    "warningCount": 0
  }
}
```

## Limitations

- **Style changes use inline styles**: Tailwind class generation is planned for Phase 5
- **React/JSX focus**: Currently optimized for React/Next.js projects
- **Single-element matching**: Complex selectors may have lower confidence
- **No CSS-in-JS support yet**: styled-components, emotion, etc. planned for future

## Related Skills

- **canvas-edit**: Create visual editing sessions
- **agent-canvas**: Interactive element picker
- **agent-eyes**: Visual context analyzer
