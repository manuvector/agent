# agent/views.py
import json, os, time, requests
from urllib.parse import urlencode
from collections import defaultdict
import io, pdfminer.high_level

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseRedirect
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST
from django.views.decorators.csrf import ensure_csrf_cookie
from django.middleware.csrf import get_token
from django.db import connection

from openai import OpenAI
from pgvector.psycopg import register_vector

from agent.models import DriveAuth, UserFile
from agent.drive_ingest import ingest_drive_file
from rag.models import RagChunk

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
EMBED_MODEL = "text-embedding-3-small"

# ───────── OAuth helpers ─────────
DRIVE_SCOPE = "https://www.googleapis.com/auth/drive.file"


@login_required
@require_GET
def drive_connect(request):
    params = {
        "client_id": os.getenv("GOOGLE_CLIENT_ID"),
        "redirect_uri": request.build_absolute_uri(reverse("drive_callback")),
        "response_type": "code",
        "scope": DRIVE_SCOPE,
        "access_type": "offline",
        "prompt": "consent",
    }
    url = "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params)
    return HttpResponseRedirect(url)


@login_required
@require_GET
def drive_callback(request):
    code = request.GET.get("code")
    if not code:
        return JsonResponse({"error": "Missing code"}, status=400)

    token_res = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "code": code,
            "client_id": os.getenv("GOOGLE_CLIENT_ID"),
            "client_secret": os.getenv("GOOGLE_CLIENT_SECRET"),
            "redirect_uri": request.build_absolute_uri(reverse("drive_callback")),
            "grant_type": "authorization_code",
        },
        timeout=30,
    ).json()

    DriveAuth.objects.update_or_create(
        user=request.user,
        defaults={
            "access_token": token_res["access_token"],
            "refresh_token": token_res.get("refresh_token"),
            "expiry_ts": time.time() + token_res.get("expires_in", 0),
        },
    )
    return HttpResponseRedirect("/chat")


def _valid_token(user):
    auth = getattr(user, "driveauth", None)
    if not auth:
        return None
    if auth.expiry_ts <= time.time() + 60 and auth.refresh_token:
        res = requests.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": os.getenv("GOOGLE_CLIENT_ID"),
                "client_secret": os.getenv("GOOGLE_CLIENT_SECRET"),
                "refresh_token": auth.refresh_token,
                "grant_type": "refresh_token",
            },
            timeout=30,
        ).json()
        auth.access_token = res["access_token"]
        auth.expiry_ts = time.time() + res.get("expires_in", 0)
        auth.save()
    return auth.access_token


@login_required
@require_GET
def drive_token(request):
    token = _valid_token(request.user)
    if not token:
        return JsonResponse({"error": "not_connected"}, status=400)
    return JsonResponse({"token": token})


@login_required
@require_POST
def store_selected_files(request):
    """
    Payload: {files:[{id,name},...]}
    Saves metadata + ingests embeddings/offsets only.
    """
    payload = json.loads(request.body or "{}")
    files = payload.get("files") or []
    if not files:
        return JsonResponse({"error": "No files"}, status=400)

    token = _valid_token(request.user)
    if not token:
        return JsonResponse({"error": "No Drive token"}, status=403)

    ingested = 0
    for f in files:
        UserFile.objects.update_or_create(
            user=request.user, file_id=f["id"], defaults={"name": f["name"]}
        )
        try:
            ingest_drive_file(request.user, f["id"], token)
            ingested += 1
        except Exception:
            continue

    return JsonResponse({"stored": len(files), "ingested": ingested})


# ───────── RAG retrieval ─────────
def _embed_query(q):
    return client.embeddings.create(model=EMBED_MODEL, input=q).data[0].embedding

def _export_drive_text(file_id: str, token: str) -> str:
    hdrs = {"Authorization": f"Bearer {token}"}
    meta = requests.get(
        f"https://www.googleapis.com/drive/v3/files/{file_id}?fields=name,mimeType",
        headers=hdrs,
        timeout=30,
    ).json()
    name = meta["name"]
    mime = meta["mimeType"]

    if mime.startswith("application/vnd.google-apps"):
        export_map = {
            "application/vnd.google-apps.document": "text/plain",
            "application/vnd.google-apps.presentation": "text/plain",
            "application/vnd.google-apps.spreadsheet": "text/csv",
        }
        export_mime = export_map.get(mime)
        if not export_mime:
            return ""
        url = (
            f"https://www.googleapis.com/drive/v3/files/{file_id}/export"
            f"?mimeType={export_mime}"
        )
    else:
        url = f"https://www.googleapis.com/drive/v3/files/{file_id}?alt=media"

    data = requests.get(url, headers=hdrs, timeout=120).content

    if mime == "application/pdf" or name.lower().endswith(".pdf"):
        return pdfminer.high_level.extract_text(io.BytesIO(data))
    return data.decode("utf-8", errors="ignore")


def get_relevant_context(q: str, user, k: int = 3):
    emb = _embed_query(q)
    with connection.cursor() as cur:
        register_vector(cur.connection)
        cur.execute(
            """
            SELECT file_id, char_start, char_end
            FROM rag_ragchunk
            WHERE user_id = %s
            ORDER BY embedding <-> %s::vector
            LIMIT %s
            """,
            [user.id, emb, k],
        )
        rows = cur.fetchall()

    if not rows:
        return []

    token = _valid_token(user)
    if not token:
        return []

    # group by file_id
    chunks_by_file = defaultdict(list)
    for file_id, start, end in rows:
        chunks_by_file[file_id].append((start, end))

    contexts = []
    for file_id, ranges in chunks_by_file.items():
        full_text = _export_drive_text(file_id, token)
        for start, end in ranges:
            contexts.append(full_text[start:end])

    return contexts[:k]


@require_POST
def chat_completion(request):
    data = json.loads(request.body or "{}")
    msg = data.get("message", "").strip()
    if not msg:
        return JsonResponse({"response": "Please enter a message."})

    docs = get_relevant_context(msg, request.user, 3)
    ctx = "".join(f"<doc>{c}</doc>\n" for c in docs)

    reply = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {
                "role": "system",
                "content": (
                    "Answer using the context below. If irrelevant, answer normally.\n" + ctx
                ),
            },
            {"role": "user", "content": msg},
        ],
    ).choices[0].message.content.strip()

    return JsonResponse({"response": reply})


# ───────── CSRF helpers ─────────
@ensure_csrf_cookie
def index_with_csrf(request):
    from django.shortcuts import render
    return render(request, "index.html")


@require_GET
def get_csrf_token(request):
    return JsonResponse({"csrfToken": get_token(request)})

