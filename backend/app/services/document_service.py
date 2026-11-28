"""Document extraction service for uploaded TXT, PDF, and DOCX story files."""

from __future__ import annotations

import hashlib
import io
from dataclasses import dataclass
from pathlib import Path

from docx import Document as DocxDocument
from pypdf import PdfReader

from app.core.exceptions import BadRequestError

ALLOWED_EXTENSIONS = {".txt", ".md", ".pdf", ".docx"}


@dataclass(slots=True)
class ExtractedDocument:
    """Extracted text and metadata from an uploaded story file."""

    filename: str
    file_type: str
    extracted_text: str
    word_count: int
    page_count: int | None
    sha256: str


class DocumentService:
    """Extracts clean story text from TXT, PDF, and DOCX uploads without altering story facts."""

    def __init__(self, max_bytes: int = 10 * 1024 * 1024) -> None:
        self.max_bytes = max_bytes

    def extract_text(self, *, filename: str, content_bytes: bytes) -> ExtractedDocument:
        if not filename or not filename.strip():
            raise BadRequestError("Uploaded file must have a valid filename.", code="INVALID_FILENAME")

        if not content_bytes:
            raise BadRequestError("Uploaded file is empty.", code="EMPTY_FILE")

        if len(content_bytes) > self.max_bytes:
            raise BadRequestError(
                f"File exceeds maximum allowed size of {self.max_bytes // (1024 * 1024)} MB.",
                code="FILE_TOO_LARGE",
            )

        ext = Path(filename).suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise BadRequestError(
                f"Unsupported file type '{ext}'. Allowed formats: TXT, PDF, DOCX, MD.",
                code="UNSUPPORTED_FILE_TYPE",
            )

        checksum = hashlib.sha256(content_bytes).hexdigest()
        page_count: int | None = None

        if ext in {".txt", ".md"}:
            text = self._decode_text(content_bytes)
        elif ext == ".pdf":
            text, page_count = self._extract_pdf(content_bytes)
        else:
            text = self._extract_docx(content_bytes)

        normalized = "\n".join(line.rstrip() for line in text.replace("\r\n", "\n").splitlines()).strip()
        if not normalized:
            raise BadRequestError(
                "No readable story text could be extracted from the uploaded file.",
                code="EMPTY_EXTRACTED_TEXT",
            )

        words = len(normalized.split())
        return ExtractedDocument(
            filename=Path(filename).name,
            file_type=ext.lstrip("."),
            extracted_text=normalized,
            word_count=words,
            page_count=page_count,
            sha256=checksum,
        )

    def _decode_text(self, content_bytes: bytes) -> str:
        for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
            try:
                return content_bytes.decode(encoding)
            except UnicodeDecodeError:
                continue
        raise BadRequestError("Could not decode text file encoding.", code="INVALID_TEXT_ENCODING")

    def _extract_pdf(self, content_bytes: bytes) -> tuple[str, int]:
        try:
            reader = PdfReader(io.BytesIO(content_bytes))
            pages: list[str] = []
            for page in reader.pages:
                extracted = page.extract_text() or ""
                if extracted.strip():
                    pages.append(extracted)
            return "\n\n".join(pages), len(reader.pages)
        except Exception as exc:
            raise BadRequestError(f"Failed to parse PDF document: {exc}", code="INVALID_PDF") from exc

    def _extract_docx(self, content_bytes: bytes) -> str:
        try:
            doc = DocxDocument(io.BytesIO(content_bytes))
            paragraphs = [p.text for p in doc.paragraphs if p.text and p.text.strip()]
            return "\n\n".join(paragraphs)
        except Exception as exc:
            raise BadRequestError(f"Failed to parse DOCX document: {exc}", code="INVALID_DOCX") from exc
