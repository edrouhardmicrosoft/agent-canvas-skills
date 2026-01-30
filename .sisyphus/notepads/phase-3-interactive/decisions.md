# Phase 3 Interactive Mode - Decisions

## Session: ses_3efb7afb6ffeqvEZsefWyfxe5W (2026-01-30)

### Warning Inclusion Policy
**DECISION**: Include warnings in pre-scan results (status !== 'pass' includes both fail AND warning)
**Rationale**: Matches existing addToReview() behavior for consistency

### Duplicate Prevention
**DECISION**: Pre-scan updates reviewState.reviewedElements set after creating each issue
**Rationale**: Prevents duplicates when user manually clicks "Add to Review" on already-scanned elements
