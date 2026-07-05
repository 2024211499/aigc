"""Image preprocessing helpers for scanned documents."""

from __future__ import annotations

from PIL import Image, ImageFilter, ImageOps


def preprocess_for_ocr(image: Image.Image, max_side: int = 2600) -> Image.Image:
    """Make scanned pages friendlier to OCR without destroying formulas."""
    image = ImageOps.exif_transpose(image).convert("RGB")
    image = _resize_if_needed(image, max_side)
    gray = ImageOps.grayscale(image)
    gray = ImageOps.autocontrast(gray)
    gray = gray.filter(ImageFilter.MedianFilter(size=3))
    # Conservative binarization: keep antialiasing enough for formulas.
    threshold = 180
    bw = gray.point(lambda p: 255 if p > threshold else 0)
    return bw.convert("RGB")


def _resize_if_needed(image: Image.Image, max_side: int) -> Image.Image:
    w, h = image.size
    longest = max(w, h)
    if longest <= max_side:
        return image
    ratio = max_side / longest
    new_size = (max(1, int(w * ratio)), max(1, int(h * ratio)))
    return image.resize(new_size)
