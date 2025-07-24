# agent/drive_ingest.py
"""
Download a Google-Drive file, extract text in-memory, chunk → embed,
store ONLY embeddings + offsets in rag_ragchunk.
"""
import io
import os
import requests
import pdfminer.high_level

from openai import OpenAI
from rag.models import RagChunk

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def _chunk_text(text, size=1500, overlap=200):
    step = size - overlap
    out = []
    start = 0
    idx = 0
    while start < len(text):
        end = min(len(text), start + size)
        out.append((idx, start, end, text[start:end]))
        idx += 1
        start += step
    return out

def _embed(text):
    return client.embeddings.create(
        model="text-embedding-3-small", input=text
    ).data[0].embedding


def ingest_drive_file(user, file_id: str, access_token: str) -> None:
    hdrs = {"Authorization": f"Bearer {access_token}"}
    meta = requests.get(
        f"https://www.googleapis.com/drive/v3/files/{file_id}?fields=name,mimeType",
        headers=hdrs,
        timeout=30,
    ).json()
    name = meta["name"]
    mime = meta["mimeType"]

    # Download/export
    if mime.startswith("application/vnd.google-apps"):
        export_map = {
            "application/vnd.google-apps.document": "text/plain",
            "application/vnd.google-apps.presentation": "text/plain",
            "application/vnd.google-apps.spreadsheet": "text/csv",
        }
        export_mime = export_map.get(mime)
        if not export_mime:
            return
        url = f"https://www.googleapis.com/drive/v3/files/{file_id}/export?mimeType={export_mime}"
    else:
        url = f"https://www.googleapis.com/drive/v3/files/{file_id}?alt=media"

    data = requests.get(url, headers=hdrs, timeout=120).content

    if mime == "application/pdf" or name.lower().endswith(".pdf"):
        text = pdfminer.high_level.extract_text(io.BytesIO(data))
    else:
        text = data.decode("utf-8", errors="ignore")

    if not text.strip():
        return

    # Chunk → embed → store offsets only
    chunks = _chunk_text(text)
    for idx, start, end, chunk_text in chunks:
        emb = _embed(chunk_text)
        RagChunk.objects.update_or_create(
            user=user,
            file_id=file_id,
            chunk_idx=idx,
            defaults={
                "file_name": name,
                "char_start": start,
                "char_end": end,
                "embedding": emb,
            },
        )

