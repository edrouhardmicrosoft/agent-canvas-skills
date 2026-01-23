# Canvas Edit Redesign: Live Annotation Feedback Toolbar

> Transform canvas-edit from a Figma-like editing tool into a **Live Annotation Feedback Toolbar** that overlays agent findings directly on watched webpages in real-time.

## Executive Summary

This plan outlines a complete overhaul of the `canvas-edit` skill to serve as the **visual feedback layer** for AI agent design reviews. Instead of enabling users to edit styles, the new tool will:

1. **Display agent findings** as live annotations/redlines directly on the page
2. **Provide a minimal floating toolbar** for controlling what's visible
3. **Enable screenshot capture** of the annotated view for documentation
4. **Integrate seamlessly** with `design-review` and `agent-eyes` skills

**Key Principle**: This is a **viewing/annotation tool**, not an editing tool. The agent marks up issues; the user sees them live.

---

## Design Philosophy & Principles

### Core Principles

| Principle | Description |
|-----------|-------------|
| **Live Feedback** | Annotations appear in real-time as the agent discovers issues |
| **Ephemeral by Design** | Annotations don't modify code; they're overlays that disappear on refresh |
| **Minimal UI** | Toolbar stays out of the way; the page content is the hero |
| **Agent-First** | Built for agents to communicate findings to developers |
| **Fluent 2 Native** | Microsoft design system for consistency and accessibility |

### Design System Requirements

- **Microsoft Fluent 2 Web Components** exclusively
- **Mono-tone dark grey palette** (no bright colors except severity indicators)
- **Shadow DOM encapsulation** for style isolation
- **Invisible to agent-eyes** screenshots (only captures the annotated page, not the toolbar)

---

## Visual Design Specification

### Color Palette (Mono-tone Dark Grey)

```css
/* Primary Surface */
--toolbar-bg: #292929;           /* Main toolbar background */
--toolbar-border: #3d3d3d;       /* Subtle borders */
--toolbar-elevated: #333333;     /* Raised elements */

/* Text */
--text-primary: #e0e0e0;         /* Primary text */
--text-secondary: #a0a0a0;       /* Secondary/muted text */
--text-disabled: #666666;        /* Disabled state */

/* Severity Indicators (the ONLY colors) */
--severity-error: #f85149;       /* Critical/blocking issues */
--severity-warning: #d29922;     /* Major issues */
--severity-info: #58a6ff;        /* Minor issues */
--severity-success: #3fb950;     /* All clear state */

/* Interaction States */
--hover-bg: #3d3d3d;
--active-bg: #454545;
--focus-ring: #58a6ff;
```

### Toolbar Layout

```
┌─────────────────────────────────────────────────────────────────┐
│  HORIZONTAL MODE (default)                                       │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │ ☰  │  3 Issues  │  🔴 1  🟡 2  │  [👁] [📸] [↕]  │  ✕  │ │
│  └─────────────────────────────────────────────────────────────┘ │
│       │             │               │                    │        │
│       │             │               │                    │        │
│    Drag          Issue           Filter              Orientation │
│    Handle        Count           Toggles             Toggle      │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘

┌──────────────────────┐
│  VERTICAL MODE       │
│                      │
│  ┌────────────────┐  │
│  │      ☰        │  │  ← Drag Handle
│  ├────────────────┤  │
│  │   3 Issues    │  │
│  │   🔴 1 🟡 2   │  │
│  ├────────────────┤  │
│  │     [👁]      │  │  ← Show/Hide Toggle
│  │     [📸]      │  │  ← Screenshot Button
│  │     [↔]       │  │  ← Orientation Toggle
│  ├────────────────┤  │
│  │      ✕        │  │  ← Dismiss All
│  └────────────────┘  │
│                      │
└──────────────────────┘
```

### ASCII Mockup: Toolbar States

```
┌─────────────────────────────────────────────────────────────────────────┐
│                                                                         │
│  STATE: Issues Found                                                     │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ ☰  │  3 Issues Found  │  🔴 1  🟡 2  │  [👁] [📸] [↕]  │  ✕  │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  STATE: All Clear                                                        │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ ☰  │  ✓ All looks good!  │  [📸] [↕]  │  ✕  │                  │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  STATE: Scanning (loading)                                               │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ ☰  │  ⟳ Analyzing...  │  [↕]  │  ✕  │                          │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Success State Creative Options

When no issues are found, display one of these (randomized or configurable):

| Message | Emoji | Vibe |
|---------|-------|------|
| "All looks good!" | ✓ | Professional |
| "Ship it!" | 🚀 | Casual/fun |
| "Pixel perfect" | ✨ | Designer-focused |
| "Zero issues found" | 0️⃣ | Data-focused |
| "Looking sharp!" | 👌 | Friendly |

---

## Component Architecture

### Fluent 2 Web Components Used

| Component | Usage | Import |
|-----------|-------|--------|
| `fluent-button` | All action buttons | `@fluentui/web-components` |
| `fluent-tooltip` | Hover info on badges | Native browser popover |
| `fluent-badge` | Issue counts by severity | `@fluentui/web-components` |
| `fluent-divider` | Section separators | `@fluentui/web-components` |
| `fluent-spinner` | Loading state | `@fluentui/web-components` |
| `fluent-switch` | Filter toggles | `@fluentui/web-components` |

### Loading Strategy (CDN Injection)

Since this is injected at runtime via Playwright, we'll use a hybrid approach:

```javascript
// Option 1: Custom elements (no external deps, Fluent-inspired)
// Implement Fluent 2 visual patterns without the library
// Benefits: No CDN dependency, smaller payload, faster injection

// Option 2: Fluent 2 via CDN (if available)
// const script = document.createElement('script');
// script.src = 'https://unpkg.com/@fluentui/web-components';
// document.head.appendChild(script);
```

**Recommendation**: Option 1 - Custom implementation following Fluent 2 patterns. This avoids CDN dependencies and keeps the injection fast and reliable.

### Component Hierarchy

```
AnnotationToolbar (Shadow Host)
├── ToolbarContainer
│   ├── DragHandle
│   ├── StatusSection
│   │   ├── IssueCount
│   │   └── SeverityBadges
│   ├── FilterSection
│   │   ├── VisibilityToggle
│   │   └── CategoryFilters (dropdown)
│   ├── ActionSection
│   │   ├── ScreenshotButton
│   │   └── OrientationToggle
│   └── DismissButton
└── AnnotationLayer (separate, overlays page)
    ├── IssueBadge (numbered)
    ├── IssueBadge
    └── ...
```

---

## Annotation System Design

### Badge Design

```
┌─────────────────────────────────────────────────────────────────────────┐
│                                                                         │
│  NUMBERED BADGE (attached to problem element)                           │
│                                                                         │
│       ┌─────┐                                                           │
│       │  1  │  ← Numbered circle (severity-colored border)              │
│       └──┬──┘                                                           │
│          │                                                              │
│          ▼                                                              │
│    ┌──────────────────────────────────────────┐                        │
│    │  Element with issue                       │                        │
│    │  (highlighted with subtle overlay)        │                        │
│    └──────────────────────────────────────────┘                        │
│                                                                         │
│  ON HOVER: Native popover appears                                       │
│                                                                         │
│       ┌─────┐                                                           │
│       │  1  │                                                           │
│       └──┬──┘                                                           │
│          │    ┌─────────────────────────────────────────┐               │
│          └────│ Contrast ratio 3.2:1                    │               │
│               │ (minimum 4.5:1 required)                │               │
│               │                                         │               │
│               │ Pillar: Quality Craft                   │               │
│               │ Severity: Major                         │               │
│               │ Selector: main > p.subtitle             │               │
│               └─────────────────────────────────────────┘               │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Badge Positioning Algorithm

```javascript
function positionBadge(element, badgeNumber) {
  const rect = element.getBoundingClientRect();
  
  // Default: top-right corner of element
  let position = {
    top: rect.top - 12,      // Slightly above element
    left: rect.right - 12,   // Slight overlap with right edge
  };
  
  // Boundary detection: keep badge on screen
  if (position.top < 8) position.top = 8;
  if (position.left > window.innerWidth - 32) {
    position.left = rect.left - 20;  // Move to left side
  }
  
  return position;
}
```

### Popover Content Structure

Using native `[popover]` API (no library needed):

```html
<div id="issue-1-popover" popover>
  <div class="issue-header">
    <span class="issue-title">Contrast ratio 3.2:1</span>
    <span class="severity-badge major">Major</span>
  </div>
  <div class="issue-body">
    <p class="description">Minimum 4.5:1 required for WCAG AA compliance</p>
    <dl class="meta">
      <dt>Pillar</dt><dd>Quality Craft</dd>
      <dt>Check</dt><dd>color-contrast</dd>
      <dt>Selector</dt><dd><code>main > p.subtitle</code></dd>
    </dl>
    <div class="recommendation">
      <strong>Fix:</strong> Darken text to #595959 or darker
    </div>
  </div>
</div>
```

### Highlight Overlay

When hovering a badge, highlight the affected element:

```css
.annotation-highlight {
  position: absolute;
  pointer-events: none;
  background: rgba(248, 81, 73, 0.1);  /* Error color at 10% */
  border: 2px solid var(--severity-error);
  border-radius: 4px;
  transition: opacity 150ms ease-out;
}
```

---

## Integration Architecture

### Relationship with `design-review`

```
┌─────────────────────────────────────────────────────────────────────────┐
│                                                                         │
│  DESIGN REVIEW WORKFLOW                                                  │
│                                                                         │
│  ┌──────────────┐      ┌──────────────┐      ┌──────────────┐          │
│  │              │      │              │      │              │          │
│  │ design-review│─────▶│ canvas-edit  │─────▶│    User      │          │
│  │  (analyzer)  │      │ (visualizer) │      │  (viewer)    │          │
│  │              │      │              │      │              │          │
│  └──────────────┘      └──────────────┘      └──────────────┘          │
│         │                     │                     │                   │
│         │                     │                     │                   │
│    Runs checks           Shows live            Views issues             │
│    Finds issues         annotations             Takes screenshots       │
│    Emits events         on page                                         │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Event Flow

```javascript
// design-review emits issues
bus.emit('review.issue_found', 'design-review', {
  id: 1,
  checkId: 'color-contrast',
  severity: 'major',
  pillar: 'Quality Craft',
  element: '.subtitle-text',
  cssSelector: 'main > section.hero > p.subtitle-text',
  description: 'Contrast ratio 3.2:1 (minimum 4.5:1 required)',
  recommendation: 'Darken text to #595959 or darker',
  bounds: { top: 200, left: 100, width: 400, height: 24 }
});

// canvas-edit subscribes and visualizes
bus.subscribe('review.issue_found', (event) => {
  addAnnotation(event.payload);
});

// design-review signals completion
bus.emit('review.completed', 'design-review', {
  totalIssues: 3,
  byCategory: { blocking: 1, major: 2, minor: 0 }
});

// canvas-edit updates status display
bus.subscribe('review.completed', (event) => {
  updateToolbarStatus(event.payload);
});
```

### Relationship with `agent-eyes`

```javascript
// canvas-edit hides during screenshots
bus.subscribe('capture_mode.changed', (event) => {
  if (event.payload.enabled) {
    hideToolbar();  // Only hide toolbar, keep annotations
  } else {
    showToolbar();
  }
});

// For annotated screenshots, annotations stay visible
// The Shadow DOM host is hidden, but the annotation overlay persists
```

### Integration Points Summary

| Skill | Receives From canvas-edit | Sends To canvas-edit |
|-------|---------------------------|----------------------|
| `design-review` | `annotation.clicked`, `screenshot.captured` | `review.issue_found`, `review.completed`, `review.started` |
| `agent-eyes` | (none) | `capture_mode.changed` |

---

## Screenshot Workflow

### Capture Process

```javascript
async function captureAnnotatedScreenshot() {
  // 1. Hide toolbar (keep annotations)
  toolbarHost.style.display = 'none';
  
  // 2. Capture full page via Playwright
  const screenshot = await page.screenshot({ 
    fullPage: true,
    type: 'png'
  });
  
  // 3. Generate filename
  const timestamp = new Date().toISOString()
    .replace(/[:.]/g, '-')
    .slice(0, 19);
  const issueCount = annotations.length;
  const filename = `${timestamp}_${issueCount}-issues.png`;
  
  // 4. Save to .canvas/
  const outputPath = `.canvas/screenshots/${filename}`;
  await fs.writeFile(outputPath, screenshot);
  
  // 5. Show toolbar again
  toolbarHost.style.display = 'block';
  
  // 6. Emit event
  bus.emit('screenshot.captured', 'canvas-edit', {
    path: outputPath,
    issueCount: issueCount,
    timestamp: timestamp
  });
  
  return outputPath;
}
```

### File Naming Convention

```
.canvas/screenshots/
├── 2026-01-23T15-18-40_3-issues.png
├── 2026-01-23T15-22-15_0-issues.png
└── 2026-01-23T15-25-30_1-issues.png
```

Format: `{YYYY-MM-DDTHH-MM-SS}_{N}-issues.png`

---

## Animation & Motion Specification

### Fluent 2 Motion Tokens

Following Fluent 2 motion guidelines:

```css
/* Durations */
--duration-faster: 100ms;
--duration-fast: 150ms;
--duration-normal: 250ms;
--duration-slow: 300ms;

/* Easing */
--ease-out: cubic-bezier(0.33, 0, 0.1, 1);      /* Decelerate */
--ease-in: cubic-bezier(0.9, 0, 0.67, 1);       /* Accelerate */
--ease-in-out: cubic-bezier(0.85, 0, 0.15, 1);  /* Symmetric */
```

### Orientation Toggle Animation

```css
/* Horizontal → Vertical transition */
@keyframes horizontalToVertical {
  0% {
    width: 400px;
    height: 48px;
    flex-direction: row;
  }
  50% {
    width: 200px;
    height: 100px;
  }
  100% {
    width: 64px;
    height: 280px;
    flex-direction: column;
  }
}

.toolbar {
  transition: 
    width var(--duration-normal) var(--ease-out),
    height var(--duration-normal) var(--ease-out),
    top var(--duration-fast) var(--ease-out),
    left var(--duration-fast) var(--ease-out);
}

/* Boundary correction (prevents off-screen) */
.toolbar.correcting {
  transition: 
    top var(--duration-fast) var(--ease-out),
    left var(--duration-fast) var(--ease-out);
}
```

### Badge Animations

```css
/* Badge appearance */
@keyframes badgeAppear {
  0% {
    opacity: 0;
    transform: scale(0.5);
  }
  100% {
    opacity: 1;
    transform: scale(1);
  }
}

.issue-badge {
  animation: badgeAppear var(--duration-fast) var(--ease-out);
}

/* Badge pulse on new issue */
@keyframes badgePulse {
  0%, 100% { transform: scale(1); }
  50% { transform: scale(1.15); }
}

.issue-badge.new {
  animation: badgePulse var(--duration-slow) var(--ease-in-out) 2;
}
```

### Popover Animation

```css
/* Native popover with custom animation */
.issue-popover {
  opacity: 0;
  transform: translateY(-8px);
  transition: 
    opacity var(--duration-fast) var(--ease-out),
    transform var(--duration-fast) var(--ease-out);
}

.issue-popover:popover-open {
  opacity: 1;
  transform: translateY(0);
}
```

---

## Boundary Detection & Edge Handling

### Position Correction Algorithm

```javascript
function correctToolbarPosition() {
  const toolbar = shadow.querySelector('.toolbar');
  const rect = toolbar.getBoundingClientRect();
  const viewport = {
    width: window.innerWidth,
    height: window.innerHeight
  };
  
  const margin = 8; // Minimum distance from edges
  let corrections = { top: null, left: null };
  
  // Horizontal overflow
  if (rect.right > viewport.width - margin) {
    corrections.left = viewport.width - rect.width - margin;
  }
  if (rect.left < margin) {
    corrections.left = margin;
  }
  
  // Vertical overflow
  if (rect.bottom > viewport.height - margin) {
    corrections.top = viewport.height - rect.height - margin;
  }
  if (rect.top < margin) {
    corrections.top = margin;
  }
  
  // Apply corrections with animation
  if (corrections.left !== null) {
    toolbar.style.left = corrections.left + 'px';
    toolbar.style.right = 'auto';
  }
  if (corrections.top !== null) {
    toolbar.style.top = corrections.top + 'px';
  }
}

// Call on:
// - Orientation toggle
// - Window resize
// - After drag end
```

### Pre-toggle Check

```javascript
function canToggleOrientation(toVertical) {
  const toolbar = shadow.querySelector('.toolbar');
  const rect = toolbar.getBoundingClientRect();
  
  const newDimensions = toVertical 
    ? { width: 64, height: 280 }
    : { width: 400, height: 48 };
  
  const wouldOverflow = {
    right: rect.left + newDimensions.width > window.innerWidth - 8,
    bottom: rect.top + newDimensions.height > window.innerHeight - 8
  };
  
  // If would overflow, pre-correct position before animating
  if (wouldOverflow.right || wouldOverflow.bottom) {
    const safePosX = Math.min(
      rect.left,
      window.innerWidth - newDimensions.width - 8
    );
    const safePosY = Math.min(
      rect.top,
      window.innerHeight - newDimensions.height - 8
    );
    
    // First move to safe position, then toggle
    toolbar.classList.add('correcting');
    toolbar.style.left = safePosX + 'px';
    toolbar.style.top = safePosY + 'px';
    
    // Then animate orientation after move completes
    setTimeout(() => {
      toolbar.classList.remove('correcting');
      performOrientationToggle(toVertical);
    }, 150);
    
    return false; // Indicate delayed toggle
  }
  
  return true; // Can toggle immediately
}
```

---

## Accessibility Considerations

### Keyboard Navigation

| Key | Action |
|-----|--------|
| `Tab` | Move focus between toolbar controls |
| `Escape` | Close any open popover |
| `Enter/Space` | Activate focused control |
| `Arrow keys` | Navigate between badges (when focused) |
| `1-9` | Jump to badge by number |

### ARIA Attributes

```html
<!-- Toolbar -->
<div role="toolbar" aria-label="Design Review Annotations">
  <button aria-label="Drag to reposition" aria-grabbed="false">...</button>
  <span role="status" aria-live="polite">3 issues found</span>
  <button aria-label="Toggle issue visibility" aria-pressed="true">...</button>
  <button aria-label="Capture screenshot">...</button>
  <button aria-label="Toggle orientation: currently horizontal">...</button>
</div>

<!-- Badges -->
<button 
  class="issue-badge" 
  aria-label="Issue 1: Contrast ratio issue"
  popovertarget="issue-1-popover"
  aria-describedby="issue-1-popover"
>1</button>

<!-- Popovers -->
<div id="issue-1-popover" popover role="dialog" aria-label="Issue details">
  ...
</div>
```

### Focus Management

- Trap focus within popover when open
- Return focus to trigger badge when popover closes
- Announce new issues via `aria-live` region

---

## Implementation Phases/Roadmap

### Phase 1: Core Toolbar (Week 1)

**Deliverables:**
- [ ] Shadow DOM host setup
- [ ] Basic toolbar layout (horizontal only)
- [ ] Drag functionality
- [ ] Issue count display
- [ ] Severity badges
- [ ] Visibility toggle (show/hide all annotations)
- [ ] Dark grey Fluent 2-inspired styling

**Files to create/modify:**
- `.claude/skills/canvas-edit/scripts/canvas_edit.py` (complete rewrite)
- `.claude/skills/canvas-edit/scripts/annotation_toolbar.js` (new)

### Phase 2: Annotation System (Week 1-2)

**Deliverables:**
- [ ] Numbered badge component
- [ ] Badge positioning algorithm
- [ ] Element highlight on hover
- [ ] Native popover integration
- [ ] Popover content template
- [ ] Badge appearance animation

**Files:**
- `.claude/skills/canvas-edit/scripts/annotation_layer.js` (new)

### Phase 3: Integration (Week 2)

**Deliverables:**
- [ ] Canvas bus event subscriptions
- [ ] design-review integration (`review.issue_found`, `review.completed`)
- [ ] agent-eyes integration (`capture_mode.changed`)
- [ ] Success state messaging
- [ ] Loading/scanning state

**Files:**
- Update `.claude/skills/design-review/scripts/design_review.py`
- Update `.claude/skills/shared/canvas_bus.py`

### Phase 4: Screenshot & Orientation (Week 2-3)

**Deliverables:**
- [ ] Screenshot capture button
- [ ] Save to `.canvas/` with naming convention
- [ ] Orientation toggle (horizontal ↔ vertical)
- [ ] Ease-out animation
- [ ] Boundary detection & correction

**Files:**
- Update annotation_toolbar.js

### Phase 5: Filtering & Polish (Week 3)

**Deliverables:**
- [ ] Category filter dropdown
- [ ] Filter state persistence
- [ ] Keyboard navigation
- [ ] ARIA attributes
- [ ] Edge case handling
- [ ] Performance optimization

**Files:**
- Final polish across all new files

### Phase 6: Documentation & Testing (Week 3-4)

**Deliverables:**
- [ ] Update SKILL.md
- [ ] Update README.md
- [ ] Integration tests
- [ ] Manual QA checklist

---

## File Structure for Implementation

```
.claude/skills/canvas-edit/
├── SKILL.md                           # Updated documentation
├── scripts/
│   ├── canvas_edit.py                 # Main entry point (rewritten)
│   ├── annotation_toolbar.js          # Toolbar component (new)
│   ├── annotation_layer.js            # Badge/overlay system (new)
│   └── styles/
│       ├── toolbar.css                # Toolbar styles (new)
│       └── annotations.css            # Badge/popover styles (new)
└── tests/
    └── test_canvas_edit.py            # Integration tests (new)
```

### Key Code Patterns

**Python Entry Point:**
```python
# canvas_edit.py

def inject_annotation_toolbar(page, issues):
    """Inject toolbar and annotations into the page."""
    # Inject canvas bus first
    page.evaluate(CANVAS_BUS_JS)
    
    # Inject toolbar
    page.evaluate(TOOLBAR_JS)
    
    # Inject annotations for each issue
    for issue in issues:
        page.evaluate(f"window.__annotationLayer.addIssue({json.dumps(issue)})")
```

**JavaScript Toolbar:**
```javascript
// annotation_toolbar.js

(() => {
  if (window.__annotationToolbarActive) return;
  window.__annotationToolbarActive = true;
  
  const host = document.createElement('div');
  host.id = '__annotation_toolbar_host';
  const shadow = host.attachShadow({ mode: 'closed' });
  
  // Inject styles
  shadow.innerHTML = `
    <style>${TOOLBAR_STYLES}</style>
    <div class="toolbar horizontal" role="toolbar">
      ...
    </div>
  `;
  
  document.body.appendChild(host);
  
  // Event handling...
})();
```

---

## Migration Notes

### Breaking Changes

| Old Functionality | New Behavior |
|-------------------|--------------|
| Text editing via textarea | **Removed** - this is now a viewing tool |
| Style sliders (fontSize, etc.) | **Removed** - agents communicate findings, not edits |
| "Save All to Code" button | **Replaced** with screenshot capture |
| contentEditable toggle | **Removed** |

### Preserved Functionality

- Shadow DOM encapsulation (invisible to agent-eyes)
- Drag to reposition
- Canvas bus integration
- Event emission for agent communication

### canvas-apply Impact

The `canvas-apply` skill will need updates since `canvas-edit` no longer produces style/text changes. Consider:
- `canvas-apply` may become deprecated or repurposed
- Or: Create new integration where `design-review` findings can generate fix suggestions

---

## Open Questions

1. **Annotation persistence**: Should annotations survive soft navigation (SPA route changes)?
2. **Multi-page reviews**: If reviewing multiple pages, should toolbar state carry over?
3. **Issue grouping**: Should multiple issues on the same element show as one badge with count?
4. **Zoom handling**: How should badges behave when user zooms the page?

---

## Success Criteria

- [ ] Toolbar renders in Shadow DOM, invisible to agent-eyes screenshots
- [ ] Annotations appear in real-time as design-review finds issues
- [ ] Badges are numbered and clickable with native popovers
- [ ] Screenshot captures annotated page (minus toolbar) to `.canvas/`
- [ ] Orientation toggle animates smoothly with boundary correction
- [ ] Filter toggles show/hide annotations by category
- [ ] Success state displays friendly message when no issues found
- [ ] All interactions follow Fluent 2 motion patterns
- [ ] Mono-tone dark grey palette throughout (except severity colors)
