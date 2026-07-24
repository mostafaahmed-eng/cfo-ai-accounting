import base64
import hashlib
import io
import json
from dataclasses import dataclass

import httpx
import magic
from fastapi import UploadFile
from PIL import Image, UnidentifiedImageError
from pypdf import PdfReader

from app.config import get_settings

settings = get_settings()
MIME_EXTENSIONS = {
    "application/pdf": "pdf",
    "image/jpeg": "jpg",
    "image/png": "png",
}


class DocumentValidationError(ValueError):
    def __init__(self, code: str, detail: str):
        self.code = code
        self.detail = detail
        super().__init__(detail)


class DocumentProviderError(RuntimeError):
    pass


@dataclass
class ValidatedUpload:
    content: bytes
    mime_type: str
    sha256_hash: str
    extension: str


async def validate_upload(file: UploadFile) -> ValidatedUpload:
    declared_mime = (file.content_type or "").lower()
    if declared_mime not in MIME_EXTENSIONS:
        raise DocumentValidationError("unsupported_mime", "Unsupported file type")

    digest = hashlib.sha256()
    content = bytearray()
    while True:
        chunk = await file.read(64 * 1024)
        if not chunk:
            break
        if len(content) + len(chunk) > settings.MAX_UPLOAD_SIZE:
            raise DocumentValidationError("file_too_large", "File exceeds upload limit")
        digest.update(chunk)
        content.extend(chunk)

    if not content:
        raise DocumentValidationError("empty_file", "The uploaded file is empty")

    actual_mime = magic.from_buffer(bytes(content[:8192]), mime=True)
    if actual_mime != declared_mime:
        raise DocumentValidationError(
            "mime_mismatch", "Declared and detected file types do not match"
        )
    if actual_mime not in MIME_EXTENSIONS:
        raise DocumentValidationError("unsupported_mime", "Unsupported file type")

    _validate_file_structure(bytes(content), actual_mime)
    return ValidatedUpload(
        content=bytes(content),
        mime_type=actual_mime,
        sha256_hash=digest.hexdigest(),
        extension=MIME_EXTENSIONS[actual_mime],
    )


def _validate_file_structure(content: bytes, mime_type: str) -> None:
    if mime_type == "application/pdf":
        try:
            reader = PdfReader(io.BytesIO(content), strict=True)
            if reader.is_encrypted:
                raise DocumentValidationError(
                    "encrypted_pdf", "Encrypted PDFs are not supported"
                )
            page_count = len(reader.pages)
            if page_count == 0:
                raise DocumentValidationError("malformed_pdf", "PDF has no pages")
            if page_count > settings.MAX_PDF_PAGES:
                raise DocumentValidationError(
                    "pdf_page_limit", "PDF exceeds the page limit"
                )
        except DocumentValidationError:
            raise
        except Exception:
            raise DocumentValidationError("malformed_pdf", "Unreadable PDF")
        return

    try:
        with Image.open(io.BytesIO(content)) as image:
            image.verify()
            expected = "JPEG" if mime_type == "image/jpeg" else "PNG"
            if image.format != expected:
                raise DocumentValidationError(
                    "malformed_image", "Image format is invalid"
                )
    except DocumentValidationError:
        raise
    except (UnidentifiedImageError, OSError, ValueError):
        raise DocumentValidationError("malformed_image", "Unreadable image")


async def extract_text_from_document(
    content: bytes,
    mime_type: str,
    filename: str,
) -> dict:
    encoded = base64.b64encode(content).decode("ascii")
    if mime_type == "application/pdf":
        media = {
            "type": "file",
            "file": {
                "filename": filename,
                "file_data": f"data:{mime_type};base64,{encoded}",
            },
        }
    else:
        media = {
            "type": "image_url",
            "image_url": {"url": f"data:{mime_type};base64,{encoded}"},
        }

    try:
        async with httpx.AsyncClient(timeout=90.0) as client:
            response = await client.post(
                f"{settings.OPENROUTER_BASE_URL}/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": settings.OPENROUTER_MODEL,
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                media,
                                {
                                    "type": "text",
                                    "text": (
                                        "Transcribe all financial text from this "
                                        "receipt or invoice. Return JSON with one "
                                        'field: {"text": "..."}'
                                    ),
                                },
                            ],
                        }
                    ],
                    "temperature": 0,
                },
            )
            response.raise_for_status()
            payload = response.json()
            content_text = payload["choices"][0]["message"]["content"]
            parsed = json.loads(content_text)
            text = parsed.get("text", "").strip()
            if not text:
                raise DocumentProviderError("OCR returned no readable text")
            usage = payload.get("usage", {})
            return {
                "text": text,
                "input_tokens": usage.get("prompt_tokens"),
                "output_tokens": usage.get("completion_tokens"),
            }
    except (httpx.TimeoutException, httpx.TransportError):
        raise
    except DocumentProviderError:
        raise
    except Exception:
        raise DocumentProviderError("OCR provider returned an invalid response")
