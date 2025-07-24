# agent/views.py
import json, os, time, requests
from urllib.parse import urlencode

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseRedirect
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST
from django.db import connection

from openai import OpenAI
from pgvector.psycopg import register_vector

from .models import DriveAuth, UserFile
from .drive_ingest import ingest_drive_file  # ← NEW

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
_register_done = False


# ─── basic RAG search ───────────────────────────────────────────────────────
def get_relevant_context(q: str, k: int = 1):
    global _register_done
    emb = client.embeddings.create(
        model="text-embedding-3-small", input=q
    ).data[0].embedding

    with connection.cursor() as cur:
        if not _register_done:
            register_vector(cur.connection)
            _register_done = True
        cur.execute(
            "SELECT content FROM rag_document ORDER BY embedding <-> %s::vector LIMIT %s",
            [emb, k],
        )
        return [row[0] for row in cur.fetchall()]


@csrf_exempt
@require_POST
def chat_completion(request):
    msg = json.loads(request.body).get("message", "").strip()
    if not msg:
        return JsonResponse({"response": "Please enter a message."})

    docs = get_relevant_context(msg, 3)
    ctx = "".join(f"<doc>{c}</doc>\n" for c in docs)

    reply = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {
                "role": "system",
                "content": (
                    "Answer using the context below. "
                    "If irrelevant, answer normally.\n" + ctx
                ),
            },
            {"role": "user", "content": msg},
        ],
    ).choices[0].message.content.strip()

    return JsonResponse({"response": reply})


# ─── Google Drive OAuth flow ────────────────────────────────────────────────
DRIVE_SCOPE = "https://www.googleapis.com/auth/drive.readonly"


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
    return HttpResponseRedirect(
        "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params)
    )


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


# ─── API endpoints for Picker ───────────────────────────────────────────────
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
    • Saves metadata
    • Immediately ingests each file into the vector DB
    """
    payload = json.loads(request.body)
    files = payload.get("files") or []
    if not files:
        return JsonResponse({"error": "No files"}, status=400)

    token = _valid_token(request.user)
    if not token:
        return JsonResponse({"error": "No Drive token"}, status=403)

    ingested = 0
    for f in files:
        uf, _ = UserFile.objects.update_or_create(
            user=request.user, file_id=f["id"], defaults={"name": f["name"]}
        )
        try:
            ingest_drive_file(request.user, f["id"], token)
            ingested += 1
        except Exception as e:
            # log or print(e) for debugging
            continue

    return JsonResponse({"stored": len(files), "ingested": ingested})

