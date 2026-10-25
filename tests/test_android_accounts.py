"""Several Android accounts, moved one after another, each with its own choices."""

import json
import zlib
from pathlib import Path

from wa_crypt_tools.lib.db.db15 import Database15
from wa_crypt_tools.lib.key.keyfactory import KeyFactory
from wa_crypt_tools.lib.props import Props

from test_android import KEY, msgstore  # noqa: F401 - fixture
from test_ui import request, run, server  # noqa: F401 - fixture
from whatferry.ui.wizard import Wizard


def encrypted(plain: Path, out: Path, ends: str) -> Path:
    key = KeyFactory.from_hex(KEY)
    out.write_bytes(Database15(key=key).encrypt(key, Props(wa_version="2.26.41.77", jid=ends),
                                                 zlib.compress(plain.read_bytes(), 1)))
    return out


def check(srv, path):
    job = run(srv, "/api/android/inspect", {"path": str(path), "key": KEY})
    assert job["status"] == "done", job


def overview(srv):
    return request(srv, "GET", "/api/overview")[2]


def test_two_accounts_keep_their_own_choices(server, msgstore, tmp_path):  # noqa: F811
    first = encrypted(msgstore, tmp_path / "whatsapp-account-1001-msgstore.db.crypt15", "78")
    second = encrypted(msgstore, tmp_path / "whatsapp-account-1002-msgstore.db.crypt15", "34")

    check(server, first)
    request(server, "POST", "/api/destination", {"choice": "second"})
    check(server, second)
    o = overview(server)
    assert [(a["name"], a["number_ends"], a["current"]) for a in o["android_accounts"]] == [
        (first.name, "78", False), (second.name, "34", True)]
    assert "destination" not in o["state"], "a new account starts without a choice"
    request(server, "POST", "/api/destination", {"choice": "existing"})

    first_key = next(a["key"] for a in o["android_accounts"] if a["name"] == first.name)
    assert request(server, "POST", "/api/android/select", {"key": first_key})[0] == 200
    o = overview(server)
    assert o["state"]["destination"] == "second"
    assert o["state"]["android"]["report"]["header"]["number_ends_with"] == "78"
    assert {a["number_ends"]: a["destination"] for a in o["android_accounts"]} == {"78": "second", "34": "existing"}

    text = request(server, "GET", "/api/summary")[2]["text"]
    assert "Android account, number ending 78" in text and "Android account, number ending 34" in text
    assert "Destination: second" in text and "Destination: existing" in text


def test_checking_the_same_file_again_keeps_its_progress(server, msgstore, tmp_path):  # noqa: F811
    first = encrypted(msgstore, tmp_path / "a.crypt15", "78")
    check(server, first)
    request(server, "POST", "/api/destination", {"choice": "second"})
    check(server, first)
    o = overview(server)
    assert len(o["android_accounts"]) == 1 and o["state"]["destination"] == "second"


def test_unknown_account_is_refused(server):  # noqa: F811
    assert request(server, "POST", "/api/android/select", {"key": "/nope"})[0] == 400


def test_progress_saved_before_accounts_were_kept_apart_is_adopted(private_home, msgstore, tmp_path):  # noqa: F811
    source = encrypted(msgstore, tmp_path / "old.crypt15", "78")
    private_home.mkdir(parents=True, exist_ok=True)
    (private_home / "state.json").write_text(json.dumps({
        "android": {"source": str(source), "report": {"header": {"number_ends_with": "78"}, "counts": {}}},
        "destination": "second",
    }))
    o = Wizard(private_home).overview()
    assert [(a["name"], a["destination"], a["current"]) for a in o["android_accounts"]] == [(source.name, "second", True)]


def test_reset_forgets_every_account(server, msgstore, tmp_path):  # noqa: F811
    check(server, encrypted(msgstore, tmp_path / "a.crypt15", "78"))
    check(server, encrypted(msgstore, tmp_path / "b.crypt15", "34"))
    request(server, "POST", "/api/reset", {})
    assert overview(server)["android_accounts"] == []
