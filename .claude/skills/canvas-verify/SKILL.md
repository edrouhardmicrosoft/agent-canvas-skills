# Canvas Verify Skill

Verify that applied canvas changes worked correctly by comparing screenshots and accessibility scans.

## Trigger Phrases

- "verify canvas changes"
- "verify session <sessionId>"
- "check if changes worked"
- "compare before and after"
- "run verification"

## Commands

```bash
SKILL_DIR=".claude/skills/canvas-verify/scripts"

# List available sessions with verification status
uv run $SKILL_DIR/canvas_verify.py --list

# Full verification (visual + a11y)
uv run $SKILL_DIR/canvas_verify.py <url> --session <sessionId>

# Visual comparison only
uv run $SKILL_DIR/canvas_verify.py <url> --session <sessionId> --visual

# Accessibility comparison only
uv run $SKILL_DIR/canvas_verify.py <url> --session <sessionId> --a11y

# Full verification (explicit)
uv run $SKILL_DIR/canvas_verify.py <url> --session <sessionId> --full

# JSON output (for CI integration)
uv run $SKILL_DIR/canvas_verify.py <url> --session <sessionId> --json
```

## Workflow

1. **Run a canvas-edit session** and make visual changes:
   ```bash
   uv run .claude/skills/agent-canvas/scripts/agent_canvas.py pick http://localhost:3000 --with-edit
   ```

2. **Apply the changes** to source files:
   ```bash
   python3 .claude/skills/canvas-apply/scripts/canvas_apply.py --list  # Find session ID
   python3 .claude/skills/canvas-apply/scripts/canvas_apply.py ses-abc123 --apply
   ```

3. **Verify the changes** worked correctly:
   ```bash
   uv run $SKILL_DIR/canvas_verify.py http://localhost:3000 --session ses-abc123
   ```

## Output Examples

### Human-Readable Output

```
Session: ses-abc123
URL: http://localhost:3000

Visual Comparison: ✅ PASS
  Pixels changed: 2.3%
  Threshold: 5.0%

Accessibility: ✅ PASS
  Before: 3 violations
  After: 1 violations
  Fixed (2):
    ✅ color-contrast: Elements must have sufficient color contrast
    ✅ image-alt: Images must have alternate text
  Introduced (0):

Overall: ✅ PASS
```

### JSON Output

```json
{
  "ok": true,
  "sessionId": "ses-abc123",
  "url": "http://localhost:3000",
  "verification": {
    "visual": {
      "status": "pass",
      "beforeScreenshot": "base64...",
      "afterScreenshot": "base64...",
      "diffPercentage": 2.3
    },
    "a11y": {
      "status": "pass",
      "beforeViolations": 3,
      "afterViolations": 1,
      "fixed": ["color-contrast: Elements must have sufficient color contrast"],
      "introduced": [],
      "unchanged": ["heading-order: Heading levels should only increase by one"]
    }
  },
  "overallStatus": "pass"
}
```

### List Sessions Output

```
Session ID           URL                            Has Baseline   Verified   Status
------------------------------------------------------------------------------------
ses-abc123           http://localhost:3000          Yes            Yes        pass
ses-def456           http://localhost:3000/about    Yes            No         -
ses-xyz789           http://localhost:8080          No             No         -
```

## Verification Logic

### Visual Comparison

- Captures current screenshot using agent-eyes
- Compares pixel-by-pixel with baseline `beforeScreenshot` from session
- Calculates percentage of pixels changed
- **Pass criteria**: Less than 5% of pixels differ (configurable)

### Accessibility Comparison

- Runs axe-core accessibility scan using agent-eyes
- Compares violations with baseline (if stored in session)
- Categorizes violations as:
  - **Fixed**: Present before, absent after
  - **Introduced**: Absent before, present after
  - **Unchanged**: Present in both
- **Pass criteria**: No new violations introduced

### Overall Status

- **Pass**: Visual passes AND no new a11y violations
- **Fail**: Visual fails OR new a11y violations introduced
- **Skip**: Missing baseline data (no beforeScreenshot or beforeA11y)

## Session Requirements

For verification to work optimally, sessions should include:

```json
{
  "sessionId": "ses-abc123",
  "url": "http://localhost:3000",
  "beforeScreenshot": "data:image/png;base64,...",
  "beforeA11y": {
    "violations": [...]
  },
  "events": {
    "edits": [...]
  }
}
```

If `beforeScreenshot` or `beforeA11y` is missing, those comparisons will be skipped.

## CI Integration

Use the JSON output and exit codes for CI pipelines:

```bash
# Run verification and capture result
result=$(uv run $SKILL_DIR/canvas_verify.py http://localhost:3000 --session ses-abc123 --json)
exit_code=$?

# Exit code: 0 = pass, 1 = fail or error
if [ $exit_code -ne 0 ]; then
  echo "Verification failed!"
  exit 1
fi

# Parse overall status
status=$(echo "$result" | jq -r '.overallStatus')
if [ "$status" != "pass" ]; then
  echo "Changes did not pass verification"
  exit 1
fi
```

## Limitations

- **Baseline required**: Visual comparison requires `beforeScreenshot` in session
- **A11y baseline optional**: If no `beforeA11y`, only current violations are reported
- **Pixel-based diff**: Does not account for anti-aliasing or rendering differences
- **Same URL assumed**: Verification URL should match session URL for meaningful comparison

## Related Skills

- **canvas-edit**: Create visual editing sessions (generates baseline)
- **canvas-apply**: Apply changes to source files (between baseline and verify)
- **agent-eyes**: Visual context analyzer (provides screenshot and a11y functions)
