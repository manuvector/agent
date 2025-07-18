# rag/views.py
import json
import logging
import os
from io import BytesIO
from django.db.models import Count
from django.views.decorators.http import require_GET, require_POST

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from openai import OpenAI
from PyPDF2 import PdfReader
import tiktoken                          # pip install tiktoken

from rag.models import Document

logger = logging.getLogger("rag.views")
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

EMBEDDING_MODEL = "text-embedding-3-small"
MAX_TOKENS      = 6_000

enc = tiktoken.encoding_for_model(EMBEDDING_MODEL)


def split_by_tokens(text: str, max_tokens: int = MAX_TOKENS):
    """Yield ≤ max_tokens each, tokenised with tiktoken."""
    tokens = enc.encode(text)
    for i in range(0, len(tokens), max_tokens):
        yield enc.decode(tokens[i : i + max_tokens])


@csrf_exempt
def ingest_document(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=405)

    try:
        # ───────────────────────────────────────────────────────────────
        # 1. Get raw text – either from an uploaded file or from JSON
        # ───────────────────────────────────────────────────────────────
        text = ""

        if request.content_type.startswith("multipart/form-data"):
            # Expect a file field called pdf_file (or any text file)
            upload = request.FILES.get("pdf_file") or request.FILES.get("file")
            if not upload:
                return JsonResponse({"error": "No file uploaded"}, status=400)

            # 1.a PDFs
            if upload.name.lower().endswith(".pdf"):
                reader = PdfReader(upload)
                text = "\n\n".join(p.extract_text() or "" for p in reader.pages).strip()

            # 1.b Plain-text-ish files
            else:
                text = upload.read().decode("utf-8", errors="ignore").strip()

        else:
            # Fallback to the old JSON structure (content only)
            payload = json.loads(request.body.decode() or "{}")
            text = (payload.get("content") or "").strip()

        if not text:
            return JsonResponse({"error": "content is empty"}, status=400)

        # ───────────────────────────────────────────────────────────────
        # 2. Split → embed → store
        # ───────────────────────────────────────────────────────────────
        for idx, chunk in enumerate(split_by_tokens(text)):
            logger.debug(
                "Chunk %d | %d tokens | preview: %s",
                idx, len(enc.encode(chunk)), chunk[:300]
            )
            resp = client.embeddings.create(model=EMBEDDING_MODEL, input=chunk)
            emb  = resp.data[0].embedding
            Document.objects.create(content=chunk,
                                    file_name=upload.name,
                                    embedding=emb)

        return JsonResponse({"status": "stored"})

    except Exception as exc:
        logger.exception("Ingestion failed")
        return JsonResponse({"error": str(exc)}, status=400)


# top of file
from django.db import connection               # NEW
from pgvector.psycopg import register_vector   # NEW
# (keep client, EMBEDDING_MODEL, etc.)

@require_GET
def list_files(request):
    """
    GET /api/files[?q=text]

    • No q  → alphabetical list
    • q=str → list ordered by semantic distance (LOWER = more similar)
    """
    q = request.GET.get("q", "").strip()
    if not q:
        files = (
            Document.objects
            .values("file_name")
            .annotate(chunks=Count("id"))
            .order_by("file_name")
        )
        return JsonResponse(list(files), safe=False)

    # ── embed the query ─────────────────────────────────────────────
    emb = client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=q
    ).data[0].embedding

    # ── distance-ranked files ───────────────────────────────────────
    with connection.cursor() as cur:
        register_vector(cur.connection)        # enable <-> operator
        cur.execute(
            """
            SELECT file_name,
                   COUNT(*)                        AS chunks,
                   MIN(embedding <-> %s::vector)   AS distance   -- ← cast here
            FROM rag_document
            GROUP BY file_name
            ORDER BY distance
            LIMIT 50
            """,
            [emb],
        )


        rows = cur.fetchall()

    files = [
        {"file_name": fn, "chunks": c, "distance": float(d)}
        for fn, c, d in rows
    ]
    return JsonResponse(files, safe=False)


@csrf_exempt
@require_POST
def search_similar(request):
    data   = json.loads(request.body or "{}")
    query  = data.get("query", "").strip()
    limit  = int(data.get("k", 5))
    hits   = get_relevant_context(query, k=limit)  # already written helper
    return JsonResponse({"results": hits})

