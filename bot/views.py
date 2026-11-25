import json

from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET, require_POST

from .models import ChatMessage, Chunk, Document
from .services import documents
from .services.agent import handle


def chat_page(request):
    return render(request, "bot/chat.html")


@require_POST
def chat_api(request):
    try:
        question = json.loads(request.body).get("question", "").strip()
    except ValueError:
        question = ""
    if not question or len(question) > 500:                       # input validation
        return JsonResponse({"error": "Question must be 1-500 characters."}, status=400)
    ChatMessage.objects.create(role="user", text=question)
    reply = handle(question, Document.objects.last())             # latest uploaded resume
    ChatMessage.objects.create(role="assistant", text=reply["text"],
                               tool=reply["tool"], extra=reply.get("extra"))
    return JsonResponse(reply)


@require_POST
def upload_api(request):
    f = request.FILES.get("file")
    if not f or not f.name.lower().endswith((".pdf", ".txt")) or f.size > 5 * 1024 * 1024:
        return JsonResponse({"error": "Upload a PDF or TXT file under 5 MB."}, status=400)
    try:
        chunks = documents.make_chunks(documents.read_file(f))
    except Exception:
        return JsonResponse({"error": "Could not read this file."}, status=400)
    if not chunks:
        return JsonResponse({"error": "No text found (scanned PDF?)."}, status=400)
    doc = Document.objects.create(name=f.name)
    Chunk.objects.bulk_create([Chunk(document=doc, text=c) for c in chunks])
    return JsonResponse({"name": f.name, "chunks": len(chunks)})


@require_GET
def history_api(request):
    last = list(ChatMessage.objects.order_by("-id")[:50])[::-1]
    return JsonResponse({"messages": [
        {"role": m.role, "text": m.text, "tool": m.tool, "extra": m.extra} for m in last]})
