# The World Outside My Window
A local-first AI photo journal for the days you spend outdoors. Built for the Hacktoberfest Open-Source AI Challenge — Week 1: Touch Grass.

**Status:** local single-user prototype. There is no authentication, so do not expose it on a public server as-is. Not yet tested by the author's tooling — see "What's tested" below.

## Stack
React + Vite (frontend) · Flask (backend) · SQLite + local `uploads/` folder · Ollama running an open-weight model. Default `qwen2.5:3b` (set `OLLAMA_MODEL` in `.env`; check the model's license on its Ollama page before redistributing).

## Windows setup (PowerShell)
1. Install Python 3.10+, Node.js 18+, and Ollama (https://ollama.com/download).
2. Pull the model: `ollama pull qwen2.5:3b`
3. Backend:
```
cd the-world-outside-my-window
copy .env.example .env
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```
4. Frontend (second terminal):
```
cd the-world-outside-my-window\frontend
npm install
npm run dev
```
5. Open http://localhost:5173. The Home page shows whether Ollama and the model are available.

## Privacy
Text and photos stay on your machine (SQLite file + `backend/uploads/`). The only network calls are to your local Ollama, plus Google Fonts and one hero image from Unsplash loaded by the browser. A local model alone doesn't guarantee privacy if you later deploy the app elsewhere.

## Troubleshooting
- "Can't reach Ollama": start the Ollama app, then check `http://localhost:11434`.
- "Model not installed": run `ollama pull <model>`.
- Script activation blocked: `Set-ExecutionPolicy -Scope Process Bypass`.

## What's tested
Nothing has been run yet. Source was written in an environment without network access, so `npm install`, the dev server, and Ollama were not exercised.

## Not built yet
Calendar/timeline views, On This Day, vision-model photo analysis, PDF export (uses browser print instead), sharing, botanical illustrations, full landing-page sections.
