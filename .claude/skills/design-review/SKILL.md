---
name: design-review
description: Spec-driven design review with visual annotations, interactive compliance checking, and automated task generation. Use when you need to review UI against design specs, check accessibility compliance, or generate annotated screenshots with issues marked. Triggers on "review design", "check compliance", "design audit", "spec review", "check against spec", or any design quality assurance task.
---

# Design Review

Spec-driven design quality assurance for web applications. Reviews UI implementations against customizable design specs, generates annotated screenshots with issues marked, and creates actionable task lists.

## Prerequisites

- Python 3.10+
- `uv` package manager
- Playwright browsers: `playwright install chromium`

## Commands

```bash
SKILL_DIR=".claude/skills/design-review/scripts"
```

### Review Page

Review a page against design specs:

```bash
# Full page review with default spec
uv run $SKILL_DIR/design_review.py review http://localhost:3000

# Review with custom spec
uv run $SKILL_DIR/design_review.py review http://localhost:3000 --spec my-project.md

# Review specific element
uv run $SKILL_DIR/design_review.py review http://localhost:3000 --selector ".hero-section"

# Generate annotated screenshot
uv run $SKILL_DIR/design_review.py review http://localhost:3000 --annotate

# Generate task file for fixes
uv run $SKILL_DIR/design_review.py review http://localhost:3000 --generate-tasks
```

### Interactive Mode

Select and review elements interactively:

```bash
uv run $SKILL_DIR/design_review.py interactive http://localhost:3000
```

1. Browser opens with review overlay
2. Hover elements to see compliance status
3. Click to see full compliance report
4. Close browser to generate final report

### Compare Against Reference

```bash
# Compare against reference image
uv run $SKILL_DIR/design_review.py compare http://localhost:3000 --reference imgs/homepage.png

# Compare with Figma (if MCP connected)
uv run $SKILL_DIR/design_review.py compare http://localhost:3000 \
  --figma "https://figma.com/file/xxx" \
  --frame "Homepage"
```

### Manage Specs

```bash
# List available specs
uv run $SKILL_DIR/design_review.py specs --list

# Validate a spec file
uv run $SKILL_DIR/design_review.py specs --validate my-project.md

# Show spec details
uv run $SKILL_DIR/design_review.py specs --show default.md
```

## Output Format

All commands return JSON:

```json
{
  "ok": true,
  "summary": {
    "blocking": 1,
    "major": 3,
    "minor": 2
  },
  "issues": [
    {
      "id": 1,
      "checkId": "color-contrast",
      "pillar": "Quality Craft",
      "severity": "major",
      "element": ".subtitle-text",
      "description": "Contrast ratio 3.2:1 (minimum 4.5:1 required)",
      "recommendation": "Darken text to #595959 or darker"
    }
  ],
  "sessionId": "ses_20260122...",
  "artifacts": {
    "screenshot": ".canvas/reviews/ses_.../screenshot.png",
    "annotated": ".canvas/reviews/ses_.../annotated.png",
    "tasks": "DESIGN-REVIEW-TASKS.md"
  }
}
```

## Specs

Design specs are Markdown files with YAML frontmatter:

```markdown
---
name: My Project Spec
version: "1.0"
extends: default.md
---

# My Project Spec

## Brand Guidelines

### Checks

#### brand-colors
- **Severity**: major
- **Description**: Uses approved brand colors
- **How to check**: Compare against approved color list
```

See `specs/README.md` for full format documentation.

## Default Spec Pillars

The default spec (`specs/default.md`) includes:

| Pillar | Focus |
|--------|-------|
| **Frictionless Insight to Action** | Task efficiency, clear navigation, single primary actions |
| **Progressive Clarity** | Smart defaults, progressive disclosure, contextual help |
| **Quality Craft** | Accessibility, contrast, keyboard navigation, touch targets |
| **Trustworthy Building** | AI disclaimers, error handling, secure defaults |

## Session Artifacts

Reviews are saved to `.canvas/reviews/<sessionId>/`:

```
session.json       # Full event log + metadata
report.json        # Structured issue data
screenshot.png     # Original screenshot
annotated.png      # Screenshot with redlines
```

## Typical Workflow

1. **Run review** to find issues:
   ```bash
   uv run $SKILL_DIR/design_review.py review http://localhost:3000 --generate-tasks
   ```

2. **Review DESIGN-REVIEW-TASKS.md** for fix priorities

3. **Fix issues** in code

4. **Re-run review** to verify fixes

## Integration with Other Skills

| Skill | Integration |
|-------|-------------|
| `agent-eyes` | Screenshots, accessibility scans, DOM analysis |
| `agent-canvas` | Interactive element picker (review mode) |
| `canvas-verify` | Visual comparison logic |
