import http.client
import json
import re
import threading
import time
from pathlib import Path

import pytest

from conftest import FakeBackup
from test_android import KEY, OTHER_KEY, encrypt, msgstore  # noqa: F401 - fixture
from test_ios import SHARED, chat_storage
from whatferry.ui.server import Server
from whatferry.ui.wizard import Wizard


@pytest.fixture
def server(private_home):
    srv = Server(Wizard(private_home))
    thread = threading.Thread(target=srv.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True)
    thread.start()
    yield srv
    srv.shutdown()
    srv.server_close()


def request(srv, method, path, body=None, *, token=True, host=None, headers=None):
    conn = http.client.HTTPConnection("127.0.0.1", srv.port, timeout=10)
    h = {"Host": host or f"127.0.0.1:{srv.port}"}
    if token:
        h["X-Whatferry-Token"] = srv.token
    if isinstance(body, (dict, list)):
        body = json.dumps(body).encode()
        h["Content-Type"] = "application/json"
    h.update(headers or {})
    conn.request(method, path, body=body, headers=h)
    res = conn.getresponse()
    data = res.read()
    conn.close()
    try:
        parsed = json.loads(data)
    except ValueError:
        parsed = data
    return res.status, dict(res.getheaders()), parsed


def wait(srv, job_id, timeout=30):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        _, _, job = request(srv, "GET", f"/api/jobs/{job_id}")
        if job["status"] != "running":
            return job
        time.sleep(0.05)
    raise AssertionError("job did not finish")


def run(srv, path, body):
    status, _, data = request(srv, "POST", path, body)
    assert status == 202, data
    return wait(srv, data["job"])


# Security


def test_page_needs_the_token(server):
    status, _, _ = request(server, "GET", "/", token=False)
    assert status == 403
    status, headers, body = request(server, "GET", f"/?t={server.token}", token=False)
    assert status == 200
    assert b"<title>whatferry</title>" in body
    assert "script-src 'self'" in headers["Content-Security-Policy"]
    assert headers["Referrer-Policy"] == "no-referrer"
    assert headers["Cache-Control"] == "no-store"


def test_wrong_token_is_refused(server):
    status, _, _ = request(server, "GET", "/?t=" + "x" * len(server.token), token=False)
    assert status == 403
    status, _, data = request(server, "GET", "/api/overview", headers={"X-Whatferry-Token": "nope"})
    assert status == 403


@pytest.mark.parametrize("host", ["evil.example:80", "127.0.0.1", "192.168.1.5:{port}", "localhost.evil:{port}"])
def test_other_hosts_are_refused(server, host):
    status, _, _ = request(server, "GET", f"/?t={server.token}", host=host.format(port=server.port))
    assert status == 421


def test_localhost_name_is_allowed(server):
    status, _, _ = request(server, "GET", "/api/overview", host=f"localhost:{server.port}")
    assert status == 200


def test_api_needs_the_token(server):
    status, _, data = request(server, "GET", "/api/overview", token=False)
    assert status == 403


def test_posts_from_another_origin_are_refused(server):
    status, _, data = request(server, "POST", "/api/reset", {}, headers={"Origin": "https://evil.example"})
    assert status == 403
    status, _, _ = request(server, "POST", "/api/reset", {}, headers={"Origin": f"http://127.0.0.1:{server.port}"})
    assert status == 200


@pytest.mark.parametrize("path", ["/static/../server.py", "/static/..%2Fserver.py", "/static/wizard.py",
                                  "/static/.hidden.js", "/static/nope.js", "/static/sub/app.js"])
def test_static_serves_only_its_own_files(server, path):
    status, _, _ = request(server, "GET", path)
    assert status == 404


def test_page_assets_are_served_with_their_types(server):
    """Every file the built page links to is served, with the right type."""
    _, _, page = request(server, "GET", f"/?t={server.token}", token=False)
    assets = re.findall(r'(?:src|href)="/static/([^"]+)"', page.decode())
    assert any(a.endswith(".js") for a in assets) and any(a.endswith(".css") for a in assets)
    static = Path(__file__).parent.parent / "src" / "whatferry" / "ui" / "static"
    fonts = [p.name for p in static.glob("*.woff2")]
    kinds = {".js": "text/javascript", ".css": "text/css", ".svg": "image/svg+xml", ".woff2": "font/woff2"}
    for name in assets + fonts:
        status, headers, _ = request(server, "GET", f"/static/{name}")
        assert status == 200, name
        assert headers["Content-Type"].startswith(kinds[Path(name).suffix]), name


def test_built_page_has_no_inline_script_or_style(server):
    """The CSP forbids inline code; a build that emits some would break the page."""
    _, _, page = request(server, "GET", f"/?t={server.token}", token=False)
    html = page.decode()
    assert not re.search(r"<script(?![^>]*\bsrc=)[^>]*>", html)
    assert "<style" not in html and " style=" not in html


def test_json_endpoints_refuse_other_bodies(server):
    status, _, data = request(server, "POST", "/api/step", b"step=start",
                              headers={"Content-Type": "application/x-www-form-urlencoded"})
    assert status == 400


# Android


def test_android_flow(server, msgstore, tmp_path, private_home):  # noqa: F811
    backup = encrypt(msgstore, tmp_path / "msgstore.db.crypt15")
    job = run(server, "/api/android/inspect", {"path": str(backup), "key": KEY})
    assert job["status"] == "done", job
    _, _, overview = request(server, "GET", "/api/overview")
    android = overview["state"]["android"]
    assert android["report"]["counts"]["messages"] == 3
    saved = (private_home / "state.json").read_text()
    assert KEY not in saved and "hello" not in saved


def test_android_wrong_key_is_a_job_error(server, msgstore, tmp_path):  # noqa: F811
    backup = encrypt(msgstore, tmp_path / "msgstore.db.crypt15")
    job = run(server, "/api/android/inspect", {"path": str(backup), "key": OTHER_KEY})
    assert job == {"status": "error", "error": "decryption failed: the key does not match this backup"}


def test_android_missing_key_is_explained(server, msgstore, tmp_path):  # noqa: F811
    backup = encrypt(msgstore, tmp_path / "msgstore.db.crypt15")
    job = run(server, "/api/android/inspect", {"path": str(backup), "key": "  "})
    assert "64-digit key" in job["error"]


def test_upload_lands_in_a_private_run_folder(server, private_home):
    data = b"\x00binary\r\n\x1a" * 1000
    status, _, saved = request(server, "POST", "/api/android/upload", data,
                               headers={"Content-Type": "application/octet-stream",
                                        "X-Filename": "..%2F..%2Fevil%3A.crypt15"})
    assert status == 200, saved
    path = Path(saved["path"])
    assert path.name == "evil_.crypt15"
    assert path.read_bytes() == data
    assert path.resolve().is_relative_to(private_home.resolve())


def test_upload_needs_a_length(server):
    status, _, _ = request(server, "POST", "/api/android/upload", b"",
                           headers={"Content-Type": "application/octet-stream"})
    assert status == 411


def test_candidates_look_in_downloads(server, tmp_path, monkeypatch):
    home = tmp_path / "user"
    (home / "Downloads").mkdir(parents=True)
    (home / "Downloads" / "msgstore.db.crypt15").write_bytes(b"x")
    (home / "Downloads" / "unrelated.crypt15").write_bytes(b"x")
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    _, _, data = request(server, "GET", "/api/android/candidates")
    assert [f["name"] for f in data["files"]] == ["msgstore.db.crypt15"]


# iPhone


@pytest.fixture
def phone(tmp_path, monkeypatch):
    root = tmp_path / "backups"
    fake = FakeBackup(root / "00008140-AAAA")
    db, wal = chat_storage(tmp_path / "ChatStorage.sqlite", messages=3, wal_messages=1)
    fake.add(SHARED, "ChatStorage.sqlite", db)
    fake.add(SHARED, "ChatStorage.sqlite-wal", wal)
    monkeypatch.setenv("WHATFERRY_BACKUP_ROOT", str(root))
    return fake


def test_ios_flow_before_and_after(server, phone, tmp_path, private_home):
    _, _, listed = request(server, "GET", "/api/ios/backups")
    assert [b["id"] for b in listed["backups"]] == ["00008140-AAAA"]
    assert listed["backups"][0]["encrypted"] is False

    before = run(server, "/api/ios/inspect", {"folder": "00008140-AAAA", "role": "before"})
    assert before["status"] == "done", before
    snapshot = Path(before["result"]["snapshot"])
    assert sorted(p.name for p in snapshot.iterdir()) == ["Info.plist", "Manifest.db", "Manifest.plist"]

    # The next backup rewrites the same folder: adding the account adds a store.
    second, _ = chat_storage(tmp_path / "second.sqlite", messages=0)
    phone.add(SHARED, "Accounts/32470000002/ChatStorage.sqlite", second)

    after = run(server, "/api/ios/inspect", {"folder": str(phone.folder), "role": "after"})
    assert after["status"] == "done", after
    diff = after["result"]["diff"]
    assert diff["new_chat_storages"] == [f"{SHARED}/Accounts/32470000002/ChatStorage.sqlite"]
    assert diff["added"] == 1

    _, _, summary = request(server, "GET", "/api/summary")
    text = summary["text"]
    assert "new chat database" in text
    assert "32470000002" not in text and "<number>" in text
    assert "secret text" not in text and "Alice" not in text


def test_ios_after_needs_before(server, phone):
    job = run(server, "/api/ios/inspect", {"folder": "00008140-AAAA", "role": "after"})
    assert job["status"] == "error" and "first iPhone backup" in job["error"]


def test_ios_unknown_backup(server, phone):
    job = run(server, "/api/ios/inspect", {"folder": "nope", "role": "before"})
    assert job["status"] == "error" and "no backup folder" in job["error"]


def test_checking_before_again_clears_after(server, phone, tmp_path):
    assert run(server, "/api/ios/inspect", {"folder": "00008140-AAAA", "role": "before"})["status"] == "done"
    assert run(server, "/api/ios/inspect", {"folder": "00008140-AAAA", "role": "after"})["status"] == "done"
    assert run(server, "/api/ios/inspect", {"folder": "00008140-AAAA", "role": "before"})["status"] == "done"
    _, _, overview = request(server, "GET", "/api/overview")
    assert "after" not in overview["state"]


# Progress


def test_progress_survives_a_restart(server, private_home):
    request(server, "POST", "/api/step", {"step": "account"})
    status, _, data = request(server, "POST", "/api/checklist", {"item": "add-account", "done": True})
    assert status == 200 and data["checklist"] == {"add-account": True}
    again = Wizard(private_home).overview()["state"]
    assert again["step"] == "account" and again["checklist"] == {"add-account": True}


def test_unknown_step_and_item_are_refused(server):
    assert request(server, "POST", "/api/step", {"step": "nope"})[0] == 400
    assert request(server, "POST", "/api/checklist", {"item": "nope", "done": True})[0] == 400


def test_settings_survive_a_restart_and_a_reset(server, private_home):
    """The page's language and theme: a new start has a new port, so the browser can't keep them."""
    assert request(server, "GET", "/api/settings")[2] == {}
    status, _, saved = request(server, "POST", "/api/settings", {"theme": "dark"})
    assert status == 200 and saved == {"theme": "dark"}
    request(server, "POST", "/api/settings", {"lang": "zh"})
    request(server, "POST", "/api/reset", {})
    assert Wizard(private_home).settings.get() == {"theme": "dark", "lang": "zh"}


@pytest.mark.parametrize("body", [{"theme": "purple"}, {"lang": "fr"}, {"token": "x"}])
def test_unknown_settings_are_refused(server, body):
    assert request(server, "POST", "/api/settings", body)[0] == 400
    assert request(server, "GET", "/api/settings")[2] == {}


def test_reset_forgets_progress(server, private_home):
    request(server, "POST", "/api/step", {"step": "after"})
    request(server, "POST", "/api/reset", {})
    _, _, overview = request(server, "GET", "/api/overview")
    assert overview["state"] == {}


def test_summary_with_nothing_checked(server):
    _, _, data = request(server, "GET", "/api/summary")
    assert "Nothing checked yet." in data["text"]
