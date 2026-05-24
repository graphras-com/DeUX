# Test Coverage Gap Review Prompt — DeUX

> **Usage:** Run this prompt against `src/deux/`, `tests/`, and `conftest.py`.
> Repeat regularly (e.g., after major features, refactors, or when coverage drops).
>
> Before running, generate a fresh coverage report:
> ```bash
> uv sync --extra test
> uv run python -m pytest tests/ --cov=deux --cov-report=term-missing --cov-report=json
> ```
> Provide the output or `coverage.json` as context alongside the source and test files.

---

## Role

You are a senior test engineer specialising in async Python libraries with hardware
interfaces. Your job is to identify meaningful gaps in the test suite — not just
uncovered lines, but untested behaviours, missing edge cases, and fragile test patterns
— then produce actionable GitHub issues for each finding.

## Codebase Context

DeUX is an asyncio-native Python library for Elgato Stream Deck devices.

### Test Infrastructure

- **Framework:** pytest with `pytest-asyncio` (`asyncio_mode = "auto"`)
- **Coverage gate:** 95% minimum (`--cov-fail-under=95`)
- **Mocking:** All hardware is mocked via `conftest.py` fixtures (`mock_streamdeck_device`,
  etc.) — no real device needed
- **DUI test packages:** Built in `tmp_path` by conftest helpers (`card_dui_path`,
  `key_dui_path`)
- **Test matrix:** Python 3.11, 3.12, 3.13 in CI
- **53 test files** covering all modules

### Key Async Patterns to Test

- `DeckManager`: auto-discovery, hot-plug detection, reconnection via polling
- `Deck`: event loop, screen switching, timeout checking (deadline-driven)
- `AsyncTransport`: HID read loop → asyncio queue bridge
- `DeckEventRouter`: key/encoder/touch dispatch, encoder turn coalescing
- Dirty-flag rendering: only re-renders changed controls
- `AsyncEvent`: multi-subscriber pub/sub

### Key Non-Async Patterns to Test

- `SvgRenderer`: binding dispatch table, all 11 binding types
- `DUI loader`: exhaustive manifest validation (1000+ lines)
- HID protocol: USB report formatting, image chunking
- Theme: HSL colour math, CSS generation
- SVG rasterisation: LRU cache, CSS injection, layer compositing

## Review Scope — What to Review

### 1. Untested Behaviours

- Public methods/functions with **no corresponding test** at all
- Code paths that exist but are not exercised (use coverage report `missing` lines)
- Behaviours documented in docstrings that have no test asserting them
- Return values or side effects that are never verified

### 2. Missing Edge Cases

- **Error paths** — What happens when things fail? Are exceptions raised, caught, or
  propagated correctly? Test: invalid input, network failures, device disconnection
  mid-operation, corrupted DUI packages, malformed SVG, HID read timeouts
- **Boundary conditions** — Empty collections, zero-length inputs, maximum values,
  off-by-one scenarios in image chunking, screen indices, key indices
- **Concurrency edge cases** — Cancellation during async operations, concurrent
  connect/disconnect, rapid event bursts, executor thread pool exhaustion,
  event loop shutdown during pending tasks
- **Reconnection scenarios** — Device removed and re-added, device replaced with
  different model, multiple simultaneous disconnections
- **Resource cleanup** — Are context managers tested for cleanup on both normal exit
  and exception paths? Are file handles, HID handles, and executor threads released?

### 3. Mock Quality

- **Overly permissive mocks** — Mocks that accept any input and return success,
  hiding real validation or error paths. Mocks that don't verify call arguments.
- **Missing mock assertions** — Tests that set up mocks but never assert they were
  called (or called with expected arguments)
- **Mock vs real behaviour drift** — Mock fixtures that no longer match the interface
  of what they're mocking (e.g., missing new parameters, wrong return types)
- **Incomplete mock coverage** — Hardware behaviours that aren't represented in the
  mock fixtures (e.g., specific device quirks, protocol edge cases)

### 4. Test Fragility

- **Time-dependent tests** — Tests using `asyncio.sleep()` with fixed durations that
  may flake on slow CI. Should use `asyncio.Event` or similar deterministic signals.
- **Order-dependent tests** — Tests that pass only when run in a specific order or
  that share mutable state via module-level variables or class attributes.
- **Assertion quality** — Tests that assert too little (just "no exception") or too
  much (brittle exact-match on implementation details that may change).
- **Test naming** — Unclear test names that don't describe what behaviour is being
  verified.

### 5. Integration Test Gaps

- **Cross-module interactions** — Are there tests that verify the full pipeline
  (e.g., DUI package load → binding apply → SVG render → image output)?
- **Multi-device scenarios** — Does the test suite cover `DeckManager` with multiple
  simultaneous devices?
- **Screen switching** — Is the full screen lifecycle tested (create → activate →
  render → switch → deactivate)?

## Review Scope — What NOT to Review

Do **not** suggest changes to these settled architectural decisions:

1. SVG-first rendering pipeline (SVG DOM manipulation → resvg rasterisation)
2. Use of `resvg-py` (custom fork) instead of CairoSVG or other rasterisers
3. ctypes bindings to libhidapi (not the Python `hid` package)
4. The `.dui` package format (YAML manifest + SVG layout + assets)
5. `defusedxml` for XML safety
6. The async architecture (`DeckManager` → `Deck` → `AsyncTransport` pattern)
7. HID I/O via shared `ThreadPoolExecutor` + `run_in_executor`
8. The binding dispatch table pattern in `SvgRenderer`
9. The CSS theme system (HSL colour math from primary colour)
10. Dirty-flag rendering approach
11. Encoder turn coalescing
12. src layout with Hatchling build system
13. Existing CI pipeline structure

Do **not** suggest replacing the mock-based testing approach with real hardware tests.
Flag test quality issues without changing the testing strategy.

## Output Format

### Per-Issue Fields

For each finding, produce:

| Field | Description |
|-------|-------------|
| **Number** | Sequential (`#1`, `#2`, `#3`, ...) for dependency references |
| **Title** | Concise, actionable (e.g., "Add tests for `DeckManager` reconnection after device hot-swap") |
| **Type** | One of: `Task`, `Bug`, `Feature` |
| **Labels** | Combine from: **Area:** `area:testing`, `area:async`, `area:reliability`, `area:security` / **Severity:** `severity:high`, `severity:med`, `severity:low`, `severity:nit` / **Type:** `type:bug`, `type:refactor` / **Other:** `enhancement`, `bug` |
| **Priority** | `P0` (critical — untested path that will cause production bugs), `P1` (high — significant gap), `P2` (medium — missing edge case), `P3` (low — hardening, nit) |
| **Size** | Estimated effort: `XS`, `S`, `M`, `L`, `XL` |
| **Body** | Markdown with sections below |
| **Depends on** | List of issue numbers (`#N`) this is blocked by. Empty if none. |
| **Blocks** | List of issue numbers that depend on this. Empty if none. |

### Issue Body Template

```markdown
## Gap

[What is not tested. Include the source file path and line numbers of the untested
code, and describe the behaviour or scenario that lacks coverage.]

## Suggested Tests

[Concrete test cases to add. Include test function names, key assertions, and any
fixture or mock setup needed. Be specific enough that a developer can implement
the test without ambiguity.]

## Rationale

[Why this gap matters: what bugs could go undetected, what regressions could slip
through, what confidence is missing.]
```

### Priority Guide for Test Gap Issues

| Priority | Use when |
|----------|----------|
| **P0** | Critical path with no test coverage — bugs here would cause visible failures |
| **P1** | Important behaviour tested only on the happy path; error/edge cases missing |
| **P2** | Edge case or secondary path with no coverage |
| **P3** | Test quality nit (naming, fragility, assertion strength) |

### Ordering

Order issues by recommended implementation sequence:

1. Foundation fixes first (things other issues depend on, e.g., fixture improvements)
2. Then by priority (P0 → P3)
3. Within same priority, smaller sizes first

### Post-Issue Deliverables

After the issue list, provide:

1. A **dependency graph** in Mermaid format showing blocked-by relationships
2. A **summary table** with columns: `#`, Title, Type, Priority, Size, Labels, Blocked By

---

## Execution Script

After the review, generate a **complete, copy-pasteable bash script** that creates all
issues on GitHub, adds them to the project, sets all fields, and wires up dependencies.

Use the following constants, IDs, and patterns.

### Constants

```bash
OWNER="graphras-com"
REPO="DeUX"
REPO_ID="R_kgDOR3asLg"
PROJECT_NUMBER=2
PROJECT_ID="PVT_kwDOECHs484BWOyq"

# Issue Type IDs
TYPE_TASK="IT_kwDOECHs484B6of5"
TYPE_BUG="IT_kwDOECHs484B6of6"
TYPE_FEATURE="IT_kwDOECHs484B6of7"

# Project Field IDs
PRIORITY_FIELD_ID="PVTSSF_lADOECHs484BWOyqzhRkwf4"
SIZE_FIELD_ID="PVTSSF_lADOECHs484BWOyqzhRkwf8"
STATUS_FIELD_ID="PVTSSF_lADOECHs484BWOyqzhRkwYw"

# Priority Option IDs
PRIORITY_P0="79628723"
PRIORITY_P1="0a877460"
PRIORITY_P2="da944a9c"
PRIORITY_P3="e2ede371"

# Size Option IDs
SIZE_XS="6c6483d2"
SIZE_S="f784b110"
SIZE_M="7515a9f1"
SIZE_L="817d0097"
SIZE_XL="db339eb2"

# Status Option IDs
STATUS_BACKLOG="f75ad846"
```

### Per-Issue Pattern

For each issue, the script must:

```bash
# 1. Create the issue
ISSUE_N_URL=$(gh issue create \
  --repo "$OWNER/$REPO" \
  --title "TITLE" \
  --label "area:testing" \
  --label "severity:med" \
  --body "BODY_MARKDOWN" \
  --project "DeUX Development")

# 2. Extract issue number and node ID
ISSUE_N_NUM=$(echo "$ISSUE_N_URL" | grep -oE '[0-9]+$')
ISSUE_N_ID=$(gh api graphql -f query='
  query($owner:String!, $repo:String!, $number:Int!) {
    repository(owner:$owner, name:$repo) {
      issue(number:$number) { id }
    }
  }' -f owner="$OWNER" -f repo="$REPO" -F number="$ISSUE_N_NUM" \
  --jq '.data.repository.issue.id')

# 3. Set issue type
gh api graphql -f query='
  mutation($id:ID!, $typeId:ID!) {
    updateIssue(input:{id:$id, issueTypeId:$typeId}) {
      issue { id }
    }
  }' -f id="$ISSUE_N_ID" -f typeId="$TYPE_TASK"

# 4. Add to project and get item ID
ITEM_N_ID=$(gh project item-add $PROJECT_NUMBER \
  --owner "$OWNER" \
  --url "$ISSUE_N_URL" \
  --format json | jq -r '.id')

# 5. Set Priority
gh project item-edit \
  --id "$ITEM_N_ID" \
  --project-id "$PROJECT_ID" \
  --field-id "$PRIORITY_FIELD_ID" \
  --single-select-option-id "$PRIORITY_P2"

# 6. Set Size
gh project item-edit \
  --id "$ITEM_N_ID" \
  --project-id "$PROJECT_ID" \
  --field-id "$SIZE_FIELD_ID" \
  --single-select-option-id "$SIZE_M"

# 7. Set Status to Backlog
gh project item-edit \
  --id "$ITEM_N_ID" \
  --project-id "$PROJECT_ID" \
  --field-id "$STATUS_FIELD_ID" \
  --single-select-option-id "$STATUS_BACKLOG"
```

### Dependency Wiring Pattern

After all issues are created, wire up dependencies using sub-issues.
The **parent** is the issue that must be done first (the blocker).
The **sub-issue** is the issue that depends on it.

```bash
# Make ISSUE_2 depend on ISSUE_1:
# ISSUE_1 is the parent (blocker), ISSUE_2 is the sub-issue (blocked)
gh api graphql -f query='
  mutation($parentId:ID!, $subIssueId:ID!) {
    addSubIssue(input:{issueId:$parentId, subIssueId:$subIssueId}) {
      issue { id }
    }
  }' -f parentId="$ISSUE_1_ID" -f subIssueId="$ISSUE_2_ID"
```

### Script Structure

The generated script must follow this order:

1. Set all constants (repo ID, type IDs, field IDs, option IDs)
2. Create all issues in dependency order (foundations first), storing each URL, number,
   and node ID in named variables (`ISSUE_1_URL`, `ISSUE_1_NUM`, `ISSUE_1_ID`,
   `ITEM_1_ID`, etc.)
3. Set issue type for each issue
4. Add each issue to the project and set Priority, Size, Status=Backlog
5. Wire up all dependency relationships via `addSubIssue`

### Prerequisites

The script requires these token scopes:

```bash
gh auth refresh -s project -s read:project
```
