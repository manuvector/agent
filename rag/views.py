import json, os
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from openai import OpenAI
from rag.models import Document

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

@csrf_exempt                      # keep or switch to DRF token auth
def ingest_document(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=405)

    try:
        payload = json.loads(request.body.decode())
        text = payload.get("content", "").strip()
        if not text:
            return JsonResponse({"error": "content is empty"}, status=400)

        emb = client.embeddings.create(
            model="text-embedding-3-small",
            input=text
        ).data[0].embedding

        doc = Document.objects.create(content=text, embedding=emb)
        return JsonResponse({"id": doc.id, "status": "stored"})
    except Exception as e:
        import traceback, sys; traceback.print_exc(file=sys.stderr)
        return JsonResponse({"error": str(e)}, status=400)

