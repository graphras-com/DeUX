"""Image rendering helpers for composing button and touchscreen images."""

from __future__ import annotations

import io

from PIL import Image, ImageDraw, ImageFont

# Stream Deck+ constants
KEY_SIZE = (120, 120)
ICON_SIZE = 80
ICON_PADDING = (KEY_SIZE[0] - ICON_SIZE) // 2  # 20px

TOUCHSCREEN_WIDTH = 800
TOUCHSCREEN_HEIGHT = 100
WIDGET_COUNT = 4

# Touchscreen margins — the bottom of the physical screen is partially
# hidden by the viewing angle, so we inset the usable area.
MARGIN_TOP = 4
MARGIN_BOTTOM = 18
MARGIN_LEFT = 4
MARGIN_RIGHT = 4
WIDGET_GAP = 4  # horizontal gap between adjacent widgets

# Usable area after margins
USABLE_WIDTH = TOUCHSCREEN_WIDTH - MARGIN_LEFT - MARGIN_RIGHT  # 792
USABLE_HEIGHT = TOUCHSCREEN_HEIGHT - MARGIN_TOP - MARGIN_BOTTOM  # 78

# Each widget size: (usable_width - 3 gaps) / 4
WIDGET_WIDTH = (USABLE_WIDTH - (WIDGET_COUNT - 1) * WIDGET_GAP) // WIDGET_COUNT  # 195
WIDGET_HEIGHT = USABLE_HEIGHT  # 78

# Font for labels/values - use default bitmap font (always available)
_font: ImageFont.FreeTypeFont | ImageFont.ImageFont | None = None
_small_font: ImageFont.FreeTypeFont | ImageFont.ImageFont | None = None


def _get_font(size: int = 14) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Get a font, trying system fonts first, falling back to default."""
    try:
        # Try common system fonts
        for font_name in [
            "/System/Library/Fonts/Helvetica.ttc",  # macOS
            "/System/Library/Fonts/SFNSText.ttf",  # macOS
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",  # Linux
            "C:\\Windows\\Fonts\\segoeui.ttf",  # Windows
        ]:
            try:
                return ImageFont.truetype(font_name, size)
            except (OSError, IOError):
                continue
        # Try by name (PIL can sometimes find fonts by name)
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
    """Get a smaller font for values/secondary text."""
    global _small_font
    if _small_font is None:
        _small_font = _get_font(12)
    return _small_font


def render_key_image(
    icon: Image.Image | None = None,
    label: str | None = None,
    background: str = "black",
) -> bytes:
    """Render a 120x120 JPEG image for a Stream Deck+ key.

    Args:
        icon: 80x80 RGBA icon image (or None for blank).
        label: Optional text label below the icon.
        background: Background color.

    Returns:
        JPEG-encoded bytes ready for ``set_key_image()``.
    """
    img = Image.new("RGB", KEY_SIZE, background)

    if icon is not None:
        # Resize icon if needed
        if icon.size != (ICON_SIZE, ICON_SIZE):
            icon = icon.resize((ICON_SIZE, ICON_SIZE), Image.LANCZOS)

        # Calculate vertical position: center if no label, shift up if label
        if label:
            y_offset = 8
        else:
            y_offset = ICON_PADDING  # 20px, centered

        x_offset = ICON_PADDING  # 20px, centered horizontally

        # Paste icon with alpha mask if RGBA
        if icon.mode == "RGBA":
            img.paste(icon, (x_offset, y_offset), icon)
        else:
            img.paste(icon, (x_offset, y_offset))

    if label:
        draw = ImageDraw.Draw(img)
        font = get_font()
        bbox = draw.textbbox((0, 0), label, font=font)
        text_width = bbox[2] - bbox[0]
        text_x = (KEY_SIZE[0] - text_width) // 2
        text_y = KEY_SIZE[1] - 24  # near bottom
        draw.text((text_x, text_y), label, fill="white", font=font)

    return _encode_jpeg(img)


def render_widget_image(
    icon: Image.Image | None = None,
    label: str | None = None,
    value: str | None = None,
    background: str = "black",
) -> Image.Image:
    """Render a single widget zone image (PIL Image, not encoded).

    Layout (195x78):
      - Left side: 50x50 icon (centered vertically, 8px from left)
      - Right side: label on top, value below

    Args:
        icon: RGBA icon image (will be resized to 50x50).
        label: Primary text label.
        value: Secondary value text.
        background: Background color.

    Returns:
        PIL Image (RGB, WIDGET_WIDTH x WIDGET_HEIGHT).
    """
    img = Image.new("RGB", (WIDGET_WIDTH, WIDGET_HEIGHT), background)
    draw = ImageDraw.Draw(img)
    font = get_font()
    small_font = get_small_font()

    widget_icon_size = 50
    icon_x = 8
    icon_y = (WIDGET_HEIGHT - widget_icon_size) // 2  # vertically centered

    if icon is not None:
        sized = icon.resize((widget_icon_size, widget_icon_size), Image.LANCZOS)
        if sized.mode == "RGBA":
            img.paste(sized, (icon_x, icon_y), sized)
        else:
            img.paste(sized, (icon_x, icon_y))

    text_x = icon_x + widget_icon_size + 10  # right of icon
    if label and value:
        # Label at top, value below
        draw.text((text_x, 18), label, fill="white", font=font)
        draw.text((text_x, 40), value, fill="#aaaaaa", font=small_font)
    elif label:
        # Label centered vertically
        draw.text((text_x, 30), label, fill="white", font=font)
    elif value:
        draw.text((text_x, 30), value, fill="#aaaaaa", font=small_font)

    return img


def compose_touchscreen(widgets: list[Image.Image | None]) -> bytes:
    """Compose 4 widget images into a single 800x100 touchscreen JPEG.

    Widgets are placed within the usable area defined by the margins,
    separated by ``WIDGET_GAP`` pixels.

    Args:
        widgets: List of up to 4 PIL Images (WIDGET_WIDTH x WIDGET_HEIGHT each).
                 None entries render as black.

    Returns:
        JPEG-encoded bytes ready for ``set_touchscreen_image()``.
    """
    img = Image.new("RGB", (TOUCHSCREEN_WIDTH, TOUCHSCREEN_HEIGHT), "black")

    for i, widget_img in enumerate(widgets):
        if i >= WIDGET_COUNT:
            break
        if widget_img is not None:
            x = MARGIN_LEFT + i * (WIDGET_WIDTH + WIDGET_GAP)
            img.paste(widget_img, (x, MARGIN_TOP))

    return _encode_jpeg(img)


def render_blank_key() -> bytes:
    """Render a blank (black) key image."""
    return render_key_image()


def render_blank_touchscreen() -> bytes:
    """Render a blank (black) touchscreen image."""
    return compose_touchscreen([None] * WIDGET_COUNT)


def _encode_jpeg(img: Image.Image, quality: int = 90) -> bytes:
    """Encode a PIL Image as JPEG bytes."""
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality)
    return buf.getvalue()
