---
name: Default Design Review
version: "1.0"
extends: null
---

# Default Design Review Spec

Base design quality standards for any web application. Built on four pillars.

---

## Frictionless Insight to Action

Design for momentum. Users complete their task efficiently.

### Checks

#### max-interactions
- **Severity**: major
- **Description**: Core task completable in 3 or fewer interactions
- **How to check**: Count clicks/taps from entry to task completion

#### single-primary-action
- **Severity**: major
- **Description**: Only 1-2 primary actions visible per view
- **How to check**: Count elements with primary button styling or prominent CTA treatment

#### clear-navigation
- **Severity**: major
- **Description**: Clear entry and exit points for every experience
- **How to check**: Verify back/cancel always available, breadcrumbs present for deep flows

#### loading-feedback
- **Severity**: minor
- **Description**: User receives feedback during async operations
- **How to check**: Verify loading indicators appear for operations over 100ms

---

## Progressive Clarity

Keep the default path simple. Reveal depth only when needed.

### Checks

#### smart-defaults
- **Severity**: minor
- **Description**: No unnecessary upfront configuration required
- **How to check**: User can proceed immediately without filling required fields

#### feature-explanation
- **Severity**: minor
- **Description**: Feature purpose explained on first encounter
- **How to check**: New features have introductory text or teaching callouts

#### progressive-disclosure
- **Severity**: minor
- **Description**: Advanced options hidden by default
- **How to check**: Secondary settings use expandable sections or advanced mode

#### contextual-help
- **Severity**: minor
- **Description**: Help available where users need it
- **How to check**: Complex fields have tooltips or inline help text

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
- **How to check**: Verify contrast ratio for all text elements (WCAG AA)

#### keyboard-navigation
- **Severity**: major
- **Description**: All interactive elements accessible via keyboard
- **How to check**: Tab through page, verify focus indicators visible and logical order

#### focus-indicators
- **Severity**: major
- **Description**: Focused elements have visible focus ring
- **How to check**: Tab through interactive elements, verify focus state is visible

#### touch-targets
- **Severity**: major
- **Description**: Touch targets are at least 44x44 pixels
- **Config**:
  - minimum_size: 44
- **How to check**: Measure interactive element dimensions on mobile viewport

#### text-scaling
- **Severity**: minor
- **Description**: Text remains readable when scaled to 200%
- **How to check**: Apply browser text zoom, verify no content truncation or overlap

#### motion-respect
- **Severity**: minor
- **Description**: Animations respect prefers-reduced-motion
- **How to check**: Enable reduced motion preference, verify animations are disabled

---

## Trustworthy Building

Equip users to build with confidence.

### Checks

#### ai-disclaimer
- **Severity**: blocking
- **Description**: AI-generated content includes required disclaimer
- **How to check**: Look for AI output areas, verify disclaimer present

#### error-messages
- **Severity**: major
- **Description**: Error messages are helpful and actionable
- **How to check**: Trigger errors, verify messages explain what went wrong and how to fix

#### data-transparency
- **Severity**: major
- **Description**: Users understand what data is collected and why
- **How to check**: Check for privacy notices, data collection explanations

#### secure-defaults
- **Severity**: major
- **Description**: Least privilege access and safe configurations by default
- **How to check**: Check default permission states, sharing settings

#### destructive-confirmation
- **Severity**: major
- **Description**: Destructive actions require confirmation
- **How to check**: Attempt delete/remove actions, verify confirmation dialog appears

#### undo-support
- **Severity**: minor
- **Description**: Reversible actions support undo
- **How to check**: Perform edit actions, verify undo option available
