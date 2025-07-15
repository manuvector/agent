# agent/views.py
import json
import os

from django.db import connection
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from openai import OpenAI
from pgvector.psycopg import register_vector, Vector   #  ← add Vector

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
_register_done = False          # register pgvector operators once


def get_relevant_context(user_query: str, k: int = 1):
    global _register_done

    emb = client.embeddings.create(
        model="text-embedding-3-small",
        input=user_query
    ).data[0].embedding                      # this is a Python list

    with connection.cursor() as cur:
        if not _register_done:               # register once
            register_vector(cur.connection)
            _register_done = True

        cur.execute(
            """
            SELECT content
            FROM rag_document
            ORDER BY embedding <-> %s::vector
            LIMIT %s
            """,
            [emb, k],                        # ← list + cast = OK
        )
        return [row[0] for row in cur.fetchall()]


@csrf_exempt
def chat_completion(request):
    if request.method != "POST":
        return JsonResponse({"error": "Only POST allowed"}, status=405)

    try:
        data = json.loads(request.body)
        message = data.get("message", "").strip()
        if not message:
            return JsonResponse({"response": "Please enter a message."})

        docs = get_relevant_context(message, k=1)
        context = "".join(f"<doc>{c}</doc>\n" for c in docs)

        reply = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Answer using the context below. "
                        "If the context is not relevant, answer normally.\n" + context
                    ),
                },
                {"role": "user", "content": message},
            ],
        ).choices[0].message.content.strip()

        return JsonResponse({"response": reply})

    except Exception as exc:
        import traceback, sys
        traceback.print_exc(file=sys.stderr)
        return JsonResponse({"error": str(exc)}, status=400)

