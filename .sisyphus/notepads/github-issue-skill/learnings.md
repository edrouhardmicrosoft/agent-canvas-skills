# Learnings - GitHub Issue Skill

## Conventions & Patterns


## Skill Structure Established

### Directory Layout
- `.claude/skills/canvas-issue/SKILL.md` - Skill metadata and documentation
- `.claude/skills/canvas-issue/scripts/` - Empty directory for future Python/Bash scripts
- `.claude/skills/canvas-issue/tests/` - Empty directory for future test files

### Frontmatter Format
- Uses YAML front matter with `---` delimiters
- Required fields: `name` and `description`
- Description includes trigger phrases ("create issue", "report bug", "file issue")
- Description explains what the skill does and when to use it

### .gitignore Update
- Added `.canvas/config.json` to prevent config leaks (alongside existing `.canvas/tools/canvas`)

### Commit Structure
- Files added: SKILL.md, scripts/, tests/ directories
- Message format: `feat(canvas-issue): create skill skeleton with SKILL.md`

## Task 2: Python CLI Backend with gh Detection

### Implementation Patterns

#### argparse with Subcommands
- Entry point under `if __name__ == "__main__":` allows functions to be imported separately
- Use `add_subparsers(dest="command")` to create subcommands (like `git status`, `git commit`)
- Each subcommand gets its own parser via `add_parser()`
- Simplifies CLI expansion for future tasks

#### GitHub CLI Detection Functions
- `check_gh_installed()`: Use `shutil.which('gh')` to check PATH - simple and reliable
- `check_gh_authenticated()`: Run `subprocess.run(['gh', 'auth', 'status'], capture_output=True)` - exit code 0 = authenticated
- `get_gh_username()`: Parse stdout with `split()` and find "account" keyword to extract username
- `get_gh_status()`: Orchestrates all three checks into single dict return

#### JSON Output Contract
- Always exit 0 (errors reported in JSON, not exit codes)
- Return dict with exact 3 keys: `installed` (bool), `authenticated` (bool), `username` (str|null)
- Use `json.dumps()` for stdout output
- Null username when not authenticated

#### Test Structure (Playwright-based)
- Import pattern: Try-except for playwright with helpful error message
- Helper function `run_canvas_issue_cli()` runs CLI via subprocess and parses JSON
- `TestResults` class tracks results with add() and print_summary() methods
- Three test suites:
  1. `test_check_gh_command()` - CLI execution, key presence, type validation, logic consistency
  2. `test_json_output_format()` - Schema validation (valid JSON, object type, exact key count)
  3. `test_edge_cases()` - Consistency across runs, exit codes
- All 15 tests passed on first implementation

### Key Decisions

1. **No subprocess imports at top level** - Import subprocess locally in functions for clarity
2. **Graceful error handling** - All errors return sensible defaults (False, None), no exceptions thrown
3. **Type hints with Optional** - `Optional[dict]` for functions that might return None
4. **Logical consistency tests** - Test that "authenticated → installed" and "authenticated → username not null"

### Files Created
- `scripts/canvas_issue.py` - 155 lines, pure Python, no external deps except subprocess/shutil
- `tests/test_canvas_issue.py` - 343 lines, comprehensive test coverage with 15 tests

### Verification Commands
```bash
uv run .claude/skills/canvas-issue/scripts/canvas_issue.py check-gh | jq -e '.installed != null'  # ✓ true
uv run .claude/skills/canvas-issue/scripts/canvas_issue.py check-gh | jq -e '.authenticated != null'  # ✓ true
uv run .claude/skills/canvas-issue/scripts/canvas_issue.py check-gh | jq -e '.username != null'  # ✓ true
```

### Commit
- Message: `feat(canvas-issue): add gh CLI detection with tests`
- Files: `scripts/canvas_issue.py`, `tests/test_canvas_issue.py`
- Hash: c84d13d

## Task 5: Multi-File Gist Upload

### Implementation Patterns

#### Multi-File Gist Creation
- `gh gist create --public file1 file2 file3` creates single gist with all files atomically
- Exit code 0 = success, stdout contains gist URL (e.g., `https://gist.github.com/username/abc123`)
- Extract gist ID with `url.split('/')[-1]` to get last path component

#### Raw URL Extraction
- Use `gh api /gists/<id>` to fetch gist metadata as JSON
- Each file in response has `files[filename].raw_url` - the direct content URL
- Build mapping: `{filename: {"raw_url": "..."}}`

#### Validation Strategy (Fail-Fast)
1. **Authentication check first** - `check_gh_authenticated()` returns error immediately if not logged in
2. **File count limit** - Max 5 files (GitHub gist limit)
3. **Individual file size** - Max 10MB per file
4. **Total size** - Max 25MB across all files (cumulative check)
5. **File existence** - Check each Path exists before proceeding
6. **Graceful degradation** - Return error dict on any validation failure, never raise exceptions

#### JSON Output Contract
- Success: `{"gist_url": "https://...", "files": {"file.png": {"raw_url": "https://..."}, ...}}`
- Error: `{"error": "descriptive message"}`
- Always exit 0 (even on error)
- Always print JSON to stdout

#### Argparse Integration
- `nargs="+"` for `files` argument accepts 1+ paths
- Matches existing subcommand pattern in canvas_issue.py
- No special parsing needed - args.files is list of strings

### Key Implementation Details

1. **Size calculations**: Use `path.stat().st_size` to get bytes, format as MB in error messages
2. **API error handling**: Check subprocess return codes before JSON parsing
3. **Mapping structure**: Match spec exactly - files dict maps filename → {raw_url}
4. **Order independence**: Handler always returns 0 (exit codes not used for success/failure)

### Files Modified
- `.claude/skills/canvas-issue/scripts/canvas_issue.py` - Added `upload_to_gist()` function + `upload-gist` subcommand

### Verification Commands
```bash
# Single file
echo "test" > /tmp/test.txt
python3 scripts/canvas_issue.py upload-gist /tmp/test.txt | jq '.gist_url'
python3 scripts/canvas_issue.py upload-gist /tmp/test.txt | jq '.files["test.txt"].raw_url'

# Multiple files  
python3 scripts/canvas_issue.py upload-gist /tmp/file1.txt /tmp/file2.txt | jq '.files | keys'

# Error cases
python3 scripts/canvas_issue.py upload-gist /tmp/nonexistent.txt | jq '.error'
python3 scripts/canvas_issue.py upload-gist $(for i in {1..6}; do touch /tmp/f$i.txt; echo /tmp/f$i.txt; done) | jq '.error'
```

### Commit
- Message: `feat(canvas-issue): add multi-file gist upload for screenshots`
- Files: `.claude/skills/canvas-issue/scripts/canvas_issue.py`
- Hash: 8fea423

## Learnings (Task 7)
- **Shadow DOM Isolation**: Using `attachShadow({ mode: 'closed' })` for the modal container effectively isolates modal styles from the host page, preventing style leakage.
- **Native Popover API**: The `popover="auto"` attribute simplifies modal management (showing/hiding/backdrop) without external libraries, but requires recent browser support (Chrome 114+, Firefox 125+, Safari 17+).
- **Event-Driven Architecture**: The separation of UI (JS) and logic (Python) via the event bus (`window.__canvasBus`) allows for clean decoupling. The UI only emits intents (`create_requested`, `repo_configured`) and reacts to state updates (`created`, `failed`), keeping the frontend "dumb".
- **Dynamic Content in Shadow DOM**: Creating elements dynamically and appending them to the Shadow Root ensures that all components (modals, buttons) are encapsulated together.
