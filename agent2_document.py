"""AGENT 2 — Document Understanding (standalone).

PDF/TXT resume upload -> keyword-scored RAG -> grounded answers. Falls back to
Wikipedia for general questions (clearly marked as external, never about the
resume owner). No web search is used to invent personal information.

Usage:
    python agent2_document.py --file resume.pdf --q "What are my skills?"
    python agent2_document.py --file resume.txt --q "Where did I study?"
"""
import argparse
import json
import os
import re
import sys

import requests
from dotenv import load_dotenv
from pypdf import PdfReader

load_dotenv()

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")

STOP = {
    "the", "a", "an", "is", "are", "of", "in", "on", "and", "to", "what", "my",
    "me", "i", "do", "did", "does", "for", "with", "about", "tell", "which",
    "where", "how", "have", "has", "your", "you", "can", "could", "would",
}


def read_file(path):
    if path.lower().endswith(".pdf"):
        return "\n".join(p.extract_text() or "" for p in PdfReader(path).pages)
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()


def make_chunks(text, size=120, overlap=30):
    """Cut text into overlapping ~120-word chunks."""
    words = text.split()
    return [" ".join(words[i : i + size]) for i in range(0, len(words), size - overlap)]


def _words(text):
    return {w for w in re.findall(r"[a-z0-9+#]+", text.lower()) if w not in STOP}


def search(question, chunks, k=3):
    """Score a chunk by shared question words; return best k."""
    q = _words(question)
    scored = [(len(q & _words(c)), c) for c in chunks]
    scored = sorted([s for s in scored if s[0] > 0], reverse=True)
    return [text for _, text in scored[:k]]


def answer_document(question, chunks):
    hits = search(question, chunks)
    if not hits:
        return "Not found in the document.", []
    system = (
        "Answer ONLY using the CONTEXT from the user's document. If the answer is not "
        "in the context, reply exactly: Not found in the document. Never guess."
    )
    context = "\n---\n".join(hits)
    body = {
        "model": OLLAMA_MODEL,
        "stream": False,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": f"CONTEXT:\n{context}\n\nQUESTION: {question}"},
        ],
    }
    r = requests.post(OLLAMA_URL + "/api/chat", json=body, timeout=120)
    r.raise_for_status()
    return r.json()["message"]["content"], hits


def answer_web(question):
    """Fallback for general knowledge (NOT about the resume owner). Returns sources."""
    r = requests.get(
        "https://en.wikipedia.org/w/api.php",
        timeout=15,
        headers={"User-Agent": "chatbot-assessment/1.0"},
        params={
            "action": "query",
            "format": "json",
            "generator": "search",
            "gsrsearch": question,
            "gsrlimit": 3,
            "prop": "extracts",
            "exintro": 1,
            "explaintext": 1,
            "exchars": 500,
        },
    )
    r.raise_for_status()
    pages = sorted(
        r.json().get("query", {}).get("pages", {}).values(), key=lambda p: p["index"]
    )
    if not pages:
        return "No web results found.", []
    text = "\n".join(
        f"[{i+1}] {p['title']}: {p['extract']}" for i, p in enumerate(pages)
    )
    body = {
        "model": OLLAMA_MODEL,
        "stream": False,
        "messages": [
            {"role": "system", "content": "Answer briefly using ONLY these results. Cite like [1]."},
            {"role": "user", "content": f"RESULTS:\n{text}\n\nQUESTION: {question}"},
        ],
    }
    r = requests.post(OLLAMA_URL + "/api/chat", json=body, timeout=120)
    r.raise_for_status()
    answer = r.json()["message"]["content"]
    links = [
        {"title": p["title"], "url": "https://en.wikipedia.org/wiki/" + p["title"].replace(" ", "_")}
        for p in pages
    ]
    return answer, links


def run(path, question):
    text = read_file(path)
    chunks = make_chunks(text)
    if not chunks:
        return {"tool": "document", "text": "No text found in the file (scanned PDF?).", "passages": []}

    answer, hits = answer_document(question, chunks)
    result = {
        "tool": "document",
        "text": answer,
        "passages": hits,
        "chunks": len(chunks),
    }

    # If the document has no answer, offer web fallback for general questions.
    if answer.strip() == "Not found in the document.":
        web_answer, links = answer_web(question)
        result["web_fallback"] = web_answer
        result["web_links"] = links
        result["text"] += f"\n\n🌐 Not in your document. External info: {web_answer}"
    return result


def main():
    ap = argparse.ArgumentParser(description="Agent 2 — Document Understanding")
    ap.add_argument("--file", required=True, help="Path to PDF or TXT resume")
    ap.add_argument("--q", required=True, help="Question about the document")
    args = ap.parse_args()

    try:
        result = run(args.file, args.q)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    except (FileNotFoundError, RuntimeError, requests.RequestException) as e:
        print(f"⚠️  {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
