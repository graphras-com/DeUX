"""InfoScreen: container for a non-touch info display (e.g. Stream Deck Neo)."""

from __future__ import annotations

import io

from PIL import Image


class InfoScreen:
    """Manage content on a non-touch info screen (e.g. Stream Deck Neo 248x58).

    The info screen is a small display that shows status information.
    It does not support touch events or interactive cards — it is a
    simple image buffer with dirty tracking.

    Args:
        width: Screen width in pixels.
        height: Screen height in pixels.
        image_format: Image format for encoding (``"JPEG"`` or ``"BMP"``).
    """

    def __init__(
        self,
        width: int,
        height: int,
        image_format: str = "JPEG",
    ) -> None:
        self._width = width
        self._height = height
        self._image_format = image_format
        self._image: Image.Image | None = None
        self._dirty = True

    @property
    def width(self) -> int:
        return self._width

    @property
    def height(self) -> int:
        return self._height

    @property
    def size(self) -> tuple[int, int]:
        return (self._width, self._height)

    @property
    def image_format(self) -> str:
        return self._image_format

    @property
    def image(self) -> Image.Image | None:
        """The current screen image, or ``None`` if not set."""
        return self._image

    def set_image(self, image: Image.Image) -> None:
        """Set the info screen image and mark dirty.

        The image is resized to fit the screen dimensions if needed.

        Args:
            image: A PIL Image to display.
        """
        if image.size != (self._width, self._height):
            image = image.resize((self._width, self._height), Image.LANCZOS)
        self._image = image
        self._dirty = True

    def clear(self) -> None:
        """Clear the info screen to black."""
        self._image = Image.new("RGB", (self._width, self._height), "black")
        self._dirty = True

    @property
    def is_dirty(self) -> bool:
        return self._dirty

    def mark_clean(self) -> None:
        self._dirty = False

    def mark_dirty(self) -> None:
        self._dirty = True

    def render_bytes(self) -> bytes:
        """Encode the current image to bytes in the device's format.

        Returns:
            Encoded image bytes. If no image has been set, returns
            a blank black image.
        """
        img = self._image or Image.new("RGB", (self._width, self._height), "black")
        if img.mode != "RGB":
            img = img.convert("RGB")

        buf = io.BytesIO()
        fmt = "JPEG" if self._image_format.upper() == "JPEG" else "BMP"
        img.save(buf, format=fmt, quality=90)
        return buf.getvalue()
