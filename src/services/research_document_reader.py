"""read_document / analyze_image — upload bytes only (no user file paths)."""

from __future__ import annotations

import base64
import io
import re
from typing import Any, Dict, List, Optional

from src.services.research_safety import sanitize_research_payload

_MAX_BYTES = 8 * 1024 * 1024
_ALLOWED_EXT = frozenset(
    {"txt", "md", "csv", "json", "pdf", "docx", "xlsx", "pptx", "png", "jpg", "jpeg", "webp"}
)


def _decode_payload(content_b64: str) -> bytes:
    raw = str(content_b64 or "").strip()
    if raw.startswith("data:") and "," in raw:
        raw = raw.split(",", 1)[1]
    try:
        data = base64.b64decode(raw, validate=True)
    except Exception as exc:
        raise ValueError("invalid_base64") from exc
    if len(data) > _MAX_BYTES:
        raise ValueError("file_too_large")
    if len(data) == 0:
        raise ValueError("empty_file")
    return data


def read_document(
    *,
    filename: str,
    content_b64: str,
    max_chars: int = 120_000,
) -> Dict[str, Any]:
    """Parse uploaded document text; OCR/vision delegated when libraries/API absent."""
    name = str(filename or "upload.bin").strip()
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else "txt"
    if ext not in _ALLOWED_EXT:
        raise ValueError("unsupported_type")
    data = _decode_payload(content_b64)
    text = ""
    parser = "plain"
    if ext in {"txt", "md", "csv", "json"}:
        text = data.decode("utf-8", errors="replace")
        parser = ext
    elif ext == "pdf":
        text, parser = _read_pdf(data)
    elif ext == "docx":
        text, parser = _read_docx(data)
    elif ext == "xlsx":
        text, parser = _read_xlsx(data)
    elif ext == "pptx":
        text, parser = _read_pptx(data)
    else:
        return sanitize_research_payload(
            {
                "ok": False,
                "filename": name,
                "type": ext,
                "hint": "Use analyze_image for chart screenshots.",
                "authority": "research_only",
            }
        )
    text = text[:max_chars]
    return sanitize_research_payload(
        {
            "ok": bool(text.strip()),
            "filename": name,
            "type": ext,
            "parser": parser,
            "char_count": len(text),
            "excerpt": text[:8000],
            "authority": "research_only",
        }
    )


def read_documents_batch(files: List[Dict[str, str]], *, max_files: int = 5) -> Dict[str, Any]:
    out: List[Dict[str, Any]] = []
    for item in (files or [])[:max_files]:
        if not isinstance(item, dict):
            continue
        try:
            out.append(
                read_document(
                    filename=str(item.get("filename") or "upload.txt"),
                    content_b64=str(item.get("content_b64") or ""),
                )
            )
        except ValueError as exc:
            out.append({"ok": False, "error": str(exc), "filename": item.get("filename")})
    return {"files": out, "count": len(out), "authority": "research_only"}


def analyze_image(
    *,
    filename: str,
    content_b64: str,
    question: Optional[str] = None,
) -> Dict[str, Any]:
    """Semantic chart read — requires configured vision provider."""
    name = str(filename or "chart.png")
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else "png"
    if ext not in {"png", "jpg", "jpeg", "webp"}:
        raise ValueError("unsupported_image_type")
    _decode_payload(content_b64)
    q = str(question or "Describe trend, levels, and indicators visible.").strip()
    try:
        from src.core.ai_provider import chat_with_vision  # type: ignore

        analysis = chat_with_vision(content_b64=content_b64, prompt=q)
        return sanitize_research_payload(
            {
                "ok": True,
                "filename": name,
                "analysis": analysis,
                "authority": "research_only",
            }
        )
    except ImportError:
        pass
    except Exception as exc:
        return sanitize_research_payload(
            {
                "ok": False,
                "filename": name,
                "error": type(exc).__name__,
                "hint": "Configure AI vision provider in environment.",
                "authority": "research_only",
            }
        )
    return sanitize_research_payload(
        {
            "ok": False,
            "filename": name,
            "pluggable_ocr": False,
            "hint": (
                "Vision model not configured — attach OPENAI/Azure key and "
                "implement chat_with_vision in ai_provider, or paste OCR text via read_document."
            ),
            "prompt_echo": q[:500],
            "authority": "research_only",
        }
    )


def _read_pdf(data: bytes) -> tuple[str, str]:
    try:
        from pypdf import PdfReader  # type: ignore

        reader = PdfReader(io.BytesIO(data))
        parts = []
        for page in reader.pages[:40]:
            parts.append(page.extract_text() or "")
        return "\n".join(parts), "pypdf"
    except ImportError:
        return "", "pdf_requires_pypdf"
    except Exception:
        return "", "pdf_parse_failed"


def _read_docx(data: bytes) -> tuple[str, str]:
    try:
        import docx  # type: ignore

        doc = docx.Document(io.BytesIO(data))
        return "\n".join(p.text for p in doc.paragraphs), "python-docx"
    except ImportError:
        return "", "docx_requires_python_docx"
    except Exception:
        return "", "docx_parse_failed"


def _read_xlsx(data: bytes) -> tuple[str, str]:
    try:
        import pandas as pd

        frames = pd.read_excel(io.BytesIO(data), sheet_name=None, nrows=200)
        chunks = []
        for name, df in list(frames.items())[:5]:
            chunks.append(f"## Sheet {name}\n{df.head(50).to_csv(index=False)}")
        return "\n".join(chunks), "pandas_excel"
    except ImportError:
        return "", "xlsx_requires_openpyxl"
    except Exception:
        return "", "xlsx_parse_failed"


def _read_pptx(data: bytes) -> tuple[str, str]:
    try:
        from pptx import Presentation  # type: ignore

        prs = Presentation(io.BytesIO(data))
        lines = []
        for slide in prs.slides[:30]:
            for shape in slide.shapes:
                if hasattr(shape, "text") and shape.text:
                    lines.append(shape.text)
        return "\n".join(lines), "python-pptx"
    except ImportError:
        return "", "pptx_requires_python_pptx"
    except Exception:
        return "", "pptx_parse_failed"
