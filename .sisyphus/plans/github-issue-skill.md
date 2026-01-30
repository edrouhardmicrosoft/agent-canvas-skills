# GitHub Issue Creation Skill for Agent Canvas

## TL;DR

> **Quick Summary**: Add a "Create Issue" button to the agent-canvas picker overlay that captures selected elements, screenshots, and page context into a GitHub issue. Uses `gh` CLI when available, falls back to web URL.
> 
> **Deliverables**:
> - New `canvas-issue` skill with SKILL.md and Python backend
> - JavaScript overlay components (button, modals, confirmation)
> - `gh` CLI integration with gist-based screenshot uploads
> - Web fallback for users without `gh` CLI
> - Config persistence in `.canvas/config.json`
> 
> **Estimated Effort**: Medium (3-5 days)
> **Parallel Execution**: YES - 3 waves
> **Critical Path**: Task 1 → Task 3 → Task 5 → Task 7 → Task 8

---

## Context

### Original Request
User wants to add GitHub issue creation capability to agent-canvas interactive flow. Should be a generic approach where the user connects their own repo/auth.

### Interview Summary
**Key Discussions**:
- Trigger: Button in picker overlay (top-right, near counter badge)
- Modal flow: First-time repo prompt → Issue creation modal (editable title, optional description)
- Auth strategy: Hybrid - `gh` CLI if available, web fallback to github.com/issues/new URL
- Screenshots: Upload via `gh gist create`, include gist image URL in issue body
- Multi-element: All selected elements included in single issue
- Failure handling: Show error + automatically open web fallback

**Research Findings**:
- `agent_canvas.py` embeds `PICKER_OVERLAY_JS` which creates the picker UI
- `canvas_bus.py` provides shared event infrastructure (emit/subscribe/drain)
- Existing UI patterns in `.claude/skills/canvas-edit/scripts/`:
  - `annotation_toolbar.js` - Uses closed Shadow DOM for style isolation
  - `annotation_layer.js` - Uses native Popover API (`popover="auto"`)
- Tests use Playwright-driven scripts (NOT pytest) - see `test_canvas_edit.py`
- `gh issue create` does NOT support image uploads - must use gist workaround

### Metis Review
**Identified Gaps** (addressed):
- Screenshot upload limitation: Using gist-based upload with `gh gist create`, then `gh api /gists/<id>` to get raw URLs
- Multi-element handling: All elements in single issue
- Failure recovery: Show error + auto-open web fallback
- Config namespace: Using `{ "github": { "repo": "..." } }` to avoid conflicts
- Git hygiene: Add `.canvas/config.json` to `.gitignore`

---

## Work Objectives

### Core Objective
Enable users to create GitHub issues directly from agent-canvas interactive sessions, capturing selected elements, screenshots, and page context automatically.

### Concrete Deliverables
- `.claude/skills/canvas-issue/SKILL.md` - Skill definition
- `.claude/skills/canvas-issue/scripts/canvas_issue.py` - Python backend (CLI with subcommands)
- `.claude/skills/canvas-issue/scripts/issue_overlay.js` - JavaScript overlay components
- `.claude/skills/canvas-issue/tests/test_canvas_issue.py` - Playwright-driven test script
- Integration with `agent_canvas.py` via `--with-issue` flag
- `.gitignore` update for `.canvas/config.json`

### Definition of Done
- [ ] User can click "Create Issue" button in picker overlay
- [ ] First-time repo configuration prompt works
- [ ] Issue creation modal accepts title and description
- [ ] `gh` CLI path creates issue with gist-uploaded screenshots
- [ ] Web fallback opens pre-filled issue URL
- [ ] Confirmation overlay shows success/failure + issue URL
- [ ] Config persists in `.canvas/config.json`
- [ ] Playwright tests pass

### Must Have
- "Create Issue" button in picker overlay (near counter badge)
- First-time repo configuration modal
- Issue creation modal (editable title, optional description)
- `gh` CLI detection and auth check
- Gist upload for screenshots (with raw URL derivation)
- Web fallback URL generation
- Success/failure visual confirmation
- Config persistence in `.canvas/config.json`

### Must NOT Have (Guardrails)
- ❌ Issue templates or label selection
- ❌ Issue search or browsing
- ❌ Multiple GitHub accounts support
- ❌ GitLab/Bitbucket/other providers
- ❌ Assignee or milestone selection
- ❌ Image editing before upload
- ❌ Issue body preview/editing beyond simple text
- ❌ Notification or webhook system
- ❌ Custom OAuth flow (use existing `gh auth`)
- ❌ Over-abstracted "issue provider" interface

---

## Verification Strategy (MANDATORY)

### Test Decision
- **Infrastructure pattern**: Playwright-driven test scripts (NOT pytest)
- **User wants tests**: TDD for backend + Playwright for UI
- **Framework**: Playwright sync API (matching `test_canvas_edit.py` pattern)

### Test Script Pattern (from existing codebase)

Tests follow the pattern in `.claude/skills/canvas-edit/tests/test_canvas_edit.py`:
- Import `playwright.sync_api`
- Create `TestResults` class for tracking
- Use `page.evaluate()` for JS assertions
- Run via `python tests/test_canvas_issue.py`

### Manual Verification for End-to-End

Full flow verified via Playwright browser interaction:
1. Launch agent-canvas with `--with-issue` flag
2. Verify button appears
3. Click button, verify modal opens
4. Complete form, verify issue creation

---

## Data Sources (CRITICAL)

### During Live Picker Session

When the "Create Issue" button is clicked, the issue handler reads from:

1. **In-memory `all_selections` list** - The current list of selection events accumulated during the session
2. **`session_dir` paths** - Screenshots that have been saved during the session (e.g., `before.png`, `selection_001.png`)
3. **`.canvas/config.json`** - Configured GitHub repo (via `get_github_repo()`)

**`session.json` is NOT read during issue creation** - it's a post-session artifact written when the browser closes. The issue handler works with live in-memory data.

### Selection Event Deduplication Rule

The picker emits `selection.changed` events AND calls `bus.setSelection()` which may emit additional events.

**Rule**: Only process `selection.changed` events with `source === "picker"`. Ignore other sources to avoid double-counting.

```python
# In event polling loop
if event.get("type") == "selection.changed" and event.get("source") == "picker":
    # This is a user-initiated selection - process it
    all_selections.append(event)
```

---

## Inputs Contract (CRITICAL)

### Session Data Structure

The issue generation reads from `session.json` (schema v1.1). Here is the **ACTUAL** structure from `write_session_artifact()`:

```typescript
// From session.json - ACTUAL schema from agent_canvas.py
interface SessionData {
  schemaVersion: "1.1";
  sessionId: string;
  url: string;
  startTime: string;       // ISO timestamp (NOT "timestamp")
  endTime: string;         // ISO timestamp
  features: {
    picker: boolean;
    eyes: boolean;
    edit: boolean;
    // issue: boolean will be added
  };
  beforeScreenshotPath: string | null;  // e.g., ".canvas/sessions/<id>/before.png"
  events: {
    selections: SelectionEvent[];  // NOT top-level, nested under events
    edits: EditEvent[];
  };
  summary: {
    totalSelections: number;
    totalEdits: number;
    hasSaveRequest: boolean;
  };
}

// Selection events (from canvas bus)
interface SelectionEvent {
  type: "selection.changed";
  source: "picker";
  timestamp: string;
  seq: number;
  payload: {
    index: number;
    element: ElementInfo;    // The actual element data is in payload.element
  };
  screenshot?: {             // Only if screenshot captured
    path: string;
    size: number;
  };
}

// ACTUAL ElementInfo from canvas_bus.py getElementInfo() - VERIFIED
interface ElementInfo {
  tag: string;              // NOT tagName - lowercase tag name
  id: string | null;
  className: string | null; // NOT classList - raw className string
  selector: string;         // CSS selector
  selectorConfidence: "high" | "medium" | "low";  // STRING, not number
  selectorAlternatives: Array<{ selector: string; note?: string }>;  // Objects, not strings
  text: string | null;      // NOT textContent - truncated to 200 chars
  boundingBox: { x, y, width, height };
  attributes: {
    role: string | null;
    ariaLabel: string | null;
    dataTestid: string | null;
    dataCy: string | null;
    href: string | null;
    src: string | null;
  };
  styles: {                 // NOT computedStyles
    display: string;
    position: string;
    backgroundColor: string;
    color: string;
    fontSize: string;
    fontWeight: string;
    padding: string;
    margin: string;
    borderRadius: string;
  };
}
```

### Extracting Data for Issue Body

```python
# Correct way to extract selection data (using ACTUAL field names):
def extract_selections(session_data: dict) -> list:
    """Extract element info from session.json for issue body."""
    selections = []
    for event in session_data.get("events", {}).get("selections", []):
        element = event.get("payload", {}).get("element", {})
        selections.append({
            "selector": element.get("selector", "unknown"),
            "tag": element.get("tag", ""),           # NOT tagName
            "text": (element.get("text") or "")[:100],  # NOT textContent
            "screenshot_path": event.get("screenshot", {}).get("path"),
        })
    return selections
```

### Schema Version Handling

Use **schemaVersion 1.1** sessions (produced by current `agent_canvas.py`). For older artifacts:
- Check `schemaVersion` field first
- If < 1.1, log warning and skip (don't attempt migration)
- The plan targets current implementation only

### What Goes in the Issue Body

| Section | Source | Required? |
|---------|--------|-----------|
| **## Description** | User-provided in modal | Optional |
| **## Page Info** | `session.url` | Always |
| **## Selected Elements** | `session.events.selections[].payload.element` | Always (may be empty) |
| **## Screenshots** | Gist URLs from uploaded images | Only if images exist |

### Accessibility Issues: OUT OF SCOPE

The `eyes.accessibility` data (if `--with-eyes` was used) is **NOT included** in issue body for v1. Rationale:
- Eyes a11y output format is complex and may change
- Would require explicit a11y-capture step and storage format definition
- Can be added in a future version with proper schema

If user runs with `--with-eyes`, the accessibility data remains in session artifacts but is not surfaced in the GitHub issue.

---

## Screenshot Handling Specification (CRITICAL)

### Actual Screenshot Filenames (from agent_canvas.py)

| Image Type | Actual Filename | Location |
|------------|-----------------|----------|
| Before screenshot | `before.png` | `.canvas/sessions/<id>/before.png` |
| Selection screenshots | `selection_001.png`, `selection_002.png`, ... | `.canvas/sessions/<id>/selection_NNN.png` |

### Which Images Are Uploaded

| Image Type | Filename Pattern | Included? |
|------------|------------------|-----------|
| Before screenshot | `before.png` | YES (if exists) - this is the main page screenshot |
| Selection screenshots | `selection_*.png` | YES (all that exist) |
| Annotated/diff | `annotated.png`, `diff.png` | NO (generated artifacts from other tools) |

### Upload Limits (Caps)

| Limit | Value | Behavior When Exceeded |
|-------|-------|----------------------|
| Max images per issue | 5 | Upload first 5 only, note "X more images not uploaded" |
| Max file size per image | 10MB | Skip image, note "Image too large" |
| Max total upload | 25MB | Stop uploading, note remaining count |

### Upload Method

**One gist containing multiple files** (NOT one gist per file).

Task 5's `upload-gist` CLI supports multiple files:
```bash
python canvas_issue.py upload-gist before.png selection_001.png selection_002.png
# Returns JSON: {"gist_url": "...", "files": {"before.png": {"raw_url": "..."}, "selection_001.png": {"raw_url": "..."}}}
```

Implementation handles the multi-file case:
```bash
gh gist create --public before.png selection_001.png selection_002.png
# Returns single gist URL
```

Then retrieve raw URLs for each file via `gh api /gists/<id>`.

### Issue Body Screenshot Section Format

```markdown
## Screenshots

| # | Description | Preview |
|---|-------------|---------|
| 1 | Page screenshot | ![before](https://gist.githubusercontent.com/.../before.png) |
| 2 | Selection 1: `.btn-primary` | ![selection_001](https://gist.githubusercontent.com/.../selection_001.png) |
| 3 | Selection 2: `#header` | ![selection_002](https://gist.githubusercontent.com/.../selection_002.png) |

> 2 additional screenshots not uploaded (limit: 5)
```

### Missing Image Handling

- If `before.png` doesn't exist → Skip "Page screenshot" row
- If `selection_NNN.png` doesn't exist for a selection → Omit from table
- If NO images exist at all → Omit entire "## Screenshots" section

### `gh issue create` Command Contract

When creating an issue via `gh` CLI:

```bash
gh issue create --repo "owner/repo" --title "Issue Title" --body "Issue body markdown..."
# Returns: URL of created issue on success
# Exit 1 on failure (auth, permission, network, etc.)
```

**Required flags**:
- `--repo owner/repo` or `-R owner/repo`: Target repository (from `.canvas/config.json`)
- `--title "..."`: Issue title (from modal)
- `--body "..."`: Issue body (generated Markdown)

**Success determination**:
- Exit code 0 AND stdout contains GitHub issue URL (e.g., `https://github.com/owner/repo/issues/123`)

### Web Fallback Semantics (CRITICAL)

The web fallback is **NOT** equivalent to issue creation. It opens a pre-filled form for manual submission.

| Scenario | Event Emitted | Confirmation UI Message |
|----------|---------------|------------------------|
| `gh issue create` succeeds | `issue.created { url, method: "gh" }` | "✓ Issue created! [View Issue]" |
| `gh issue create` fails | `issue.failed { error, fallbackUrl }` | "⚠ Could not create issue. Opened GitHub for manual creation." |
| `gh` not available | `issue.failed { error, fallbackUrl }` | "⚠ gh CLI not found. Opened GitHub for manual creation." |

**The `issue.created` event with `method: "web"` is NOT used** because the web fallback doesn't create an issue—it opens a form. The user must manually submit.

---

## Web Fallback Flow (CRITICAL)

### Requirement: Never Break the Picker

The fallback MUST open GitHub "new issue" in a **new tab/window**, NOT navigate the page being picked.

### Popup/User-Gesture Plan

Browser popup blockers require user gesture. The flow:

```javascript
// In issue_overlay.js - when "Create" button clicked:

// 1. IMMEDIATELY open blank window (within user gesture)
const win = window.open('about:blank', '_blank');

// 2. Emit event to Python
window.__canvasBus.emit('issue.create_requested', 'issue-overlay', {
  title: titleInput.value,
  description: descTextarea.value,
  _fallbackWindow: true  // Signal that window is ready
});

// 3. Python builds URL, emits back
// (in response to issue.failed with fallbackUrl)
bus.subscribe('issue.failed', (e) => {
  if (win && e.fallbackUrl) {
    win.location = e.fallbackUrl;
  }
});
```

### URL Length Policy

GitHub "new issue" URL format: `https://github.com/OWNER/REPO/issues/new?title=...&body=...`

| Constraint | Value |
|------------|-------|
| Safe URL length | 2000 chars (conservative for all browsers) |
| Max title in URL | 100 chars |
| Max body in URL | 1800 chars (2000 - title - overhead) |

### Truncation Strategy (in order)

1. **Screenshots section** - Remove entirely (can't inline images in URL anyway)
2. **Element details** - Truncate to selector + first 50 chars of text
3. **Elements list** - Keep first 3 elements only
4. **Description** - Truncate to 500 chars with "... [truncated]"

### When Even Truncation Isn't Enough

If body > 1800 chars after all truncation:
```markdown
Body too long for URL. Create issue manually:

Repository: owner/repo
Suggested title: [title]

Full issue body copied to clipboard.
```

Then copy full body to clipboard via `navigator.clipboard.writeText()`.

---

## Integration Architecture (CRITICAL)

### How JS ↔ Python Communication Works

**The Python side OWNS the browser** via `agent_canvas.py`. The integration pattern is:

1. **JS overlay emits events** via `window.__canvasBus.emit(type, source, payload)`
2. **Python polls events** via `drain_bus_events(page)` in the main loop
3. **Python handles events** by checking `event.get("type")` and calling appropriate functions
4. **Python emits responses** by calling `page.evaluate()` to emit events back to JS

**Integration will NOT be a separate script**. Instead, issue handling will be:
- A Python module imported by `agent_canvas.py`
- Called from within the existing event polling loop
- Using the same `page` object that owns the browser

### Module Import Strategy (CRITICAL)

The repo uses **sys.path insertion via a setup function**. Actual pattern from `agent_canvas.py` (search for `_setup_shared_imports`):

```python
# Existing pattern in agent_canvas.py
def _setup_shared_imports():
    """Add shared module to path for imports."""
    shared_path = Path(__file__).parent.parent.parent / "shared"
    if shared_path.exists() and str(shared_path) not in sys.path:
        sys.path.insert(0, str(shared_path))

_setup_shared_imports()
from canvas_bus import CanvasBus, drain_bus_events
```

**For issue_handler.py**, follow the SAME pattern:

```python
# New function to add to agent_canvas.py
def _setup_issue_imports():
    """Add canvas-issue module to path for imports."""
    issue_path = Path(__file__).parent.parent / "canvas-issue" / "scripts"
    if issue_path.exists() and str(issue_path) not in sys.path:
        sys.path.insert(0, str(issue_path))

# Called conditionally when --with-issue is used
if args.with_issue:
    _setup_issue_imports()
    from issue_handler import handle_issue_event
```

**File location**: `.claude/skills/canvas-issue/scripts/issue_handler.py`

**Path structure**:
- `agent_canvas.py` is at `.claude/skills/agent-canvas/scripts/agent_canvas.py`
- `issue_handler.py` is at `.claude/skills/canvas-issue/scripts/issue_handler.py`
- Relative from agent_canvas: `parent.parent / "canvas-issue" / "scripts"`

### Event Contract (JS ↔ Python)

| Event Type | Source | Direction | Payload Schema |
|------------|--------|-----------|----------------|
| `issue.button_clicked` | `issue-overlay` | JS→Python | `{}` |
| `issue.repo_prompt` | `canvas-issue` | Python→JS | `{ existing: string \| null }` |
| `issue.repo_configured` | `issue-overlay` | JS→Python | `{ repo: "owner/repo" }` |
| `issue.create_modal` | `canvas-issue` | Python→JS | `{ suggestedTitle: string, selections: array }` |
| `issue.create_requested` | `issue-overlay` | JS→Python | `{ title: string, description: string }` |
| `issue.creating` | `canvas-issue` | Python→JS | `{ status: "uploading_screenshots" \| "creating_issue" }` |
| `issue.created` | `canvas-issue` | Python→JS | `{ url: string }` (only for successful gh create) |
| `issue.failed` | `canvas-issue` | Python→JS | `{ error: string, fallbackUrl: string }` |

**Note**: `issue.created` is ONLY emitted when `gh issue create` succeeds. Web fallback emits `issue.failed` with a `fallbackUrl` that gets opened in a new tab.

### Gist Raw URL Derivation (Multi-File)

`gh gist create` with multiple files returns a single gist URL like `https://gist.github.com/<id>`. To get raw URLs for each file:

```python
def upload_screenshots_to_gist(file_paths: list) -> dict:
    """Upload multiple screenshot files to a single gist."""
    # 1. Create gist with all files
    cmd = ['gh', 'gist', 'create', '--public'] + file_paths
    result = subprocess.run(cmd, capture_output=True, text=True)
    gist_url = result.stdout.strip()  # e.g., https://gist.github.com/abc123
    
    # 2. Extract gist ID
    gist_id = gist_url.split('/')[-1]
    
    # 3. Get raw URLs via gh api
    api_result = subprocess.run(['gh', 'api', f'/gists/{gist_id}'], capture_output=True, text=True)
    gist_data = json.loads(api_result.stdout)
    
    # 4. Map each filename to its raw URL
    raw_urls = {}
    for filename, file_info in gist_data['files'].items():
        raw_urls[filename] = file_info['raw_url']
        # Use in Markdown: ![](raw_urls[filename])
    
    return {"gist_url": gist_url, "files": raw_urls}
```

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 1 (Start Immediately):
├── Task 1: Create skill skeleton (SKILL.md, directory structure)
├── Task 2: Python backend - gh CLI detection module
└── Task 6: JavaScript overlay - button component

Wave 2 (After Wave 1):
├── Task 3: Python backend - config management
├── Task 4: Python backend - issue body generation
├── Task 5: Python backend - gist upload
└── Task 7: JavaScript overlay - modals

Wave 3 (After Wave 2):
├── Task 8: Integration - issue handling module for agent_canvas.py
└── Task 9: Integration - add --with-issue flag to agent_canvas.py

Wave 4 (Final):
└── Task 10: End-to-end verification
```

### Dependency Matrix

| Task | Depends On | Blocks | Can Parallelize With |
|------|------------|--------|---------------------|
| 1 | None | 2, 3, 4, 5, 6, 7 | None |
| 2 | 1 | 8 | 3, 4, 5, 6, 7 |
| 3 | 1 | 8 | 2, 4, 5, 6, 7 |
| 4 | 1 | 8 | 2, 3, 5, 6, 7 |
| 5 | 1 | 8 | 2, 3, 4, 6, 7 |
| 6 | 1 | 8 | 2, 3, 4, 5, 7 |
| 7 | 1 | 8 | 2, 3, 4, 5, 6 |
| 8 | 2, 3, 4, 5, 6, 7 | 9, 10 | None |
| 9 | 8 | 10 | None |
| 10 | 9 | None | None |

### Agent Dispatch Summary

| Wave | Tasks | Recommended Agents |
|------|-------|-------------------|
| 1 | 1, 2, 6 | 3x parallel: quick, quick, visual-engineering |
| 2 | 3, 4, 5, 7 | 4x parallel: quick, quick, quick, visual-engineering |
| 3 | 8, 9 | Sequential: unspecified-high |
| 4 | 10 | Manual verification |

---

## TODOs

### Task 1: Create skill skeleton

**What to do**:
- Create directory `.claude/skills/canvas-issue/`
- Create `SKILL.md` with proper frontmatter (name: canvas-issue, description with triggers)
- Create `scripts/` directory
- Create `tests/` directory
- Add `.canvas/config.json` to root `.gitignore`

**Must NOT do**:
- Don't implement actual functionality yet
- Don't add unnecessary documentation files

**Recommended Agent Profile**:
- **Category**: `quick`
  - Reason: Simple file creation, no complex logic
- **Skills**: [`skill-creator`]
  - `skill-creator`: Provides skill anatomy and SKILL.md format guidance

**Parallelization**:
- **Can Run In Parallel**: YES
- **Parallel Group**: Wave 1 (with Tasks 2, 6)
- **Blocks**: Tasks 2, 3, 4, 5, 6, 7
- **Blocked By**: None

**References**:
- `.claude/skills/skill-creator/SKILL.md` - Search for "## Skill Anatomy" - Skill directory structure pattern
- `.claude/skills/agent-canvas/SKILL.md` - First 4 lines - Frontmatter format example
- `.claude/skills/agent-eyes/SKILL.md` - Similar skill structure to follow
- `.gitignore` - Search for `.canvas/` - Current .canvas/ ignore pattern (only ignores `.canvas/tools/canvas`)

**Acceptance Criteria**:

**Verification (automated)**:
```bash
# Check directory structure exists
ls -la .claude/skills/canvas-issue/ && echo "PASS: Directory exists"
ls -la .claude/skills/canvas-issue/scripts/ && echo "PASS: Scripts dir exists"
ls -la .claude/skills/canvas-issue/tests/ && echo "PASS: Tests dir exists"

# Check SKILL.md has proper frontmatter
head -10 .claude/skills/canvas-issue/SKILL.md | grep -q "^name: canvas-issue" && echo "PASS: Name field present"
head -10 .claude/skills/canvas-issue/SKILL.md | grep -q "^description:" && echo "PASS: Description field present"

# Check .gitignore updated
grep -q ".canvas/config.json" .gitignore && echo "PASS: Config ignored"
```

**Commit**: YES (group with initial setup)
- Message: `feat(canvas-issue): create skill skeleton with SKILL.md`
- Files: `.claude/skills/canvas-issue/*`, `.gitignore`

---

### Task 2: Python backend - gh CLI detection module

**What to do**:
- Create `scripts/canvas_issue.py` as a CLI script with argparse subcommands
- Implement CLI subcommand `check-gh` that outputs JSON:
  ```bash
  python scripts/canvas_issue.py check-gh
  # Output: {"installed": true, "authenticated": true, "username": "user"}
  ```
- Internal functions:
  - `check_gh_installed()` - Returns True if `gh` is in PATH via `shutil.which('gh')`
  - `check_gh_authenticated()` - Returns True if `gh auth status` exits 0
  - `get_gh_status()` - Returns dict with `installed`, `authenticated`, `username`
- Create Playwright-based test file `tests/test_canvas_issue.py` following `test_canvas_edit.py` pattern

**CLI Contract**:
```bash
python scripts/canvas_issue.py check-gh
# Exit 0, stdout: JSON object with keys: installed, authenticated, username
# Example: {"installed": true, "authenticated": true, "username": "octocat"}
# Example: {"installed": false, "authenticated": false, "username": null}
```

**Must NOT do**:
- Don't implement issue creation yet
- Don't add complex error handling beyond basic detection

**Recommended Agent Profile**:
- **Category**: `quick`
  - Reason: Simple subprocess calls, well-defined scope
- **Skills**: []
  - No special skills needed - standard Python subprocess

**Parallelization**:
- **Can Run In Parallel**: YES
- **Parallel Group**: Wave 1 (with Tasks 1, 6)
- **Blocks**: Task 8
- **Blocked By**: Task 1

**References**:
- `.claude/skills/canvas-edit/tests/test_canvas_edit.py` - Search for `class TestResults` - Test utilities pattern (TestResults class, setup helpers)
- `.claude/skills/agent-canvas/scripts/agent_canvas.py` - Search for `def run_verify_workflow` - Subprocess pattern for external commands

**Acceptance Criteria**:

**Verification (automated)**:
```bash
# Test CLI directly - must output valid JSON
uv run .claude/skills/canvas-issue/scripts/canvas_issue.py check-gh | jq -e '.installed != null' && echo "PASS: installed field present"
uv run .claude/skills/canvas-issue/scripts/canvas_issue.py check-gh | jq -e '.authenticated != null' && echo "PASS: authenticated field present"

# Run Playwright tests
python .claude/skills/canvas-issue/tests/test_canvas_issue.py 2>&1 | grep -q "PASS" && echo "PASS: Tests executed"
```

**Commit**: YES
- Message: `feat(canvas-issue): add gh CLI detection with tests`
- Files: `scripts/canvas_issue.py`, `tests/test_canvas_issue.py`

---

### Task 3: Python backend - config management

**What to do**:
- Add CLI subcommand `get-repo` that outputs the configured repo or empty string:
  ```bash
  python scripts/canvas_issue.py get-repo
  # Output: owner/repo (or empty line if not configured)
  ```
- Add CLI subcommand `set-repo` that saves the repo:
  ```bash
  python scripts/canvas_issue.py set-repo owner/repo
  # Exit 0 on success, creates/updates .canvas/config.json
  ```
- Internal functions:
  - `get_config()` - Read `.canvas/config.json`, return dict (empty dict if not exists)
  - `set_config(key_path, value)` - Update config file with nested key support
  - `get_github_repo()` - Get `config["github"]["repo"]` or None
  - `set_github_repo(owner_repo)` - Set `config["github"]["repo"]`
- Validate owner/repo format: must contain exactly one `/`

**CLI Contract**:
```bash
python scripts/canvas_issue.py set-repo "owner/repo"
# Exit 0, creates .canvas/config.json with {"github": {"repo": "owner/repo"}}

python scripts/canvas_issue.py get-repo
# Exit 0, stdout: "owner/repo" (or empty line if not configured)
```

**Must NOT do**:
- Don't add complex validation beyond basic `owner/repo` format check
- Don't add migration logic for old configs

**Recommended Agent Profile**:
- **Category**: `quick`
  - Reason: Simple JSON file I/O
- **Skills**: []
  - No special skills needed

**Parallelization**:
- **Can Run In Parallel**: YES
- **Parallel Group**: Wave 2 (with Tasks 4, 5, 7)
- **Blocks**: Task 8
- **Blocked By**: Task 1

**References**:
- `.canvas/sessions/` - Example of .canvas directory usage pattern
- `.claude/skills/agent-canvas/scripts/agent_canvas.py` - Search for `def get_session_dir` - Pattern for creating directories

**Acceptance Criteria**:

**Verification (automated)**:
```bash
# Clean start
rm -f .canvas/config.json

# Test set-repo
uv run .claude/skills/canvas-issue/scripts/canvas_issue.py set-repo "test/demo-repo"
echo "Exit code: $?"  # Should be 0

# Test get-repo
REPO=$(uv run .claude/skills/canvas-issue/scripts/canvas_issue.py get-repo)
[ "$REPO" = "test/demo-repo" ] && echo "PASS: Repo retrieved correctly"

# Verify JSON structure
cat .canvas/config.json | jq -e '.github.repo == "test/demo-repo"' && echo "PASS: JSON structure correct"

# Cleanup
rm -f .canvas/config.json
```

**Commit**: YES
- Message: `feat(canvas-issue): add config management for GitHub repo`
- Files: `scripts/canvas_issue.py`

---

### Task 4: Python backend - issue body generation

**What to do**:
- Add CLI subcommand `generate-body` that creates Markdown:
  ```bash
  python scripts/canvas_issue.py generate-body --session <session_id> [--description "user text"]
  # Output: Markdown string to stdout
  ```
- Add `--mock` flag for testing without real session:
  ```bash
  python scripts/canvas_issue.py generate-body --mock
  # Output: Markdown with mock data
  ```
- Internal function `generate_issue_body(session_data, user_description=None, screenshot_urls=None)`:
  - Input: session data dict (from `session.json`), user description, gist URLs
  - Output: Markdown string with sections:
    - ## Description (if user provided)
    - ## Page Info (URL from `session.url`)
    - ## Selected Elements (for each from `session.events.selections[]`: selector, text preview)
    - ## Screenshots (gist URLs, or omit section if no images)

**CLI Contract**:
```bash
python scripts/canvas_issue.py generate-body --mock
# Exit 0, stdout: Markdown containing "## Page Info" and other sections

python scripts/canvas_issue.py generate-body --session ses-abc123 --description "Bug report"
# Exit 0, stdout: Full Markdown with session data
```

**Must NOT do**:
- Don't add template customization
- Don't add HTML rendering

**Recommended Agent Profile**:
- **Category**: `quick`
  - Reason: String formatting, well-defined output
- **Skills**: []
  - No special skills needed

**Parallelization**:
- **Can Run In Parallel**: YES
- **Parallel Group**: Wave 2 (with Tasks 3, 5, 7)
- **Blocks**: Task 8
- **Blocked By**: Task 1

**References**:
- `.claude/skills/agent-canvas/scripts/agent_canvas.py` - Search for `def write_session_artifact` - Session artifact schema
- `.canvas/sessions/*/session.json` - Example session data structure with schemaVersion 1.1

**Acceptance Criteria**:

**Verification (automated)**:
```bash
# Test with mock data
BODY=$(uv run .claude/skills/canvas-issue/scripts/canvas_issue.py generate-body --mock)
echo "$BODY" | grep -q "## Page Info" && echo "PASS: Page Info section present"
echo "$BODY" | grep -q "## Selected Elements" && echo "PASS: Elements section present"
```

**Commit**: YES
- Message: `feat(canvas-issue): add issue body Markdown generation`
- Files: `scripts/canvas_issue.py`

---

### Task 5: Python backend - gist upload for screenshots

**What to do**:
- Add CLI subcommand `upload-gist` that uploads **one or more files** and returns raw URLs for each:
  ```bash
  python scripts/canvas_issue.py upload-gist /path/to/before.png /path/to/selection_001.png
  # Output: JSON with gist_url and file-to-raw_url mapping
  ```
- Internal functions:
  - `upload_to_gist(file_paths: list)` - Creates public gist with multiple files, returns `{ gist_url, files: {filename: {raw_url}} }`
  - Uses `gh gist create --public <file1> <file2> ...` to create single gist
  - Parses gist ID from output URL
  - Calls `gh api /gists/<id>` to get `files[*].raw_url` for each file
- Error handling: Return `{ error: "message" }` on failure
- Respects limits: Max 5 files, max 10MB per file, max 25MB total

**CLI Contract**:
```bash
# Single file
python scripts/canvas_issue.py upload-gist /path/to/file.png
# Exit 0 on success, stdout: {"gist_url": "https://gist.github.com/...", "files": {"file.png": {"raw_url": "https://..."}}}

# Multiple files (the expected usage)
python scripts/canvas_issue.py upload-gist before.png selection_001.png selection_002.png
# Exit 0 on success, stdout: {"gist_url": "https://gist.github.com/...", "files": {"before.png": {"raw_url": "..."}, "selection_001.png": {"raw_url": "..."}, "selection_002.png": {"raw_url": "..."}}}

# Exit 1 on failure, stdout: {"error": "gh not authenticated"}
```

**Raw URL Derivation (multi-file)**:
```python
def upload_to_gist(file_paths: list) -> dict:
    """Upload multiple files to a single gist, return raw URLs for each."""
    # 1. Validate limits
    if len(file_paths) > 5:
        return {"error": f"Too many files ({len(file_paths)}), max 5"}
    
    # 2. Create gist with all files
    cmd = ['gh', 'gist', 'create', '--public'] + file_paths
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        return {"error": result.stderr.strip()}
    
    gist_url = result.stdout.strip()  # https://gist.github.com/abc123
    gist_id = gist_url.split('/')[-1]
    
    # 3. Get file info via API
    api_result = subprocess.run(['gh', 'api', f'/gists/{gist_id}'], capture_output=True, text=True)
    gist_data = json.loads(api_result.stdout)
    
    # 4. Build file-to-raw_url mapping
    files = {}
    for filename, file_info in gist_data['files'].items():
        files[filename] = {"raw_url": file_info['raw_url']}
    
    return {"gist_url": gist_url, "files": files}
```

**Must NOT do**:
- Don't add retry logic (simple fail fast)
- Don't add gist management (list/delete)

**Recommended Agent Profile**:
- **Category**: `quick`
  - Reason: Subprocess call with output parsing
- **Skills**: []
  - No special skills needed

**Parallelization**:
- **Can Run In Parallel**: YES
- **Parallel Group**: Wave 2 (with Tasks 3, 4, 7)
- **Blocks**: Task 8
- **Blocked By**: Task 1

**References**:
- `.claude/skills/agent-canvas/scripts/agent_canvas.py` - Search for `def run_verify_workflow` - Subprocess execution pattern
- `gh gist create --help` - CLI creates gist and outputs URL
- `gh api --help` - CLI for GitHub API calls

**Acceptance Criteria**:

**Verification (automated)**:
```bash
# Create test files
echo "test content 1" > /tmp/test-gist-1.txt
echo "test content 2" > /tmp/test-gist-2.txt

# Test single file upload (requires gh auth - skip in CI)
if gh auth status &>/dev/null; then
    RESULT=$(uv run .claude/skills/canvas-issue/scripts/canvas_issue.py upload-gist /tmp/test-gist-1.txt)
    echo "$RESULT" | jq -e '.gist_url' && echo "PASS: gist_url present"
    echo "$RESULT" | jq -e '.files["test-gist-1.txt"].raw_url' && echo "PASS: raw_url present for file"
    
    # Test multi-file upload
    RESULT2=$(uv run .claude/skills/canvas-issue/scripts/canvas_issue.py upload-gist /tmp/test-gist-1.txt /tmp/test-gist-2.txt)
    echo "$RESULT2" | jq -e '.files | keys | length == 2' && echo "PASS: Two files in gist"
else
    echo "SKIP: gh not authenticated (expected in CI)"
fi

# Cleanup
rm -f /tmp/test-gist-1.txt /tmp/test-gist-2.txt
```

**Commit**: YES
- Message: `feat(canvas-issue): add multi-file gist upload for screenshots`
- Files: `scripts/canvas_issue.py`

---

### Task 6: JavaScript overlay - button component

**What to do**:
- Create `scripts/issue_overlay.js` with:
  - "Create Issue" button styled to match existing counter badge
  - Button positioned in top-right area (left of selection counter)
  - Click handler that emits `issue.button_clicked` event via canvas bus
  - Subscribe to `capture_mode.changed` to hide during screenshots
- **TOKENS dependency**: Since `TOKENS` is a const inside the `PICKER_OVERLAY_JS` IIFE and NOT exported to `window`, you must:
  - **Option A (Recommended)**: Duplicate the token values directly in `issue_overlay.js`:
    ```javascript
    const ISSUE_TOKENS = {
      colors: {
        primary: '#58a6ff',
        background: '#0d1117',
        text: '#c9d1d9',
        border: '#30363d',
        status: { success: '#3fb950', error: '#f85149' }
      },
      fonts: { family: '-apple-system, ...', sizes: { sm: '12px', md: '14px' } },
      spacing: { xs: '4px', sm: '8px', md: '12px' },
      // ... relevant subset
    };
    ```
  - This is acceptable because the token values are simple CSS values, and the button styling should match the counter badge exactly.

**Must NOT do**:
- Don't implement modals (Task 7)
- Don't implement issue creation logic (Task 8)
- Don't attempt to import TOKENS from PICKER_OVERLAY_JS (it's not exported)

**Recommended Agent Profile**:
- **Category**: `visual-engineering`
  - Reason: UI component with styling, visual consistency required
- **Skills**: [`frontend-ui-ux`]
  - `frontend-ui-ux`: Button styling, visual consistency with existing overlay

**Parallelization**:
- **Can Run In Parallel**: YES
- **Parallel Group**: Wave 1 (with Tasks 1, 2)
- **Blocks**: Task 8
- **Blocked By**: Task 1

**References**:
- `.claude/skills/agent-canvas/scripts/agent_canvas.py` - Search for `TOKENS = {` - TOKENS design system (colors, fonts, shadows, z-index)
- `.claude/skills/agent-canvas/scripts/agent_canvas.py` - Search for `selectionCount` or `counter badge` - Counter badge styling (use same visual style)
- `.claude/skills/shared/canvas_bus.py` - Search for `function emit(type, source, payload)` - Event emission pattern (JS function inside CANVAS_BUS_JS string)
- `.claude/skills/canvas-edit/scripts/annotation_toolbar.js` - Search for `__canvasBus.emit` - Canvas bus integration pattern

**Acceptance Criteria**:

**Manual Verification (Playwright)**:
```
1. Navigate to: http://localhost:3000 via agent-canvas with --with-issue
2. Assert: Button "Create Issue" visible in top-right area (left of counter)
3. Assert: Button uses same color scheme as counter badge (#58a6ff primary)
4. Click: "Create Issue" button
5. Assert: Console shows event emission with type "issue.button_clicked"
6. Screenshot: .sisyphus/evidence/task-6-button.png
```

**Automated check**:
```bash
# Check JS file exists and has button creation
grep -q "Create Issue" .claude/skills/canvas-issue/scripts/issue_overlay.js && echo "PASS: Button text found"
grep -q "issue.button_clicked" .claude/skills/canvas-issue/scripts/issue_overlay.js && echo "PASS: Event emission found"
grep -q "__canvasBus" .claude/skills/canvas-issue/scripts/issue_overlay.js && echo "PASS: Canvas bus usage found"
```

**Commit**: YES
- Message: `feat(canvas-issue): add Create Issue button to overlay`
- Files: `scripts/issue_overlay.js`

---

### Task 7: JavaScript overlay - modals (repo config + issue creation)

**What to do**:
- Add to `scripts/issue_overlay.js`:
  - **Repo config modal**: Input field for "owner/repo", Save/Cancel buttons
  - **Issue creation modal**: Title input (pre-filled), Description textarea, Create/Cancel buttons
  - **Confirmation overlay**: Success/failure message, issue URL link, dismiss button
- Use closed Shadow DOM for style isolation (follow `annotation_toolbar.js` pattern line 18-56)
- Use native Popover API for modal dialogs (follow `annotation_layer.js` line 1-18, uses `popover="auto"`)
- Emit events per the Event Contract defined above
- Subscribe to `issue.repo_prompt`, `issue.create_modal`, `issue.creating`, `issue.created`, `issue.failed` from Python

**Must NOT do**:
- Don't implement actual issue creation (Task 8 handles Python integration)
- Don't add form validation beyond basic empty check

**Recommended Agent Profile**:
- **Category**: `visual-engineering`
  - Reason: Complex UI components, modal interactions
- **Skills**: [`frontend-ui-ux`]
  - `frontend-ui-ux`: Modal design, form UX, visual feedback

**Parallelization**:
- **Can Run In Parallel**: YES
- **Parallel Group**: Wave 2 (with Tasks 3, 4, 5)
- **Blocks**: Task 8
- **Blocked By**: Task 1

**References**:
- `.claude/skills/canvas-edit/scripts/annotation_toolbar.js` - Search for `attachShadow({ mode: 'closed' })` (near line ~506) - Closed Shadow DOM pattern
- `.claude/skills/canvas-edit/scripts/annotation_layer.js` - Search for `setAttribute('popover', 'auto')` (near line ~663) - Native Popover API usage
- `.claude/skills/canvas-edit/scripts/annotation_toolbar.js` - Search for `--toolbar-` - CSS variables for consistent theming

**Acceptance Criteria**:

**Manual Verification (Playwright)**:
```
# Repo config modal
1. Click "Create Issue" (simulate no config exists by emitting issue.repo_prompt)
2. Assert: Modal appears with "Enter your GitHub repo (e.g., owner/repo):" prompt
3. Fill: "test/demo" in input field
4. Click: "Save" button
5. Assert: Modal closes, console shows issue.repo_configured event with payload {repo: "test/demo"}

# Issue creation modal
6. Emit issue.create_modal event with suggestedTitle
7. Assert: Modal appears with title input, description textarea
8. Assert: Title pre-filled with suggested value
9. Edit title to "Test Issue"
10. Fill description: "This is a test"
11. Click: "Create" button
12. Assert: Console shows issue.create_requested event with {title: "Test Issue", description: "This is a test"}

# Confirmation overlay
13. Emit issue.created event with {url: "https://github.com/...", method: "gh"}
14. Assert: Confirmation shows "Issue created!" and clickable URL
15. Click dismiss: Confirmation closes
```

**Automated check**:
```bash
# Check modal elements exist in JS
grep -q "issue.repo_configured" .claude/skills/canvas-issue/scripts/issue_overlay.js && echo "PASS: Repo event"
grep -q "issue.create_requested" .claude/skills/canvas-issue/scripts/issue_overlay.js && echo "PASS: Create event"
grep -q "attachShadow" .claude/skills/canvas-issue/scripts/issue_overlay.js && echo "PASS: Shadow DOM"
grep -q 'popover' .claude/skills/canvas-issue/scripts/issue_overlay.js && echo "PASS: Popover API"
```

**Commit**: YES
- Message: `feat(canvas-issue): add repo config and issue creation modals`
- Files: `scripts/issue_overlay.js`

---

### Task 8: Integration - issue handling module for agent_canvas.py

**What to do**:
- Create `scripts/issue_handler.py` as an importable module (NOT a standalone CLI script)
- Module provides functions called from within `agent_canvas.py`'s event loop:
  - `handle_issue_event(page, event, session_id, selections)` - Main dispatcher
  - `handle_button_click(page)` - Check config, emit `issue.repo_prompt` or `issue.create_modal`
  - `handle_repo_configured(page, repo)` - Save config via `set_github_repo()`
  - `handle_create_requested(page, title, description, session_data)` - Full creation flow:
    1. Emit `issue.creating` with status
    2. Upload screenshots to gist (if gh available)
    3. Generate issue body
    4. Create issue via `gh issue create` or generate web fallback URL
    5. Emit `issue.created` or `issue.failed`
- Import and use functions from `canvas_issue.py` for CLI operations

**Integration Pattern** (how it fits in agent_canvas.py):
```python
# In agent_canvas.py event polling loop
# NOTE: issue_handler is imported via sys.path (see Module Import Strategy)
# NOT as a package path like "canvas_issue.scripts.issue_handler"

for event in events:
    if event.get("type", "").startswith("issue."):
        handle_issue_event(page, event, session_id, all_selections)
    elif event.get("type") == "selection.changed":
        # ... existing selection handling
```

**Module Structure Requirements**:
- `canvas_issue.py` must have CLI code under `if __name__ == "__main__":` to be safely importable
- `issue_handler.py` imports from `canvas_issue.py` for CLI functions (e.g., `from canvas_issue import get_gh_status, upload_to_gist`)

**Must NOT do**:
- Don't modify agent_canvas.py yet (Task 9)
- Don't add complex retry logic

**Recommended Agent Profile**:
- **Category**: `unspecified-high`
  - Reason: Integration task connecting multiple components
- **Skills**: []
  - No special skills - requires understanding existing patterns

**Parallelization**:
- **Can Run In Parallel**: NO
- **Parallel Group**: Sequential (Wave 3)
- **Blocks**: Task 9, Task 10
- **Blocked By**: Tasks 2, 3, 4, 5, 6, 7

**References**:
- `.claude/skills/agent-canvas/scripts/agent_canvas.py` - Search for `while True:` and `drain_bus_events` - Event polling loop pattern
- `.claude/skills/agent-canvas/scripts/agent_canvas.py` - Search for `event.get("type")` - Event type handling pattern (how to check event types and dispatch)
- `.claude/skills/shared/canvas_bus.py` - Search for `def drain_bus_events` - `drain_bus_events(page)` usage

**Acceptance Criteria**:

**Verification (automated)**:
```bash
# Check module is importable
python -c "from pathlib import Path; import sys; sys.path.insert(0, str(Path('.claude/skills/canvas-issue/scripts'))); from issue_handler import handle_issue_event; print('PASS: Module importable')"

# Check required functions exist
python -c "
import sys
from pathlib import Path
sys.path.insert(0, str(Path('.claude/skills/canvas-issue/scripts')))
from issue_handler import handle_issue_event, handle_button_click, handle_repo_configured, handle_create_requested
print('PASS: All functions exist')
"
```

**Commit**: YES
- Message: `feat(canvas-issue): add issue handler module for agent_canvas integration`
- Files: `scripts/issue_handler.py`

---

### Task 9: Integration - add --with-issue flag to agent_canvas.py

**What to do**:
- Add `--with-issue` flag to pick command argument parser
- When flag is set:
  1. Load `issue_overlay.js` content (follow `get_review_overlay_js()` pattern at line 291-301)
  2. Inject after picker overlay via `page.evaluate(issue_js)`
  3. Add `issue_handler` to imports
  4. Add issue event handling to the polling loop (call `handle_issue_event()`)
  5. Update features dict to include `issue: True`
- Follow existing pattern for `--with-eyes`, `--with-edit`, `--with-review`

**Must NOT do**:
- Don't refactor existing code
- Don't change existing flag behavior

**Recommended Agent Profile**:
- **Category**: `quick`
  - Reason: Adding flag following existing pattern
- **Skills**: []
  - No special skills - follows existing code patterns

**Parallelization**:
- **Can Run In Parallel**: NO
- **Parallel Group**: Sequential (Wave 3, after Task 8)
- **Blocks**: Task 10
- **Blocked By**: Task 8

**References**:
- `.claude/skills/agent-canvas/scripts/agent_canvas.py` - Search for `--with-eyes` or `add_argument.*with` - Existing flag definitions
- `.claude/skills/agent-canvas/scripts/agent_canvas.py` - Search for `def get_review_overlay_js` - Pattern for loading JS files
- `.claude/skills/agent-canvas/scripts/agent_canvas.py` - Search for `page.evaluate(review_js)` - Injection pattern
- `.claude/skills/agent-canvas/scripts/agent_canvas.py` - Search for `features = {` - Features dict pattern

**Acceptance Criteria**:

**Verification (automated)**:
```bash
# Check flag exists in help
uv run .claude/skills/agent-canvas/scripts/agent_canvas.py pick --help | grep -q "with-issue" && echo "PASS: Flag exists in help"

# Check JS loading function exists
grep -q "def get_issue_overlay_js" .claude/skills/agent-canvas/scripts/agent_canvas.py && echo "PASS: JS loader function present"

# Check issue_handler import
grep -q "from.*issue_handler import" .claude/skills/agent-canvas/scripts/agent_canvas.py && echo "PASS: issue_handler imported"

# Check features dict includes issue
grep -q '"issue":' .claude/skills/agent-canvas/scripts/agent_canvas.py && echo "PASS: issue feature in features dict"
```

**Commit**: YES
- Message: `feat(agent-canvas): add --with-issue flag for GitHub issue creation`
- Files: `.claude/skills/agent-canvas/scripts/agent_canvas.py`

---

### Task 10: End-to-end verification

**What to do**:
- Full manual verification of the complete flow using Playwright
- Document any issues found
- Verify all acceptance criteria met

**Must NOT do**:
- Don't add new features
- Don't fix non-critical issues (create follow-up tasks instead)

**Recommended Agent Profile**:
- **Category**: N/A (Manual verification)
- **Skills**: [`playwright`]
  - `playwright`: Browser automation for verification

**Parallelization**:
- **Can Run In Parallel**: NO
- **Parallel Group**: Final (Wave 4)
- **Blocks**: None (final task)
- **Blocked By**: Task 9

**References**:
- All previous task acceptance criteria

**Acceptance Criteria**:

**Full Flow Verification (Playwright)**:
```
# Setup
1. Ensure test server running at http://localhost:3000
2. Remove any existing .canvas/config.json

# First-time flow (with gh CLI)
3. Run: uv run .claude/skills/agent-canvas/scripts/agent_canvas.py pick http://localhost:3000 --with-issue --with-eyes
4. Browser opens with picker overlay
5. Assert: "Create Issue" button visible (top-right, left of counter)
6. Click element on page
7. Assert: Selection counter increments
8. Click "Create Issue" button
9. Assert: Repo config modal appears (first time, no config)
10. Enter: "test/canvas-demo" in repo field
11. Click "Save"
12. Assert: Issue creation modal appears with suggested title
13. Edit title to "Test from E2E"
14. Enter description: "Testing the full flow"
15. Click "Create"
16. Assert: Creating status shown briefly
17. If gh authenticated: Assert confirmation shows "✓ Issue created!" with URL
18. If gh not available: Assert confirmation shows "⚠ Could not create issue" and new tab opened
19. Close browser

# Subsequent flow (config exists)
20. Re-run agent-canvas with --with-issue
21. Click element, click "Create Issue"
22. Assert: Issue modal appears directly (no repo prompt)
23. Close browser

# Verify artifacts
24. Check: .canvas/config.json contains github.repo = "test/canvas-demo"
25. Check: Session JSON contains issue-related events (in events.jsonl if streamed)
```

**Evidence to Capture:**
- [ ] Screenshot: Button in overlay
- [ ] Screenshot: Repo config modal
- [ ] Screenshot: Issue creation modal
- [ ] Screenshot: Confirmation overlay
- [ ] Terminal output: Issue URL
- [ ] File: .canvas/config.json contents

**Commit**: NO (verification only)

---

## Commit Strategy

| After Task | Message | Files | Verification |
|------------|---------|-------|--------------|
| 1 | `feat(canvas-issue): create skill skeleton with SKILL.md` | `.claude/skills/canvas-issue/*`, `.gitignore` | ls check |
| 2 | `feat(canvas-issue): add gh CLI detection with tests` | `scripts/canvas_issue.py`, `tests/*` | CLI + tests |
| 3 | `feat(canvas-issue): add config management for GitHub repo` | `scripts/canvas_issue.py` | CLI check |
| 4 | `feat(canvas-issue): add issue body Markdown generation` | `scripts/canvas_issue.py` | CLI check |
| 5 | `feat(canvas-issue): add gist upload for screenshots` | `scripts/canvas_issue.py` | CLI check |
| 6 | `feat(canvas-issue): add Create Issue button to overlay` | `scripts/issue_overlay.js` | grep check |
| 7 | `feat(canvas-issue): add repo config and issue creation modals` | `scripts/issue_overlay.js` | grep check |
| 8 | `feat(canvas-issue): add issue handler module for agent_canvas integration` | `scripts/issue_handler.py` | import check |
| 9 | `feat(agent-canvas): add --with-issue flag for GitHub issue creation` | `agent_canvas.py` | help check |

---

## Success Criteria

### Prerequisites for Verification
- `jq` installed (for JSON parsing in verification commands)
- `gh` installed and authenticated (for full gh CLI path testing)
- Test server running at `http://localhost:3000` (for E2E tests)

### Verification Commands
```bash
# All CLI subcommands work
uv run .claude/skills/canvas-issue/scripts/canvas_issue.py check-gh | jq -e '.installed'
uv run .claude/skills/canvas-issue/scripts/canvas_issue.py set-repo "test/demo"
uv run .claude/skills/canvas-issue/scripts/canvas_issue.py get-repo
uv run .claude/skills/canvas-issue/scripts/canvas_issue.py generate-body --mock | grep "## Page Info"

# Playwright tests pass
python .claude/skills/canvas-issue/tests/test_canvas_issue.py

# Help shows new flag
uv run .claude/skills/agent-canvas/scripts/agent_canvas.py pick --help | grep "with-issue"

# Config persists and is gitignored
cat .canvas/config.json | jq '.github.repo'
grep ".canvas/config.json" .gitignore

# SKILL.md valid
head -5 .claude/skills/canvas-issue/SKILL.md | grep "name: canvas-issue"
```

### Final Checklist
- [ ] "Create Issue" button appears in picker overlay
- [ ] First-time repo prompt works and persists config
- [ ] Issue creation modal has editable title and description
- [ ] `gh` CLI path creates issue with gist screenshots
- [ ] Web fallback opens pre-filled GitHub issue URL
- [ ] Confirmation shows success/failure and issue URL
- [ ] Playwright tests pass
- [ ] `.canvas/config.json` is gitignored
- [ ] No guardrail violations (no labels, no templates, no other providers)

---

## Objective Verification Checklist

This checklist provides **pass/fail criteria** for complete implementation verification.

### Scenario 1: With `gh` Installed and Authenticated

| Step | Action | Pass Criteria |
|------|--------|---------------|
| 1 | Run: `gh auth status` | Exit 0, shows authenticated user |
| 2 | Run: `uv run agent_canvas.py pick http://localhost:3000 --with-issue` | Browser opens |
| 3 | Verify button | "Create Issue" button visible top-right, left of counter |
| 4 | Click 2 elements on page | Selection counter shows "2" |
| 5 | Click "Create Issue" | Repo config modal appears (first time) |
| 6 | Enter `test-owner/test-repo`, click Save | Modal closes, config saved |
| 7 | Issue modal appears | Title pre-filled, description empty |
| 8 | Edit title to "Test Issue", add description | Fields editable |
| 9 | Click "Create" | Status shows "Creating..." |
| 10 | Verify issue created | Confirmation shows GitHub issue URL |
| 11 | Open URL in browser | Issue exists with correct title, body contains selections, images render |
| 12 | Check gist | Gist exists with screenshot files, raw URLs work |

### Scenario 2: Without `gh` (Web Fallback)

| Step | Action | Pass Criteria |
|------|--------|---------------|
| 1 | Run in subshell: `PATH=/usr/bin:/bin uv run canvas_issue.py check-gh` | Returns `{"installed": false, ...}` (gh not in restricted PATH) |
| 2 | OR: Create test that mocks `shutil.which('gh')` returning None | Unit test passes |
| 3 | In browser: click "Create Issue" button | Modal appears |
| 4 | Fill form, click "Create" | **New tab** opens with GitHub "new issue" page |
| 5 | Verify picker tab | Picker tab remains interactive (not navigated away) |
| 6 | Verify URL | Title and body pre-filled in GitHub form |
| 7 | Verify truncation | If body was long, it's truncated sensibly |

### Scenario 3: With/Without `--with-eyes`

| Step | Action | Pass Criteria |
|------|--------|---------------|
| 1 | Run with `--with-eyes --with-issue` | Both features active |
| 2 | Create issue | Issue body contains "## Selected Elements" |
| 3 | Verify NO a11y section | Issue body does NOT contain "## Accessibility Issues" |
| 4 | Check session.json | `eyes.accessibility` data present (but not in issue) |

### Scenario 4: Config Persistence

| Step | Action | Pass Criteria |
|------|--------|---------------|
| 1 | Delete `.canvas/config.json` | File gone |
| 2 | Run picker, configure repo as `owner/repo` | Config saved |
| 3 | Verify file | `cat .canvas/config.json` shows `{"github":{"repo":"owner/repo"}}` |
| 4 | Run picker again, click "Create Issue" | Issue modal appears directly (no repo prompt) |
| 5 | Check `.gitignore` | Contains `.canvas/config.json` |
| 6 | Run `git status` | `.canvas/config.json` not shown as untracked |

### Scenario 5: Screenshot Limits

| Step | Action | Pass Criteria |
|------|--------|---------------|
| 1 | Select 7 elements (generating 7 selection screenshots) | All selected |
| 2 | Create issue | Issue created |
| 3 | Check issue body | Contains max 5 images, note says "2 additional screenshots not uploaded" |
| 4 | Verify gist | Gist contains exactly 5 files (1 main + 4 selection or 5 selection) |

### Scenario 6: Error Recovery

| Step | Action | Pass Criteria |
|------|--------|---------------|
| 1 | Configure invalid repo `not-a-real-owner/not-a-real-repo` | Config saved |
| 2 | Click "Create Issue" | Attempt made |
| 3 | `gh issue create` fails | Error shown in UI |
| 4 | Verify fallback | New tab opens with GitHub "new issue" page for manual creation |
| 5 | Picker tab intact | Picker remains functional |
