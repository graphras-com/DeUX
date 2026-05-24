# Dependency Health Review Prompt — DeUX

> **Usage:** Run this prompt against `pyproject.toml`, `uv.lock`, and the output of
> the commands below. Repeat regularly (e.g., monthly, or before each release).
>
> Before running, gather dependency data:
> ```bash
> # Sync the audit extra so pip-audit is available
> uv sync --extra audit
>
> # List installed packages with versions
> uv pip list --format json > /tmp/deps-installed.json
>
> # Check for known vulnerabilities
> uv run pip-audit --format json --output /tmp/deps-audit.json 2>&1 || true
>
> # Show outdated packages
> uv pip list --outdated --format json > /tmp/deps-outdated.json 2>&1 || true
> ```
> Provide these files as context alongside `pyproject.toml` and `uv.lock`.

---

## Role

You are a senior software supply chain analyst. Your job is to assess the health,
security, and maintenance status of all dependencies in the DeUX project and produce
actionable GitHub issues for each finding.

## Codebase Context

DeUX is an asyncio-native Python library for Elgato Stream Deck devices.

### Direct Dependencies (runtime)

| Package | Constraint | Purpose |
|---------|-----------|---------|
| `pillow` | >=12.0.0 | Image manipulation, font measurement |
| `pyyaml` | >=6.0 | YAML manifest parsing |
| `platformdirs` | >=4.0 | OS-appropriate config/data directories |
| `defusedxml` | >=0.7.0 | Safe XML parsing against XXE/entity attacks |
| `resvg` | git+graphras-com/resvg-py@main | Rust-based SVG rasterisation (custom fork) |

### Direct Dependencies (test)

`pytest`, `pytest-asyncio`, `pytest-cov`, `types-PyYAML`

### Direct Dependencies (docs)

`mkdocs-material`, `mkdocstrings[python]`, `mkdocs-gen-files`, `mkdocs-literate-nav`, `pylint`

### Notable Characteristics

- `resvg-py` is installed via a **git URL** pointing to `@main` branch (not a pinned commit)
- Lock file is `uv.lock` (managed by `uv`)
- Python 3.11+ required

## Review Scope — What to Review

### 1. Known Vulnerabilities (CVEs)

- Check all direct and transitive dependencies for **known CVEs** using pip-audit output
- For each CVE: severity, affected version range, fixed version, exploitability in the
  context of DeUX's usage
- Flag any dependency where the pinned/locked version is within a vulnerable range

### 2. Outdated Dependencies

- Identify dependencies that are **significantly behind** the latest release
- Distinguish between: patch updates (safe), minor updates (usually safe), and major
  updates (may require migration)
- Prioritise updates that include security fixes or bug fixes relevant to DeUX's usage
- Note any dependencies pinned to minimum versions that are very old

### 3. Maintenance Status

- Check if any dependency is **unmaintained** (no releases in 12+ months, archived repo,
  no response to issues)
- Check for dependencies with **known succession** (e.g., a package replaced by a
  maintained fork)
- Flag dependencies with very few maintainers (bus factor = 1)

### 4. Supply Chain Risks

- **`resvg-py` git reference** — Is `@main` a stable reference? Should it be pinned to
  a commit hash or tag for reproducibility? What happens if the fork diverges?
- **Transitive dependency count** — Are there unexpectedly large dependency trees pulled
  in by any direct dependency?
- **Package integrity** — Are all packages sourced from PyPI (except resvg-py)? Any
  unexpected sources in the lock file?

### 5. License Compatibility

- Verify all dependency licenses are **compatible** with the project's license
- Flag any dependency with a viral/copyleft license (GPL, AGPL) that could affect
  distribution
- Flag any dependency with no declared license or an ambiguous one

### 6. Version Constraint Hygiene

- Are version constraints in `pyproject.toml` **appropriate**? Too loose (accepting
  known-bad versions)? Too tight (preventing security updates)?
- Are there dependencies that should have **upper bounds** to prevent breaking changes?
- Are test/docs dependencies appropriately constrained?

## Review Scope — What NOT to Review

- Do **not** suggest replacing `resvg-py` with CairoSVG or another rasteriser
- Do **not** suggest replacing `defusedxml` with another XML library
- Do **not** suggest replacing the `uv` package manager
- Do **not** suggest adding runtime dependencies that change the architecture
- Flag supply chain risks and suggest mitigations within the current dependency choices

## Output Format

### Per-Issue Fields

For each finding, produce:

| Field | Description |
|-------|-------------|
| **Number** | Sequential (`#1`, `#2`, `#3`, ...) for dependency references |
| **Title** | Concise, actionable (e.g., "Pin `resvg-py` to commit hash instead of `@main` branch") |
| **Type** | One of: `Task`, `Bug`, `Feature` |
| **Labels** | Combine from: **Area:** `area:security`, `area:packaging`, `area:reliability` / **Severity:** `severity:high`, `severity:med`, `severity:low`, `severity:nit` / **Type:** `type:security`, `type:refactor` / **Other:** `dependencies`, `bug`, `enhancement` |
| **Priority** | `P0` (critical — active CVE in used code path), `P1` (high — CVE or significant risk), `P2` (medium — outdated, maintenance concern), `P3` (low — hygiene, best practice) |
| **Size** | Estimated effort: `XS`, `S`, `M`, `L`, `XL` |
| **Body** | Markdown with sections below |
| **Depends on** | List of issue numbers (`#N`) this is blocked by. Empty if none. |
| **Blocks** | List of issue numbers that depend on this. Empty if none. |

### Issue Body Template

```markdown
## Finding

[What the issue is. Include package name, current version, affected version range,
and the specific risk or concern.]

## Recommended Action

[Concrete steps: version to upgrade to, constraint to change, commit to pin to, etc.
Include the exact change to `pyproject.toml` where applicable.]

## Risk Assessment

[Impact if not addressed: security exposure, build breakage risk, reproducibility
concern, legal risk, etc.]
```

### Ordering

Order issues by recommended implementation sequence:

1. Active CVEs first (P0/P1)
2. Supply chain risks (pinning, integrity)
3. Outdated dependencies by severity
4. Maintenance and license concerns
5. Hygiene items

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
  --label "dependencies" \
  --label "area:packaging" \
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
  --single-select-option-id "$SIZE_S"

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
