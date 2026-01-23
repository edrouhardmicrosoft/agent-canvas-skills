# Canvas Edit Redesign: Live Annotation Feedback Toolbar - Tasks

> **Scope**: Complete transformation of `canvas-edit` from a Figma-like editing tool into a **Live Annotation Feedback Toolbar** that overlays agent findings directly on watched webpages in real-time.

**Source Plan**: [plans/canvas-edit-update.md](../plans/canvas-edit-update.md)

---

## Implementation Status

| Phase | Description | Status |
|-------|-------------|--------|
| Phase 1 | Core Toolbar | ✅ Complete |
| Phase 2 | Annotation System | ✅ Complete |
| Phase 3 | Integration | ✅ Complete |
| Phase 4 | Screenshot & Orientation | 🔲 Pending |
| Phase 5 | Filtering & Polish | 🔲 Pending |
| Phase 6 | Documentation & Testing | 🔲 Pending |

---

## Phase 1: Core Toolbar

> **Goal**: Basic floating toolbar with Shadow DOM, drag, and issue status display.

### 1.1 Shadow DOM Setup

| Task | Description | Status | Verification |
|------|-------------|--------|--------------|
| 1.1.1 | Create Shadow DOM host element (`__annotation_toolbar_host`) | ✅ | Host exists in DOM, shadow root created with `mode: 'closed'` |
| 1.1.2 | Ensure Shadow DOM is invisible to agent-eyes screenshots | ✅ | Run agent-eyes screenshot, confirm toolbar NOT captured |
| 1.1.3 | Set up CSS variable injection for Fluent 2 color palette | ✅ | All 13 CSS variables from spec injected (toolbar-bg, severity colors, etc.) |

### 1.2 Toolbar Layout (Horizontal Mode)

| Task | Description | Status | Verification |
|------|-------------|--------|--------------|
| 1.2.1 | Create toolbar container with horizontal flexbox layout | ✅ | Toolbar renders horizontally, matches ASCII mockup dimensions |
| 1.2.2 | Implement drag handle (`☰`) as first element | ✅ | Drag handle visible, styled per spec |
| 1.2.3 | Implement status section showing issue count | ✅ | "N Issues" text displays, updates when count changes |
| 1.2.4 | Implement severity badges (🔴 🟡 🔵 counts) | ✅ | Three severity badges with counts, correct colors per spec |
| 1.2.5 | Add visibility toggle button (`👁`) | ✅ | Button renders, toggles `aria-pressed` on click |
| 1.2.6 | Add screenshot button (`📸`) | ✅ | Button renders, placeholder click handler |
| 1.2.7 | Add orientation toggle button (`↕`/`↔`) | ✅ | Button renders, placeholder click handler |
| 1.2.8 | Add dismiss button (`✕`) | ✅ | Button removes all annotations and toolbar |

### 1.3 Drag Functionality

| Task | Description | Status | Verification |
|------|-------------|--------|--------------|
| 1.3.1 | Implement mouse drag on drag handle | ✅ | Toolbar follows mouse when dragging handle |
| 1.3.2 | Implement touch drag for mobile | ✅ | Toolbar follows touch when dragging handle |
| 1.3.3 | Store position in memory for session persistence | ✅ | Position persists during page interaction |
| 1.3.4 | Set default initial position (top-right, 8px margin) | ✅ | Toolbar appears at top-right on first load |

### 1.4 Styling (Fluent 2 Inspired)

| Task | Description | Status | Verification |
|------|-------------|--------|--------------|
| 1.4.1 | Apply mono-tone dark grey palette to toolbar | ✅ | Background #292929, border #3d3d3d matches spec |
| 1.4.2 | Style buttons with hover/active states | ✅ | Hover shows #3d3d3d, active shows #454545 |
| 1.4.3 | Apply Fluent 2 motion tokens for transitions | ✅ | Transitions use correct durations and easings from spec |
| 1.4.4 | Add focus ring styling for keyboard navigation | ✅ | Tab through controls shows #58a6ff focus ring |

### 1.5 Toolbar States

| Task | Description | Status | Verification |
|------|-------------|--------|--------------|
| 1.5.1 | Implement "Issues Found" state (default) | ✅ | Shows count and severity badges |
| 1.5.2 | Implement "All Clear" state with success message | ✅ | Shows "✓ All looks good!" (or random variant) |
| 1.5.3 | Implement "Scanning" state with spinner | ✅ | Shows "⟳ Analyzing..." with animation |
| 1.5.4 | Implement randomized success messages (5 variants) | ✅ | Success state cycles through: "Ship it!", "Pixel perfect", etc. |

**Files created:**
- `.claude/skills/canvas-edit/scripts/annotation_toolbar.js` ✅
- `.claude/skills/canvas-edit/scripts/styles/toolbar.css` ✅
- `.claude/skills/canvas-edit/scripts/verify_phase1.py` ✅ (verification script)
- `.claude/skills/canvas-edit/scripts/test_toolbar.html` ✅ (manual test page)

---

## Phase 2: Annotation System

> **Goal**: Numbered badges on page elements with hover popovers showing issue details.

### 2.1 Badge Component

| Task | Description | Status | Verification |
|------|-------------|--------|--------------|
| 2.1.1 | Create numbered badge HTML structure | ✅ | Badge renders as circle with number inside |
| 2.1.2 | Style badge with severity-colored border | ✅ | Border color matches severity (red/orange/blue) |
| 2.1.3 | Implement badge appearance animation | ✅ | Badge fades in with scale animation per spec |
| 2.1.4 | Implement badge pulse animation for new issues | ✅ | New badges pulse twice per spec keyframes |

### 2.2 Badge Positioning

| Task | Description | Status | Verification |
|------|-------------|--------|--------------|
| 2.2.1 | Implement `positionBadge()` algorithm from spec | ✅ | Badges appear at top-right of target element |
| 2.2.2 | Add boundary detection (keep on screen) | ✅ | Badges near edges reposition to stay visible |
| 2.2.3 | Handle multiple badges on same element | ✅ | Badges stack or offset when overlapping |
| 2.2.4 | Reposition badges on window resize | ✅ | Badges move with their target elements |

### 2.3 Element Highlight

| Task | Description | Status | Verification |
|------|-------------|--------|--------------|
| 2.3.1 | Create highlight overlay element | ✅ | Overlay element exists with `pointer-events: none` |
| 2.3.2 | Style highlight per spec (10% opacity, 2px border) | ✅ | Highlight matches `.annotation-highlight` CSS from spec |
| 2.3.3 | Show highlight on badge hover | ✅ | Hovering badge highlights target element |
| 2.3.4 | Animate highlight with 150ms ease-out | ✅ | Highlight fades in/out smoothly |

### 2.4 Native Popover Integration

| Task | Description | Status | Verification |
|------|-------------|--------|--------------|
| 2.4.1 | Create popover HTML structure per spec template | ✅ | Popover contains header, body, meta, recommendation |
| 2.4.2 | Use native `[popover]` API with `popovertarget` | ✅ | Badge click opens native popover |
| 2.4.3 | Style popover with dark grey theme | ✅ | Popover matches toolbar styling |
| 2.4.4 | Implement popover animation (translateY, opacity) | ✅ | Popover slides in per spec CSS |
| 2.4.5 | Add Escape key to close popover | ✅ | Escape closes open popover (native API) |
| 2.4.6 | Return focus to badge on popover close | ✅ | Focus returns to trigger badge (native API) |

### 2.5 Annotation Layer

| Task | Description | Status | Verification |
|------|-------------|--------|--------------|
| 2.5.1 | Create annotation layer container (separate from toolbar host) | ✅ | Layer overlays page, contains all badges |
| 2.5.2 | Implement `addIssue(issue)` method | ✅ | Calling method adds badge to correct position |
| 2.5.3 | Implement `removeIssue(id)` method | ✅ | Calling method removes specific badge |
| 2.5.4 | Implement `clearAll()` method | ✅ | Calling method removes all badges |
| 2.5.5 | Expose `window.__annotationLayer` API | ✅ | API accessible from Python via page.evaluate |

**Files created:**
- `.claude/skills/canvas-edit/scripts/annotation_layer.js` ✅
- `.claude/skills/canvas-edit/scripts/styles/annotations.css` ✅

---

## Phase 3: Integration

> **Goal**: Connect to canvas bus, receive events from design-review, integrate with agent-eyes.

### 3.1 Canvas Bus Integration

| Task | Description | Status | Verification |
|------|-------------|--------|--------------|
| 3.1.1 | Subscribe to `review.issue_found` events | ✅ | Event handler fires when design-review emits issue |
| 3.1.2 | Subscribe to `review.completed` events | ✅ | Toolbar status updates when review finishes |
| 3.1.3 | Subscribe to `review.started` events | ✅ | Toolbar shows "Scanning" state when review starts |
| 3.1.4 | Subscribe to `capture_mode.changed` events | ✅ | Toolbar hides when agent-eyes captures |
| 3.1.5 | Emit `annotation.clicked` events | ✅ | Clicking badge emits event with issue data |
| 3.1.6 | Emit `screenshot.captured` events | ✅ | Screenshot button emits `screenshot.requested`; capture handled in Phase 4 |

### 3.2 Design-Review Integration

| Task | Description | Status | Verification |
|------|-------------|--------|--------------|
| 3.2.1 | Map design-review issue format to annotation format | ✅ | Issue data correctly populates badge and popover |
| 3.2.2 | Update toolbar issue count on each new issue | ✅ | Count increments as issues arrive |
| 3.2.3 | Update severity breakdown as issues arrive | ✅ | Severity badges show correct counts |
| 3.2.4 | Handle "no issues found" state | ✅ | Shows success state when review completes with 0 issues |

### 3.3 Agent-Eyes Integration

| Task | Description | Status | Verification |
|------|-------------|--------|--------------|
| 3.3.1 | Hide toolbar on `capture_mode.changed` (enabled=true) | ✅ | Toolbar invisible during screenshot capture |
| 3.3.2 | Keep annotations visible during capture | ✅ | Badges and highlights appear in screenshot |
| 3.3.3 | Show toolbar on `capture_mode.changed` (enabled=false) | ✅ | Toolbar reappears after capture |

### 3.4 Loading/Success States

| Task | Description | Status | Verification |
|------|-------------|--------|--------------|
| 3.4.1 | Show spinner during `review.started` | ✅ | Spinner animates, text shows "Analyzing..." |
| 3.4.2 | Transition from scanning to results state | ✅ | Smooth transition when review completes |
| 3.4.3 | Display random success message when 0 issues | ✅ | One of 5 success messages appears |

**Files modified:**
- `.claude/skills/design-review/scripts/review_overlay.js` (emit `review.started`, `review.issue_found`, `review.completed`)
- `.claude/skills/design-review/scripts/design_review.py` (call `__designReviewComplete` before browser close)
- `.claude/skills/canvas-edit/scripts/annotation_layer.js` (subscribe to `review.issue_found`, `review.completed`)

---

## Phase 4: Screenshot & Orientation

> **Goal**: Capture annotated screenshots and toggle toolbar orientation.

### 4.1 Screenshot Capture

| Task | Description | Status | Verification |
|------|-------------|--------|--------------|
| 4.1.1 | Implement `captureAnnotatedScreenshot()` function | 🔲 | Function executes full capture flow |
| 4.1.2 | Hide toolbar before capture | 🔲 | Toolbar not visible in screenshot |
| 4.1.3 | Keep annotations visible during capture | 🔲 | Badges visible in screenshot |
| 4.1.4 | Generate filename per convention (`YYYY-MM-DDTHH-MM-SS_N-issues.png`) | 🔲 | Filename matches pattern |
| 4.1.5 | Save to `.canvas/screenshots/` directory | 🔲 | File appears in correct directory |
| 4.1.6 | Show toolbar after capture | 🔲 | Toolbar reappears after save |
| 4.1.7 | Emit `screenshot.captured` event with path | 🔲 | Event contains correct file path |
| 4.1.8 | Create `.canvas/screenshots/` directory if missing | 🔲 | Directory created automatically |

### 4.2 Orientation Toggle

| Task | Description | Status | Verification |
|------|-------------|--------|--------------|
| 4.2.1 | Implement horizontal → vertical transition | 🔲 | Toolbar transforms from 400x48 to 64x280 |
| 4.2.2 | Implement vertical → horizontal transition | 🔲 | Toolbar transforms from 64x280 to 400x48 |
| 4.2.3 | Animate dimensions with ease-out timing | 🔲 | Transition takes 250ms with correct easing |
| 4.2.4 | Update button icon (`↕` ↔ `↔`) | 🔲 | Icon changes based on current orientation |
| 4.2.5 | Persist orientation state during session | 🔲 | Orientation remembered during session |

### 4.3 Boundary Detection

| Task | Description | Status | Verification |
|------|-------------|--------|--------------|
| 4.3.1 | Implement `correctToolbarPosition()` function | 🔲 | Toolbar stays within viewport bounds |
| 4.3.2 | Implement `canToggleOrientation()` pre-check | 🔲 | Function returns false if toggle would overflow |
| 4.3.3 | Pre-correct position before toggle if needed | 🔲 | Toolbar moves to safe position, then toggles |
| 4.3.4 | Add `correcting` class for smooth position fix | 🔲 | Position correction uses 150ms animation |
| 4.3.5 | Run boundary check on window resize | 🔲 | Toolbar repositions when window shrinks |
| 4.3.6 | Run boundary check after drag end | 🔲 | Toolbar snaps back if dragged off-screen |

**Files to modify:**
- `.claude/skills/canvas-edit/scripts/annotation_toolbar.js`

---

## Phase 5: Filtering & Polish

> **Goal**: Category filters, keyboard navigation, accessibility, and edge cases.

### 5.1 Category Filter

| Task | Description | Status | Verification |
|------|-------------|--------|--------------|
| 5.1.1 | Add filter dropdown/menu UI | 🔲 | Dropdown accessible from toolbar |
| 5.1.2 | Implement filter by severity (blocking/major/minor) | 🔲 | Toggling severity shows/hides matching badges |
| 5.1.3 | Implement filter by pillar | 🔲 | Toggling pillar shows/hides matching badges |
| 5.1.4 | Update badge visibility based on active filters | 🔲 | Only matching badges visible |
| 5.1.5 | Update toolbar count to reflect filtered view | 🔲 | Count shows "3 of 5 issues" when filtered |
| 5.1.6 | Persist filter state during session | 🔲 | Filters remembered during session |

### 5.2 Keyboard Navigation

| Task | Description | Status | Verification |
|------|-------------|--------|--------------|
| 5.2.1 | Tab navigation between toolbar controls | 🔲 | Tab moves focus through buttons |
| 5.2.2 | Escape closes open popover | 🔲 | (Already covered in 2.4.5) |
| 5.2.3 | Enter/Space activates focused control | 🔲 | Keyboard activation works for all buttons |
| 5.2.4 | Arrow keys navigate between badges | 🔲 | Arrow keys move focus between badges |
| 5.2.5 | Number keys (1-9) jump to badge by number | 🔲 | Pressing "1" focuses badge #1 |

### 5.3 ARIA Accessibility

| Task | Description | Status | Verification |
|------|-------------|--------|--------------|
| 5.3.1 | Add `role="toolbar"` to toolbar container | 🔲 | Screen reader identifies as toolbar |
| 5.3.2 | Add `aria-label` to all buttons | 🔲 | Each button has descriptive label |
| 5.3.3 | Add `aria-pressed` to toggle buttons | 🔲 | Toggle state communicated to screen readers |
| 5.3.4 | Add `aria-live="polite"` to status region | 🔲 | Issue count changes announced |
| 5.3.5 | Add `aria-describedby` linking badges to popovers | 🔲 | Badge describes its popover |
| 5.3.6 | Trap focus within popover when open | 🔲 | Tab doesn't leave open popover |

### 5.4 Edge Cases

| Task | Description | Status | Verification |
|------|-------------|--------|--------------|
| 5.4.1 | Handle target element removed from DOM | 🔲 | Badge removed or repositioned gracefully |
| 5.4.2 | Handle target element scrolled out of view | 🔲 | Badge stays attached or hides |
| 5.4.3 | Handle very long popover content | 🔲 | Popover scrolls or truncates gracefully |
| 5.4.4 | Handle rapid successive issues (debounce) | 🔲 | No visual glitches with fast issue stream |
| 5.4.5 | Handle page zoom | 🔲 | Badges reposition correctly on zoom |

### 5.5 Performance Optimization

| Task | Description | Status | Verification |
|------|-------------|--------|--------------|
| 5.5.1 | Debounce resize handler | 🔲 | No excessive reflow on window resize |
| 5.5.2 | Use transform instead of top/left where possible | 🔲 | Animations GPU-accelerated |
| 5.5.3 | Batch DOM updates for multiple badges | 🔲 | Single reflow for multiple badge additions |

**Files to modify:**
- `.claude/skills/canvas-edit/scripts/annotation_toolbar.js`
- `.claude/skills/canvas-edit/scripts/annotation_layer.js`

---

## Phase 6: Documentation & Testing

> **Goal**: Update documentation and create test coverage.

### 6.1 Documentation Updates

| Task | Description | Status | Verification |
|------|-------------|--------|--------------|
| 6.1.1 | Rewrite `.claude/skills/canvas-edit/SKILL.md` | 🔲 | Reflects new annotation toolbar functionality |
| 6.1.2 | Update README.md canvas-edit section | 🔲 | Quick start shows new commands |
| 6.1.3 | Document breaking changes from old canvas-edit | 🔲 | Migration notes for existing users |
| 6.1.4 | Document event API for other skills | 🔲 | Clear docs for integration events |
| 6.1.5 | Update `docs/AGENTS.md` with new trigger phrases | 🔲 | AI agents know when to use this skill |

### 6.2 Testing

| Task | Description | Status | Verification |
|------|-------------|--------|--------------|
| 6.2.1 | Create `test_canvas_edit.py` | 🔲 | Test file exists |
| 6.2.2 | Test toolbar injection and rendering | 🔲 | Test passes |
| 6.2.3 | Test badge positioning | 🔲 | Test passes |
| 6.2.4 | Test popover display | 🔲 | Test passes |
| 6.2.5 | Test screenshot capture | 🔲 | Test passes |
| 6.2.6 | Test orientation toggle | 🔲 | Test passes |
| 6.2.7 | Test boundary detection | 🔲 | Test passes |
| 6.2.8 | Test event integration (canvas bus) | 🔲 | Test passes |

### 6.3 Manual QA Checklist

| Task | Description | Status | Verification |
|------|-------------|--------|--------------|
| 6.3.1 | QA toolbar on Chrome | 🔲 | All features work |
| 6.3.2 | QA toolbar on Firefox | 🔲 | All features work |
| 6.3.3 | QA toolbar on Safari | 🔲 | All features work |
| 6.3.4 | QA keyboard navigation | 🔲 | All keyboard shortcuts work |
| 6.3.5 | QA with screen reader (VoiceOver) | 🔲 | Announces correctly |
| 6.3.6 | QA with design-review integration | 🔲 | End-to-end workflow works |

**Files to create:**
- `.claude/skills/canvas-edit/tests/test_canvas_edit.py`

**Files to modify:**
- `.claude/skills/canvas-edit/SKILL.md`
- `README.md`
- `docs/AGENTS.md`

---

## Python Entry Point Rewrite

> **Goal**: Rewrite `canvas_edit.py` to serve as injection entry point.

### 7.1 Python Script

| Task | Description | Status | Verification |
|------|-------------|--------|--------------|
| 7.1.1 | Remove all old editing functionality | 🔲 | No text editing, style sliders, contentEditable |
| 7.1.2 | Create `inject_annotation_toolbar(page, issues)` function | 🔲 | Function injects toolbar into page |
| 7.1.3 | Inject canvas bus JS before toolbar | 🔲 | Bus available when toolbar loads |
| 7.1.4 | Inject toolbar JS | 🔲 | Toolbar renders in page |
| 7.1.5 | Inject annotation layer JS | 🔲 | Annotation layer available |
| 7.1.6 | Loop through issues and call `addIssue()` | 🔲 | All issues added as badges |
| 7.1.7 | Provide CLI for standalone testing | 🔲 | `canvas_edit.py inject <url> --issues <json>` |

**Files to modify:**
- `.claude/skills/canvas-edit/scripts/canvas_edit.py` (complete rewrite)

---

## File Checklist

### New Files

| File | Phase | Status |
|------|-------|--------|
| `.claude/skills/canvas-edit/scripts/annotation_toolbar.js` | 1 | ✅ |
| `.claude/skills/canvas-edit/scripts/annotation_layer.js` | 2 | ✅ |
| `.claude/skills/canvas-edit/scripts/styles/toolbar.css` | 1 | ✅ |
| `.claude/skills/canvas-edit/scripts/styles/annotations.css` | 2 | ✅ |
| `.claude/skills/canvas-edit/tests/test_canvas_edit.py` | 6 | 🔲 |
| `.claude/skills/canvas-edit/scripts/verify_phase1.py` | 1 | ✅ |
| `.claude/skills/canvas-edit/scripts/test_toolbar.html` | 1 | ✅ |

### Modified Files

| File | Phase | Status |
|------|-------|--------|
| `.claude/skills/canvas-edit/scripts/canvas_edit.py` | 7 | 🔲 |
| `.claude/skills/canvas-edit/SKILL.md` | 6 | 🔲 |
| `.claude/skills/design-review/scripts/design_review.py` | 3 | 🔲 |
| `.claude/skills/shared/canvas_bus.py` | 3 | 🔲 (if needed) |
| `README.md` | 6 | 🔲 |
| `docs/AGENTS.md` | 6 | 🔲 |

---

## Migration Notes

### Breaking Changes

| Old Functionality | New Behavior |
|-------------------|--------------|
| Text editing via textarea | **REMOVED** - this is now a viewing tool |
| Style sliders (fontSize, etc.) | **REMOVED** - agents communicate findings, not edits |
| "Save All to Code" button | **REPLACED** with screenshot capture |
| contentEditable toggle | **REMOVED** |

### Preserved Functionality

- Shadow DOM encapsulation (invisible to agent-eyes)
- Drag to reposition
- Canvas bus integration
- Event emission for agent communication

### canvas-apply Impact

`canvas-apply` skill may need updates since `canvas-edit` no longer produces style/text changes. Options:
- Deprecate canvas-apply
- Repurpose for design-review fix suggestions

---

## Open Questions (To Resolve Before Implementation)

| Question | Options | Decision |
|----------|---------|----------|
| Annotation persistence on SPA navigation? | Persist / Clear on route change | TBD |
| Multi-page review state carry-over? | Persist toolbar state / Reset | TBD |
| Multiple issues on same element? | Single badge with count / Multiple badges | TBD |
| Zoom handling? | Scale badges / Fixed size | TBD |

---

## Success Criteria

All must pass before marking complete:

- [ ] Toolbar renders in Shadow DOM, invisible to agent-eyes screenshots
- [ ] Annotations appear in real-time as design-review finds issues
- [ ] Badges are numbered and clickable with native popovers
- [ ] Screenshot captures annotated page (minus toolbar) to `.canvas/`
- [ ] Orientation toggle animates smoothly with boundary correction
- [ ] Filter toggles show/hide annotations by category
- [ ] Success state displays friendly message when no issues found
- [ ] All interactions follow Fluent 2 motion patterns
- [ ] Mono-tone dark grey palette throughout (except severity colors)
