"""The harness's own steps on real whatferry, with backups built as iOS and WhatsApp make them; no phones."""

from pathlib import Path

import pytest

from conftest import make_sqlite
from encrypted_backup import make_encrypted_backup
from harness import config, oracle, scenarios
from harness.report import Run
from harness.scenarios import Context
from test_android import KEY, encrypt
from test_convert import ACCOUNT, IOS, inputs  # noqa: F401 - fixture
from test_to_android import TEMPLATE
from whatferry import android, convert, ios_backup, to_android
from whatferry.backup_writer import SHARED_DOMAIN as SHARED

PASS = "correct horse"
UDID = "00008160-0020"


@pytest.fixture
def kit(tmp_path, monkeypatch):
    secrets = tmp_path / "secrets.toml"
    secrets.write_text(f'backup_passphrase = "{PASS}"\nnumber_b = "+32 470 00 00 00"\n'
                       f'iphone_udid = "{UDID}"\nandroid_serial = "PIXEL"\nandroid_key = "{KEY}"\n')
    secrets.chmod(0o600)
    return config.load(secrets, tmp_path / "kit-home")


@pytest.fixture
def ctx(kit):
    return Context(kit, Run.new(kit.runs, "test"), {"b_on": "android"})


def backups_returning(monkeypatch, *folders):
    """The iPhone's backups, in the order the steps ask for them."""
    queue = list(folders)
    monkeypatch.setattr(scenarios, "_backup", lambda c, whatsapp_only=False: queue.pop(0))


def test_android_to_iphone_after_adding_b(ctx, inputs, tmp_path, monkeypatch):  # noqa: F811
    android_db, ios_db, media = inputs
    main = make_sqlite(tmp_path / "main.sqlite", IOS).read_bytes()
    before = make_encrypted_backup(tmp_path / "before" / UDID, PASS, {(SHARED, "ChatStorage.sqlite"): main},
                                   folders=[(SHARED, "data")])
    after = make_encrypted_backup(tmp_path / "after" / UDID, PASS, {
        (SHARED, "ChatStorage.sqlite"): main, (SHARED, f"{ACCOUNT}/ChatStorage.sqlite"): ios_db.read_bytes(),
    }, folders=[(SHARED, "data"), (SHARED, ACCOUNT)])
    ctx.ctx.update({"a2i.android_db": str(android_db), "a2i.media": str(media),
                    "a2i.before_index": str(ios_backup.snapshot_manifest(before, tmp_path / "index"))})
    scenarios._seed(ctx, "a2i", oracle.android(android_db, media))

    backups_returning(monkeypatch, after)
    scenarios.a2i_ios_after(ctx)
    assert ctx.ctx["a2i.account"] == ACCOUNT
    written = Path(ctx.ctx["a2i.written"])
    assert (written / "Manifest.db").is_file()
    for name in ("compat/a2i-convert.json", "compat/a2i-write.json", "compat/a2i-iphone-schema.json"):
        assert (ctx.run.folder / name).is_file()

    # After the restore the phone holds what was written: its WhatsApp-only backup is that.
    backups_returning(monkeypatch, written)
    scenarios.a2i_verify(ctx)
    assert ctx.ctx["a2i.verdict"] == {"passed": True, "summary": "10 messages, all arrived unchanged"}
    assert ctx.kit_state["b_on"] == "iphone"
    assert (ctx.kit.home / "baseline.json").is_file()


def test_android_to_iphone_without_a_new_account_stops(ctx, inputs, tmp_path, monkeypatch):  # noqa: F811
    main = make_sqlite(tmp_path / "main.sqlite", IOS).read_bytes()
    before = make_encrypted_backup(tmp_path / "before" / UDID, PASS, {(SHARED, "ChatStorage.sqlite"): main})
    same = make_encrypted_backup(tmp_path / "after" / UDID, PASS, {(SHARED, "ChatStorage.sqlite"): main})
    ctx.ctx["a2i.before_index"] = str(ios_backup.snapshot_manifest(before, tmp_path / "index"))
    backups_returning(monkeypatch, same)
    with pytest.raises(scenarios.StepFailed, match="was B added"):
        scenarios.a2i_ios_after(ctx)


def test_a_verify_that_differs_fails_the_run(ctx, inputs, tmp_path, monkeypatch):  # noqa: F811
    android_db, ios_db, media = inputs
    seed = oracle.android(android_db, media)
    seed["items"]["0:never-arrived"] = dict(next(iter(seed["items"].values())))
    scenarios._seed(ctx, "a2i", seed)
    _, run = convert.convert(android_db, ios_db, media, ACCOUNT)
    phone = make_encrypted_backup(tmp_path / "phone" / UDID, PASS, {
        (SHARED, f"{ACCOUNT}/ChatStorage.sqlite"): (run / "files" / "ChatStorage.sqlite").read_bytes()},
        folders=[(SHARED, "data"), (SHARED, ACCOUNT)])
    ctx.ctx["a2i.account"] = ACCOUNT
    backups_returning(monkeypatch, phone)
    with pytest.raises(scenarios.StepFailed, match="1 missing"):
        scenarios.a2i_verify(ctx)
    assert ctx.ctx["a2i.verdict"]["passed"] is False
    assert (ctx.run.folder / "a2i-diff.json").is_file()


def test_iphone_to_android_into_the_template(ctx, inputs, tmp_path):  # noqa: F811
    android_db, ios_db, media = inputs
    # B's account on the iPhone: the forward conversion's result, with its media, in an encrypted backup.
    _, run = convert.convert(android_db, ios_db, media, ACCOUNT)
    files = {(SHARED, f"{ACCOUNT}/ChatStorage.sqlite"): (run / "files" / "ChatStorage.sqlite").read_bytes()}
    message = run / "files" / ACCOUNT / "Message"
    for f in message.rglob("*"):
        if f.is_file():
            files[(SHARED, f"{ACCOUNT}/Message/{f.relative_to(message).as_posix()}")] = f.read_bytes()
    phone = make_encrypted_backup(tmp_path / "phone" / UDID, PASS, files, folders=[(SHARED, "data"), (SHARED, ACCOUNT)])
    extracted = tmp_path / "b.sqlite"
    extracted.write_bytes(files[(SHARED, f"{ACCOUNT}/ChatStorage.sqlite")])
    ctx.ctx.update({"i2a.backup": str(phone), "i2a.account": ACCOUNT, "i2a.ios_db": str(extracted),
                    "i2a.whatsapp": "2.26.41.7"})
    template = ctx.kit.home / "templates" / "2.26.41.7"
    template.mkdir(parents=True)
    encrypt(make_sqlite(tmp_path / "template.db", TEMPLATE), template / "msgstore.db.crypt15")
    assert scenarios._template_cached(ctx)

    scenarios.i2a_android_convert(ctx)
    written = Path(ctx.ctx["i2a.written"])
    _, inspected = android.inspect(written / "Databases" / "msgstore.db.crypt15", android.parse_key(KEY))
    result = oracle.android(inspected / "msgstore.db", written / "Media")
    backup = ios_backup.Backup(phone, PASS)
    seed = oracle.ios(extracted, to_android.backup_media(backup, ACCOUNT))
    assert oracle.diff(seed, result)["passed"]
