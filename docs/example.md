# Example: A Complete Stream Deck App

This page walks through [`examples/streamdeck.py`](https://github.com/graphras-com/DeUX/blob/main/examples/streamdeck.py),
a single-file demo that exercises every major DeUX feature. It is the
recommended starting point for new users — clone the repo, plug in any
Stream Deck, and run:

```bash
python examples/streamdeck.py
```

No external services are required. All state lives in memory and every
action is logged to the console.

## What it demonstrates

- **Auto-discovery and lifecycle** via `DeckManager`.
- **Loading `.dui` packages** with `load_package` and using `DuiCard` /
  `DuiKey`.
- **Declarative UI bindings** — `set`, `set_many`, `set_range`, and
  `adjust_range` keep domain values normalised for SVG renderers.
- **Refreshing from any handler** — `request_refresh()` works from key
  handlers, encoder handlers, and background tasks alike.
- **A live countdown timer** driven by an `asyncio` task that ticks
  every second.
- **A live dashboard clock** that updates only when the displayed value
  changes.
- **Multi-screen navigation** — a `main` screen and a `settings` screen
  swap atomically via `Deck.set_screen`. The dashboard encoder's
  press-release cycles screens via the `next_screen` event declared in
  `DashboardCard.dui` — no key needed.
- **All three key event sources** — `press`, `release`, and the
  higher-level `click`. Scene keys flash their colours while held to
  prove that all three fire.

## Layout

The example is structured as a set of single-purpose **controllers**
that each own one widget plus its state. A top-level
`StreamDeckApp` wires them together and hooks into the manager.

```
StreamDeckApp
├── AudioController        ── AudioCard.dui      (touch-strip card 0)
├── LightsController       ── LightCard.dui      (touch-strip card 1)
├── TimerController        ── TimerCard.dui      (touch-strip card 2)
├── DashboardController    ── DashboardCard.dui  (touch-strip card 3)
├── FavoritesController    ── PictureKey.dui     (keys 0..N favourites)
├── SceneController        ── IconKey.dui        (remaining keys)
└── ScreenCycler           ── (no widget; bound to dashboard's
                                 ``next_screen`` event)
```

Controllers never talk to the deck directly. They mutate their card's
bindings via `set`/`set_many` and call `card.request_refresh()` when the
display needs to update. The deck transparently re-renders dirty regions
on the next refresh tick.

## The lifecycle

The example follows the canonical DeUX flow:

```python
async def run() -> None:
    app = StreamDeckApp(MEDIA_CATALOG, SCENE_DEFS)
    manager = DeckManager(brightness=60, auto_reconnect=True)

    @manager.on_connect()
    async def _on_connect(deck):
        await app.on_connect(deck)

    @manager.on_disconnect
    async def _on_disconnect(info):
        await app.on_disconnect(info)

    async with manager:
        await manager.wait_closed()
```

`DeckManager` discovers connected devices, calls `on_connect` once a
deck is ready, and re-fires it on reconnects when `auto_reconnect=True`.
On disconnect, the example shuts down its background tasks cleanly.

> **Note:** the two hooks have different shapes. `on_connect()` is a
> decorator factory (call with parens) and accepts optional `serial=` /
> `deck_type=` filters to scope the handler to specific devices.
> `on_disconnect` is a property that returns the decorator directly — use
> it bare, without parens (`@manager.on_disconnect`). Calling
> `@manager.on_disconnect()` will raise `TypeError`.

## Highlights

### Real countdown timer

`TimerController` runs an `asyncio` task that decrements a counter once
per second. When the user toggles, resets, or adjusts the duration,
state is mutated and a refresh requested — the task itself does no UI
work directly.

```python
async def _tick_loop(self) -> None:
    while True:
        await asyncio.sleep(self.TICK_INTERVAL_S)
        if not self.is_running:
            continue
        if self.remaining > 0:
            self.remaining -= 1
            self._sync_card()
            await self._card.request_refresh()
        if self.remaining <= 0 and self.is_running:
            self.is_running = False
            self._sync_card()
            await self._card.request_refresh()
```

The `request_refresh()` call is wired automatically when the screen is
activated — no need to pass the deck handle into the controller.

### Press, release, and click on the same key

Scene keys register all three handlers. The press/release pair invert
the foreground and background colours so the key visually flashes while
held; click logs the scene name:

```python
@key.on("press")
async def _press():
    key.set_many(background=FG, foreground=BG)
    await key.request_refresh()

@key.on("release")
async def _release():
    key.set_many(background=BG, foreground=FG)
    await key.request_refresh()

@key.on("click")
async def _click():
    log.info("Scene activated: %s", label)
```

### Two screens, cycled by an encoder press

`ScreenCycler` swaps between a busy `main` screen (favourites, scenes,
all four cards) and a focused `settings` screen (dashboard and lights
only). The dashboard card stays in the same slot on every screen so
the encoder used to cycle screens is always the rightmost one. The
same controllers appear on both — DeUX re-renders whatever is
installed on the active screen.

The cycler doesn't own any widget. Instead, `DashboardCard.dui`
declares a `next_screen` event mapped to an encoder press-release, and
the cycler binds a handler to that event:

```python
class ScreenCycler:
    def attach(self, card: DuiCard, event: str = "next_screen") -> None:
        @card.on(event)
        async def _trigger() -> None:
            await self.advance()

    async def advance(self) -> None:
        if self._deck is None:
            return
        self._index = (self._index + 1) % len(self._screens)
        await self._deck.set_screen(self._screens[self._index])
```

The corresponding manifest fragment in `DashboardCard.dui`:

```yaml
events:
  - name: next_screen
    source: encoder_press_release
    max_duration_ms: 250
```

This keeps every key slot available for favourites and scenes while
still giving the user a one-press way to flip between layouts.

## Try it

Once running, here are some interactions to try:

| Action | Effect |
| ------ | ------ |
| Press a favourite key (cover art) | Starts that track; AudioCard updates instantly |
| Press and hold a scene key | Key inverts colours; releases to log the scene |
| Hold the audio encoder | Toggles play/pause |
| Turn the audio encoder | Volume up/down |
| Click the audio encoder | Mute toggle |
| Press + turn the audio encoder | Previous/next track |
| Click the timer encoder | Start or pause the countdown |
| Hold the timer encoder | Reset the timer |
| Turn the timer encoder | Add/remove 30 seconds |
| Press the dashboard encoder | Cycle to the next screen |

## Full source

The complete example, embedded straight from the repository so it stays
in sync with what you'll run locally:

```python title="examples/streamdeck.py"
--8<-- "examples/streamdeck.py"
```

## Related

- [Creating DUI Packages](guides/creating-dui-packages.md) — how to
  build your own `.dui` cards and keys.
- [API Reference](reference/runtime.md) — full library API documentation.
