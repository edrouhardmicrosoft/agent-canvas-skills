# Design Review Skill - Implementation Plan

> **Hero Feature**: Spec-driven design review with visual annotations, interactive compliance checking, and automated task generation.

## Vision

Transform agent-canvas from a visual editing tool into a **design quality assurance system** that:
1. Reviews UI implementations against customizable design specs
2. Generates annotated screenshots with redlined issues
3. Creates actionable task lists for fixes
4. Enables interactive element-by-element compliance checking

---

## Key Design Decisions

| Decision | Choice |
|----------|--------|
| Spec format | **Markdown** with frontmatter for metadata |
| Default mode | **Design review** (not live editing) |
| User prompt | **Ask what they're looking for** if not specified |
| Figma integration | **Optional enhancement**, `imgs/` is default |
| Review scope (v1) | **Full page** + **specific element** |
| Task output | **todowrite integration** + **DESIGN-REVIEW-TASKS.md** file |
| Interactive selection | **Core feature** - select element, get spec compliance feedback |

---

## Skill Structure

```
.claude/skills/design-review/
├── SKILL.md                          # Main skill + default review criteria
├── scripts/
│   ├── design_review.py              # Main entry point
│   ├── spec_loader.py                # Parse markdown specs
│   ├── image_comparator.py           # Compare against reference images
│   ├── annotator.py                  # Draw redlines/markers
│   ├── issue_generator.py            # Structured issue output
│   └── task_generator.py             # Generate DESIGN-REVIEW-TASKS.md
├── specs/
│   ├── default.md                    # Ships with skill - sensible defaults
│   ├── fluent-ui.md                  # Microsoft Fluent patterns (example)
│   └── README.md                     # How to add custom specs
└── imgs/
    └── README.md                     # How to add reference images
```

---

## Markdown Spec Format

### Default Spec (specs/default.md)

```markdown
---
name: Default Design Review
version: "1.0"
extends: null
---

# Default Design Review Spec

Base design quality standards for any web application.

## Frictionless Insight to Action

Design for momentum. Users complete their task efficiently.

### Checks

#### max-interactions
- **Severity**: major
- **Description**: Core task completable in ≤3 interactions
- **How to check**: Count clicks/taps from entry to task completion

#### single-primary-action
- **Severity**: major  
- **Description**: Only 1-2 primary actions per view
- **How to check**: Count elements with primary button styling or prominent CTA treatment

#### clear-navigation
- **Severity**: major
- **Description**: Clear entry and exit points for every experience
- **How to check**: Verify back/cancel always available, breadcrumbs present for deep flows

---

## Progressive Clarity

Keep the default path simple. Reveal depth only when needed.

### Checks

#### smart-defaults
- **Severity**: minor
- **Description**: No unnecessary upfront configuration
- **How to check**: User can proceed immediately without filling required fields

#### feature-explanation
- **Severity**: minor
- **Description**: Feature purpose explained on first encounter
- **How to check**: New features have introductory text or teaching callouts

---

## Quality Craft

Typography, density, spacing, and accessibility shape outcomes.

### Checks

#### accessibility-grade
- **Severity**: blocking
- **Description**: Meets minimum accessibility standards
- **Config**:
  - minimum_grade: C
  - target_grade: B
- **How to check**: Run axe-core scan, evaluate WCAG compliance level

#### color-contrast
- **Severity**: major
- **Description**: Text has sufficient contrast against background
- **Config**:
  - minimum_ratio: 4.5
- **How to check**: Verify contrast ratio for all text elements

#### keyboard-navigation
- **Severity**: major
- **Description**: All interactive elements accessible via keyboard
- **How to check**: Tab through page, verify focus indicators visible

---

## Trustworthy Building

Equip users to build with confidence.

### Checks

#### ai-disclaimer
- **Severity**: blocking
- **Description**: AI-generated content includes required disclaimer
- **How to check**: Look for AI output areas, verify disclaimer present

#### secure-defaults
- **Severity**: major
- **Description**: Least privilege access, safe configurations by default
- **How to check**: Check default permission states, sharing settings
```

### User Custom Spec Example (specs/my-project.md)

```markdown
---
name: My Project Design Spec
version: "1.0"
extends: default.md
---

# My Project Design Spec

Custom rules for our specific project. Extends the default spec.

## Overrides

### accessibility-grade
- **Severity**: blocking
- **Config**:
  - minimum_grade: B
  - target_grade: A

---

## Brand Guidelines

Project-specific brand requirements.

### Checks

#### brand-colors
- **Severity**: major
- **Description**: Uses approved brand colors only
- **Approved colors**:
  - `#0078D4` - Primary Blue
  - `#FFFFFF` - White
  - `#F3F3F3` - Light Gray
  - `#323130` - Dark Gray
- **How to check**: Extract colors from elements, compare against approved list

#### typography
- **Severity**: minor
- **Description**: Uses approved font families
- **Approved fonts**:
  - Segoe UI
  - Segoe UI Variable
- **How to check**: Check computed font-family on text elements

#### spacing-scale
- **Severity**: minor
- **Description**: Uses 4px/8px spacing scale
- **How to check**: Verify margins/padding are multiples of 4px

---

## Component Library

### Checks

#### fluent-components
- **Severity**: minor
- **Description**: Uses Fluent UI React components
- **Required patterns**:
  - `@fluentui/react-components`
- **Forbidden patterns**:
  - Custom button implementations
  - Inline style overrides for colors
```

---

## CLI Interface

```bash
SKILL_DIR=".claude/skills/design-review/scripts"

# === MAIN COMMANDS ===

# Launch design review (prompts user for what they want if not specified)
uv run $SKILL_DIR/design_review.py http://localhost:3000

# Full page review with default spec
uv run $SKILL_DIR/design_review.py review http://localhost:3000

# Full page review with custom spec
uv run $SKILL_DIR/design_review.py review http://localhost:3000 --spec my-project.md

# Review specific element (by selector)
uv run $SKILL_DIR/design_review.py review http://localhost:3000 --selector ".hero-section"

# Interactive mode - pick elements to review
uv run $SKILL_DIR/design_review.py interactive http://localhost:3000

# === COMPARISON ===

# Compare against reference image
uv run $SKILL_DIR/design_review.py compare http://localhost:3000 --reference imgs/homepage.png

# Compare with Figma (if MCP connected)
uv run $SKILL_DIR/design_review.py compare http://localhost:3000 \
  --figma "https://figma.com/file/xxx" \
  --frame "Homepage"

# === OUTPUT OPTIONS ===

# Generate annotated screenshot with issues marked
uv run $SKILL_DIR/design_review.py review http://localhost:3000 --annotate

# Generate task file for fixes
uv run $SKILL_DIR/design_review.py review http://localhost:3000 --generate-tasks

# JSON output for programmatic use
uv run $SKILL_DIR/design_review.py review http://localhost:3000 --json

# === UTILITIES ===

# List available specs
uv run $SKILL_DIR/design_review.py specs --list

# Validate a spec file
uv run $SKILL_DIR/design_review.py specs --validate my-project.md

# List reference images
uv run $SKILL_DIR/design_review.py imgs --list
```

---

## Interactive Mode Flow

When user runs `design_review.py interactive`:

1. **Browser opens** with design-review overlay (NOT edit panel)
   - Similar to current picker but styled for review
   - Shows spec compliance indicators as you hover

2. **User hovers over elements:**
   - See quick compliance status (✅ Pass / ⚠️ Warning / ❌ Fail)
   - See which spec rules apply to this element type

3. **User clicks element to select:**
   - Full spec compliance report for that element
   - Issues listed with severity
   - Recommendations shown inline

4. **User can:**
   - Click "Add to Review" to include in final report
   - Click "Next Issue" to jump to next non-compliant element
   - Close browser to generate final report

5. **On close:**
   - Annotated screenshot generated
   - DESIGN-REVIEW-TASKS.md created (if editable context)
   - Session saved to .canvas/reviews/

---

## Prompt Flow (When User Doesn't Specify)

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

If user types a description like "check if the buttons follow our brand guidelines", the skill parses intent and runs appropriate checks.

---

## Output: DESIGN-REVIEW-TASKS.md

```markdown
# Design Review Tasks

> Generated: 2026-01-22T20:30:00Z
> URL: http://localhost:3000
> Spec: my-project.md
> Session: ses-abc123

## Summary

| Severity | Count |
|----------|-------|
| 🔴 Blocking | 1 |
| 🟠 Major | 3 |
| 🟡 Minor | 2 |

## Blocking Issues

### 1. Missing AI Disclaimer
- **Pillar**: Trustworthy Building
- **Rule**: `ai-disclaimer`
- **Element**: `.ai-response-container`
- **Location**: `app/components/AIResponse.tsx` (line ~45)
- **Issue**: AI-generated content displayed without required disclaimer
- **Fix**: Add MessageBar with "AI-generated content may be incorrect"

```tsx
// Suggested fix
<MessageBar intent="warning">
  AI-generated content may be incorrect
</MessageBar>
```

---

## Major Issues

### 2. Insufficient Color Contrast
- **Pillar**: Quality Craft
- **Rule**: `color-contrast`
- **Element**: `.subtitle-text`
- **Issue**: Contrast ratio 3.2:1 (minimum 4.5:1 required)
- **Current**: `color: #767676` on `background: #FFFFFF`
- **Fix**: Darken text to `#595959` or darker

### 3. Multiple Primary Actions
- **Pillar**: Frictionless
- **Rule**: `single-primary-action`
- **Element**: `.hero-section`
- **Issue**: Found 3 primary-styled buttons in hero section
- **Fix**: Demote secondary actions to default/subtle button variants

### 4. Missing Keyboard Focus Indicator
- **Pillar**: Quality Craft
- **Rule**: `keyboard-navigation`
- **Element**: `.card-link`
- **Issue**: No visible focus state when tabbing
- **Fix**: Add `:focus-visible` styles or use Fluent Link component

---

## Minor Issues

### 5. Non-Standard Spacing
- **Pillar**: Brand Guidelines
- **Rule**: `spacing-scale`
- **Element**: `.content-wrapper`
- **Issue**: Uses 15px margin (not on 4px scale)
- **Fix**: Change to 16px (4 × 4)

### 6. Custom Font Detected
- **Pillar**: Brand Guidelines
- **Rule**: `typography`
- **Element**: `.promo-badge`
- **Issue**: Uses "Arial" instead of approved fonts
- **Fix**: Change to "Segoe UI"

---

## Reference

- **Annotated Screenshot**: `.canvas/reviews/ses-abc123/annotated.png`
- **Full Report (JSON)**: `.canvas/reviews/ses-abc123/report.json`
- **Session Data**: `.canvas/reviews/ses-abc123/session.json`

---

*To apply fixes, review each task and say "fix these design issues".*
```

---

## Session Artifacts

```
.canvas/reviews/
└── ses-abc123/
    ├── session.json              # Full event log + metadata
    ├── report.json               # Structured issue data
    ├── screenshot-before.png     # Original screenshot
    ├── annotated.png             # Screenshot with redlines
    └── DESIGN-REVIEW-TASKS.md    # Human-readable task list
```

---

## Integration with Existing Skills

| Skill | How Design Review Uses It |
|-------|---------------------------|
| `agent-eyes` | Screenshots, a11y scans, DOM analysis, element descriptions |
| `agent-canvas` | Interactive element picker (modified for review mode) |
| `canvas-verify` | Visual comparison logic (reuse for reference image comparison) |
| `shared/canvas_bus` | Event coordination, capture mode for clean screenshots |

**New overlay mode for agent-canvas:**
Instead of the blue "picker" overlay, design-review injects a "review" overlay that:
- Shows compliance indicators (✅⚠️❌) as you hover
- Displays spec rule matches for element types
- Has "Add to Review" instead of "Select"
- Shows issue count badge instead of selection count

---

## Implementation Phases

### Phase 1: Core Review Engine
- [ ] Markdown spec parser (`spec_loader.py`)
- [ ] Default spec (`specs/default.md`)
- [ ] Basic issue detection from agent-eyes data
- [ ] CLI with `review` command
- [ ] JSON output format

### Phase 2: Annotation & Output
- [ ] Screenshot annotator (`annotator.py`)
- [ ] Redline drawing (numbered markers, severity colors)
- [ ] DESIGN-REVIEW-TASKS.md generation
- [ ] Session artifacts structure

### Phase 3: Interactive Mode
- [ ] Review overlay JS (modify picker overlay)
- [ ] Compliance indicators on hover
- [ ] Element-specific review flow
- [ ] "Add to Review" workflow

### Phase 4: Comparison Features
- [ ] Reference image comparison from `imgs/`
- [ ] Visual diff output
- [ ] Figma MCP integration (optional)

### Phase 5: Smart Features
- [ ] User prompt parsing (natural language → review type)
- [ ] Editable context detection
- [ ] Source file mapping for tasks
- [ ] todowrite integration

---

## Open Questions (To Resolve Before Implementation)

1. **Default spec content**: Should we include all 4 pillars from the CoreAI example in `default.md`, or start with a lighter set of universal rules (a11y, contrast, basic UX)?

2. **Annotation style**: For the redlined screenshots:
   - Red borders with numbered circles (①②③)?
   - Color-coded by severity (red/orange/yellow)?
   - Both?

3. **Review overlay UX**: When hovering in interactive mode:
   - Show mini compliance card?
   - Just show ✅⚠️❌ icon?
   - Show applicable rule names?

4. **Agent-canvas default change**: Should we:
   - Add a `--mode review|edit|pick` flag to agent-canvas?
   - Create a separate entry point that calls agent-canvas under the hood?
   - Make design-review completely standalone (copy needed code)?
