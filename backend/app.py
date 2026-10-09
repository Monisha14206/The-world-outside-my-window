import os, json, sqlite3, uuid, urllib.request, urllib.error
from datetime import datetime
from pathlib import Path
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv
import prompts
load_dotenv(Path(__file__).parent.parent / ".env")
BASE = Path(__file__).parent
OLLAMA = os.getenv("OLLAMA_URL", "http://localhost:11434")
MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:3b")
UP = Path(os.getenv("UPLOAD_DIR", BASE / "uploads")); UP.mkdir(parents=True, exist_ok=True)
DB = os.getenv("DB_PATH", str(BASE / "journal.db"))
EXT = {"jpg", "jpeg", "png", "webp"}; MAXB = 8 * 1024 * 1024
app = Flask(__name__); CORS(app); app.config["MAX_CONTENT_LENGTH"] = 60 * 1024 * 1024

def db():
    c = sqlite3.connect(DB); c.row_factory = sqlite3.Row; return c
with db() as c:
    c.execute("""CREATE TABLE IF NOT EXISTS journals(id TEXT PRIMARY KEY, data TEXT, date TEXT, created TEXT)""")

def row(r):
    d = json.loads(r["data"]); d["id"] = r["id"]; return d

@app.get("/api/health")
def health():
    try:
        with urllib.request.urlopen(OLLAMA + "/api/tags", timeout=3) as r:
            names = [m["name"] for m in json.load(r).get("models", [])]
        ok = any(n == MODEL or n.split(":")[0] == MODEL.split(":")[0] and ":" not in MODEL for n in names)
        return jsonify(ollama=True, model=MODEL, modelInstalled=ok or MODEL in names,
                       hint=None if (ok or MODEL in names) else f"Run: ollama pull {MODEL}")
    except Exception:
        return jsonify(ollama=False, model=MODEL, modelInstalled=False, hint="Install Ollama from ollama.com, start it, then run: ollama pull " + MODEL)

@app.get("/api/journals")
def list_j():
    with db() as c: rows = c.execute("SELECT * FROM journals ORDER BY date DESC, created DESC").fetchall()
    return jsonify([row(r) for r in rows])

@app.get("/api/journals/<jid>")
def get_j(jid):
    with db() as c: r = c.execute("SELECT * FROM journals WHERE id=?", (jid,)).fetchone()
    return (jsonify(row(r)) if r else (jsonify(error="Not found"), 404))

def save_photos(files, caps, existing):
    out = list(existing)
    for f, cap in zip(files, caps):
        ext = (f.filename or "").rsplit(".", 1)[-1].lower()
        if ext not in EXT: raise ValueError(f"'{f.filename}' is not JPG, PNG or WebP.")
        blob = f.read()
        if len(blob) > MAXB: raise ValueError(f"'{f.filename}' is larger than 8 MB.")
        name = uuid.uuid4().hex + "." + ext; (UP / name).write_bytes(blob)
        out.append({"file": name, "caption": cap})
    return out

def parse_form():
    d = json.loads(request.form.get("data", "{}"))
    # d["photos"]: ordered list of {file?:existing name, caption, new?:true}; new ones consume uploaded files in order
    files = request.files.getlist("photos"); new_caps = [p.get("caption", "") for p in d.get("photos", []) if p.get("new")]
    saved = iter(save_photos(files, new_caps, []))
    photos = [next(saved) if p.get("new") else {"file": os.path.basename(p["file"]), "caption": p.get("caption", "")} for p in d.get("photos", [])]
    d["photos"] = photos; return d

@app.post("/api/journals")
def create():
    try: d = parse_form()
    except ValueError as e: return jsonify(error=str(e)), 400
    if not (d.get("notes") or d.get("story") or d["photos"]): return jsonify(error="Add a photo or write something first."), 400
    jid = uuid.uuid4().hex
    with db() as c: c.execute("INSERT INTO journals VALUES(?,?,?,?)", (jid, json.dumps(d), d.get("date", ""), datetime.utcnow().isoformat()))
    d["id"] = jid; return jsonify(d), 201

@app.put("/api/journals/<jid>")
def update(jid):
    try: d = parse_form()
    except ValueError as e: return jsonify(error=str(e)), 400
    with db() as c:
        if not c.execute("SELECT 1 FROM journals WHERE id=?", (jid,)).fetchone(): return jsonify(error="Not found"), 404
        c.execute("UPDATE journals SET data=?, date=? WHERE id=?", (json.dumps(d), d.get("date", ""), jid))
    d["id"] = jid; return jsonify(d)

@app.delete("/api/journals/<jid>")
def delete(jid):
    with db() as c:
        r = c.execute("SELECT * FROM journals WHERE id=?", (jid,)).fetchone()
        if not r: return jsonify(error="Not found"), 404
        for p in row(r).get("photos", []): (UP / os.path.basename(p["file"])).unlink(missing_ok=True)
        c.execute("DELETE FROM journals WHERE id=?", (jid,))
    return jsonify(ok=True)

@app.get("/uploads/<path:name>")
def uploads(name): return send_from_directory(UP, os.path.basename(name))

def ask(task):
    d = request.get_json(force=True) or {}
    if not (d.get("notes") or "").strip(): return jsonify(error="Write a few words about your day first."), 400
    body = json.dumps({"model": MODEL, "prompt": prompts.build(task, d), "format": "json", "stream": False,
                       "options": {"temperature": 0.7}}).encode()
    try:
        req = urllib.request.Request(OLLAMA + "/api/generate", body, {"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=180) as r: raw = json.load(r)["response"]
    except urllib.error.HTTPError as e:
        return jsonify(error=f"Model '{MODEL}' is not installed. Run: ollama pull {MODEL}" if e.code == 404 else f"Ollama error {e.code}"), 503
    except Exception:
        return jsonify(error="Can't reach Ollama. Install and start it from ollama.com, then run: ollama pull " + MODEL), 503
    try: out = json.loads(raw)
    except Exception: return jsonify(error="The model returned something unreadable. Try again."), 502
    if task == "journal" and not isinstance(out.get("story"), str): return jsonify(error="The model's reply was incomplete. Try again."), 502
    if task == "title" and not isinstance(out.get("title"), str): return jsonify(error="No title came back. Try again."), 502
    n = len(d.get("captions", []))
    if "captions" in out: out["captions"] = [str(x) for x in (out["captions"] or [])][:n] if isinstance(out["captions"], list) else []
    return jsonify(out)

@app.post("/api/ai/generate-journal")
def gj(): return ask("journal")
@app.post("/api/ai/generate-title")
def gt(): return ask("title")
@app.post("/api/ai/generate-captions")
def gc(): return ask("captions")

if __name__ == "__main__": app.run(port=5000, debug=True)
