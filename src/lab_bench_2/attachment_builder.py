"""Build Inspect Content attachments from local question files."""

from __future__ import annotations

import base64
import hashlib
from pathlib import Path

# MEDIA_TYPES is reused from EdisonScientific/labbench2 evals/utils.py.
# Its unusual entries (".json" / ".csv" -> "text/plain") are deliberate
# provider-compatibility workarounds: Vertex AI rejects application/json and
# Anthropic's Messages document API rejects text/csv.
from evals.utils import MEDIA_TYPES
from inspect_ai.model import Content, ContentDocument, ContentImage

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg"}
MAX_IMAGE_ATTACHMENT_BYTES = 3_900_000
IMAGE_ATTACHMENT_CACHE_DIR = (
    Path.home() / ".cache" / "inspect_evals" / "lab_bench_2" / "images"
)


class AttachmentBuilder:
    """Turn local file paths into Inspect ``Content`` attachments."""

    def __init__(self, resize_oversized_images: bool = False) -> None:
        """Construct a builder.

        Args:
            resize_oversized_images: When True, downscale image files over
                ``MAX_IMAGE_ATTACHMENT_BYTES`` before attaching, to fit
                provider per-image size ceilings (~4 MB). Off by default to
                match the reference loader's behavior (attach as-is).
        """
        self._resize_oversized_images = resize_oversized_images

    def build(self, files: list[Path]) -> list[Content]:
        attachments: list[Content] = []
        for file_path in files:
            if file_path.suffix.lower() in IMAGE_EXTENSIONS:
                image_path = (
                    self._fit_image(file_path)
                    if self._resize_oversized_images
                    else file_path
                )
                attachments.append(ContentImage(image=str(image_path)))
            else:
                mime_type = self.mime_type(file_path)
                attachments.append(
                    ContentDocument(
                        document=self._document_payload(file_path, mime_type),
                        filename=file_path.name,
                        mime_type=mime_type,
                    )
                )
        return attachments

    @staticmethod
    def mime_type(file_path: Path) -> str:
        return MEDIA_TYPES.get(file_path.suffix.lower(), "application/octet-stream")

    @staticmethod
    def _document_payload(file_path: Path, mime_type: str) -> str:
        if mime_type == "application/pdf":
            return str(file_path)
        encoded = base64.b64encode(file_path.read_bytes()).decode("utf-8")
        return f"data:{mime_type};base64,{encoded}"

    @staticmethod
    def _fit_image(file_path: Path) -> Path:
        if file_path.stat().st_size <= MAX_IMAGE_ATTACHMENT_BYTES:
            return file_path

        from PIL import Image

        IMAGE_ATTACHMENT_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha256(str(file_path.resolve()).encode("utf-8")).hexdigest()[
            :12
        ]
        cached_base = (
            IMAGE_ATTACHMENT_CACHE_DIR
            / f"{file_path.stem}-{digest}-{file_path.stat().st_size}"
        )
        png_path = cached_base.with_suffix(".png")
        jpg_path = cached_base.with_suffix(".jpg")

        with Image.open(file_path) as source_image:
            image = source_image.copy()

        def resize(image_to_resize: "Image.Image", scale: float) -> "Image.Image":
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
