# rag/views.py
import json
from django.db import connection
from django.db.models import Count
from django.views.decorators.http import require_GET, require_POST
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from openai import OpenAI
from pgvector.psycopg import register_vector

from rag.models import RagChunk

client = OpenAI()
EMBED_MODEL = "text-embedding-3-small"

def _embed_query(q):
    return client.embeddings.create(model=EMBED_MODEL, input=q).data[0].embedding

@require_GET
def list_files(request):
    user = request.user if request.user.is_authenticated else None
    if not user:
        return JsonResponse([], safe=False)

    q = request.GET.get("q", "").strip()
    if not q:
        qs = (
            RagChunk.objects
            .filter(user=user)
            .values("file_name")
            .annotate(chunks=Count("id"))
            .order_by("file_name")
        )
        return JsonResponse(list(qs), safe=False)

    emb = _embed_query(q)
    with connection.cursor() as cur:
        register_vector(cur.connection)
        cur.execute(
            """
            SELECT file_name,
                   COUNT(*)                      AS chunks,
                   MIN(embedding <-> %s::vector) AS distance
            FROM rag_ragchunk
            WHERE user_id = %s
            GROUP BY file_name
            ORDER BY distance
            LIMIT 50
            """,
            [emb, user.id],
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
    # If still used, implement properly or delete
    return JsonResponse({"results": []})

