import json

from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET, require_POST

from .models import ChatMessage
from .services import weather


def chat_page(request):
    return render(request, "weather/chat.html")


@require_POST
def chat_api(request):
    try:
        question = json.loads(request.body).get("question", "").strip()
    except ValueError:
        question = ""
    if not question or len(question) > 500:
        return JsonResponse({"error": "Question must be 1-500 characters."}, status=400)

    ChatMessage.objects.create(role="user", text=question)

    # Lightweight keyword->mode mapping (can be replaced by an LLM router)
    q = question.lower()
    if "last 10" in q or "past 10" in q:
        mode = "last_10_days"
    elif any(w in q for w in ("tomorrow", "forecast", "will be")):
        mode = "forecast"
    elif any(w in q for w in ("yesterday", "was", "history")):
        mode = "history"
    else:
        mode = "current"

    m = __import__("re").search(r"in\s+([A-Za-z .,'-]+)", question, __import__("re").I)
    city = m.group(1).strip() if m else ""
    if not city:
        reply = {
            "tool": "weather", "text": "Which city? Example: 'Weather in Chennai today'.",
            "extra": None,
        }
    else:
        try:
            res = weather.get_weather(city, mode)
            text = weather.summarize(question, res)
            reply = {
                "tool": "weather", "city": res["city"], "mode": mode,
                "source": res["source"], "text": text,
                "extra": {"weather": res},
            }
        except (ValueError, RuntimeError, PermissionError) as e:
            reply = {"tool": "error", "text": f"⚠️ {e}", "extra": None}

    ChatMessage.objects.create(
        role="assistant", text=reply["text"], tool=reply["tool"], extra=reply.get("extra")
    )
    return JsonResponse(reply)


@require_GET
def history_api(request):
    last = list(ChatMessage.objects.order_by("-id")[:50])[::-1]
    return JsonResponse({
        "messages": [
            {"role": m.role, "text": m.text, "tool": m.tool, "extra": m.extra}
            for m in last
        ],
    })
