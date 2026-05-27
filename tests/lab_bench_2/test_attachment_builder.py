import base64
from pathlib import Path

import pytest
from inspect_ai.model import ContentDocument, ContentImage
from PIL import Image

from lab_bench_2 import attachment_builder as attachment_builder_module
from lab_bench_2.attachment_builder import AttachmentBuilder


def _make_png(path: Path, size: tuple[int, int] = (10, 10)) -> Path:
    Image.new("RGB", size, color=(255, 0, 0)).save(path, format="PNG")
    return path


class TestMimeType:
    @pytest.mark.parametrize(
        "filename,expected",
        [
            ("data.pdf", "application/pdf"),
            ("sequence.gbk", "text/plain"),
            ("notes.txt", "text/plain"),
            ("table.csv", "text/plain"),
            ("payload.json", "text/plain"),
            ("sequence.fasta", "text/plain"),
            ("graph.png", "image/png"),
            ("photo.jpg", "image/jpeg"),
            ("diagram.jpeg", "image/jpeg"),
            ("manifest.xml", "application/xml"),
            ("unknown.bin", "application/octet-stream"),
        ],
    )
    def test_maps_extension_to_provider_compatible_mime(
        self, tmp_path: Path, filename: str, expected: str
    ) -> None:
        # given a file with the named extension
        file_path = tmp_path / filename
        file_path.write_bytes(b"")

        # when / then
        assert AttachmentBuilder.mime_type(file_path) == expected


class TestBuild:
    def test_emits_content_document_for_pdf(self, tmp_path: Path) -> None:
        # given a pdf file
        pdf_path = tmp_path / "doc.pdf"
        pdf_path.write_bytes(b"%PDF-1.4")

        # when
        sut = AttachmentBuilder().build([pdf_path])

        # then
        assert len(sut) == 1
        assert isinstance(sut[0], ContentDocument)
        assert sut[0].mime_type == "application/pdf"
        assert sut[0].filename == "doc.pdf"
        # pdf attachments pass the path through, not base64
        assert sut[0].document == str(pdf_path)

    def test_emits_content_image_for_png(self, tmp_path: Path) -> None:
        # given a png file
        png_path = _make_png(tmp_path / "fig.png")

        # when
        sut = AttachmentBuilder().build([png_path])

        # then
        assert len(sut) == 1
        assert isinstance(sut[0], ContentImage)
        assert sut[0].image == str(png_path)

    def test_emits_base64_data_url_for_text_document(self, tmp_path: Path) -> None:
        # given a plain text file
        txt_path = tmp_path / "notes.txt"
        txt_path.write_text("hello world")

        # when
        sut = AttachmentBuilder().build([txt_path])

        # then
        assert isinstance(sut[0], ContentDocument)
        encoded = base64.b64encode(b"hello world").decode("utf-8")
        assert sut[0].document == f"data:text/plain;base64,{encoded}"

    def test_builds_mixed_attachments_in_order(self, tmp_path: Path) -> None:
        # given a mix of file types in caller-supplied order
        pdf = tmp_path / "a.pdf"
        png = _make_png(tmp_path / "b.png")
        txt = tmp_path / "c.txt"
        pdf.write_bytes(b"%PDF")
        txt.write_text("c")

        # when
        sut = AttachmentBuilder().build([pdf, png, txt])

        # then
        assert [type(a).__name__ for a in sut] == [
            "ContentDocument",
            "ContentImage",
            "ContentDocument",
        ]


class TestImageResize:
    def test_default_does_not_resize_even_when_oversized(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # given an image larger than the ceiling, with resizing disabled (default)
        png_path = _make_png(tmp_path / "big.png", size=(100, 100))
        monkeypatch.setattr(attachment_builder_module, "MAX_IMAGE_ATTACHMENT_BYTES", 1)

        # when
        sut = AttachmentBuilder().build([png_path])

        # then — image attached at the original path, unmodified
        assert isinstance(sut[0], ContentImage)
        assert sut[0].image == str(png_path)

    def test_opt_in_resizes_oversized_image_into_cache(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # given an image larger than the (tiny) ceiling with resize opt-in
        png_path = _make_png(tmp_path / "big.png", size=(100, 100))
        cache_dir = tmp_path / "cache"
        monkeypatch.setattr(attachment_builder_module, "MAX_IMAGE_ATTACHMENT_BYTES", 1)
        monkeypatch.setattr(
            attachment_builder_module, "IMAGE_ATTACHMENT_CACHE_DIR", cache_dir
        )

        # when
        sut = AttachmentBuilder(resize_oversized_images=True).build([png_path])

        # then — output points at the cache, not the source
        assert isinstance(sut[0], ContentImage)
        assert sut[0].image != str(png_path)
        assert str(cache_dir) in sut[0].image

    def test_opt_in_passes_through_when_image_is_already_small(
        self, tmp_path: Path
    ) -> None:
        # given a small image with resize opt-in
        png_path = _make_png(tmp_path / "small.png")

        # when
        sut = AttachmentBuilder(resize_oversized_images=True).build([png_path])

        # then — no resize needed, original path returned
        assert isinstance(sut[0], ContentImage)
        assert sut[0].image == str(png_path)
