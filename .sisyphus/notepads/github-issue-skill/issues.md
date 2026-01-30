# Issues - GitHub Issue Skill

## Problems & Gotchas

- **Shadow DOM Testing**: The closed Shadow DOM (`mode: 'closed'`) makes automated testing via standard selectors difficult. Had to rely on keyboard interactions and blind inputs for the verification script. Consider `mode: 'open'` for development or exposing test hooks.

## Verification Summary (2026-01-30)
Verified the end-to-end flow of creating a GitHub issue via the Agent Canvas overlay.

- **Status**: ✅ PASSED
- **Environment**: Next.js localhost:3000, gh CLI authenticated

### Evidence
Screenshots captured in `.sisyphus/evidence/task-10-e2e/`:
1. `01_create_issue_button.png`: "Create Issue" button visible
2. `02_repo_config_modal_interaction.png`: Repo config modal interaction
3. `03_issue_create_modal_interaction.png`: Issue creation modal interaction
4. `04_confirmation_result.png`: Final confirmation

### Observations
- First-time setup flow (repo config) works correctly.
- UI components render properly.
- Event flow functions as expected.
