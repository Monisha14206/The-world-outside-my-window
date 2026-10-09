"""Backend tests. Run from the backend folder:  python -m unittest -v
Uses a temporary database and upload folder, so your real journal is never touched."""
import io, json, shutil, sqlite3, tempfile, unittest
from pathlib import Path
from unittest import mock
import app as appmod

JPEG = b"\xff\xd8\xff\xe0" + b"0" * 100


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.app = appmod.create_app({"DB_PATH": str(self.tmp / "t.db"), "UPLOAD_DIR": str(self.tmp / "up"),
                                      "OLLAMA_URL": "http://127.0.0.1:9", "TESTING": True})
        self.c = self.app.test_client(); self.up = self.tmp / "up"
    def tearDown(self): shutil.rmtree(self.tmp, ignore_errors=True)

    def save(self, photos=(), method="post", jid="", **over):
        data = {"date": "2026-10-09", "notes": "A walk by the river.", "photos": [{"new": True, "caption": f"p{i}"} for i, _ in enumerate(photos)]}
        data.update(over)
        form = {"data": json.dumps(data), "photos": [(io.BytesIO(b), n) for n, b in photos]}
        return getattr(self.c, method)("/api/journals" + (f"/{jid}" if jid else ""), data=form, content_type="multipart/form-data")
    def files(self): return sorted(p.name for p in self.up.iterdir())


class JournalTests(Base):
    def test_health_without_ollama(self):
        r = self.c.get("/api/health").get_json()
        self.assertFalse(r["ollama"]); self.assertIn("ollama pull", r["hint"])

    def test_db_init_keeps_existing_data(self):
        jid = self.save().get_json()["id"]
        appmod.create_app({"DB_PATH": str(self.tmp / "t.db"), "UPLOAD_DIR": str(self.up)})  # restart
        self.assertEqual(self.c.get(f"/api/journals/{jid}").status_code, 200)

    def test_create_get_list(self):
        r = self.save([("a.jpg", JPEG)]); self.assertEqual(r.status_code, 201)
        j = r.get_json(); self.assertEqual(len(self.files()), 1)
        self.assertEqual(self.c.get(f"/api/journals/{j['id']}").get_json()["notes"], "A walk by the river.")
        self.assertEqual(len(self.c.get("/api/journals").get_json()), 1)
        self.assertEqual(self.c.get("/uploads/" + j["photos"][0]["file"]).status_code, 200)

    def test_invalid_and_missing_ids(self):
        for bad in ("nope", "../../etc/passwd", "0" * 32):
            self.assertEqual(self.c.get(f"/api/journals/{bad}").status_code, 404)
        self.assertEqual(self.c.delete("/api/journals/" + "0" * 32).status_code, 404)
        self.assertEqual(self.save(method="put", jid="0" * 32).status_code, 404)

    def test_validation(self):
        self.assertEqual(self.save(date="bad").status_code, 400)
        self.assertEqual(self.save(notes="", photos=[]).status_code, 400)
        self.assertEqual(self.save([("a.gif", JPEG)]).status_code, 400)
        self.assertEqual(self.save([("a.png", JPEG)]).status_code, 400)  # content doesn't match extension
        self.assertEqual(self.save([("a.jpg", JPEG + b"0" * 9_000_000)]).status_code, 400)
        self.assertEqual(self.files(), [])  # nothing left behind after rejections

    def test_path_traversal_in_existing_photo(self):
        jid = self.save().get_json()["id"]
        form = {"data": json.dumps({"date": "2026-10-09", "notes": "x", "photos": [{"file": "../app.py", "caption": ""}]})}
        r = self.c.put(f"/api/journals/{jid}", data=form, content_type="multipart/form-data")
        self.assertEqual(r.status_code, 400)

    def test_update_keeps_adds_and_removes_photos(self):
        j = self.save([("a.jpg", JPEG), ("b.jpg", JPEG)]).get_json(); a, b = (p["file"] for p in j["photos"])
        form = {"data": json.dumps({"date": "2026-10-10", "notes": "edited", "photos": [{"file": a, "caption": "kept"}, {"new": True, "caption": "n"}]}),
                "photos": [(io.BytesIO(JPEG), "c.jpg")]}
        r = self.c.put(f"/api/journals/{j['id']}", data=form, content_type="multipart/form-data"); self.assertEqual(r.status_code, 200)
        names = self.files(); self.assertIn(a, names); self.assertNotIn(b, names); self.assertEqual(len(names), 2)
        self.assertEqual(self.c.get(f"/api/journals/{j['id']}").get_json()["notes"], "edited")

    def test_delete_cleans_photos(self):
        j = self.save([("a.jpg", JPEG)]).get_json()
        self.assertEqual(self.c.delete(f"/api/journals/{j['id']}").status_code, 200)
        self.assertEqual(self.files(), []); self.assertEqual(self.c.get("/api/journals").get_json(), [])

    def test_shared_file_not_deleted(self):
        j = self.save([("a.jpg", JPEG)]).get_json(); f = j["photos"][0]["file"]
        with self.app.connect() as c:  # simulate a second entry referencing the same file
            c.execute("INSERT INTO journals VALUES(?,?,?,?)", ("1" * 32, json.dumps({"photos": [{"file": f, "caption": ""}]}), "2026-01-01", "x"))
        self.c.delete(f"/api/journals/{j['id']}"); self.assertEqual(self.files(), [f])

    def test_missing_image_file_returns_404(self):
        self.assertEqual(self.c.get("/uploads/missing.jpg").status_code, 404)

    def test_db_failure_cleans_new_uploads_and_hides_details(self):
        with mock.patch.object(appmod.sqlite3, "connect", side_effect=sqlite3.OperationalError("boom /secret/path")):
            r = self.save([("a.jpg", JPEG)])
        self.assertEqual(r.status_code, 500); self.assertNotIn("secret", r.get_data(as_text=True))
        self.assertEqual(self.files(), [])

    def test_cors_only_for_frontend_origin(self):
        ok = self.c.get("/api/health", headers={"Origin": "http://localhost:5173"})
        no = self.c.get("/api/health", headers={"Origin": "http://evil.example"})
        self.assertEqual(ok.headers.get("Access-Control-Allow-Origin"), "http://localhost:5173")
        self.assertNotIn("Access-Control-Allow-Origin", no.headers)


class AITests(Base):
    body = {"notes": "Walked to the lake.", "emotions": ["Peaceful"], "captions": ["lake"]}

    def test_requires_notes(self):
        self.assertEqual(self.c.post("/api/ai/generate-journal", json={"notes": ""}).status_code, 400)

    def test_ollama_unavailable_gives_helpful_error(self):
        r = self.c.post("/api/ai/generate-journal", json=self.body)
        self.assertEqual(r.status_code, 503); self.assertIn("ollama pull qwen2.5:3b", r.get_json()["error"])

    def test_request_uses_configured_model_and_user_facts(self):
        seen = {}
        def fake(req, timeout=None):
            seen.update(url=req.full_url, body=json.loads(req.data)); raise OSError("stop here")
        with mock.patch.object(appmod.urllib.request, "urlopen", fake):
            r = self.c.post("/api/ai/generate-journal", json=self.body)
        self.assertEqual(r.status_code, 503)  # a failed call is never reported as success
        self.assertTrue(seen["url"].endswith("/api/generate")); self.assertEqual(seen["body"]["model"], "qwen2.5:3b")
        self.assertIn("Walked to the lake.", seen["body"]["prompt"]); self.assertIn("Peaceful", seen["body"]["prompt"])

    def test_bad_model_output_is_rejected(self):
        class R:
            def __enter__(s): return s
            def __exit__(s, *a): pass
            def read(s): return json.dumps({"response": "not json"}).encode()
        with mock.patch.object(appmod.urllib.request, "urlopen", lambda *a, **k: R()):
            self.assertEqual(self.c.post("/api/ai/generate-journal", json=self.body).status_code, 502)


if __name__ == "__main__": unittest.main()
