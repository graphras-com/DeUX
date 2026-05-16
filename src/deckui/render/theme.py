"""Theme system for generating CSS colour palettes from a primary colour.

A :class:`Theme` encapsulates a primary colour, font family, and the
derived 18-class CSS colour palette used by DUI SVG layouts.  Themes
can be applied at three levels — system-wide, per-deck, or per-screen —
with a cascade where the most specific level wins.

Examples
--------
Use the built-in default theme::

    from deckui import Theme
    theme = Theme.default()      # rgb(39, 87, 179), Inter

Create a custom theme::

    theme = Theme.from_color(255, 0, 128, font_family="Roboto")

Generate a random theme::

    theme = Theme.from_random()
"""

from __future__ import annotations

import colorsys
import logging
import random

logger = logging.getLogger(__name__)

# Default primary colour: rgb(39, 87, 179)
_DEFAULT_PRIMARY: tuple[int, int, int] = (39, 87, 179)
_DEFAULT_FONT_FAMILY = "Inter"

# Fallback font stack appended after the primary font family.
_FALLBACK_FONTS = "system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"


class Theme:
    """An immutable colour theme derived from a single primary colour.

    A theme contains a primary RGB colour, a font family, the derived
    18-class CSS palette, and the complete CSS stylesheet string ready
    for :func:`~deckui.set_svg_stylesheet`.

    Instances are created via the factory class methods
    :meth:`default`, :meth:`from_color`, or :meth:`from_random`.

    Parameters
    ----------
    primary : tuple[int, int, int]
        Primary colour as ``(r, g, b)`` with channels in 0–255.
    font_family : str
        CSS font-family name (e.g. ``"Inter"``).

    Attributes
    ----------
    primary : tuple[int, int, int]
        The primary RGB colour.
    font_family : str
        The configured font family name.
    palette : dict[str, str]
        Mapping of CSS class name to hex colour (18 entries).
    css : str
        Complete CSS stylesheet string.
    """

    __slots__ = ("_primary", "_font_family", "_palette", "_css")

    def __init__(
        self,
        primary: tuple[int, int, int],
        font_family: str = _DEFAULT_FONT_FAMILY,
    ) -> None:
        self._primary = primary
        self._font_family = font_family
        self._palette = _generate_palette(
            (float(primary[0]), float(primary[1]), float(primary[2]))
        )
        self._css = _palette_to_css(self._palette, self._font_family)

    # --- public properties ---

    @property
    def primary(self) -> tuple[int, int, int]:
        """The primary RGB colour."""
        return self._primary

    @property
    def font_family(self) -> str:
        """The configured font family name."""
        return self._font_family

    @property
    def palette(self) -> dict[str, str]:
        """Mapping of CSS class name to hex colour string (18 entries)."""
        return dict(self._palette)

    @property
    def css(self) -> str:
        """Complete CSS stylesheet string ready for SVG rasterisation."""
        return self._css

    # --- factory class methods ---

    @classmethod
    def default(cls) -> Theme:
        """Create the default DeckUI theme.

        Uses ``rgb(39, 87, 179)`` as the primary colour and ``Inter``
        as the font family.

        Returns
        -------
        Theme
            The default theme instance.
        """
        return cls(_DEFAULT_PRIMARY, _DEFAULT_FONT_FAMILY)

    @classmethod
    def from_color(
        cls,
        r: int,
        g: int,
        b: int,
        *,
        font_family: str = _DEFAULT_FONT_FAMILY,
    ) -> Theme:
        """Create a theme from a specific primary RGB colour.

        Parameters
        ----------
        r, g, b : int
            Primary colour channels (0–255).
        font_family : str, default="Inter"
            CSS font-family name.

        Returns
        -------
        Theme
            A new theme instance.
        """
        return cls((r, g, b), font_family)

    @classmethod
    def from_random(cls, *, font_family: str = _DEFAULT_FONT_FAMILY) -> Theme:
        """Create a theme from a random primary colour.

        Picks a random hue with moderate saturation and value to
        ensure readable, visually appealing palettes.

        Parameters
        ----------
        font_family : str, default="Inter"
            CSS font-family name.

        Returns
        -------
        Theme
            A new theme instance with a random primary colour.
        """
        hue = random.random()
        saturation = random.uniform(0.45, 0.85)
        value = random.uniform(0.35, 0.75)
        r, g, b = colorsys.hsv_to_rgb(hue, saturation, value)
        primary = (round(r * 255), round(g * 255), round(b * 255))
        logger.debug("Random primary colour: rgb%s", primary)
        return cls(primary, font_family)

    def __repr__(self) -> str:
        r, g, b = self._primary
        return f"Theme(primary=({r}, {g}, {b}), font_family={self._font_family!r})"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Theme):
            return NotImplemented
        return self._primary == other._primary and self._font_family == other._font_family


# ---------------------------------------------------------------------------
# Colour math helpers (operate on float RGB 0–255 tuples)
# ---------------------------------------------------------------------------


def _rgb_to_hsl(r: float, g: float, b: float) -> tuple[float, float, float]:
    """Convert RGB (0–255) to HSL (degrees, percent, percent).

    Parameters
    ----------
    r, g, b : float
        Red, green, blue channels in 0–255.

    Returns
    -------
    tuple[float, float, float]
        ``(hue, saturation, lightness)`` with hue in degrees
        (0–360) and saturation/lightness as percentages (0–100).
    """
    h, lt, s = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
    return h * 360, s * 100, lt * 100


def _hsl_to_rgb(h: float, s: float, lt: float) -> tuple[float, float, float]:
    """Convert HSL back to RGB (0–255).

    Parameters
    ----------
    h : float
        Hue in degrees (0–360).
    s : float
        Saturation as a percentage (0–100).
    lt : float
        Lightness as a percentage (0–100).

    Returns
    -------
    tuple[float, float, float]
        ``(r, g, b)`` channels in 0–255.
    """
    r, g, b = colorsys.hls_to_rgb(h / 360, lt / 100, s / 100)
    return r * 255, g * 255, b * 255


def _adjust(
    rgb: tuple[float, ...], hue: float = 0
) -> tuple[float, float, float]:
    """Shift the hue of *rgb* by *hue* degrees.

    Parameters
    ----------
    rgb : tuple[float, ...]
        ``(r, g, b)`` in 0–255.
    hue : float, default=0
        Hue rotation in degrees.

    Returns
    -------
    tuple[float, float, float]
        Adjusted ``(r, g, b)`` in 0–255.
    """
    h, s, lt = _rgb_to_hsl(*rgb)
    return _hsl_to_rgb((h + hue) % 360, s, lt)


def _scale(
    rgb: tuple[float, ...],
    saturation: float = 0,
    lightness: float = 0,
) -> tuple[float, float, float]:
    """Scale saturation and/or lightness of *rgb*.

    Positive values scale towards 100%; negative values scale
    towards 0%.

    Parameters
    ----------
    rgb : tuple[float, ...]
        ``(r, g, b)`` in 0–255.
    saturation : float, default=0
        Percentage to scale saturation by.
    lightness : float, default=0
        Percentage to scale lightness by.

    Returns
    -------
    tuple[float, float, float]
        Adjusted ``(r, g, b)`` in 0–255.
    """
    h, s, lt = _rgb_to_hsl(*rgb)
    if saturation > 0:
        s += (100 - s) * saturation / 100
    elif saturation < 0:
        s += s * saturation / 100
    if lightness > 0:
        lt += (100 - lt) * lightness / 100
    elif lightness < 0:
        lt += lt * lightness / 100
    return _hsl_to_rgb(h, max(0, min(100, s)), max(0, min(100, lt)))


def _to_hex(r: float, g: float, b: float) -> str:
    """Format an RGB triplet as a ``#rrggbb`` hex string."""
    return f"#{round(r):02x}{round(g):02x}{round(b):02x}"


# ---------------------------------------------------------------------------
# Palette generation
# ---------------------------------------------------------------------------


def _generate_palette(primary: tuple[float, ...]) -> dict[str, str]:
    """Derive a full CSS-class colour palette from a *primary* colour.

    The palette contains 18 named colours covering backgrounds,
    text, borders, icons, and semantic states (success, warning,
    error) — matching the CSS classes expected by bundled DUI SVG
    layouts.

    Parameters
    ----------
    primary : tuple[float, ...]
        ``(r, g, b)`` primary colour in 0–255.

    Returns
    -------
    dict[str, str]
        Mapping of CSS class name to hex colour string.
    """
    background = _scale(primary, saturation=-85, lightness=-80)
    analogous_left = _adjust(primary, hue=-30)
    complementary = _adjust(primary, hue=180)
    success = _adjust(primary, hue=-140)
    warning = _scale(_adjust(primary, hue=170), saturation=45, lightness=38)
    error = _adjust(_adjust(primary, hue=180), hue=-40)
    text_primary = _scale(primary, lightness=85)

    return {
        "background-dark": _to_hex(*background),
        "background-light": _to_hex(*_scale(background, lightness=18)),
        "border-primary": _to_hex(*_scale(background, lightness=50)),
        "border-secondary": _to_hex(*_scale(background, lightness=20)),
        "text-primary": _to_hex(*text_primary),
        "text-secondary": _to_hex(*primary),
        "text-accent": _to_hex(*analogous_left),
        "text-muted": _to_hex(*_scale(background, lightness=50)),
        "text-selected": _to_hex(*text_primary),
        "text-fancy": _to_hex(*complementary),
        "success": _to_hex(*success),
        "warning": _to_hex(*warning),
        "error": _to_hex(*error),
        "icon": _to_hex(*analogous_left),
        "icon-active": _to_hex(*warning),
        "icon-inactive": _to_hex(*_scale(background, lightness=40)),
        "sliders": _to_hex(*complementary),
        "dynamic": _to_hex(*complementary),
    }


def _palette_to_css(palette: dict[str, str], font_family: str) -> str:
    """Convert a palette dict to a CSS stylesheet string.

    Prepends the font-family declaration so all SVG elements use
    the specified font by default.

    Parameters
    ----------
    palette : dict[str, str]
        Mapping of CSS class name to hex colour string.
    font_family : str
        Primary font family name.

    Returns
    -------
    str
        Complete CSS stylesheet ready for
        :func:`~deckui.set_svg_stylesheet`.
    """
    font_css = (
        f"svg {{ font-family: '{font_family}', {_FALLBACK_FONTS}; }}\n"
    )
    classes = "\n".join(
        f".{name} {{ color: {color}; }}" for name, color in palette.items()
    )
    return font_css + classes


# ---------------------------------------------------------------------------
# Active theme (module-level singleton for system-wide default)
# ---------------------------------------------------------------------------

_active_theme: Theme | None = None


def get_active_theme() -> Theme:
    """Return the currently active system-wide theme.

    If no theme has been explicitly set, returns :meth:`Theme.default`.

    Returns
    -------
    Theme
        The active theme.
    """
    global _active_theme  # noqa: PLW0603
    if _active_theme is None:
        _active_theme = Theme.default()
    return _active_theme


def set_active_theme(theme: Theme | None) -> None:
    """Set the system-wide active theme.

    Also updates the global SVG stylesheet via
    :func:`~deckui.render.svg_rasterize.set_svg_stylesheet` so that
    all subsequent SVG rasterisation uses the new theme's CSS.

    Parameters
    ----------
    theme : Theme or None
        The theme to activate.  Pass ``None`` to reset to the
        default theme.
    """
    global _active_theme  # noqa: PLW0603
    from .svg_rasterize import set_svg_stylesheet

    _active_theme = Theme.default() if theme is None else theme
    set_svg_stylesheet(_active_theme.css)
    logger.debug("Active theme set to %r", _active_theme)


def get_default_font_family() -> str:
    """Return the font family from the active system-wide theme.

    Used by the SVG renderer for text measurement so that CSS font
    declarations and pixel-based text wrapping agree.

    Returns
    -------
    str
        The active theme's font family name.
    """
    return get_active_theme().font_family


def _apply_default_theme() -> None:
    """Apply the default theme on first import.

    Called by :mod:`deckui.render.__init__` to ensure a baseline
    CSS stylesheet is always active.
    """
    set_active_theme(None)
