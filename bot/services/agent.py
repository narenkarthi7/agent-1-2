"""The 'brain': the LLM picks the tool, then we run it."""
import json

import requests

from . import documents
from .llm import ask_llm
from .weather import get_weather

MODES = {"current", "history", "forecast", "last_10_days"}

ROUTER_PROMPT = """You are a router. Reply ONLY with JSON.
Tools:
- "weather": weather, temperature or rain of a place. Also give "city" and "mode":
    current = now/today, history = yesterday, forecast = tomorrow/future, last_10_days = past 10 days
- "document": questions about the uploaded resume (skills, education, projects, experience)
- "web": general knowledge that is NOT weather and NOT about the resume owner
Examples:
{"tool":"weather","city":"Chennai","mode":"last_10_days"}
{"tool":"document"}
{"tool":"web"}"""


def route(question, has_doc):
    try:
        plan = json.loads(ask_llm(ROUTER_PROMPT, f"Resume uploaded: {has_doc}\nQuestion: {question}",
                                  as_json=True))
    except (ValueError, TypeError):
        plan = {}
    if plan.get("tool") not in ("weather", "document", "web"):   # safety net
        plan["tool"] = "document" if has_doc else "web"
    if plan.get("mode") not in MODES:
        plan["mode"] = "current"
    return plan


def handle(question, doc):
    """Returns {"tool", "text", "extra"} - the browser shows it."""
    try:
        plan = route(question, doc is not None)
        tool = plan["tool"]
        if tool == "weather":
            if not plan.get("city"):
                return {"tool": tool, "text": "Which city? Example: 'Weather in Chennai today'."}
            res = get_weather(plan["city"], plan["mode"])
            data = json.dumps(res["current"] or res["rows"])
            text = ask_llm("Summarize this weather data in 2-3 simple sentences. Use ONLY the "
                           "given numbers (°C, mm, m/s). Answer the user's question.",
                           f"Question: {question}\nCity: {res['city']}\nData: {data}")
            return {"tool": tool, "text": text, "extra": {"weather": res}}
        if tool == "document":
            if doc is None:
                return {"tool": tool, "text": "Please upload your resume (PDF/TXT) first."}
            text, hits = documents.answer_document(question, doc)
            return {"tool": tool, "text": text, "extra": {"passages": hits}}
        text, links = documents.answer_web(question)
        return {"tool": tool, "extra": {"links": links},
                "text": "🌐 External info (NOT from your document): " + text}
    except (ValueError, RuntimeError, requests.RequestException) as e:
        return {"tool": "error", "text": f"⚠️ {e}"}
