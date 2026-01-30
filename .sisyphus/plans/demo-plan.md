# Interactive Tutorial - Agent Canvas Playground

## TL;DR

> **Quick Summary**: Create an interactive tutorial at `/tutorial` that demonstrates the Agent Canvas design-review loop. Users see a page with an intentional contrast issue, ask their agent to fix it, then verify the fix—ending with an ASCII "NICE!" celebration.
> 
> **Deliverables**:
> - `/tutorial` page with intentional low-contrast text (marked with `data-testid="tutorial-contrast-issue"`)
> - Tutorial skill file at `.claude/skills/tutorial/SKILL.md`
> - ASCII "NICE!" celebration echoed to terminal on successful verification (skill-based, not UI component)
> 
> **Estimated Effort**: Medium (3 tasks, ~2-3 hours)
> **Parallel Execution**: YES - 2 waves
> **Critical Path**: Task 1 → Task 3
>
> **CRITICAL**: The `design-review` contrast check requires `--selector` to detect `color-contrast` issues. All commands must specify `--selector "[data-testid='tutorial-contrast-issue']"`.
>
> **CRITICAL**: The selected element MUST have an **explicit background color** set (e.g., `bg-white`) for contrast detection to work reliably. Transparent backgrounds cause contrast checks to fail silently.

---

## Prerequisites

Before running any verification commands, ensure:

```bash
# 1. Node.js dependencies installed
npm install

# 2. Dev server running (in a separate terminal)
npm run dev
# Expected: Server at http://localhost:3000

# 3. Python/uv and Playwright installed (for design-review)
uv run .claude/skills/agent-canvas-setup/scripts/check_setup.py check
# If fails, run: uv run .claude/skills/agent-canvas-setup/scripts/check_setup.py install --scope temporary

# 4. jq installed (for JSON parsing in verification)
which jq || echo "Install jq: brew install jq (mac) or apt install jq (linux)"
```

### Important Notes

1. **Browser Opens Visibly**: The `design_review.py review` command opens a real browser window (not headless). This is expected behavior for interactive review.

2. **Reset Mechanism Requires Committed State**: The `git checkout app/tutorial/page.tsx` reset command only works if Task 1 was committed to HEAD (not just staged). Before running reset, verify file exists in HEAD: `git cat-file -e HEAD:app/tutorial/page.tsx` (exit 0 = committed).

3. **Selector Required for Contrast Check**: The design-review script only emits `checkId: "color-contrast"` when `--selector` is provided. All verification commands MUST use `--selector "[data-testid='tutorial-contrast-issue']"`.

4. **Explicit Background Color Required**: The element with `data-testid="tutorial-contrast-issue"` MUST have an explicit `bg-white` (or similar solid color) set on it directly—not just inherited. Transparent backgrounds cause `design_review.py` to read `backgroundColor` as `rgba(0,0,0,0)`, which breaks contrast calculations.

---

## Context

### Original Request
User wants the repo to feel more like a "playground" where people can try out Agent Canvas without installing it on their own project. An interactive tutorial that walks through: see issue → fix it → verify it was fixed → celebrate with ASCII "NICE!".

### Interview Summary
**Key Discussions**:
- **Trigger method**: Both URL (`/tutorial`) AND skill file for agent commands
- **Fix interaction**: Originally wanted live browser editing, but Metis identified canvas-edit v2 removed editing (it's view-only now). Fix flow is: agent edits code → design-review verifies
- **Tutorial length**: Single issue (~2 min experience)
- **Dependencies**: Requires agent-canvas skills already installed
- **Success celebration**: ASCII art "NICE!" echoed to terminal on successful verification

**Research Findings**:
- canvas-edit v2 is a VIEWING tool, not editing tool
- For agent-orchestrated flow: agent modifies source code, then re-runs design-review
- Skill frontmatter: For this tutorial skill, use ONLY `name` and `description` (matching `design-review/SKILL.md` pattern). Note: repo skills are not uniform—some have extra fields, some have none.
- Design-review outputs JSON by default (no `--json` flag needed)
- **Contrast detection requires `--selector`**: The design-review script only checks contrast on a specific element when `--selector` is provided
- **Explicit background required**: `design_review.py` reads `getComputedStyle(el).backgroundColor`; transparent backgrounds break contrast checks

### Metis Review
**Identified Gaps** (addressed):
- **Fix mechanism clarification**: Resolved - agent edits code, not browser editing
- **ASCII display location**: Resolved - terminal echo only (not UI component)
- **Loop orchestration**: Resolved - skill documents the flow, agent follows instructions
- **Reset mechanism**: Defined below

### Reset Strategy (CRITICAL)
After completing the tutorial, the page should remain "broken" (with contrast issue) for the next user. The fix/verify loop is:

1. Agent applies fix (changes `text-gray-300` to `text-gray-700` in `app/tutorial/page.tsx`)
2. Agent runs verification with `--selector "[data-testid='tutorial-contrast-issue']"` (design-review finds 0 issues)
3. Agent echoes ASCII "NICE!" celebration
4. Agent reverts the fix: `git checkout app/tutorial/page.tsx`
5. Repo returns to "broken by default" state

**IMPORTANT**: The reset step (`git checkout`) only works if Task 1 was committed first. The skill file must:
- Document this revert step explicitly
- Warn that uncommitted changes to the tutorial file will be lost

---

## Work Objectives

### Core Objective
Create a "playground" experience where users can see Agent Canvas in action without setting up their own project—demonstrating the full REVIEW → FIX → VERIFY → CELEBRATE → RESET loop.

### Concrete Deliverables
- `app/tutorial/page.tsx` - Tutorial page with intentional contrast issue
- `.claude/skills/tutorial/SKILL.md` - Skill file guiding agents through the tutorial (includes ASCII art to echo)

### Definition of Done
- [ ] `curl -s http://localhost:3000/tutorial | grep -q 'data-testid="tutorial-contrast-issue"'` exits 0 (page loads with testid marker)
- [ ] `uv run .claude/skills/design-review/scripts/design_review.py review http://localhost:3000/tutorial --selector "[data-testid='tutorial-contrast-issue']" | jq -e '[.issues[] | select(.checkId == "color-contrast")] | length > 0'` exits 0 (contrast issue detected)
- [ ] After fix applied, same `jq -e` command exits non-zero (0 contrast issues)
- [ ] After revert (`git checkout app/tutorial/page.tsx`), contrast issue returns (jq -e exits 0 again)
- [ ] Skill file passes `grep -q "^name: tutorial" .claude/skills/tutorial/SKILL.md`

### Must Have
- Page loads at `/tutorial` with visible low-contrast text element marked with `data-testid="tutorial-contrast-issue"`
- Design-review detects the contrast issue when run with `--selector "[data-testid='tutorial-contrast-issue']"`
- Skill provides clear instructions for the fix → verify → reset loop
- ASCII "NICE!" echoed to terminal on successful verification

### Must NOT Have (Guardrails)
- NO scripts directory in tutorial skill (use existing design-review)
- NO modifications to existing skills
- NO new dependencies in package.json
- NO complex state management or progress tracking
- NO multi-step wizard UI
- NO custom CSS (use existing Tailwind classes only)
- NO analytics or telemetry
- NO internationalization
- NO React component for ASCII art (terminal echo only)

---

## Verification Strategy (MANDATORY)

### Test Decision
- **Infrastructure exists**: YES (design-review exists)
- **User wants tests**: Manual verification via design-review skill
- **Framework**: Uses existing design-review for automated checks

### Automated Verification (Agent-Executable)

**Page Verification** (using Bash curl):
```bash
# Verify page loads (requires dev server running)
curl -s http://localhost:3000/tutorial | grep -q 'Tutorial' && echo "PASS: Page loads"
```

**Contrast Issue Detection** (using Bash):
```bash
# Verify intentional issue exists (MUST use --selector for contrast check to work)
# Note: This opens a visible browser window (not headless)
uv run .claude/skills/design-review/scripts/design_review.py review http://localhost:3000/tutorial --selector "[data-testid='tutorial-contrast-issue']" 2>/dev/null | jq -e '.issues[] | select(.checkId == "color-contrast")' > /dev/null && echo "PASS: Contrast issue detected"
```

**Fix Verification** (using Bash):
```bash
# After fix, verify issue resolved
ISSUES=$(uv run .claude/skills/design-review/scripts/design_review.py review http://localhost:3000/tutorial --selector "[data-testid='tutorial-contrast-issue']" 2>/dev/null | jq '[.issues[] | select(.checkId == "color-contrast")] | length')
[ "$ISSUES" -eq 0 ] && echo "PASS: Contrast issue fixed"
```

**Reset Verification** (using Bash):
```bash
# After revert, verify issue returns
git checkout app/tutorial/page.tsx
ISSUES=$(uv run .claude/skills/design-review/scripts/design_review.py review http://localhost:3000/tutorial --selector "[data-testid='tutorial-contrast-issue']" 2>/dev/null | jq '[.issues[] | select(.checkId == "color-contrast")] | length')
[ "$ISSUES" -gt 0 ] && echo "PASS: Reverted to broken state"
```

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 1 (Start Immediately):
├── Task 1: Create tutorial page with contrast issue
└── Task 2: Create tutorial skill file

Wave 2 (After Wave 1):
└── Task 3: Integration testing (full loop verification)

Critical Path: Task 1 → Task 3
Parallel Speedup: ~30% faster than sequential
```

### Dependency Matrix

| Task | Depends On | Blocks | Can Parallelize With |
|------|------------|--------|---------------------|
| 1 | None | 3 | 2 |
| 2 | None | 3 | 1 |
| 3 | 1, 2 | None | None (final) |

### Agent Dispatch Summary

| Wave | Tasks | Recommended Agents |
|------|-------|-------------------|
| 1 | 1, 2 | `delegate_task(category="quick", load_skills=["frontend-ui-ux"], run_in_background=true)` |
| 2 | 3 | `delegate_task(category="quick", load_skills=["playwright"], run_in_background=false)` |

---

## TODOs

- [ ] 1. Create Tutorial Page with Intentional Contrast Issue

  **What to do**:
  - Create directory `app/tutorial/` and file `app/tutorial/page.tsx` (Next.js App Router convention)
  - Follow structure from `app/page.tsx` - export default function component
  - Add a heading and description paragraph
  - **EXACT ELEMENT TO CREATE** (contrast-failing element, ALL ATTRIBUTES ON SINGLE LINE for verification):
    ```tsx
    <p data-testid="tutorial-contrast-issue" className="text-gray-300 bg-white p-4">
      This text has low contrast. Can you fix it?
    </p>
    ```
  - **CRITICAL**: Attributes MUST be on a single line (not split across lines) so grep verification works
  - **CRITICAL REQUIREMENTS for this element**:
    - `data-testid="tutorial-contrast-issue"` - required for `--selector` targeting
    - `text-gray-300` - the failing color (~2:1 ratio, below 4.5:1 WCAG AA requirement)
    - `bg-white` - MUST be on the SAME element (not inherited) so `design_review.py` can read computed backgroundColor
    - `p-4` - padding to make element visible
  - The fix will change `text-gray-300` to `text-gray-700` (which passes 4.5:1)

  **Must NOT do**:
  - NO custom CSS files or CSS modules
  - NO new dependencies
  - NO complex state management
  - NO wizard/stepper UI
  - NO relying on inherited background colors (bg-white MUST be on the testid element)
  - NO splitting the `<p>` tag attributes across multiple lines (breaks grep verification)

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Single file creation following existing pattern
  - **Skills**: [`frontend-ui-ux`]
    - `frontend-ui-ux`: Helps craft the visual layout and ensures contrast issue is properly visible yet detectable

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Task 2)
  - **Blocks**: Task 3
  - **Blocked By**: None

  **References**:

  **Pattern References**:
  - `app/page.tsx:1-10` - Existing page structure with minimal Next.js setup
  - `app/layout.tsx` - Layout pattern showing font imports and body structure

  **API/Type References**:
  - Next.js App Router page conventions (export default function)

  **External References**:
  - WCAG 2.1 contrast requirements: 4.5:1 for normal text, 3:1 for large text

  **WHY Each Reference Matters**:
  - `app/page.tsx` shows the exact minimal structure to follow
  - WCAG reference explains what makes a "failing" contrast ratio

  **Acceptance Criteria**:

  ```bash
  # Prerequisites: npm install && npm run dev (in separate terminal)

  # 1. Page file exists (Next.js App Router creates /tutorial route)
  test -f app/tutorial/page.tsx
  # Assert: exits 0

  # 2. Page has the testid marker for contrast checking (on single line with className)
  grep -q 'data-testid="tutorial-contrast-issue".*className=' app/tutorial/page.tsx
  # Assert: exits 0

  # 3. Element has both testid AND bg-white on same line (CRITICAL for contrast detection + verification)
  grep -q 'data-testid="tutorial-contrast-issue".*bg-white' app/tutorial/page.tsx
  # Assert: exits 0 (both on same line means bg-white is on the element, not inherited)

  # 4. Element has the failing text-gray-300 color
  grep -q 'text-gray-300' app/tutorial/page.tsx
  # Assert: exits 0

  # 5. Design-review detects contrast issue (opens visible browser)
  uv run .claude/skills/design-review/scripts/design_review.py review http://localhost:3000/tutorial --selector "[data-testid='tutorial-contrast-issue']" 2>/dev/null | jq -e '[.issues[] | select(.checkId == "color-contrast")] | length > 0'
  # Assert: exits 0 (contrast issue detected)
  ```

  **Commit**: YES (MUST commit to HEAD before Task 3 - reset mechanism depends on file being in HEAD)
  - Message: `feat(tutorial): add tutorial page with intentional contrast issue`
  - Files: `app/tutorial/page.tsx`
  - Pre-commit: Run `npm run build` and verify it passes

---

- [ ] 2. Create Tutorial Skill File

  **What to do**:
  - Create `.claude/skills/tutorial/SKILL.md` with YAML frontmatter
  - **Frontmatter (follow `design-review/SKILL.md` pattern - only name and description)**:
    ```yaml
    ---
    name: tutorial
    description: Interactive Agent Canvas tutorial. Trigger: "run the tutorial", "start tutorial", "agent canvas tutorial"
    ---
    ```
    - Use only `name` and `description` fields (matching design-review style)
    - Note: Other skills in repo have varying frontmatter; this is a deliberate choice for consistency
  - Skill body should guide agents through the REVIEW → FIX → VERIFY → CELEBRATE → RESET loop
  - Include the exact commands to run at each step:
    - **CRITICAL**: All design-review commands MUST include `--selector "[data-testid='tutorial-contrast-issue']"` for contrast detection
    - Note that design-review outputs JSON by default (no `--json` flag)
    - Note that design-review opens a visible browser window
  - Include the ASCII "NICE!" art to be echoed to terminal on success
  - Include explicit reset instructions: `git checkout app/tutorial/page.tsx`
    - Warn that this discards local changes to the tutorial file
  - Keep skill body under 100 lines

  **Must NOT do**:
  - NO `scripts/` directory (use existing design-review)
  - NO complex logic or conditionals
  - NO modifications to other skills

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Single markdown file creation
  - **Skills**: []
    - No special skills needed for markdown writing

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Task 1)
  - **Blocks**: Task 3
  - **Blocked By**: None

  **References**:

  **Pattern References**:
  - `.claude/skills/design-review/SKILL.md:1-50` - Skill structure with frontmatter and commands section (USE THIS as primary template - only `name` and `description` in frontmatter)

  **Documentation References**:
  - Skill frontmatter: Use only `name` and `description` (matching design-review/SKILL.md pattern)
  - Note: Repo skills have varying frontmatter styles; this is a deliberate choice for the tutorial skill

  **WHY Each Reference Matters**:
  - `design-review/SKILL.md` shows the exact format to follow - copy its frontmatter structure
  - Use only `name` and `description` for this skill (deliberate choice for simplicity)

  **Acceptance Criteria**:

  ```bash
  # Skill file exists
  test -f .claude/skills/tutorial/SKILL.md
  # Assert: exits 0

  # Has required frontmatter fields
  grep -q "^name: tutorial" .claude/skills/tutorial/SKILL.md
  # Assert: exits 0

  grep -q "^description:" .claude/skills/tutorial/SKILL.md
  # Assert: exits 0

  # Contains ASCII art
  grep -q "NICE" .claude/skills/tutorial/SKILL.md
  # Assert: exits 0

  # Contains design-review command with --selector (CRITICAL)
  grep -q '\-\-selector.*tutorial-contrast-issue' .claude/skills/tutorial/SKILL.md
  # Assert: exits 0

  # Contains reset/revert instructions
  grep -q "git checkout" .claude/skills/tutorial/SKILL.md
  # Assert: exits 0
  ```

  **Commit**: YES
  - Message: `feat(tutorial): add tutorial skill file with guided workflow`
  - Files: `.claude/skills/tutorial/SKILL.md`
  - Pre-commit: None (markdown file)

---

- [ ] 3. Integration Test: Full Tutorial Loop

  **What to do**:
  - Verify the complete flow works end-to-end:
    1. Ensure dev server is running (`npm run dev`)
    2. Run design-review on `/tutorial` with `--selector "[data-testid='tutorial-contrast-issue']"` - should find contrast issue
    3. Apply the documented fix: change `text-gray-300` to `text-gray-700` in `app/tutorial/page.tsx`
    4. Re-run design-review with same selector - should find 0 contrast issues
    5. Echo ASCII "NICE!" celebration
    6. Revert the fix: `git checkout app/tutorial/page.tsx`
    7. Verify contrast issue returns (page is "broken" again)
  - Verify skill file instructions match actual commands (especially --selector usage)

  **Must NOT do**:
  - NO leaving the fix applied (must revert to broken state)
  - NO adding new features beyond verification

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Testing and verification only
  - **Skills**: [`playwright`]
    - `playwright`: For browser-based verification if needed

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 2 (sequential)
  - **Blocks**: None (final task)
  - **Blocked By**: Tasks 1, 2

  **References**:

  **Pattern References**:
  - `.claude/skills/design-review/SKILL.md:24-47` - Commands for running design-review
  - `.claude/skills/tutorial/SKILL.md` (created in Task 2) - The workflow to verify

  **WHY Each Reference Matters**:
  - Need to verify commands in skill file actually work as documented

  **Acceptance Criteria**:

  ```bash
  # Prerequisites: 
  # - npm install && npm run dev (in separate terminal)
  # - Task 1 must be COMMITTED TO HEAD before this test (reset depends on file being in HEAD)

  # Step 0: PRECONDITION - Verify file exists in HEAD (required for git checkout reset)
  git cat-file -e HEAD:app/tutorial/page.tsx
  # Assert: exits 0 (file is committed). If this fails, commit Task 1 first!
  # Note: git ls-files only checks if tracked, not if committed to HEAD

  # Step 1: Verify initial state has contrast issue (using --selector, opens visible browser)
  BEFORE=$(uv run .claude/skills/design-review/scripts/design_review.py review http://localhost:3000/tutorial --selector "[data-testid='tutorial-contrast-issue']" 2>/dev/null | jq '[.issues[] | select(.checkId == "color-contrast")] | length')
  [ "$BEFORE" -gt 0 ] && echo "PASS: Initial state has contrast issue (count: $BEFORE)"
  # Assert: At least 1 contrast issue exists

  # Step 2: Apply the documented fix (temporarily)
  # Change text-gray-300 to text-gray-700 in app/tutorial/page.tsx
  sed -i.bak 's/text-gray-300/text-gray-700/g' app/tutorial/page.tsx

  # Step 3: Verify fix resolves the issue (wait for hot reload)
  sleep 2
  AFTER=$(uv run .claude/skills/design-review/scripts/design_review.py review http://localhost:3000/tutorial --selector "[data-testid='tutorial-contrast-issue']" 2>/dev/null | jq '[.issues[] | select(.checkId == "color-contrast")] | length')
  [ "$AFTER" -eq 0 ] && echo "PASS: Fix resolved contrast issue"
  # Assert: 0 contrast issues after fix

  # Step 4: Echo ASCII celebration
  echo ""
  echo " _   _ ___ ____ _____ _ "
  echo "| \\ | |_ _/ ___| ____| |"
  echo "|  \\| || | |   |  _| | |"
  echo "| |\\  || | |___| |___|_|"
  echo "|_| \\_|___\\____|_____(_)"
  echo ""
  echo "Tutorial verification complete!"

  # Step 5: Revert to broken state (REQUIRES file to exist in HEAD)
  # WARNING: This discards all local changes to this file
  git checkout app/tutorial/page.tsx
  rm -f app/tutorial/page.tsx.bak

  # Step 6: Verify revert worked
  sleep 2
  REVERTED=$(uv run .claude/skills/design-review/scripts/design_review.py review http://localhost:3000/tutorial --selector "[data-testid='tutorial-contrast-issue']" 2>/dev/null | jq '[.issues[] | select(.checkId == "color-contrast")] | length')
  [ "$REVERTED" -gt 0 ] && echo "PASS: Reverted to broken state (count: $REVERTED)"
  # Assert: Contrast issue is back

  # Step 7: Verify skill file contains correct --selector usage
  grep -q '\-\-selector.*tutorial-contrast-issue' .claude/skills/tutorial/SKILL.md && echo "PASS: Skill has correct --selector usage"
  # Assert: exits 0

  # Step 8: Verify skill file contains reset instructions
  grep -q "git checkout app/tutorial/page.tsx" .claude/skills/tutorial/SKILL.md && echo "PASS: Skill has reset instructions"
  # Assert: exits 0
  ```

  **Commit**: NO (testing only, all changes reverted)

---

## Commit Strategy

| After Task | Message | Files | Verification |
|------------|---------|-------|--------------|
| 1 | `feat(tutorial): add tutorial page with intentional contrast issue` | `app/tutorial/page.tsx` | `npm run build` |
| 2 | `feat(tutorial): add tutorial skill file with guided workflow` | `.claude/skills/tutorial/SKILL.md` | None |

---

## Success Criteria

### Verification Commands
```bash
# Prerequisites
npm install
npm run dev  # In separate terminal

# Full verification script
npm run build                                    # Expected: builds successfully
test -f app/tutorial/page.tsx                   # Expected: exit 0 (page file exists)
test -f .claude/skills/tutorial/SKILL.md        # Expected: exit 0 (skill file exists)

# Verify testid and bg-white are on same line (single-line attributes for grep verification)
grep -q 'data-testid="tutorial-contrast-issue".*bg-white' app/tutorial/page.tsx
# Expected: exit 0 (both on same element/line)

# Contrast issue detection (MUST use --selector; opens visible browser window)
uv run .claude/skills/design-review/scripts/design_review.py review http://localhost:3000/tutorial --selector "[data-testid='tutorial-contrast-issue']" | jq -e '[.issues[] | select(.checkId == "color-contrast")] | length > 0'
# Expected: exit 0 (at least 1 contrast issue detected)
```

### Final Checklist
- [ ] Tutorial page file exists at `app/tutorial/page.tsx`
- [ ] Page has `data-testid="tutorial-contrast-issue"` with attributes on single line
- [ ] Same element has explicit `bg-white` on same line (not inherited) for contrast detection
- [ ] Same element has `text-gray-300` (the failing color)
- [ ] Design-review with `--selector` detects contrast issue on fresh page
- [ ] Documented fix (`text-gray-300` → `text-gray-700`) resolves the issue
- [ ] Skill file exists with frontmatter: only `name` and `description` fields (deliberate choice)
- [ ] Skill file contains ASCII "NICE!" art
- [ ] Skill file documents `--selector "[data-testid='tutorial-contrast-issue']"` in all design-review commands
- [ ] Skill file documents the complete REVIEW → FIX → VERIFY → RESET loop
- [ ] Skill file includes reset command: `git checkout app/tutorial/page.tsx`
- [ ] Task 1 is committed to HEAD (verify with `git cat-file -e HEAD:app/tutorial/page.tsx`)
- [ ] After reset, page returns to broken state
- [ ] All "Must Have" present
- [ ] All "Must NOT Have" absent
