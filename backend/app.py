"""Flask backend for The World Outside My Window (local single-user prototype)."""
import json, os, re, sqlite3, threading, uuid, urllib.error, urllib.request
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from flask import Flask, jsonify, request, send_from_directory
from werkzeug.exceptions import HTTPException

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env")
except ImportError:
    pass
import prompts

BASE = Path(__file__).parent
ID_RE = re.compile(r"^[0-9a-f]{32}$")
EXTS = {"jpg", "jpeg", "png", "webp"}
MAX_PHOTO = 8 * 1024 * 1024
TEXT_LIMIT = {"title": 200, "places": 300, "activity": 50, "people": 300, "notes": 20000,
              "reflection": 5000, "story": 20000, "feelings": 500}


def defaults():
    return {"OLLAMA_URL": os.getenv("OLLAMA_URL", "http://localhost:11434"),
            "OLLAMA_MODEL": os.getenv("OLLAMA_MODEL", "qwen2.5:3b"),
            "OLLAMA_TIMEOUT": int(os.getenv("OLLAMA_TIMEOUT", "180")),
            "DB_PATH": os.getenv("DB_PATH", str(BASE / "journal.db")),
            "UPLOAD_DIR": os.getenv("UPLOAD_DIR", str(BASE / "uploads")),
            "FRONTEND_ORIGINS": os.getenv("FRONTEND_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")}


def looks_like_image(blob, ext):
    if ext in ("jpg", "jpeg"): return blob[:3] == b"\xff\xd8\xff"
    if ext == "png": return blob[:8] == b"\x89PNG\r\n\x1a\n"
    return blob[:4] == b"RIFF" and blob[8:12] == b"WEBP"


def create_app(config=None):
    app = Flask(__name__)
    app.config.update(defaults()); app.config.update(config or {})
    app.config["MAX_CONTENT_LENGTH"] = 60 * 1024 * 1024
    uploads = Path(app.config["UPLOAD_DIR"]); uploads.mkdir(parents=True, exist_ok=True)
    ai_lock = threading.Lock()  # one local generation at a time

    def connect():
        c = sqlite3.connect(app.config["DB_PATH"], timeout=10); c.row_factory = sqlite3.Row; return c

    with closing(connect()) as c, c:  # CREATE IF NOT EXISTS: never wipes existing entries
        c.execute("CREATE TABLE IF NOT EXISTS journals(id TEXT PRIMARY KEY, data TEXT, date TEXT, created TEXT)")
    app.connect = connect  # exposed so tests can simulate DB failures

    # ---------- errors & CORS ----------
    @app.errorhandler(sqlite3.Error)
    def db_err(e):
        app.logger.error("database error: %s", e)
        return jsonify(error="The journal database could not be accessed. Check DB_PATH and file permissions."), 500

    @app.errorhandler(HTTPException)
    def http_err(e): return jsonify(error=e.description if e.code != 413 else "Upload is too large (60 MB max)."), e.code

    @app.errorhandler(Exception)
    def any_err(e):
        app.logger.exception("unexpected error")
        return jsonify(error="Something went wrong on the server."), 500

    @app.after_request
    def cors(resp):
        origin = request.headers.get("Origin")
        if origin and origin in app.config["FRONTEND_ORIGINS"].split(","):
            resp.headers["Access-Control-Allow-Origin"] = origin
            resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
            resp.headers["Access-Control-Allow-Methods"] = "GET,POST,PUT,DELETE,OPTIONS"
        return resp

    # ---------- helpers ----------
    def row_to_dict(r):
        d = json.loads(r["data"]); d["id"] = r["id"]; return d

    def find(c, jid):
        return c.execute("SELECT * FROM journals WHERE id=?", (jid,)).fetchone() if ID_RE.match(jid or "") else None

    def referenced_files(c, exclude=None):
        used = set()
        for r in c.execute("SELECT id, data FROM journals"):
            if r["id"] != exclude: used |= {p["file"] for p in json.loads(r["data"]).get("photos", [])}
        return used

    def remove_files(names, c):
        shared = referenced_files(c)
        for n in names:
            if n not in shared: (uploads / os.path.basename(n)).unlink(missing_ok=True)

    def clean(d, allowed_existing):
        """Validate/whitelist the JSON part of the form. Raises ValueError with a user-friendly message."""
        if not isinstance(d, dict): raise ValueError("Invalid request.")
        out = {}
        for k, lim in TEXT_LIMIT.items():
            v = d.get(k, "")
            if not isinstance(v, str): raise ValueError(f"'{k}' must be text.")
            if len(v) > lim: raise ValueError(f"'{k}' is too long.")
            out[k] = v.strip()
        try: datetime.strptime(d.get("date", ""), "%Y-%m-%d")
        except ValueError: raise ValueError("Please choose a valid date.")
        out["date"] = d["date"]
        for k in ("emotions", "details"):
            v = d.get(k, [])
            if not isinstance(v, list) or not all(isinstance(x, str) for x in v) or len(v) > 50: raise ValueError(f"'{k}' is invalid.")
            out[k] = [x.strip()[:300] for x in v if x.strip()]
        out["favorite"] = bool(d.get("favorite", False))
        photos = d.get("photos", [])
        if not isinstance(photos, list) or len(photos) > 30: raise ValueError("Too many photos (30 max).")
        out["photos"] = []
        for p in photos:
            if not isinstance(p, dict): raise ValueError("Invalid photo data.")
            cap = str(p.get("caption", ""))[:300]
            if p.get("new"): out["photos"].append({"new": True, "caption": cap})
            elif os.path.basename(str(p.get("file", ""))) in allowed_existing:
                out["photos"].append({"file": os.path.basename(p["file"]), "caption": cap})
            else: raise ValueError("A photo in this entry could not be found.")
        return out

    def build_entry(allowed_existing):
        """Returns (entry_dict, list_of_new_filenames_written). Cleans up its own files on failure."""
        try: raw = json.loads(request.form.get("data", ""))
        except ValueError: raise ValueError("Invalid request.")
        d = clean(raw, allowed_existing)
        files = request.files.getlist("photos")
        if len(files) != sum(1 for p in d["photos"] if p.get("new")): raise ValueError("Photo upload didn't match. Please re-add your photos.")
        if not (d["notes"] or d["story"] or d["photos"]): raise ValueError("Add a photo or write something first.")
        written, it = [], iter(files)
        try:
            for p in d["photos"]:
                if not p.get("new"): continue
                f = next(it); ext = (f.filename or "").rsplit(".", 1)[-1].lower()
                if ext not in EXTS: raise ValueError(f"'{f.filename}' is not a JPG, PNG or WebP image.")
                blob = f.read()
                if len(blob) > MAX_PHOTO: raise ValueError(f"'{f.filename}' is larger than 8 MB.")
                if not looks_like_image(blob, ext): raise ValueError(f"'{f.filename}' doesn't look like a real {ext.upper()} image.")
                name = uuid.uuid4().hex + "." + ext; (uploads / name).write_bytes(blob)
                written.append(name); p.pop("new"); p["file"] = name
        except Exception:
            for n in written: (uploads / n).unlink(missing_ok=True)
            raise
        return d, written

    def bad(msg, code=400): return jsonify(error=msg), code

    # ---------- routes ----------
    @app.get("/api/health")
    def health():
        model = app.config["OLLAMA_MODEL"]
        try:
            with urllib.request.urlopen(app.config["OLLAMA_URL"] + "/api/tags", timeout=3) as r:
                names = [m["name"] for m in json.load(r).get("models", [])]
        except Exception:
            return jsonify(ollama=False, model=model, modelInstalled=False,
                           hint=f"Ollama isn't running. Start the Ollama app, then run: ollama pull {model}")
        ok = model in names or (":" not in model and model + ":latest" in names)
        return jsonify(ollama=True, model=model, modelInstalled=ok, hint=None if ok else f"Model not installed. Run: ollama pull {model}")

    @app.get("/api/journals")
    def list_j():
        with closing(connect()) as c: rows = c.execute("SELECT * FROM journals ORDER BY date DESC, created DESC").fetchall()
        return jsonify([row_to_dict(r) for r in rows])

    @app.get("/api/journals/<jid>")
    def get_j(jid):
        with closing(connect()) as c: r = find(c, jid)
        return jsonify(row_to_dict(r)) if r else bad("Journal not found.", 404)

    @app.post("/api/journals")
    def create():
        try: d, written = build_entry(set())
        except ValueError as e: return bad(str(e))
        jid = uuid.uuid4().hex
        try:
            with closing(connect()) as c, c:
                c.execute("INSERT INTO journals VALUES(?,?,?,?)", (jid, json.dumps(d), d["date"], datetime.now(timezone.utc).isoformat()))
        except Exception:
            for n in written: (uploads / n).unlink(missing_ok=True)  # don't leave orphan photos
            raise
        d["id"] = jid; return jsonify(d), 201

    @app.put("/api/journals/<jid>")
    def update(jid):
        with closing(connect()) as c: r = find(c, jid)
        if not r: return bad("Journal not found.", 404)
        old = {p["file"] for p in row_to_dict(r).get("photos", [])}
        try: d, written = build_entry(old)
        except ValueError as e: return bad(str(e))
        try:
            with closing(connect()) as c, c:
                c.execute("UPDATE journals SET data=?, date=? WHERE id=?", (json.dumps(d), d["date"], jid))
        except Exception:
            for n in written: (uploads / n).unlink(missing_ok=True)
            raise
        with closing(connect()) as c: remove_files(old - {p["file"] for p in d["photos"]}, c)  # only after DB success
        d["id"] = jid; return jsonify(d)

    @app.delete("/api/journals/<jid>")
    def delete(jid):
        with closing(connect()) as c:
            r = find(c, jid)
            if not r: return bad("Journal not found.", 404)
            files = {p["file"] for p in row_to_dict(r).get("photos", [])}
            with c: c.execute("DELETE FROM journals WHERE id=?", (jid,))
            remove_files(files, c)
        return jsonify(ok=True)

    @app.get("/uploads/<path:name>")
    def serve_upload(name):
        safe = os.path.basename(name)
        if not (uploads / safe).is_file(): return bad("Image not found.", 404)
        return send_from_directory(uploads, safe)

    def ask(task):
        d = request.get_json(silent=True) or {}
        if not str(d.get("notes", "")).strip(): return bad("Write a few words about your day first.")
        d["emotions"] = d.get("emotions") if isinstance(d.get("emotions"), list) else []
        if not ai_lock.acquire(blocking=False): return bad("The model is still working on a request. Please wait a moment.", 429)
        model = app.config["OLLAMA_MODEL"]
        try:
            body = json.dumps({"model": model, "prompt": prompts.build(task, d), "format": "json", "stream": False,
                               "options": {"temperature": 0.7}}).encode()
            req = urllib.request.Request(app.config["OLLAMA_URL"] + "/api/generate", body, {"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=app.config["OLLAMA_TIMEOUT"]) as r: raw = json.load(r)["response"]
        except urllib.error.HTTPError as e:
            return bad(f"Model '{model}' is not installed. Run: ollama pull {model}" if e.code == 404 else f"Ollama returned an error ({e.code}).", 503)
        except TimeoutError:
            return bad("The model took too long to answer. Try again, or use a smaller model.", 504)
        except Exception:
            return bad(f"Can't reach Ollama. Start the Ollama app, then run: ollama pull {model}", 503)
        finally:
            ai_lock.release()
        try: out = json.loads(raw)
        except ValueError: return bad("The model's reply was unreadable. Please try again.", 502)
        if not isinstance(out, dict): return bad("The model's reply was unreadable. Please try again.", 502)
        need = {"journal": "story", "title": "title", "captions": "captions"}[task]
        if not out.get(need): return bad("The model's reply was incomplete. Please try again.", 502)
        for k in ("title", "story", "feelings"):
            if k in out and not isinstance(out[k], str): out[k] = str(out[k])
        n = len(d.get("captions", []))
        if "captions" in out: out["captions"] = [str(x) for x in out["captions"]][:n] if isinstance(out["captions"], list) else []
        if "details" in out and not isinstance(out["details"], list): out["details"] = []
        return jsonify(out)

    @app.post("/api/ai/generate-journal")
    def gj(): return ask("journal")
    @app.post("/api/ai/generate-title")
    def gt(): return ask("title")
    @app.post("/api/ai/generate-captions")
    def gc(): return ask("captions")

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=os.getenv("FLASK_DEBUG") == "1")
