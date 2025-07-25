import io
import json
import os
import time
import requests
import pdfminer.high_level

from collections import defaultdict
from urllib.parse import urlencode, parse_qs, unquote

from django.contrib.auth.decorators import login_required
from django.db import connection
from django.http import JsonResponse, HttpResponseRedirect
from django.middleware.csrf import get_token
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST
from django.views.decorators.csrf import ensure_csrf_cookie

from openai import OpenAI
from pgvector.psycopg import register_vector

from agent.models import DriveAuth, UserFile
from agent.drive_ingest import ingest_drive_file
from rag.models import RagChunk

# ────────────────────────────────────────────────────────────────────────────────
# Globals
# ────────────────────────────────────────────────────────────────────────────────
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
EMBED_MODEL = "text-embedding-3-small"
DRIVE_SCOPE = "https://www.googleapis.com/auth/drive.file"


@login_required
@require_GET
def drive_token(request):
    """
    • If the user already has a fresh Drive token:
        – when the request came via <a href> / window.location (i.e. a *navigation*)
          and includes a ?next=… param → redirect to that `next` URL.
        – otherwise (XHR / fetch) → return JSON  {token: …}.
    • If there's no token yet: redirect to Google OAuth.
    """
    token = _valid_token(request.user)
    next_param = request.GET.get("next")          # may be None

    if token:
        if next_param:                            # browser navigation branch
            return redirect(unquote(next_param))
        return JsonResponse({"token": token})     # XHR / fetch branch

    # ---------- no token yet: kick off OAuth ----------
    next_target = next_param or "/chat?picker=1"
    return redirect(
        f"{reverse('drive_connect')}?{urlencode({'next': next_target})}"
    )


# ────────────────────────────────────────────────────────────────────────────────
# OAuth helpers
# ────────────────────────────────────────────────────────────────────────────────
@login_required
@require_GET
def drive_connect(request):
    """
    Kick‑off Google OAuth. A `next` query param is passed through Google via the
    OAuth `state` parameter so we know where to come back afterwards.
    """
    next_url = unquote(request.GET.get("next", "/chat"))
    params = {
        "client_id":       os.getenv("GOOGLE_CLIENT_ID"),
        "redirect_uri":    request.build_absolute_uri(reverse("drive_callback")),
        "response_type":   "code",
        "scope":           DRIVE_SCOPE,
        "access_type":     "offline",
        "prompt":          "consent",
        "state":           urlencode({"next": next_url}),
    }
    url = "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params)
    return HttpResponseRedirect(url)


@login_required
@require_GET
def drive_callback(request):
    """
    Handle Google's redirect, exchange the `code` for tokens, store them,
    then send the user back to whatever we got in `state->next` (defaults /chat).
    """
    code = request.GET.get("code")
    if not code:
        return JsonResponse({"error": "Missing code"}, status=400)

    # Exchange code for tokens
    token_res = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "code":          code,
            "client_id":     os.getenv("GOOGLE_CLIENT_ID"),
            "client_secret": os.getenv("GOOGLE_CLIENT_SECRET"),
            "redirect_uri":  request.build_absolute_uri(reverse("drive_callback")),
            "grant_type":    "authorization_code",
        },
        timeout=30,
    ).json()

    DriveAuth.objects.update_or_create(
        user=request.user,
        defaults={
            "access_token": token_res["access_token"],
            "refresh_token": token_res.get("refresh_token"),
            "expiry_ts":     time.time() + token_res.get("expires_in", 0),
        },
    )

    # Figure out where to go next
    next_url = "/chat"
    if "state" in request.GET:
        qs = parse_qs(request.GET["state"])
        next_url = qs.get("next", [next_url])[0]

    return redirect(next_url)


def _valid_token(user):
    """
    Return a fresh Drive access token or None.
    """
    auth = getattr(user, "driveauth", None)
    if not auth:
        return None

    # refresh if expiring in the next 60 s
    if auth.expiry_ts <= time.time() + 60 and auth.refresh_token:
        res = requests.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id":     os.getenv("GOOGLE_CLIENT_ID"),
                "client_secret": os.getenv("GOOGLE_CLIENT_SECRET"),
                "refresh_token": auth.refresh_token,
                "grant_type":    "refresh_token",
            },
            timeout=30,
        ).json()
        auth.access_token = res["access_token"]
        auth.expiry_ts   = time.time() + res.get("expires_in", 0)
        auth.save()

    return auth.access_token


# ────────────────────────────────────────────────────────────────────────────────
# File ingestion  &  storage
# ────────────────────────────────────────────────────────────────────────────────
@login_required
@require_POST
def store_selected_files(request):
    """
    Payload: {"files":[{"id":"…","name":"…"}, …]}
    Saves metadata + ingests embeddings/offsets only.
    """
    payload = json.loads(request.body or "{}")
    files   = payload.get("files") or []
    if not files:
        return JsonResponse({"error": "No files"}, status=400)

    token = _valid_token(request.user)
    if not token:
        return JsonResponse({"error": "No Drive token"}, status=403)

    ingested = 0
    for f in files:
        UserFile.objects.update_or_create(
            user=request.user,
            file_id=f["id"],
            defaults={"name": f["name"]},
        )
        try:
            ingest_drive_file(request.user, f["id"], token)
            ingested += 1
        except Exception:
            continue

    return JsonResponse({"stored": len(files), "ingested": ingested})

# ────────────────────────────────────────────────────────────────────────────────
# RAG helpers & chat endpoint
# ────────────────────────────────────────────────────────────────────────────────
def _embed_query(q: str):
    return client.embeddings.create(model=EMBED_MODEL, input=q).data[0].embedding


def _export_drive_text(file_id: str, token: str) -> str:
    hdrs = {"Authorization": f"Bearer {token}"}
    meta = requests.get(
        f"https://www.googleapis.com/drive/v3/files/{file_id}?fields=name,mimeType",
        headers=hdrs, timeout=30,
    ).json()
    name, mime = meta["name"], meta["mimeType"]

    if mime.startswith("application/vnd.google-apps"):
        export_map = {
            "application/vnd.google-apps.document":     "text/plain",
            "application/vnd.google-apps.presentation": "text/plain",
            "application/vnd.google-apps.spreadsheet":  "text/csv",
        }
        export_mime = export_map.get(mime)
        if not export_mime:
            return ""
        url = (f"https://www.googleapis.com/drive/v3/files/{file_id}/export"
               f"?mimeType={export_mime}")
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
    msg  = data.get("message", "").strip()
    if not msg:
        return JsonResponse({"response": "Please enter a message."})

    docs = get_relevant_context(msg, request.user, 3)
    ctx  = "".join(f"<doc>{c}</doc>\n" for c in docs)

    reply = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {
                "role":    "system",
                "content":
                    "Answer using the context below. If irrelevant, answer normally.\n" + ctx,
            },
            {"role": "user", "content": msg},
        ],
    ).choices[0].message.content.strip()

    return JsonResponse({"response": reply})

# ────────────────────────────────────────────────────────────────────────────────
# CSRF helpers / SPA entry
# ────────────────────────────────────────────────────────────────────────────────
@ensure_csrf_cookie
def index_with_csrf(request):
    return render(request, "index.html")


@require_GET
def get_csrf_token(request):
    return JsonResponse({"csrfToken": get_token(request)})

