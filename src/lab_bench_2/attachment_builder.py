"""Build Inspect Content attachments from local question files."""

from __future__ import annotations

import base64
import hashlib
from pathlib import Path

from inspect_ai.model import Content, ContentDocument, ContentImage

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg"}
MAX_IMAGE_ATTACHMENT_BYTES = 3_900_000
IMAGE_ATTACHMENT_CACHE_DIR = (
    Path.home() / ".cache" / "inspect_evals" / "lab_bench_2" / "images"
)


def build(files: list[Path], resize_oversized_images: bool = False) -> list[Content]:
    """Turn local file paths into Inspect ``Content`` attachments.

    Args:
        files: Local paths to attach, in caller-supplied order.
        resize_oversized_images: When True, downscale image files over
            ``MAX_IMAGE_ATTACHMENT_BYTES`` before attaching, to fit
            provider per-image size ceilings (~4 MB). Off by default to
            match the reference loader's behavior (attach as-is).
    """
    return [_attachment_for(f, resize_oversized_images) for f in files]


def mime_type(file_path: Path) -> str:
    # MEDIA_TYPES is reused from EdisonScientific/labbench2 evals/utils.py.
    # Its unusual entries (".json" / ".csv" -> "text/plain") are deliberate
    # provider-compatibility workarounds: Vertex AI rejects application/json and
    # Anthropic's Messages document API rejects text/csv.
    from evals.utils import MEDIA_TYPES

    return MEDIA_TYPES.get(file_path.suffix.lower(), "application/octet-stream")


def _attachment_for(file_path: Path, resize_oversized_images: bool) -> Content:
    if file_path.suffix.lower() in IMAGE_EXTENSIONS:
        image_path = _fit_image(file_path) if resize_oversized_images else file_path
        return ContentImage(image=str(image_path))
    file_mime_type = mime_type(file_path)
    return ContentDocument(
        document=_document_payload(file_path, file_mime_type),
        filename=file_path.name,
        mime_type=file_mime_type,
    )


def _document_payload(file_path: Path, mime_type_str: str) -> str:
    if mime_type_str == "application/pdf":
        return str(file_path)
    encoded = base64.b64encode(file_path.read_bytes()).decode("utf-8")
    return f"data:{mime_type_str};base64,{encoded}"


def _fit_image(file_path: Path) -> Path:
    """Return a path to a version of the image that fits under the size ceiling.

    Cheap path: if the source is already under ``MAX_IMAGE_ATTACHMENT_BYTES``,
    return its path unchanged. Otherwise write a resized copy to
    ``IMAGE_ATTACHMENT_CACHE_DIR`` (keyed by source path + size, so repeated
    runs reuse it) and return that path.

    Tries PNG first at progressively smaller scales, then falls back to JPEG
    (RGB) at decreasing scale and quality. Returns the final JPEG path even
    if nothing fits the ceiling — caller gets the smallest we could produce.
    """
    if file_path.stat().st_size <= MAX_IMAGE_ATTACHMENT_BYTES:
        return file_path

    from PIL import Image

    IMAGE_ATTACHMENT_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(str(file_path.resolve()).encode("utf-8")).hexdigest()[:12]
    cached_base = (
        IMAGE_ATTACHMENT_CACHE_DIR
        / f"{file_path.stem}-{digest}-{file_path.stat().st_size}"
    )
    png_path = cached_base.with_suffix(".png")
    jpg_path = cached_base.with_suffix(".jpg")

    with Image.open(file_path) as source_image:
        image = source_image.copy()

    def resize(image_to_resize: "Image.Image", scale: float) -> "Image.Image":
        """Return a Lanczos-resampled copy at ``scale`` of the original size.

        ``scale=1.0`` short-circuits to a plain copy so the PNG/JPEG retry
        loops can pass 1.0 as their first attempt without paying for a
        no-op resample.
        """
        if scale == 1.0:
            return image_to_resize.copy()
        width = max(1, int(image_to_resize.width * scale))
        height = max(1, int(image_to_resize.height * scale))
        return image_to_resize.resize((width, height), Image.Resampling.LANCZOS)

    for scale in (1.0, 0.9, 0.8, 0.7, 0.6):
        candidate = resize(image, scale)
        candidate.save(png_path, format="PNG", optimize=True)
        if png_path.stat().st_size <= MAX_IMAGE_ATTACHMENT_BYTES:
            return png_path

    rgb_image = image.convert("RGB")
    for scale in (1.0, 0.9, 0.8, 0.7, 0.6):
        candidate = resize(rgb_image, scale)
        for quality in (90, 80, 70):
            candidate.save(jpg_path, format="JPEG", optimize=True, quality=quality)
            if jpg_path.stat().st_size <= MAX_IMAGE_ATTACHMENT_BYTES:
                return jpg_path

    return jpg_path
