"""One helper to talk to a local open-source LLM (Ollama)."""
import os
import requests


def ask_llm(system, user, as_json=False):
    body = {"model": os.getenv("OLLAMA_MODEL", "llama3.2"), "stream": False,
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": user}]}
    if as_json:
        body["format"] = "json"
    url = os.getenv("OLLAMA_URL", "http://localhost:11434") + "/api/chat"
    try:
        r = requests.post(url, json=body, timeout=120)
        r.raise_for_status()
        return r.json()["message"]["content"]
    except requests.RequestException:
        raise RuntimeError("Cannot reach Ollama. Start it and run: ollama pull llama3.2")
