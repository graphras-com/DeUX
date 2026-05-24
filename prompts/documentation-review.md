# Documentation Review Prompt — DeUX

> **Usage:** Run this prompt against `docs/`, `src/deux/` (for docstrings), and `mkdocs.yml`.
> Repeat regularly (e.g., after each milestone, major feature merge, or API change).

---

## Role

You are a senior technical documentation reviewer. Your job is to verify that all
documentation in the DeUX project is accurate, complete, and current — then produce
actionable GitHub issues for each finding.

## Codebase Context

DeUX is an asyncio-native Python library for Elgato Stream Deck devices.

### Documentation Structure

| Location | Content |
|----------|---------|
| `docs/index.md` | Landing page: badges, features, quick-start, installation, usage example |
| `docs/architecture.md` | Embeds auto-generated SVG class and package diagrams |
| `docs/architecture/classes.svg` | Auto-generated class diagram (via `gen_diagrams.py`) |
| `docs/architecture/packages.svg` | Auto-generated package diagram (via `gen_diagrams.py`) |
| `docs/example.md` | Walkthrough of `examples/streamdeck.py` (full source embedded via snippet) |
| `docs/elgato-hid-protocol.md` | HID protocol reference (devices, reports, image chunking) |
| `docs/guides/creating-dui-packages.md` | DUI package format guide (manifest, SVG, bindings, events, spinners) |
| `docs/gen_ref_pages.py` | Build-time script: generates `reference/<pkg>.md` for each top-level sub-package |
| `docs/gen_diagrams.py` | Build-time script: regenerates architecture SVGs |
| `mkdocs.yml` | MkDocs Material config with mkdocstrings (NumPy-style), gen-files, literate-nav |

### API Reference (auto-generated at build time)

One page per top-level public sub-package via mkdocstrings directives:

- `reference/dui.md` → `::: deux.dui`
- `reference/render.md` → `::: deux.render`
- `reference/runtime.md` → `::: deux.runtime`
- `reference/tools.md` → `::: deux.tools`
- `reference/ui.md` → `::: deux.ui`

### Docstring Convention

All public code must have NumPy-style docstrings covering: purpose, parameters, return
values, raised exceptions, side effects, and examples where useful.

## Review Scope — What to Review

### 1. Accuracy

- **Docstrings vs code** — Do function/method/class docstrings match current signatures?
  Parameters added/removed/renamed but not updated in docstrings? Return types described
  incorrectly? Raises sections listing exceptions no longer raised, or missing new ones?
- **Guides vs code** — Does `creating-dui-packages.md` reflect all current binding types,
  event types, manifest fields, validation rules, and CLI tool options? Are any described
  features removed or changed?
- **Examples vs code** — Does the quick-start in `index.md` work against the current API?
  Does `example.md` accurately describe `examples/streamdeck.py`? Are embedded snippets
  current?
- **HID protocol doc vs implementation** — Does `elgato-hid-protocol.md` match the actual
  protocol implementation in `src/deux/runtime/hid/protocol.py`? Any devices, reports, or
  fields added/changed in code but not documented?
- **Architecture diagrams** — Do `classes.svg` and `packages.svg` reflect the current
  module structure and class hierarchy? (Check if `gen_diagrams.py` output is stale.)
- **Config references** — Do documented installation instructions, system requirements,
  dependency names, and version constraints match `pyproject.toml`?

### 2. Completeness

- **Missing docstrings** — Public functions, classes, methods, or modules lacking
  docstrings entirely.
- **Incomplete docstrings** — Docstrings missing Parameters, Returns, Raises, or
  description sections per NumPy-style convention.
- **Undocumented features** — New modules, classes, binding types, event types, CLI
  options, or configuration that exist in code but are not mentioned anywhere in `docs/`.
- **API reference gaps** — Nested sub-packages (`runtime.hid`, `ui.cards`, `ui.controls`,
  `render.defaults`) that may not be surfaced by the current mkdocstrings directives.
  Check if `gen_ref_pages.py` covers everything that should be public.
- **Missing guides** — Workflows or features that warrant a guide but have none.

### 3. Staleness

- **Dead links** — Internal cross-references (`[text](path)`) pointing to moved/deleted
  files. External URLs that may be broken.
- **Old module paths** — References to renamed or reorganized modules/files.
- **Removed features** — Documentation describing features, config options, functions,
  or classes that no longer exist in the codebase.
- **Version references** — Outdated version numbers, Python version requirements, or
  dependency versions in prose that contradict `pyproject.toml`.

### 4. Consistency

- **Docstring format** — Docstrings not following NumPy-style convention.
- **Terminology** — Inconsistent naming across docs and docstrings (e.g., "DUI" vs "dui"
  vs ".dui", "Stream Deck" vs "StreamDeck", "key slot" vs "KeySlot").
- **Formatting** — Broken markdown, missing code fences, inconsistent heading levels,
  malformed tables, missing admonition types.
- **Tone and style** — Inconsistent voice or level of detail across documents.

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
14. MkDocs Material + mkdocstrings as the documentation toolchain

If documentation about these areas is wrong or incomplete, flag the **documentation**
issue — do not suggest changing the underlying architecture.

## Output Format

### Per-Issue Fields

For each finding, produce:

| Field | Description |
|-------|-------------|
| **Number** | Sequential (`#1`, `#2`, `#3`, ...) for dependency references |
| **Title** | Concise, actionable (e.g., "Update `creating-dui-packages.md` with new `css_class` binding type") |
| **Type** | One of: `Task`, `Bug`, `Feature` |
| **Labels** | Combine from: **Area:** `area:docs`, `area:api`, `area:code-quality` / **Severity:** `severity:high`, `severity:med`, `severity:low`, `severity:nit` / **Other:** `documentation`, `enhancement`, `bug` |
| **Priority** | `P0` (critical), `P1` (high), `P2` (medium), `P3` (low) |
| **Size** | Estimated effort: `XS`, `S`, `M`, `L`, `XL` |
| **Body** | Markdown with three sections (see template below) |
| **Depends on** | List of issue numbers (`#N`) this is blocked by. Empty if none. |
| **Blocks** | List of issue numbers that depend on this. Empty if none. |

### Issue Body Template

```markdown
## Problem

[What is wrong, outdated, or missing. Include file paths, line numbers, and the
specific text or section that is incorrect/absent. Quote the problematic content
where helpful.]

## Suggested Fix

[Concrete guidance: what to add, remove, or rewrite. Include corrected text or
a description of what the updated content should cover.]

## Rationale

[Why this matters: user confusion, incorrect usage, missing discoverability, etc.]
```

### Priority Guide for Documentation Issues

| Priority | Use when |
|----------|----------|
| **P0** | Documentation is actively misleading — users will hit errors following it |
| **P1** | Significant inaccuracy or major missing content (undocumented public API) |
| **P2** | Minor inaccuracy, incomplete sections, or stale references |
| **P3** | Nits: formatting, style, terminology consistency |

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
  --label "documentation" \
  --label "area:docs" \
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
