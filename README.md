# The World Outside My Window
*Go live the moment. Capture what matters. Keep the memory.*

A local-first photo journal for days spent outdoors. You add photos, captions and your own notes; an open-weight model running on your own computer (Ollama + `qwen2.5:3b`) turns them into an editable story, title and captions. Built for the Hacktoberfest Open-Source AI Challenge — Week 1: Touch Grass.

**Local single-user prototype.** No login. Anyone who can reach the running backend can read and change the journal, so don't expose it on a network or public server.

## What works
Write an entry (date, places, activity, people, feelings, notes, reflection) · upload, preview, caption, reorder and remove photos · AI story / title / captions via Ollama (editable before saving) · save, list, search and filter (text, mood, activity) · open, edit, favourite, delete with confirmation · print / save as PDF through the browser · daily outdoor prompt on Explore · honest AI-status line.

## Stack
React + Vite · Flask · SQLite (`backend/journal.db`) · photos on disk (`backend/uploads/`) · Ollama.
Model: **Qwen2.5-3B-Instruct** (`qwen2.5:3b` on Ollama), by Alibaba Cloud/Qwen. Its licence is the *Qwen Research licence*, not Apache-2.0 — confirm the current terms on the model's Ollama/Hugging Face page. "Open-weight" means the weights are downloadable, not that everything is open source. Change the model with `OLLAMA_MODEL` in `.env`.

## How the AI part works
React → `POST /api/ai/generate-journal` → Flask builds a prompt from your notes, feelings, place, activity, people and photo captions (`backend/prompts.py`) → Flask calls `http://localhost:11434/api/generate` → the JSON reply is validated → you edit it → you save. If Ollama or the model is missing, you get an error with the fix; nothing is faked. The model only sees your text; **it does not look at the photos** — your captions stand in for them. A 3B model can still write generic or slightly off prose, so always read it before saving.

## Windows setup (PowerShell)
**Install once:** Python 3.10+ (tick "Add to PATH"), Node.js 18+, and Ollama from https://ollama.com/download.

**Terminal 0 – model (any terminal):**
```
ollama pull qwen2.5:3b
```
Keep the Ollama app running (it starts in the tray after install; or run `ollama serve`).

**Terminal 1 – backend:**
```
cd the-world-outside-my-window
copy .env.example .env
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```
SQLite needs no setup: `journal.db` and `uploads\` are created automatically on first start and never wiped on restart.

**Terminal 2 – frontend:**
```
cd the-world-outside-my-window\frontend
npm install
npm run dev
```
Open **http://localhost:5173** (the backend is at http://127.0.0.1:5000/api/health).

**Stop:** press `Ctrl+C` in each terminal. **Restart later:** terminal 1 → `cd backend`, `.venv\Scripts\Activate.ps1`, `python app.py`; terminal 2 → `npm run dev`. Your entries remain.

## Tests
```
cd backend
.venv\Scripts\Activate.ps1
python -m unittest -v
```
Uses a temporary database and uploads folder.

## Troubleshooting
- *Activate.ps1 is blocked:* `Set-ExecutionPolicy -Scope Process Bypass`, then retry.
- *"Can't reach Ollama":* start the Ollama app; check http://localhost:11434 shows "Ollama is running".
- *"Model not installed":* `ollama pull qwen2.5:3b`.
- *Slow or timing out:* first generation loads the model (~2 GB RAM+); raise `OLLAMA_TIMEOUT` or use a smaller model.
- *Port in use:* close the other program on 5000 / 5173.

## Privacy, benefits and trade-offs
Entries and photos are stored only on this computer and generation runs locally, so no hosted AI API sees them and there is no analytics. **Not fully offline:** the page loads Google Fonts and one Unsplash hero image, and you need internet to download Ollama and the model once. Local inference reduces reliance on paid APIs and lets you choose the model and edit the prompts; the costs are hardware requirements, weaker writing than large hosted models, and a more involved setup.

## Security notes
Uploads are checked server-side for extension, size (8 MB) and file signature, and saved under random names; photo names from the client are only accepted if they already belong to that entry. CORS allows only the local frontend origins. Debug mode is off unless `FLASK_DEBUG=1`. Errors don't return stack traces. `.env`, the database and uploads are git-ignored.

## Known limitations / future work
No authentication; photos aren't analysed by a vision model; calendar/timeline views, On This Day and a yearly recap aren't built; PDF export is the browser's print dialog; the Cancel button reloads the page; no browser-based UI tests.

## Verification status
- **Backend:** 16 automated tests were run and passed in the development sandbox (create/read/update/delete, invalid IDs, upload validation, photo cleanup, DB failure, CORS, AI errors).
- **Ollama:** not run — the sandbox has no Ollama or model. The tests confirm the request goes to `/api/generate` with the configured model and that failures are reported as failures. **Run one real generation on your laptop before the demo.**
- **Frontend:** not built or run — npm installs were blocked in the sandbox. Please run `npm install` and `npm run dev` and check the full workflow, including mobile width.
