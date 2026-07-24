import io

import pytest
from fastapi import UploadFile
from PIL import Image
from pypdf import PdfWriter

from app.services.document_processing import (
    DocumentValidationError,
    validate_upload,
)


def _image_bytes(image_format: str) -> bytes:
    output = io.BytesIO()
    Image.new("RGB", (4, 4), color="white").save(output, format=image_format)
    return output.getvalue()


def _pdf_bytes(*, encrypted: bool = False) -> bytes:
    output = io.BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    if encrypted:
        writer.encrypt("secret")
    writer.write(output)
    return output.getvalue()


def _upload(content: bytes, content_type: str, filename: str) -> UploadFile:
    return UploadFile(
        file=io.BytesIO(content),
        filename=filename,
        headers={"content-type": content_type},
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("content", "mime", "filename"),
    [
        (_image_bytes("JPEG"), "image/jpeg", "receipt.jpg"),
        (_image_bytes("PNG"), "image/png", "receipt.png"),
        (_pdf_bytes(), "application/pdf", "receipt.pdf"),
    ],
)
async def test_supported_documents_validate(content, mime, filename):
    result = await validate_upload(_upload(content, mime, filename))
    assert result.mime_type == mime
    assert len(result.sha256_hash) == 64


@pytest.mark.asyncio
async def test_mime_signature_mismatch_is_rejected():
    with pytest.raises(DocumentValidationError, match="do not match"):
        await validate_upload(
            _upload(_image_bytes("PNG"), "image/jpeg", "disguised.jpg")
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("content", "mime", "code"),
    [
        (b"", "image/png", "empty_file"),
        (b"not a pdf", "application/pdf", "mime_mismatch"),
        (_pdf_bytes(encrypted=True), "application/pdf", "encrypted_pdf"),
    ],
)
async def test_invalid_documents_are_rejected(content, mime, code):
    with pytest.raises(DocumentValidationError) as exc_info:
        await validate_upload(_upload(content, mime, "invalid"))
    assert exc_info.value.code == code


@pytest.mark.asyncio
async def test_unsupported_declared_mime_is_rejected():
    with pytest.raises(DocumentValidationError) as exc_info:
        await validate_upload(_upload(b"hello", "text/plain", "note.txt"))
    assert exc_info.value.code == "unsupported_mime"


@pytest.mark.asyncio
async def test_oversized_upload_is_bounded(monkeypatch):
    monkeypatch.setattr(
        "app.services.document_processing.settings.MAX_UPLOAD_SIZE",
        8,
    )
    with pytest.raises(DocumentValidationError) as exc_info:
        await validate_upload(
            _upload(b"\x89PNG\r\n\x1a\nextra", "image/png", "large.png")
        )
    assert exc_info.value.code == "file_too_large"
