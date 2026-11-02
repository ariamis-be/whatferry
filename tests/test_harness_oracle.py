"""The harness's oracle on real conversions: a faithful one diffs to zero, a damaged one doesn't."""

import sqlite3
from contextlib import closing

from conftest import make_sqlite
from harness import oracle
from test_convert import ACCOUNT, inputs  # noqa: F401 - fixture
from test_to_android import TEMPLATE, iphone  # noqa: F401 - fixture
from whatferry import convert, to_android


def test_android_to_iphone_diffs_to_zero(inputs):  # noqa: F811
    android, ios, media = inputs
    _, run = convert.convert(android, ios, media, ACCOUNT)
    files = run / "files" / ACCOUNT / "Message"

    def read(local):
        path = files / local
        return path.read_bytes() if path.is_file() else None

    seed = oracle.android(android, media)
    result = oracle.ios(run / "files" / "ChatStorage.sqlite", read)
    d = oracle.diff(seed, result)
    assert d["passed"], d
    assert d["seed"] == 10
    # The poll and the system lines are known losses, counted, not failures.
    assert d["known_losses"]["seed"] == {"other": 1, "system": 2}
    assert d["known_losses"]["result"] == {"system": 1}
    assert oracle.summary(d) == "10 messages, all arrived unchanged"


def test_iphone_to_android_diffs_to_zero(iphone, tmp_path):  # noqa: F811
    ios_db, media = iphone
    template = make_sqlite(tmp_path / "template.db", TEMPLATE)
    _, run = to_android.convert(ios_db, template, media)
    seed = oracle.ios(ios_db, media)
    result = oracle.android(run / "files" / "msgstore.db", run / "files" / "Media")
    d = oracle.diff(seed, result)
    assert d["passed"], d
    assert d["seed"] == 10


def test_a_lost_file_a_changed_text_and_a_missing_message_show(inputs, tmp_path):  # noqa: F811
    android, ios, media = inputs
    _, run = convert.convert(android, ios, media, ACCOUNT)
    merged = run / "files" / "ChatStorage.sqlite"
    files = run / "files" / ACCOUNT / "Message"
    with closing(sqlite3.connect(merged)) as db:
        db.execute("UPDATE ZWAMESSAGE SET ZTEXT = 'changed' WHERE ZSTANZAID = 'k-in'")
        db.execute("DELETE FROM ZWAMESSAGE WHERE ZSTANZAID = 'k-out'")
        db.commit()
    for f in files.rglob("*.jpg"):
        f.unlink()

    def read(local):
        path = files / local
        return path.read_bytes() if path.is_file() else None

    d = oracle.diff(oracle.android(android, media), oracle.ios(merged, read))
    assert not d["passed"]
    assert d["missing"] == 1 and d["examples"]["missing"] == ["1:k-out"]
    assert d["changed"] == {"text": 1, "media": 1}
    assert sorted(d["examples"]["changed"]) == ["0:k-in", "1:k-img"]
    assert oracle.summary(d) == "10 messages: 1 missing; 1 with a different text, 1 with a different media"


def test_without_files_the_recorded_hashes_are_compared(inputs):  # noqa: F811
    android, ios, media = inputs
    _, run = convert.convert(android, ios, media, ACCOUNT)
    result = oracle.ios(run / "files" / "ChatStorage.sqlite")
    image = result["items"]["1:k-img"]
    assert image["media"]  # the hash the forward converter recorded for the copied file
    assert image["text"] == oracle._hash("a caption")


def test_chats_are_named_by_their_last_digits_only():
    label = oracle.chat_label("32470000111@s.whatsapp.net")
    assert label.startswith("…0111@s.whatsapp.net#") and "3247" not in label
    assert oracle.chat_label("32470000111@s.whatsapp.net") != oracle.chat_label("32479990111@s.whatsapp.net")
