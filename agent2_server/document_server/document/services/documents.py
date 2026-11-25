"""AGENT 2 — Document Understanding (self-contained Django server).

PDF/TXT resume upload -> keyword-scored RAG -> grounded answers.
Wikipedia web fallback for general questions (clearly marked external).
"""
import re
import requests
from dotenv import load_dotenv
from pypdf import PdfReader

from . import llm

load_dotenv()

STOP = {"the", "a", "an", "is", "are", "of", "in", "on", "and", "to", "what", "my", "me", "i",
        "do", "did", "does", "for", "with", "about", "tell", "which", "where", "how", "have", "has",
        "your", "you", "can", "could", "would"}


def read_file(f):
    if f.name.lower().endswith(".pdf"):
        return "\n".join(p.extract_text() or "" for p in PdfReader(f).pages)
    return f.read().decode("utf-8", errors="ignore")


def make_chunks(text, size=120, overlap=30):
    words = text.split()
    return [" ".join(words[i:i + size]) for i in range(0, len(words), size - overlap)]


def _words(text):
    return {w for w in re.findall(r"[a-z0-9+#]+", text.lower()) if w not in STOP}


def search(question, chunks, k=3):
    q = _words(question)
    scored = [(len(q & _words(c.text)), c.text) for c in chunks]
    scored = sorted([s for s in scored if s[0] > 0], reverse=True)
    return [text for _, text in scored[:k]]


def answer_document(question, doc):
    hits = search(question, doc.chunks.all())
    if not hits:
        return "Not found in the document.", []
    system = ("Answer ONLY using the CONTEXT from the user's document. If the answer is not "
              "in the context, reply exactly: Not found in the document. Never guess.")
    context = "\n---\n".join(hits)
    return llm.ask_llm(system, f"CONTEXT:\n{context}\n\nQUESTION: {question}"), hits


def answer_web(question):
    r = requests.get("https://en.wikipedia.org/w/api.php", timeout=15,
                     headers={"User-Agent": "chatbot-assessment/1.0"},
                     params={"action": "query", "format": "json", "generator": "search",
                             "gsrsearch": question, "gsrlimit": 3, "prop": "extracts",
                             "exintro": 1, "explaintext": 1, "exchars": 500})
    r.raise_for_status()
    pages = sorted(r.json().get("query", {}).get("pages", {}).values(), key=lambda p: p["index"])
    if not pages:
        return "No web results found.", []
    text = "\n".join(f"[{i+1}] {p['title']}: {p['extract']}" for i, p in enumerate(pages))
    answer = llm.ask_llm("Answer briefly using ONLY these results. Cite like [1].",
                         f"RESULTS:\n{text}\n\nQUESTION: {question}")
    links = [{"title": p["title"], "url": "https://en.wikipedia.org/wiki/" + p["title"].replace(" ", "_")}
             for p in pages]
    return answer, links
