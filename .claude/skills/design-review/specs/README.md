# Custom Design Specs

Add your project-specific design specs here.

## Project-Level Spec (Recommended)

Create a `DESIGN-SPEC.md` in your project root. It will be automatically used instead of the default spec.

**Discovery locations (in priority order):**
1. `./DESIGN-SPEC.md`
2. `./design-spec.md`
3. `./.claude/DESIGN-SPEC.md`

## Creating a Custom Spec

Two frontmatter formats are supported:

### Spec Format (with inheritance)

```markdown
---
name: My Project Design Spec
version: "1.0"
extends: default.md
---
```

### Skill Format (simpler)

```markdown
---
name: my-project-design-review
description: Review UI for my project against our standards.
---
```

# My Project Design Spec

Custom rules extending the default spec.

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
- **How to check**: Extract colors from elements, compare against approved list

#### typography
- **Severity**: minor
- **Description**: Uses approved font families
- **Approved fonts**:
  - Segoe UI
  - Segoe UI Variable
- **How to check**: Check computed font-family on text elements
```

## Spec Format Reference

### Frontmatter (Required)

```yaml
---
name: Human-readable spec name
version: "1.0"
extends: default.md  # Optional: inherit from another spec
---
```

### Pillars (H2 headers)

Group related checks under design pillars:

```markdown
## Pillar Name

Description of what this pillar covers.

### Checks
```

### Checks (H4 headers under ### Checks)

```markdown
#### check-id
- **Severity**: blocking | major | minor
- **Description**: What this check validates
- **Config**:
  - key: value
- **How to check**: Manual verification steps
```

### Severity Levels

| Level | Meaning |
|-------|---------|
| `blocking` | Must fix before shipping |
| `major` | Should fix, significant impact |
| `minor` | Nice to fix, polish issue |

### Overrides Section

Override inherited check settings:

```markdown
## Overrides

### check-id-to-override
- **Severity**: major  # Change severity
- **Config**:
  - minimum_ratio: 7.0  # Change config value
```
