# Design Review Skill - Implementation Tasks

> **Hero Feature**: Spec-driven design review with visual annotations, interactive compliance checking, and automated task generation.

---

## Implementation Status

| Phase | Description | Status |
|-------|-------------|--------|
| Phase 1 | Core Review Engine | ✅ Complete |
| Phase 2 | Annotation & Output | ✅ Complete |
| Phase 3 | Interactive Mode | 🔲 Pending |
| Phase 4 | Comparison Features | 🔲 Pending |
| Phase 5 | Smart Features | 🔲 Pending |

---

## Phase 1: Core Review Engine ✅

| Task | Description | Status |
|------|-------------|--------|
| Markdown spec parser | `spec_loader.py` - Parse specs with YAML frontmatter and inheritance | ✅ |
| Default spec | `specs/default.md` - 4 pillars, 21 checks | ✅ |
| Basic issue detection | Integration with axe-core for a11y, contrast checking | ✅ |
| CLI with `review` command | `design_review.py review <url> [options]` | ✅ |
| CLI with `specs` command | `design_review.py specs --list|--validate|--show` | ✅ |
| JSON output format | Structured output with summary, issues, artifacts | ✅ |
| Project spec discovery | Auto-discover `DESIGN-SPEC.md` in project root | ✅ |
| Spec inheritance | `extends: default.md` in frontmatter | ✅ |

**Files created:**
- `.claude/skills/design-review/scripts/spec_loader.py`
- `.claude/skills/design-review/scripts/design_review.py`
- `.claude/skills/design-review/specs/default.md`
- `.claude/skills/design-review/specs/README.md`
- `.claude/skills/design-review/SKILL.md`

---

## Phase 2: Annotation & Output ✅

| Task | Description | Status |
|------|-------------|--------|
| Screenshot annotator | `annotator.py` - Draw on screenshots using Pillow | ✅ |
| Numbered circles | ①②③ markers at issue locations | ✅ |
| Severity colors | Red (blocking), orange (major), yellow (minor) | ✅ |
| Border drawing | Borders around problematic elements | ✅ |
| Legend | Issue list at bottom of annotated screenshot | ✅ |
| Enhanced DESIGN-REVIEW-TASKS.md | Better formatting with issue numbers, source hints | ✅ |
| Annotated screenshot reference | Include annotated.png reference in tasks file | ✅ |
| Source file detection | Heuristics to detect likely source files | ✅ |
| Code fix examples | Suggested fixes with code examples | ✅ |
| Session artifacts | Full directory structure with session.json | ✅ |
| Wire --annotate flag | Connect flag to annotator module | ✅ |

**Files created/modified:**
- `.claude/skills/design-review/scripts/annotator.py` (NEW)
- `.claude/skills/design-review/scripts/design_review.py` (enhanced)

**Session artifacts structure:**
```
.canvas/reviews/<sessionId>/
├── session.json       # Full event log + metadata
├── report.json        # Structured issue data
├── screenshot.png     # Original screenshot
└── annotated.png      # Screenshot with redlines (when --annotate used)
```

---

## Phase 3: Interactive Mode 🔲

| Task | Description | Status |
|------|-------------|--------|
| Review overlay JS | Browser overlay styled for review (not editing) | 🔲 |
| Compliance indicators | Show ✅⚠️❌ as user hovers over elements | 🔲 |
| Element-specific review | Click element → full compliance report | 🔲 |
| "Add to Review" workflow | User curates which issues to include | 🔲 |
| "Next Issue" navigation | Jump to next non-compliant element | 🔲 |
| Browser close handling | Generate report when browser closes | 🔲 |

**Expected CLI:**
```bash
uv run .claude/skills/design-review/scripts/design_review.py interactive http://localhost:3000
```

---

## Phase 4: Comparison Features 🔲

| Task | Description | Status |
|------|-------------|--------|
| Reference image comparison | Compare against images in `imgs/` folder | 🔲 |
| `image_comparator.py` | Visual diff algorithm (SSIM or pixel diff) | 🔲 |
| Visual diff output | Highlight differences between current and reference | 🔲 |
| Figma MCP integration | Optional: fetch frames from Figma API | 🔲 |
| Compare command | `design_review.py compare <url> --reference <img>` | 🔲 |

**Expected CLI:**
```bash
uv run .claude/skills/design-review/scripts/design_review.py compare http://localhost:3000 --reference imgs/homepage.png
```

---

## Phase 5: Smart Features 🔲

| Task | Description | Status |
|------|-------------|--------|
| User prompt parsing | Natural language → review type | 🔲 |
| Intent detection | "check buttons" → filter to button-related checks | 🔲 |
| Editable context detection | Detect if source files are available | 🔲 |
| Source file mapping | Map selectors to actual source files | 🔲 |
| todowrite integration | Create todos for each issue | 🔲 |
| Interactive prompts | Prompt user for review type if not specified | 🔲 |

**Expected flow:**
```
$ uv run design_review.py http://localhost:3000

🎨 Design Review - What would you like to check?

  1. Full page review (check entire page against spec)
  2. Specific element (select an element to review)
  3. Compare to reference (compare against design image)
  4. Accessibility audit (deep-dive a11y checks)
  5. Custom (describe what you're looking for)

Enter choice [1-5] or describe your goal: 
```

---

## Commands Reference

```bash
SKILL_DIR=".claude/skills/design-review/scripts"

# === REVIEW COMMANDS ===
uv run $SKILL_DIR/design_review.py review <url>                    # Basic review
uv run $SKILL_DIR/design_review.py review <url> --spec my-spec.md  # Custom spec
uv run $SKILL_DIR/design_review.py review <url> --selector ".hero" # Specific element
uv run $SKILL_DIR/design_review.py review <url> --annotate         # With annotations
uv run $SKILL_DIR/design_review.py review <url> --generate-tasks   # With task file

# === SPEC MANAGEMENT ===
uv run $SKILL_DIR/design_review.py specs --list                    # List specs
uv run $SKILL_DIR/design_review.py specs --validate my-spec.md     # Validate spec
uv run $SKILL_DIR/design_review.py specs --show default.md         # Show spec details

# === TESTING ===
npm run dev                                                         # Start dev server
uv run $SKILL_DIR/design_review.py review http://localhost:3000 --annotate --generate-tasks
```

---

## Design Decisions Made

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Spec format | Markdown + YAML frontmatter | Human-readable, easy to version control |
| Annotation style | Numbered circles + severity colors | Both numbers (for reference) and colors (for scanning) |
| Session ID format | `review_YYYYMMDDHHMMSS###` | Timestamp-based, sortable |
| Screenshot in legend | Yes, with issue list | Provides visual reference alongside annotations |
| Source file detection | Heuristic-based | data-testid, class names, common patterns |
| Code examples | Per check-id lookup | Extensible dictionary of common fixes |

---

## Open Questions (Future Phases)

1. **Interactive overlay UX**: Mini compliance card vs simple icon on hover?
2. **Agent-canvas integration**: Separate entry point or `--mode review` flag?
3. **Figma auth**: How to handle Figma API authentication for comparison?
4. **Real-time checks**: Run checks as page loads or only on demand?

---

## Files Overview

```
.claude/skills/design-review/
├── SKILL.md                     # Skill documentation
├── scripts/
│   ├── design_review.py         # Main CLI (review, specs commands)
│   ├── spec_loader.py           # Markdown spec parser
│   └── annotator.py             # Screenshot annotation
├── specs/
│   ├── default.md               # Default spec (4 pillars, 21 checks)
│   └── README.md                # Spec format documentation
└── imgs/
    └── README.md                # Reference image documentation (future)
```
