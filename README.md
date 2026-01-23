<p align="center">
  <img src="Agent Canvas Logo.png" alt="Agent Canvas" width="600">
</p>

# Agent Canvas

> **Spec-driven design QA for AI agents**

Review UI implementations against design specs, generate annotated screenshots with issues marked, and create actionable fix lists. Works with **any AI agent** (Copilot, Claude Desktop, Cursor, etc.) on **any web page**.

---

## Quick Start

**Copy and paste this into your AI agent:**

```
Set up Agent Canvas for design review. Follow the instructions in .claude/skills/agent-canvas-setup/SKILL.md to check dependencies and install anything missing. Use the "temporary" scope unless I specify otherwise.
```

That's it. Your agent will handle Python, uv, Playwright, and everything else.

Once setup completes, try:

```
Review the design at http://localhost:3000
```

---

## Customizing Your Reviews (CRITICAL)

By default, Agent Canvas reviews against generic design principles. **For meaningful reviews, give it YOUR design context:**

### Option 1: Custom Design Spec (Recommended)

Create a `DESIGN-SPEC.md` in your project root:

```
your-project/
├── DESIGN-SPEC.md    ← Agent Canvas auto-detects this
├── src/
└── ...
```

Your spec can define brand colors, typography rules, spacing standards, component patterns—anything your team cares about. See [specs/README.md](.claude/skills/design-review/specs/README.md) for the full format.

**Example DESIGN-SPEC.md:**

```markdown
---
name: My Project Design Spec
version: "1.0"
extends: default.md
---

# My Project Design Spec

## Brand Guidelines

### Checks

#### brand-colors
- **Severity**: major
- **Description**: Uses approved brand colors only
- **Approved colors**:
  - `#0078D4` - Primary Blue
  - `#1B1B1B` - Text Black
  - `#FFFFFF` - White
- **How to check**: Extract colors from elements, compare against approved list

#### typography
- **Severity**: minor
- **Description**: Uses approved font families
- **Approved fonts**:
  - Inter
  - SF Pro
- **How to check**: Check computed font-family on text elements
```

### Option 2: Visual References

Drop reference images (exported from Figma, screenshots from prod, etc.) into:

```
.claude/skills/design-review/imgs/
├── homepage.png
├── settings-page.png
└── mobile-nav.png
```

Then ask your agent:

```
Compare http://localhost:3000 against the homepage.png reference
```

### Option 3: Figma MCP (If Connected)

If your agent has Figma MCP connected, it will automatically use it for comparisons:

```
Compare http://localhost:3000 against the Homepage frame in our Figma file
```

> **Note**: Without Figma MCP, export frames as PNG and use Option 2.

---

## What You Can Do

| Ask your agent... | What happens |
|-------------------|--------------|
| "Review the design at [url]" | Checks against spec, lists issues by severity |
| "Review [url] and show me the problems" | Generates annotated screenshot with issues marked |
| "Review [url] and create a task list" | Creates `DESIGN-REVIEW-TASKS.md` with fix priorities |
| "Compare [url] to homepage.png" | Visual diff against reference image |
| "Let me pick elements to review" | Opens browser, you click elements to inspect |

---

## Workflows

```
REVIEW ──▶ FIX ──▶ VERIFY          (Design QA)
PICK ──▶ EDIT ──▶ APPLY ──▶ VERIFY (Live Editing)
```

### Design QA Workflow

1. **Review** - Find issues:
   ```
   Review http://localhost:3000 and generate a task list
   ```

2. **Fix** - Your agent (or you) fixes the issues

3. **Verify** - Re-run review to confirm:
   ```
   Review http://localhost:3000 again
   ```

### Live Editing Workflow

```
Pick an element on http://localhost:3000 to edit
```

1. Browser opens → click elements to select
2. Edit in floating panel → changes apply live
3. Click "Save All to Code" → agent updates your source files

---

## Skills Reference

| Skill | What it does |
|-------|--------------|
| [design-review](.claude/skills/design-review/SKILL.md) | Reviews UI against specs, generates annotated screenshots |
| [agent-canvas-setup](.claude/skills/agent-canvas-setup/SKILL.md) | Installs dependencies (Python, Playwright, etc.) |
| [agent-eyes](.claude/skills/agent-eyes/SKILL.md) | Takes screenshots, runs accessibility scans |
| [agent-canvas](.claude/skills/agent-canvas/SKILL.md) | Interactive element picker |
| [canvas-edit](.claude/skills/canvas-edit/SKILL.md) | Annotation toolbar overlay |
| [canvas-apply](.claude/skills/canvas-apply/SKILL.md) | Converts visual edits to code changes |
| [canvas-verify](.claude/skills/canvas-verify/SKILL.md) | Before/after visual comparison |

---

## Default Review Criteria

Without a custom spec, Agent Canvas checks these pillars:

| Pillar | Focus |
|--------|-------|
| **Frictionless Insight to Action** | Task efficiency, clear navigation, single primary actions |
| **Progressive Clarity** | Smart defaults, progressive disclosure, contextual help |
| **Quality Craft** | Accessibility, contrast, keyboard navigation, touch targets |
| **Trustworthy Building** | AI disclaimers, error handling, secure defaults |

See the full default spec: [specs/default.md](.claude/skills/design-review/specs/default.md)

---

## Session Artifacts

Reviews are saved to `.canvas/reviews/<sessionId>/`:

```
session.json       # Full event log
report.json        # Structured issue data
screenshot.png     # Original screenshot
annotated.png      # Screenshot with issues marked
diff.png           # Visual diff (compare mode)
```

---

## Troubleshooting

**Browser doesn't open?**
```
Run agent-canvas-setup to check dependencies
```

**"uv not found" or "Python not found"?**
Your agent will guide you through installing prerequisites.

**Reviews too generic?**
Add a `DESIGN-SPEC.md` to your project root with your actual design standards.

---

## Project Structure

```
.claude/skills/
├── design-review/         # Main review skill
│   ├── specs/             # Design spec files
│   │   └── default.md     # Default review criteria
│   └── imgs/              # Reference images go here
├── agent-canvas-setup/    # Dependency installer
├── agent-eyes/            # Screenshots & a11y
├── agent-canvas/          # Element picker
├── canvas-edit/           # Annotation overlay
├── canvas-apply/          # Code generator
├── canvas-verify/         # Verification
└── shared/                # Shared utilities
```

---

## For AI Agent Developers

See **[docs/AGENTS.md](docs/AGENTS.md)** for:
- Skill trigger phrases
- Command reference  
- Output parsing
- Error handling
