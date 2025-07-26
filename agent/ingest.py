# agent/ingest.py
import io, os, time, requests, pdfminer.high_level, itertools
from openai import OpenAI
from rag.models import RagChunk

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ───────── shared helpers ─────────
def _chunk_text(text, size=1500, overlap=200):
    step = size - overlap
    for idx, start in enumerate(range(0, len(text), step)):
        yield idx, start, min(len(text), start + size), text[start:start + size]

def _embed(text):
    return client.embeddings.create(
        model="text-embedding-3-small", input=text
    ).data[0].embedding

# ───────── Drive ingestion (finished) ─────────
def ingest_drive_file(user, file_id: str, token: str):
    hdrs = {"Authorization": f"Bearer {token}"}
    meta = requests.get(
        f"https://www.googleapis.com/drive/v3/files/{file_id}?fields=name,mimeType",
        headers=hdrs, timeout=30
    ).json()
    name, mime = meta["name"], meta["mimeType"]

    if mime.startswith("application/vnd.google-apps"):
        export_map = {
            "application/vnd.google-apps.document":     "text/plain",
            "application/vnd.google-apps.presentation": "text/plain",
            "application/vnd.google-apps.spreadsheet":  "text/csv",
        }
        mime_out = export_map.get(mime)
        if not mime_out:
            return
        url = f"https://www.googleapis.com/drive/v3/files/{file_id}/export?mimeType={mime_out}"
    else:
        url = f"https://www.googleapis.com/drive/v3/files/{file_id}?alt=media"

    data  = requests.get(url, headers=hdrs, timeout=120).content
    text  = (
        pdfminer.high_level.extract_text(io.BytesIO(data))
        if mime == "application/pdf" or name.lower().endswith(".pdf")
        else data.decode("utf-8", errors="ignore")
    )

    for idx, start, end, chunk in _chunk_text(text):
        RagChunk.objects.create(
            user=user, file_id=file_id, idx=idx,
            char_start=start, char_end=end,
            embedding=_embed(chunk)
        )

# ───────── Notion helpers ─────────
def _pull_page_text(page_id, headers):
    """DFS walk the block tree → plain‑text"""
    out, stack = [], [page_id]
    while stack:
        blk_id = stack.pop()
        res = requests.get(
            f"https://api.notion.com/v1/blocks/{blk_id}/children?page_size=100",
            headers=headers, timeout=30
        ).json()
        for blk in res.get("results", []):
            if blk["type"] == "paragraph":
                parts = blk["paragraph"]["rich_text"]
                out.append("".join(t["plain_text"] for t in parts))
            # push children (if any)
            if blk.get("has_children"):
                stack.append(blk["id"])
    return "\n".join(out)

def ingest_notion_page(user, page_id: str, token: str):
    headers = {
        "Authorization": f"Bearer {token}",
        "Notion-Version": "2022-06-28"
    }
    text = _pull_page_text(page_id, headers)
    if not text.strip():
        return
    for idx, start, end, chunk in _chunk_text(text):
        RagChunk.objects.create(
            user=user, file_id=page_id, idx=idx,
            char_start=start, char_end=end,
            embedding=_embed(chunk)
        )

