# Error Handling

Every exception raised by DeUX inherits from a single root class,
[`deux.DeuxError`][deux.DeuxError]. A single `except deux.DeuxError`
handler is therefore sufficient to catch any library error without
masking unrelated exceptions from your own code.

```python
import deux

try:
    card = deux.DuiCard("DashboardCard")
except deux.DeuxError as exc:
    log.error("DUI load failed: %s", exc)
```

## Exception hierarchy

```
DeuxError
├── DeckError              # runtime device / transport failures
├── PackageError           # malformed or unloadable .dui packages
├── SSRFError              # blocked private / loopback URL access
├── IconifyError           # iconify fetch / cache failures
├── ImageFetchError        # image binding fetch failures
├── RasterizeError         # SVG rasterisation failures
└── SplashError            # splash-screen rendering failures
```

The publicly re-exported names from `deux` are
[`DeuxError`][deux.DeuxError], [`DeckError`][deux.runtime.DeckError],
[`PackageError`][deux.dui.PackageError], and
[`SSRFError`][deux.SSRFError].
The remaining classes are accessible through their owning sub-packages
(for example [`IconifyError`][deux.dui.IconifyError],
[`ImageFetchError`][deux.render.ImageFetchError]).

## URL safety and SSRF

`.dui` packages are designed to be distributed between users. To
mitigate Server-Side Request Forgery (SSRF), DeUX validates every URL
used by `image:` and `iconify:` bindings before fetching. Hostnames are
resolved via DNS and rejected when any resulting IP address falls in a
blocked range:

- Loopback — `127.0.0.0/8`, `::1`
- Private (RFC 1918) — `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`
- Link-local — `169.254.0.0/16`, `fe80::/10`
- Cloud metadata — `169.254.169.254`

A blocked request raises [`SSRFError`][deux.SSRFError]:

```python
import deux

try:
    deux.DuiCard("SomeCard")  # contains image binding to 192.168.1.1
except deux.SSRFError as exc:
    log.warning("Blocked private URL in DUI: %s", exc)
```

### Allowing private URLs

If you genuinely need to fetch from LAN resources (a local Home
Assistant, a self-hosted icon server, …) opt in explicitly with
[`set_allow_private_urls`][deux.set_allow_private_urls]:

```python
import deux

# Permit private / loopback / link-local addresses for this process.
deux.set_allow_private_urls(True)
```

This is process-global; only enable it when you trust the DUI packages
your application loads.

## Patterns

**Fail fast on package load:** catch `PackageError` during startup to
surface broken packages before the device session begins.

```python
try:
    deux.load_all_packages()
except deux.PackageError as exc:
    sys.exit(f"Refusing to start with bad DUI packages: {exc}")
```

**Resilient runtime:** within event handlers, catch the narrow
sub-class you care about and let everything else bubble up to the deck
manager's logger.

```python
@card.on("refresh")
async def handle():
    try:
        await refresh_data()
    except deux.DeckError as exc:
        log.warning("device unavailable, skipping refresh: %s", exc)
```

## See also

- [`deux.DeuxError`][deux.DeuxError]
- [`deux.runtime.DeckError`][deux.runtime.DeckError]
- [`deux.dui.PackageError`][deux.dui.PackageError]
- [`deux.SSRFError`][deux.SSRFError]
- [`deux.set_allow_private_urls`][deux.set_allow_private_urls]
