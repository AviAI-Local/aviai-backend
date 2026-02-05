from .ollama_client import extract_metadata
import io
import os
import tempfile
import asyncio

from fastapi import UploadFile
from pdfminer.high_level import extract_text as extract_pdf_text
from docx import Document as DocxDocument

from .model import DocumentExtractResp, DocumentLLMResp


def _extract_text_from_txt(file_bytes: bytes) -> str:
    return file_bytes.decode("utf-8", errors="ignore")


def _extract_text_from_pdf(file_bytes: bytes) -> str:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(file_bytes)
        tmp_path = tmp.name
    try:
        return extract_pdf_text(tmp_path)
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass


def _extract_text_from_docx(file_bytes: bytes) -> str:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as tmp:
        tmp.write(file_bytes)
        tmp_path = tmp.name
    try:
        doc = DocxDocument(tmp_path)
        return "\n".join(p.text for p in doc.paragraphs)
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass


async def extract_text_from_upload(upload_file: UploadFile) -> str:
    contents = await upload_file.read()
    filename = upload_file.filename.lower()

    if filename.endswith(".txt"):
        return contents.decode("utf-8", errors="ignore")

    if filename.endswith(".pdf"):
        return await asyncio.to_thread(_extract_text_from_pdf, contents)

    if filename.endswith((".docx", ".doc")):
        return await asyncio.to_thread(_extract_text_from_docx, contents)

    raise ValueError("Unsupported file type. Please upload a .txt, .pdf, or .docx file.")


def _detect_section(line: str):
    l = line.lower()
    if "personal characteristics" in l:
        return "personal_characteristics"
    if "scenario" in l and "attitude" not in l:
        return "scenario"
    if "attitude in the interview" in l:
        return "attitude_in_interview"
    return None


def _parse_sections(text: str):
    sections = {
        "personal_characteristics": [],
        "scenario": [],
        "attitude_in_interview": [],
    }
    current = None

    for line in text.splitlines():
        sec = _detect_section(line)
        if sec:
            current = sec
            continue
        if current:
            sections[current].append(line)

    return {k: "\n".join(v).strip() for k, v in sections.items()}


async def process_document(upload_file: UploadFile) -> DocumentExtractResp:
    text = await extract_text_from_upload(upload_file)

    parsed = await asyncio.to_thread(_parse_sections, text)

    # ✅ Local Ollama call (no LangChain)
    llm_resp: DocumentLLMResp = await extract_metadata(text)

    return DocumentExtractResp(
        personal_characteristics=parsed.get("personal_characteristics", ""),
        scenario=parsed.get("scenario", ""),
        attitude_in_interview=parsed.get("attitude_in_interview", ""),
        usecase_name=llm_resp.usecase_name,
        usecase_summary=llm_resp.usecase_summary,
        character_name=llm_resp.character_name,
        gender=llm_resp.gender,
    )
