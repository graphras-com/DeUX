# Security Review Prompt — DeUX

> **Usage:** Run this prompt against `src/deux/`, `tests/`, and `pyproject.toml`.
> Repeat regularly (e.g., before each release, after adding network-facing code,
> or when DUI package loading changes).

---

## Role

You are a senior application security reviewer specialising in Python libraries that
handle untrusted input, network I/O, and hardware interfaces. Your job is to identify
security issues in the DeUX codebase and produce actionable GitHub issues for each finding.

## Codebase Context

DeUX is an asyncio-native Python library for Elgato Stream Deck devices. Security-relevant
characteristics:

- **Untrusted input:** `.dui` packages (YAML manifests + SVG templates + image assets)
  may come from third-party authors or a future public repository
- **XML parsing:** SVG templates are parsed and manipulated at the DOM level; currently
  guarded by `defusedxml` via `_xml.py:safe_fromstring()`
- **Network I/O:** Iconify icon fetching and image URL resolution; currently guarded by
  SSRF protection in `_url_safety.py`
- **SVG rasterisation:** Untrusted SVG content is passed to `resvg` for rendering
- **HID transport:** ctypes bindings to libhidapi (`runtime/hid/_ctypes_hidapi.py`)
  with direct memory buffer operations
- **YAML parsing:** Manifest files parsed via PyYAML
- **CI:** Gitleaks scans for leaked secrets

## Review Scope — What to Review

### 1. Input Validation

- **DUI package loading** (`dui/loader.py`) — Are all manifest fields validated? Can
  malformed YAML cause crashes or unexpected behaviour? Are there path traversal risks
  in asset references? Can a `.dui` package reference files outside its directory?
- **SVG content** — Beyond XXE (handled by defusedxml), are there SVG-specific attack
  vectors? `<script>` tags, `<foreignObject>`, external references (`xlink:href` to
  remote URLs), CSS `@import` or `url()` in inline styles, event handlers (`onload`,
  `onclick`)?
- **Binding values** — When user-supplied data is injected into SVG via bindings (text,
  image, color, etc.), is it sanitised? Can binding values inject SVG/XML markup?
- **YAML safety** — Is `yaml.safe_load()` used consistently, or are there any paths
  using `yaml.load()` with the default (unsafe) loader?

### 2. Network Security

- **SSRF protection** (`_url_safety.py`) — Is the allow/deny list comprehensive? Are
  there bypass vectors (DNS rebinding, IPv6 mapped addresses, URL encoding tricks,
  redirect following)?
- **Iconify client** (`dui/iconify.py`) — Is the response from the Iconify API treated
  as untrusted? Is the returned SVG parsed safely? Are there cache poisoning risks?
- **Image fetching** (`render/image_fetch.py`) — Same questions: response validation,
  content-type checking, size limits, timeout enforcement?
- **TLS verification** — Are all outbound HTTPS requests verifying certificates?

### 3. Memory and Buffer Safety

- **ctypes HID bindings** (`runtime/hid/_ctypes_hidapi.py`) — Buffer allocation sizes,
  null pointer checks, use-after-free potential, buffer overflows in read/write paths.
- **Image processing** — Are there decompression bomb protections on images loaded via
  Pillow? (`PIL.Image.MAX_IMAGE_PIXELS`)
- **LRU cache** (`render/svg_rasterize.py`) — Can cache entries grow unboundedly in
  individual entry size? Is the SHA-256 keying scheme collision-resistant in practice?

### 4. Concurrency Safety

- **Shared executor** (`runtime/_executor.py`) — Thread safety of shared state accessed
  from both the executor threads and the asyncio event loop.
- **AsyncTransport** — Race conditions in connect/disconnect/reconnect sequences.
- **Event routing** — Can malicious or rapid input cause unbounded queue growth or
  event loop starvation?

### 5. Dependency Security

- **Known CVEs** — Check current pinned versions of `pillow`, `pyyaml`, `defusedxml`,
  `resvg-py`, `platformdirs` against known vulnerabilities.
- **Supply chain** — `resvg-py` is a custom fork installed via `git+` URL. Is the
  reference pinned to a commit hash or only a branch (`@main`)?

### 6. Secrets and Credentials

- **Hardcoded secrets** — API keys, tokens, or credentials in source code (beyond
  gitleaks coverage).
- **Config files** — Do any config paths or defaults risk exposing sensitive data?

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

Flag security issues **within** these systems without suggesting replacements.

## Output Format

### Per-Issue Fields

For each finding, produce:

| Field | Description |
|-------|-------------|
| **Number** | Sequential (`#1`, `#2`, `#3`, ...) for dependency references |
| **Title** | Concise, actionable (e.g., "Sanitise text binding values to prevent SVG injection") |
| **Type** | One of: `Task`, `Bug`, `Feature` |
| **Labels** | Combine from: **Area:** `area:security`, `area:async`, `area:reliability`, `area:api`, `area:packaging` / **Severity:** `severity:high`, `severity:med`, `severity:low`, `severity:nit` / **Type:** `type:security`, `type:bug` / **Other:** `bug`, `enhancement` |
| **Priority** | `P0` (critical — exploitable vulnerability), `P1` (high — significant risk), `P2` (medium — defence-in-depth), `P3` (low — hardening) |
| **Size** | Estimated effort: `XS`, `S`, `M`, `L`, `XL` |
| **Body** | Markdown with sections below |
| **Depends on** | List of issue numbers (`#N`) this is blocked by. Empty if none. |
| **Blocks** | List of issue numbers that depend on this. Empty if none. |

### Issue Body Template

```markdown
## Vulnerability / Risk

[What the issue is, where it exists (file paths + line numbers), and what an
attacker could achieve by exploiting it. Include attack scenario if applicable.]

## Suggested Fix

[Concrete, specific remediation guidance. Include code patterns where helpful.]

## Severity Rationale

[Why this severity level: exploitability, impact, prerequisites, existing mitigations.]
```

### Priority Guide for Security Issues

| Priority | Use when |
|----------|----------|
| **P0** | Exploitable vulnerability with no mitigating controls (RCE, arbitrary file read, SSRF bypass) |
| **P1** | Significant risk requiring specific conditions or partial mitigation exists |
| **P2** | Defence-in-depth improvement; not directly exploitable but reduces attack surface |
| **P3** | Hardening; best-practice alignment with minimal current risk |

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
  --label "area:security" \
  --label "type:security" \
  --label "severity:high" \
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
  --single-select-option-id "$PRIORITY_P1"

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
