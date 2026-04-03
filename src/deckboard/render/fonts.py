"""Font loading helpers used by key and touch rendering."""

from __future__ import annotations

from PIL import ImageFont

_font: ImageFont.FreeTypeFont | ImageFont.ImageFont | None = None
_small_font: ImageFont.FreeTypeFont | ImageFont.ImageFont | None = None
_large_font: ImageFont.FreeTypeFont | ImageFont.ImageFont | None = None


def _get_font(size: int = 14) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Get a font, trying system fonts first, falling back to default."""
    try:
        for font_name in [
            "/System/Library/Fonts/Helvetica.ttc",
            "/System/Library/Fonts/SFNSText.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "C:\\Windows\\Fonts\\segoeui.ttf",
        ]:
            try:
                return ImageFont.truetype(font_name, size)
            except (OSError, IOError):
                continue
        return ImageFont.truetype("Arial", size)
    except (OSError, IOError):
        return ImageFont.load_default()


def get_font() -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Get the standard label font."""
    global _font
    if _font is None:
        _font = _get_font(14)
    return _font


def get_small_font() -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Get a smaller font for values or secondary text."""
    global _small_font
    if _small_font is None:
        _small_font = _get_font(12)
    return _small_font


def get_large_font() -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Get a larger font for prominent text elements."""
    global _large_font
    if _large_font is None:
        _large_font = _get_font(20)
    return _large_font
