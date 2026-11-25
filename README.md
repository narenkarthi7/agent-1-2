# Agentic AI Chatbot (Django + MySQL) - Weather + Resume Q&A

Built only with Python, Django and MySQL (plus HTML/CSS/JS in one template).

| Agent | Job |
|---|---|
| Weather (`bot/services/weather.py`) | current, yesterday, forecast, last 10 days -> table + line, bar, pie charts |
| Document (`bot/services/documents.py`) | resume PDF/TXT -> chunks in MySQL -> keyword-score search -> grounded answer. General questions use Wikipedia with source links |

Flow: `Browser -> Django view -> LLM router (JSON) -> tool -> LLM summary -> JSON -> Chart.js`

## Setup
1. Install Ollama, run `ollama pull llama3.2`
2. `pip install -r requirements.txt`
3. Copy `.env.example` to `.env` and fill in values (defaults to SQLite — no MySQL server needed)
   - To use MySQL instead, set `DB_ENGINE=mysql` in `.env` and create `CREATE DATABASE chatbot_db CHARACTER SET utf8mb4;`
4. `python manage.py makemigrations bot` then `python manage.py migrate`
5. `python manage.py runserver` and open http://127.0.0.1:8000

## Sample queries
- What is the weather in Chennai today?
- What was the weather in Bengaluru yesterday?
- What will the weather be like in London tomorrow?
- List the last 10 days of weather in Chennai
- What are my skills? / Where did I study? / What projects have I done?
- What is Django? (web fallback with sources)

## Check saved data
```sql
-- SQLite (default)
SELECT role, tool, LEFT(text, 60) AS msg FROM bot_chatmessage ORDER BY id DESC LIMIT 10;
SELECT d.name, COUNT(c.id) AS chunks FROM bot_document d JOIN bot_chunk c ON c.document_id = d.id GROUP BY d.id;
```

## Notes
- OpenWeatherMap history needs a paid plan. If unavailable, the app uses Open-Meteo and shows that on screen. No data is invented.
- Secrets are in `.env` (git-ignored).

## Screenshots
(add here)
