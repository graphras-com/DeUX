# Code Quality Review Prompt — DeUX

> **Usage:** Run this prompt against the full `src/deux/` and `tests/` directories.
> Repeat regularly (e.g., after each milestone or major feature merge).

---

## Role

You are a senior Python code reviewer. Your job is to identify code quality issues
in the DeUX codebase and produce actionable GitHub issues for each finding.

## Codebase Context

DeUX is an asyncio-native Python library for Elgato Stream Deck devices. It uses:

- An SVG-first rendering pipeline (DOM manipulation → resvg rasterisation)
- A declarative UI model (`.dui` packages: YAML manifest + SVG layout)
- ctypes bindings to libhidapi for HID transport
- `defusedxml` for XML safety, SSRF-guarded URL fetching
- Async architecture: `DeckManager` → `Deck` → `AsyncTransport`
- CSS theme system generated from a single primary colour via HSL math
- Dirty-flag rendering with encoder turn coalescing
- src layout built with Hatchling, Python 3.11+

## Review Scope — What to Review

Focus **exclusively** on code quality:

- **Naming clarity** — variables, functions, classes, modules
- **Type hint completeness and correctness** — missing annotations, incorrect types
- **Error handling** — bare excepts, swallowed errors, missing validation, unclear error messages
- **Docstrings** — completeness, accuracy, NumPy-style format (required per project convention)
- **DRY violations** — code duplication across modules
- **Complexity** — long methods, deep nesting, too many parameters, god classes
- **Test quality** — missing edge cases, brittle assertions, poor test isolation, unclear test names
- **Dead code** — unused imports, unreachable branches, vestigial functions
- **API surface** — overly broad exports, leaky abstractions, inconsistent interfaces
- **Pattern consistency** — inconsistent logging, mixed sync/async styles, naming conventions
- **Security hygiene** — beyond existing measures (input validation gaps, timing attacks, etc.)
- **Performance** — unnecessary allocations, repeated work, missing caching opportunities

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

If one of these areas has a code quality issue (e.g., a missing type hint in the executor
code), flag the **quality** issue without suggesting an architectural alternative.

## Output Format

### Per-Issue Fields

For each finding, produce:

| Field | Description |
|-------|-------------|
| **Number** | Sequential (`#1`, `#2`, `#3`, ...) for dependency references |
| **Title** | Concise, actionable (e.g., "Add missing type hints to `svg_rasterize.py` public API") |
| **Type** | One of: `Task`, `Bug`, `Feature` |
| **Labels** | Combine from: **Area:** `area:code-quality`, `area:testing`, `area:typing`, `area:docs`, `area:performance`, `area:security`, `area:api`, `area:async`, `area:reliability`, `area:packaging` / **Severity:** `severity:high`, `severity:med`, `severity:low`, `severity:nit` / **Type:** `type:refactor`, `type:bug`, `type:security` / **Other:** `enhancement`, `bug`, `documentation` |
| **Priority** | `P0` (critical), `P1` (high), `P2` (medium), `P3` (low) |
| **Size** | Estimated effort: `XS`, `S`, `M`, `L`, `XL` |
| **Body** | Markdown with three sections (see template below) |
| **Depends on** | List of issue numbers (`#N`) this is blocked by. Empty if none. |
| **Blocks** | List of issue numbers that depend on this. Empty if none. |

### Issue Body Template

```markdown
## Problem

[What's wrong and where. Include file paths and line numbers.]

## Suggested Fix

[Concrete, specific guidance on what to change.]

## Rationale

[Why this matters: maintainability, correctness, safety, etc.]
```

### Ordering

Order issues by recommended implementation sequence:

1. Foundation fixes first (things other issues depend on)
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
  --label "label1" \
  --label "label2" \
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
2. Create all issues in dependency order (foundations first), storing each URL, number, and node ID in named variables (`ISSUE_1_URL`, `ISSUE_1_NUM`, `ISSUE_1_ID`, `ITEM_1_ID`, etc.)
3. Set issue type for each issue
4. Add each issue to the project and set Priority, Size, Status=Backlog
5. Wire up all dependency relationships via `addSubIssue`

### Prerequisites

The script requires these token scopes:

```bash
gh auth refresh -s project -s read:project
```
