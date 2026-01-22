<p align="center">
  <img src="Agent Canvas Logo.png" alt="Agent Canvas" width="600">
</p>

# Agent Canvas

> **Spec-driven design QA for AI agents**

Review UI implementations against design specs, generate annotated screenshots with issues marked, and create actionable fix lists. Then pick, edit, apply, and verify changes visually.

## Overview

A suite of 7 AI agent skills for visual web development and design quality assurance. Works with **any web page**.

| Skill | Role | Docs |
|-------|------|------|
| [design-review](.claude/skills/design-review/SKILL.md) | Design QA | Spec compliance, visual diffs, task generation |
| [agent-canvas-setup](.claude/skills/agent-canvas-setup/SKILL.md) | Dependency installer | First-time setup |
| [agent-eyes](.claude/skills/agent-eyes/SKILL.md) | Visual context | Screenshots, a11y, DOM |
| [agent-canvas](.claude/skills/agent-canvas/SKILL.md) | Element picker | Interactive selection |
| [canvas-edit](.claude/skills/canvas-edit/SKILL.md) | Live editing | Style/text changes |
| [canvas-apply](.claude/skills/canvas-apply/SKILL.md) | Code generation | Visual edits → code |
| [canvas-verify](.claude/skills/canvas-verify/SKILL.md) | Verification | Before/after comparison |

### Workflows

```
REVIEW ──▶ FIX ──▶ VERIFY          (Design QA)
PICK ──▶ EDIT ──▶ APPLY ──▶ VERIFY (Live Editing)
```

---

## Design Review

The headline skill for spec-driven design quality assurance. Reviews UI against customizable design specs, generates annotated screenshots with issues marked, and creates actionable task lists.

**Trigger phrases**: "review design", "check compliance", "design audit", "spec review", "check against spec", "compare to reference", "design QA"

### Quick Start

```bash
SKILL_DIR=".claude/skills/design-review/scripts"

# Review a page against default spec
uv run $SKILL_DIR/design_review.py review http://localhost:3000

# Generate annotated screenshot with issues marked
uv run $SKILL_DIR/design_review.py review http://localhost:3000 --annotate

# Generate a task file for fixes
uv run $SKILL_DIR/design_review.py review http://localhost:3000 --generate-tasks

# Review with custom spec
uv run $SKILL_DIR/design_review.py review http://localhost:3000 --spec my-project.md
```

### Compare Against Reference Image

```bash
# Compare current page to a reference screenshot
uv run $SKILL_DIR/design_review.py compare http://localhost:3000 --reference homepage.png

# Customize thresholds
uv run $SKILL_DIR/design_review.py compare http://localhost:3000 \
  --reference homepage.png \
  --threshold 3.0 \
  --ssim-threshold 0.98

# Different diff visualization styles: overlay, sidebyside, heatmap
uv run $SKILL_DIR/design_review.py compare http://localhost:3000 \
  --reference homepage.png \
  --diff-style sidebyside
```

### Interactive Mode

```bash
uv run $SKILL_DIR/design_review.py interactive http://localhost:3000
```

1. Browser opens with review overlay
2. Hover elements to see compliance status
3. Click to see full compliance report
4. Close browser to generate final report

### Key Features

| Feature | Description |
|---------|-------------|
| Spec-driven review | Review against customizable design specs |
| Visual annotations | Generate screenshots with issues marked |
| Reference comparison | Compare pages against reference images |
| Task generation | Create DESIGN-REVIEW-TASKS.md with fix priorities |
| Multiple comparison methods | Pixel diff, SSIM, or hybrid analysis |

### Default Spec Pillars

| Pillar | Focus |
|--------|-------|
| **Frictionless Insight to Action** | Task efficiency, clear navigation, single primary actions |
| **Progressive Clarity** | Smart defaults, progressive disclosure, contextual help |
| **Quality Craft** | Accessibility, contrast, keyboard navigation, touch targets |
| **Trustworthy Building** | AI disclaimers, error handling, secure defaults |

### Comparison Methods

| Method | Description | Use Case |
|--------|-------------|----------|
| `pixel` | Fast pixel-by-pixel diff | Quick checks, exact matches |
| `ssim` | Structural Similarity Index | Perceptual comparison, minor shifts OK |
| `hybrid` (default) | Both methods combined | Comprehensive analysis |

### Design Review Workflow

1. **Review** - Find issues:
   ```bash
   uv run $SKILL_DIR/design_review.py review http://localhost:3000 --generate-tasks
   ```

2. **Fix** - Review DESIGN-REVIEW-TASKS.md and fix issues in code

3. **Verify** - Re-run review to confirm fixes

Place reference images in `.claude/skills/design-review/imgs/` for comparison.

[Full design-review docs](.claude/skills/design-review/SKILL.md)

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

## Quick Start (Live Editing)

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

## Supporting Skills

### agent-canvas-setup

Dependency checker and installer. **Run this first.**

```bash
uv run .claude/skills/agent-canvas-setup/scripts/check_setup.py check
```

[Full docs](.claude/skills/agent-canvas-setup/SKILL.md)

### agent-eyes

Screenshots, accessibility scans, DOM snapshots.

```bash
uv run .claude/skills/agent-eyes/scripts/agent_eyes.py screenshot <url>
uv run .claude/skills/agent-eyes/scripts/agent_eyes.py a11y <url>
```

[Full docs](.claude/skills/agent-eyes/SKILL.md)

### agent-canvas

Interactive element picker with browser overlay.

```bash
uv run .claude/skills/agent-canvas/scripts/agent_canvas.py pick <url> --with-edit --with-eyes
```

[Full docs](.claude/skills/agent-canvas/SKILL.md)

### canvas-edit

Floating panel for live text and style editing.

```bash
uv run .claude/skills/canvas-edit/scripts/canvas_edit.py edit <url>
```

[Full docs](.claude/skills/canvas-edit/SKILL.md)

### canvas-apply

Convert visual edit sessions to code changes.

```bash
python3 .claude/skills/canvas-apply/scripts/canvas_apply.py --list
python3 .claude/skills/canvas-apply/scripts/canvas_apply.py <sessionId> --apply
```

[Full docs](.claude/skills/canvas-apply/SKILL.md)

### canvas-verify

Verify changes with before/after comparison.

```bash
uv run .claude/skills/canvas-verify/scripts/canvas_verify.py <url> --session <sessionId>
```

[Full docs](.claude/skills/canvas-verify/SKILL.md)

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

### Design Reviews

Reviews are saved to `.canvas/reviews/<sessionId>/`:

```
session.json       # Full event log + metadata
report.json        # Structured issue data
screenshot.png     # Original screenshot
annotated.png      # Screenshot with redlines
diff.png           # Visual diff (compare mode)
```

### Edit Sessions

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

# 2. Run design review against it
uv run .claude/skills/design-review/scripts/design_review.py review http://localhost:3000 --annotate

# 3. Or run canvas skills for live editing
uv run .claude/skills/agent-canvas/scripts/agent_canvas.py pick http://localhost:3000 --with-edit --with-eyes
```

The skills work with any web page - the demo is just a convenient starting point.

---

## Project Structure

```
.claude/skills/
├── design-review/         # Design QA (headline skill)
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
