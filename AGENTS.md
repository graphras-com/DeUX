# AGENTS.md

## Project

DeckUI — asyncio-native Python library for Elgato Stream Deck devices. Single package at `src/deckui`, built with Hatchling.

## Setup

```bash
uv sync --extra test        # uses uv.lock; Python 3.11+ required
```

System deps (CI uses `libcairo2-dev libhidapi-dev`; on macOS: `brew install cairo hidapi`).

## Mandatory workflow — read this FIRST

You MUST follow this sequence for every task. Do not write any code before step 1.

1. **Create a branch** from up-to-date `main`:
   ```
   git checkout main && git pull
   git checkout -b <prefix>/<name>
   ```
2. **Do the work.**
3. **Run the full test suite** — every test must pass before you commit:
   ```
   python -m pytest tests/ --cov=deckui --cov-report=term-missing --cov-fail-under=95
   ```
4. **Commit** — only after all tests pass.
5. **Push and create a PR**:
   ```
   git push -u origin <branch>
   gh pr create --title "..." --body "..."
   ```

**Never commit directly to `main`.** No exceptions.

## Commands

```bash
ruff check .                              # lint
mypy                                      # typecheck (strict mode)
pytest                                    # run all tests
pytest --cov=deckui --cov-fail-under=95   # tests with coverage gate
pytest tests/test_screen.py               # single test file
pytest -k test_name                       # single test
```

CI runs: lint, build, typecheck, tests (3.11/3.12/3.13), gitleaks. All must pass for the quality gate.

## Architecture

- `src/deckui/runtime/` — device discovery, capabilities, transport
- `src/deckui/ui/` — Screen, KeySlot, EncoderSlot, TouchStrip controls
- `src/deckui/dsui/` — `.dui` package format (SVG layout + YAML manifest, data bindings, event maps)
- `src/deckui/render/` — image rendering, metrics
- `src/deckui/tools/` — CLI utilities

## Testing

- `asyncio_mode = "auto"` — async tests need no `@pytest.mark.asyncio`
- All hardware is mocked via `conftest.py` fixtures (`mock_streamdeck_device`, etc.) — no real device needed
- `.dui` test packages are built in `tmp_path` by `conftest.py` helpers (`card_dsui_path`, `key_dsui_path`)
- Coverage threshold: **95%**

## Style

- Ruff: line length 100, target py311, rules: E/W/F/I/B/UP/C4/SIM (B008 ignored)
- `tests/*` ignores B011
- mypy strict with `ignore_missing_imports` for `StreamDeck.*` and `cairosvg`
- Wheel packages from `src/deckui` (src layout)
