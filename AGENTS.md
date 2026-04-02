# AGENTS.md

Instructions for AI coding agents working on the **deckboard** repository.

## Project overview

Deckboard is a high-level, asyncio-native Python library for Elgato Stream Deck+ devices. It wraps the low-level `python-elgato-streamdeck` HID library and provides a clean API for buttons, dials, touchscreen widgets, icons, and page management.

### Tech stack

- **Language:** Python 3.11+
- **Build system:** Hatchling (`pyproject.toml`)
- **Async:** asyncio (native, no third-party event loop)
- **Dependencies:** Pillow, streamdeck, cairosvg, httpx
- **Testing:** pytest, pytest-asyncio, pytest-cov
- **Linting:** Ruff
- **Type checking:** mypy (strict mode)
- **CI:** GitHub Actions with reusable workflows

### Repository structure

```
src/deckboard/          # Library source code
  __init__.py           # Public API surface
  _transport.py         # Async bridge for HID callbacks
  button.py             # Button abstraction
  deck.py               # Main Deck class (entry point)
  dial.py               # Dial abstraction
  icon.py               # Icon fetching (Iconify API) and caching
  image.py              # Image rendering helpers (key/touchscreen composition)
  page.py               # Page management
  touchscreen.py        # Widget and TouchScreen abstractions
  types.py              # Event types and data classes
tests/                  # Test suite (287 tests, 100% coverage)
  conftest.py           # Shared fixtures
  test_*.py             # One test file per source module
.github/workflows/
  ci.yml                # CI caller workflow
  python-test.yml       # Reusable test workflow
```

## Git workflow

**All development must happen on task/feature-specific branches. Never commit directly to `main`.**

### Branch naming

Use descriptive branch names with a prefix:

- `feature/<name>` — new functionality
- `fix/<name>` — bug fixes
- `refactor/<name>` — code restructuring
- `docs/<name>` — documentation changes
- `ci/<name>` — CI/CD changes

### Development process

1. **Create a branch** from `main` before starting work:
   ```
   git checkout main && git pull
   git checkout -b feature/<name>
   ```

2. **Run tests before every commit** to ensure nothing is broken:
   ```
   python -m pytest tests/ --cov=deckboard --cov-report=term-missing --cov-fail-under=95
   ```

3. **Only commit when all tests pass.** Do not commit with failing tests.

4. **Push the branch** and **create a pull request** when the task is complete:
   ```
   git push -u origin feature/<name>
   gh pr create --title "..." --body "..."
   ```

5. PRs must target `main` and CI must pass before merging.

### Commit messages

Follow this style (see existing history):

- Start with a verb: `Add`, `Fix`, `Update`, `Refactor`, `Remove`
- First line: concise summary (imperative mood)
- Optional body: explain the "why", not the "what"

## Testing

### Running tests

```bash
# Full suite with coverage
python -m pytest tests/ --cov=deckboard --cov-report=term-missing

# Single file
python -m pytest tests/test_deck.py -v

# Single test
python -m pytest tests/test_deck.py::TestDeckEventLoop::test_event_loop_timeout_continues -v
```

### Test requirements

- **Coverage must stay at or above 95%.** The CI enforces this gate.
- Every source module has a corresponding `tests/test_<module>.py` file.
- Shared fixtures live in `tests/conftest.py`.
- All async tests use `asyncio_mode = "auto"` (no `@pytest.mark.asyncio` needed).
- Hardware interactions (Stream Deck HID device) must be **mocked** — tests must run without physical hardware.
- Use `unittest.mock.MagicMock` / `AsyncMock` for device mocking.

### Writing new tests

- Place tests in the appropriate `test_<module>.py` file.
- Group related tests in classes (e.g., `class TestDeckDispatch:`).
- If adding a new source module, create a corresponding test file.
- Test edge cases and error paths, not just the happy path.

## Code style

- **Ruff** handles linting and import sorting. Config is in `pyproject.toml`:
  ```
  select = ["E", "F", "I", "N", "UP", "B", "SIM", "TCH"]
  ```
- **mypy** runs in strict mode targeting Python 3.11.
- Use type annotations everywhere.
- Use `from __future__ import annotations` in every file.

## CI/CD

CI runs automatically on pushes to `main`, PRs targeting `main`, and manual dispatch.

- **`ci.yml`** — Caller workflow. Invokes the reusable test workflow.
- **`python-test.yml`** — Reusable workflow. Tests against Python 3.11, 3.12, 3.13 on Ubuntu. Enforces 95% coverage minimum. Uploads coverage XML as artifact.

System dependencies required in CI: `libcairo2-dev`, `libhidapi-dev`.

## Important reminders

1. **Never push directly to `main`.** Always use a feature branch + PR.
2. **Always run the full test suite before committing.** All 287+ tests must pass.
3. **Maintain coverage at 95%+.** Add tests for any new code.
4. **Create a PR when the task is done.** Include a summary of changes.
5. **Do not commit secrets** (`.env`, keys, credentials). The `.gitignore` is already configured.
6. **Mock all hardware.** Tests must work without a physical Stream Deck device.
