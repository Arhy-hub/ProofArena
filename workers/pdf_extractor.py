#!/usr/bin/env python3
"""
workers/pdf_extractor.py — PDF / image extraction worker

Reads {"file_path": "...", "file_type": "pdf|image"} JSON from stdin.
Extracts conjecture + proof text via pdfplumber (PDFs) or Claude Vision (images / scanned PDFs).
Writes extraction result JSON to stdout.

Usage:
    echo '{"file_path": "/tmp/proof.pdf", "file_type": "pdf"}' | python workers/pdf_extractor.py
    echo '{"file_path": "/tmp/proof.png", "file_type": "image"}' | python workers/pdf_extractor.py
"""

import base64
import json
import os
import sys
from pathlib import Path

import anthropic
from dotenv import load_dotenv

load_dotenv()

EXTRACTION_MODEL = "claude-haiku-4-5-20251001"
MIN_TEXT_CHARS = 50

SYSTEM_PROMPT = """You are extracting a mathematical proof from an image or document.
Return ONLY valid JSON with two fields:
- "conjecture": the statement being proved (string)
- "proof": the proof text (string)

Preserve mathematical notation. Use Unicode for symbols (², ∀, ∈, →).
If you cannot identify a clear proof, return:
{"conjecture": null, "proof": null, "error": "No proof found"}"""


def _claude_vision(client: anthropic.Anthropic, image_bytes: bytes, media_type: str) -> dict:
    """Send image bytes to Claude Vision and return extracted conjecture/proof."""
    b64 = base64.standard_b64encode(image_bytes).decode("utf-8")
    response = client.messages.create(
        model=EXTRACTION_MODEL,
        max_tokens=2048,
        system=SYSTEM_PROMPT,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {"type": "base64", "media_type": media_type, "data": b64},
                },
                {"type": "text", "text": "Extract the conjecture and proof from this image."},
            ],
        }],
    )
    text = response.content[0].text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    return json.loads(text)


def _claude_text(client: anthropic.Anthropic, text: str) -> dict:
    """Ask Claude to identify conjecture/proof from extracted text."""
    response = client.messages.create(
        model=EXTRACTION_MODEL,
        max_tokens=2048,
        system=SYSTEM_PROMPT,
        messages=[{
            "role": "user",
            "content": f"Extract the conjecture and proof from this text:\n\n{text}",
        }],
    )
    raw = response.content[0].text.strip()
    if raw.startswith("```"):
        lines = raw.split("\n")
        raw = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    return json.loads(raw)


def _extract_pdf(client: anthropic.Anthropic, file_path: Path) -> dict:
    """Try pdfplumber first; fall back to Claude Vision if text is too short."""
    try:
        import pdfplumber
    except ImportError:
        return _extract_pdf_vision(client, file_path)

    raw_text = ""
    try:
        with pdfplumber.open(file_path) as pdf:
            raw_text = "\n".join(
                page.extract_text() or "" for page in pdf.pages
            ).strip()
    except Exception:
        pass

    if len(raw_text) >= MIN_TEXT_CHARS:
        result = _claude_text(client, raw_text)
        result["raw_extracted_text"] = raw_text
        result["extraction_method"] = "pdfplumber"
        result.setdefault("error", None)
        return result

    # Scanned PDF — fall back to Vision on each page
    return _extract_pdf_vision(client, file_path)


def _extract_pdf_vision(client: anthropic.Anthropic, file_path: Path) -> dict:
    """Render PDF pages as images and run Claude Vision on each."""
    try:
        from PIL import Image
        import pdfplumber
        import io

        pages_text = []
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                img = page.to_image(resolution=150).original
                buf = io.BytesIO()
                img.save(buf, format="PNG")
                page_result = _claude_vision(client, buf.getvalue(), "image/png")
                if page_result.get("conjecture") or page_result.get("proof"):
                    pages_text.append(page_result)
                    break  # take the first page that yields a result

        if pages_text:
            r = pages_text[0]
            r["raw_extracted_text"] = ""
            r["extraction_method"] = "claude_vision"
            r.setdefault("error", None)
            return r

    except Exception as e:
        pass

    return {
        "conjecture": None,
        "proof": None,
        "raw_extracted_text": "",
        "extraction_method": "claude_vision",
        "error": "Could not extract proof from PDF",
    }


def _extract_image(client: anthropic.Anthropic, file_path: Path) -> dict:
    """Send image directly to Claude Vision."""
    suffix = file_path.suffix.lower()
    media_type_map = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png"}
    media_type = media_type_map.get(suffix, "image/png")

    image_bytes = file_path.read_bytes()
    result = _claude_vision(client, image_bytes, media_type)
    result["raw_extracted_text"] = ""
    result["extraction_method"] = "claude_vision"
    result.setdefault("error", None)
    return result


def main():
    raw = sys.stdin.read().strip()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        json.dump({"conjecture": None, "proof": None, "raw_extracted_text": "",
                   "extraction_method": None, "error": f"Invalid JSON input: {e}"}, sys.stdout)
        sys.exit(1)

    file_path = Path(data.get("file_path", ""))
    file_type = data.get("file_type", "")

    if not file_path.exists():
        json.dump({"conjecture": None, "proof": None, "raw_extracted_text": "",
                   "extraction_method": None, "error": f"File not found: {file_path}"}, sys.stdout)
        sys.exit(1)

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        json.dump({"conjecture": None, "proof": None, "raw_extracted_text": "",
                   "extraction_method": None, "error": "ANTHROPIC_API_KEY not set"}, sys.stdout)
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)

    try:
        if file_type == "image":
            result = _extract_image(client, file_path)
        elif file_type == "pdf":
            result = _extract_pdf(client, file_path)
        else:
            result = {"conjecture": None, "proof": None, "raw_extracted_text": "",
                      "extraction_method": None, "error": f"Unknown file_type: {file_type}"}
    except Exception as e:
        result = {"conjecture": None, "proof": None, "raw_extracted_text": "",
                  "extraction_method": None, "error": str(e)}

    json.dump(result, sys.stdout, ensure_ascii=False)


if __name__ == "__main__":
    main()
