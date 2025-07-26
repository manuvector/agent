import base64
import io, json, os, time, requests, pdfminer.high_level
from collections import defaultdict
from urllib.parse import urlencode, parse_qs, unquote

from django.conf               import settings
from django.contrib.auth.decorators import login_required
from django.db                 import connection
from django.http               import JsonResponse, HttpResponseRedirect
from django.middleware.csrf    import get_token
from django.shortcuts          import redirect, render
from django.urls               import reverse
from django.views.decorators.http  import require_GET, require_POST
from django.views.decorators.csrf  import ensure_csrf_cookie

from openai                    import OpenAI
from pgvector.psycopg          import register_vector

from agent.models  import DriveAuth, NotionAuth, UserFile
from agent.ingest  import ingest_drive_file, ingest_notion_page
from rag.models    import RagChunk


# ─────────────────────────
client         = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
EMBED_MODEL    = "text-embedding-3-small"
DRIVE_SCOPE    = "https://www.googleapis.com/auth/drive.file"
NOTION_SCOPE   = "read:content,search:read"
NOTION_BASE    = "https://api.notion.com/v1"


# ------------------------------------------------------------------ helpers ---
def _abs_uri(request, name, fallback):
    """Dynamic in DEBUG, hard‑coded in prod."""
    if settings.DEBUG:
        return request.build_absolute_uri(reverse(name))
    return fallback


def _basic_auth_header() -> str:
    """Return 'Basic base64(client_id:client_secret)' for Notion OAuth."""
    creds = f"{os.getenv('NOTION_CLIENT_ID')}:{os.getenv('NOTION_CLIENT_SECRET')}"
    return "Basic " + base64.b64encode(creds.encode()).decode()


# =============================================================================
# 1. GOOGLE DRIVE
# =============================================================================
@login_required
@require_GET
def drive_token(request):
    token = _valid_drive_token(request.user)
    nxt   = request.GET.get("next")
    if token:
        return redirect(unquote(nxt)) if nxt else JsonResponse({"token": token})
    nxt = nxt or "/chat?picker=1"
    return redirect(f"{reverse('drive_connect')}?{urlencode({'next': nxt})}")


@login_required
@require_GET
def drive_connect(request):
    nxt = unquote(request.GET.get("next", "/chat"))
    params = {
        "client_id":     os.getenv("GOOGLE_CLIENT_ID"),
        "response_type": "code",
        "redirect_uri":  _abs_uri(request, "drive_callback", settings.DRIVE_REDIRECT_URI),
        "scope":         DRIVE_SCOPE,
        "access_type":   "offline",
        "prompt":        "consent",
        "state":         urlencode({"next": nxt}),
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
            "code":          code,
            "client_id":     os.getenv("GOOGLE_CLIENT_ID"),
            "client_secret": os.getenv("GOOGLE_CLIENT_SECRET"),
            "redirect_uri":  _abs_uri(request, "drive_callback", settings.DRIVE_REDIRECT_URI),
            "grant_type":    "authorization_code",
        },
        timeout=30,
    ).json()

    DriveAuth.objects.update_or_create(
        user=request.user,
        defaults={
            "access_token":  token_res["access_token"],
            "refresh_token": token_res.get("refresh_token"),
            "expiry_ts":     time.time() + token_res.get("expires_in", 0),
        },
    )

    nxt = "/chat"
    if "state" in request.GET:
        qs = parse_qs(request.GET["state"])
        nxt = qs.get("next", [nxt])[0]
    return redirect(nxt)


def _valid_drive_token(user):
    auth = getattr(user, "driveauth", None)
    if not auth:
        return None
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
        auth.expiry_ts    = time.time() + res.get("expires_in", 0)
        auth.save()
    return auth.access_token


@login_required
@require_POST
def store_selected_files(request):
    """POST {"files":[{"id":…,"name":…}]} to ingest Drive files."""
    files = (json.loads(request.body or "{}")).get("files") or []
    if not files:
        return JsonResponse({"error": "No files"}, status=400)

    token = _valid_drive_token(request.user)
    if not token:
        return JsonResponse({"error": "No Drive token"}, status=403)

    ing = 0
    for f in files:
        UserFile.objects.update_or_create(
            user=request.user, file_id=f["id"], defaults={"name": f["name"]}
        )
        try:
            ingest_drive_file(request.user, f["id"], token)
            ing += 1
        except Exception:
            continue
    return JsonResponse({"stored": len(files), "ingested": ing})


# =============================================================================
# 2. NOTION
# =============================================================================
@login_required
@require_GET
def notion_token(request):
    token = _valid_notion_token(request.user)
    nxt   = request.GET.get("next")
    if token:
        return redirect(unquote(nxt)) if nxt else JsonResponse({"token": token})
    nxt = nxt or "/chat?npicker=1"
    return redirect(f"{reverse('notion_connect')}?{urlencode({'next': nxt})}")


@login_required
@require_GET
def notion_connect(request):
    nxt = unquote(request.GET.get("next", "/chat"))
    params = {
        "client_id":     os.getenv("NOTION_CLIENT_ID"),
        "response_type": "code",
        "redirect_uri":  _abs_uri(request, "notion_callback", settings.NOTION_REDIRECT_URI),
        "scope":         NOTION_SCOPE,
        "owner":         "user",
        "state":         urlencode({"next": nxt}),
    }
    return HttpResponseRedirect(f"{NOTION_BASE}/oauth/authorize?" + urlencode(params))


@login_required
@require_GET
def notion_callback(request):
    code = request.GET.get("code")
    if not code:
        return JsonResponse({"error": "Missing code"}, status=400)

    res = requests.post(
        f"{NOTION_BASE}/oauth/token",
        headers={
            "Content-Type": "application/json",
            "Authorization": _basic_auth_header(),
        },
        json={
            "grant_type":   "authorization_code",
            "code":         code,
            "redirect_uri": _abs_uri(request, "notion_callback", settings.NOTION_REDIRECT_URI),
        },
        timeout=30,
    ).json()

    if "access_token" not in res:
        return JsonResponse(res, status=400)

    NotionAuth.objects.update_or_create(
        user=request.user,
        defaults={
            "access_token":  res["access_token"],
            "refresh_token": res.get("refresh_token"),
            "workspace_id":  res["workspace_id"],
            "expiry_ts":     time.time() + res.get("expires_in", 0),
        },
    )

    nxt = "/chat"
    if "state" in request.GET:
        qs = parse_qs(request.GET["state"])
        nxt = qs.get("next", [nxt])[0]
    return redirect(nxt)


def _valid_notion_token(user):
    auth = getattr(user, "notionauth", None)
    if not auth:
        return None
    if auth.expiry_ts <= time.time() + 60 and auth.refresh_token:
        res = requests.post(
            f"{NOTION_BASE}/oauth/token",
            headers={
                "Content-Type": "application/json",
                "Authorization": _basic_auth_header(),
            },
            json={
                "grant_type":    "refresh_token",
                "refresh_token": auth.refresh_token,
            },
            timeout=30,
        ).json()
        auth.access_token = res["access_token"]
        auth.expiry_ts    = time.time() + res.get("expires_in", 0)
        auth.save()
    return auth.access_token


@login_required
@require_GET
def notion_pages(request):
    """Proxy Notion /search so the SPA can list pages."""
    token = _valid_notion_token(request.user)
    if not token:
        return JsonResponse({"error": "No Notion token"}, status=403)
    q = request.GET.get("q", "")
    res = requests.post(
        f"{NOTION_BASE}/search",
        headers={
            "Authorization": f"Bearer {token}",
            "Notion-Version": "2022-06-28",
            "Content-Type":   "application/json",
        },
        json={"query": q, "sort": {"direction": "descending", "timestamp": "last_edited_time"}},
        timeout=30,
    ).json()
    pages = []
    for p in res.get("results", []):
        if p["object"] != "page":
            continue
        title_els = p["properties"].get("title", {}).get("title", [])
        title = title_els[0]["plain_text"] if title_els else "(untitled)"
        pages.append({"id": p["id"], "title": title})
    return JsonResponse(pages, safe=False)


@login_required
@require_POST
def store_notion_pages(request):
    pages = (json.loads(request.body or "{}")).get("pages") or []
    if not pages:
        return JsonResponse({"error": "No pages"}, status=400)
    token = _valid_notion_token(request.user)
    if not token:
        return JsonResponse({"error": "No Notion token"}, status=403)
    ing = 0
    for p in pages:
        UserFile.objects.update_or_create(
            user=request.user, file_id=p["id"], defaults={"name": p["title"]}
        )
        try:
            ingest_notion_page(request.user, p["id"], token)
            ing += 1
        except Exception:
            continue
    return JsonResponse({"stored": len(pages), "ingested": ing})


# =============================================================================
# 3. COMMON RAG / CHAT (unchanged)
# =============================================================================
def _embed_query(q: str):
    return client.embeddings.create(model=EMBED_MODEL, input=q).data[0].embedding


def _pull_drive_text(file_id: str, token: str) -> str:
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
        mime_out = export_map.get(mime)
        if not mime_out:
            return ""
        url = f"https://www.googleapis.com/drive/v3/files/{file_id}/export?mimeType={mime_out}"
    else:
        url = f"https://www.googleapis.com/drive/v3/files/{file_id}?alt=media"

    data = requests.get(url, headers=hdrs, timeout=120).content
    return (
        pdfminer.high_level.extract_text(io.BytesIO(data))
        if mime == "application/pdf" or name.lower().endswith(".pdf")
        else data.decode("utf-8", errors="ignore")
    )


def _pull_notion_text(file_id: str, token: str) -> str:
    hdrs = {
        "Authorization": f"Bearer {token}",
        "Notion-Version": "2022-06-28"
    }
    out, stack = [], [file_id]
    while stack:
        blk_id = stack.pop()
        res = requests.get(f"{NOTION_BASE}/blocks/{blk_id}/children?page_size=100",
                           headers=hdrs, timeout=30).json()
        for blk in res.get("results", []):
            if blk["type"] == "paragraph":
                out.append("".join(t["plain_text"] for t in blk["paragraph"]["rich_text"]))
            if blk.get("has_children"):
                stack.append(blk["id"])
    return "\n".join(out)


def _export_text(user, file_id):
    dt = _valid_drive_token(user)
    if dt:
        try:
            return _pull_drive_text(file_id, dt)
        except Exception:
            pass
    nt = _valid_notion_token(user)
    if nt:
        try:
            return _pull_notion_text(file_id, nt)
        except Exception:
            pass
    return ""


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
            [user.id, emb, k]
        )
        rows = cur.fetchall()

    if not rows:
        return []

    contexts = []
    for file_id, start, end in rows:
        full = _export_text(user, file_id)
        contexts.append(full[start:end])
    return contexts[:k]


@require_POST
def chat_completion(request):
    msg = (json.loads(request.body or "{}")).get("message", "").strip()
    if not msg:
        return JsonResponse({"response": "Please enter a message."})

    docs = get_relevant_context(msg, request.user, 3)
    ctx  = "".join(f"<doc>{c}</doc>\n" for c in docs)

    reply = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system",
             "content": "Answer using the context below. If irrelevant, answer normally.\n" + ctx},
            {"role": "user", "content": msg},
        ],
    ).choices[0].message.content.strip()

    return JsonResponse({"response": reply})


# =============================================================================
# 4. CSRF / SPA ENTRY
# =============================================================================
@ensure_csrf_cookie
def index_with_csrf(request):
    return render(request, "index.html")


@require_GET
def get_csrf_token(request):
    return JsonResponse({"csrfToken": get_token(request)})

