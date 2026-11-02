"""`whatferry ios backup`: the phone is a stand-in that writes a Finder-format folder."""

import shutil
from collections import namedtuple
from pathlib import Path

import pytest

from conftest import FakeBackup
from encrypted_backup import make_encrypted_backup
from test_ui import request, run, server  # noqa: F401 - fixture
from whatferry import backup_writer, iphone, restore, workdir
from whatferry.ui.wizard import StepError, Wizard
from whatferry.backup_writer import WriteError
from whatferry.cli import main
from whatferry.iphone import Iphone, IphoneError
from whatferry.ios_backup import list_backups

UDID = "00008160-0020"
PASS = "correct horse"
SHARED = "AppDomainGroup-group.net.whatsapp.WhatsApp.shared"
Call = namedtuple("Call", "folder udid full passphrase whatsapp_only")


class Phone:
    """Stands in for the iPhone: its backup setting, and the folder a backup writes."""

    def __init__(self, monkeypatch, *, encrypts=True, passphrase=PASS, paired=True, phones=None):
        self.encrypts, self.passphrase = encrypts, passphrase
        self.phones = [Iphone(UDID, "Test iPhone", "27.0.1", paired, False)] if phones is None else phones
        self.backups: list[Call] = []
        self.passwords: list[str] = []
        self.autopair: list[bool] = []

        async def listing(autopair=False):
            self.autopair.append(autopair)
            return self.phones

        async def will_encrypt(udid):
            return self.encrypts

        async def change_password(udid, new):
            self.passwords.append(new)
            self.encrypts, self.passphrase = True, new

        async def backup(folder, udid, full, passphrase, progress, whatsapp_only):
            self.backups.append(Call(folder, udid, full, passphrase, whatsapp_only))
            target = folder / udid
            shutil.rmtree(target, ignore_errors=True)
            files = {(SHARED, "ChatStorage.sqlite"): b"chats"}
            if self.encrypts:
                make_encrypted_backup(target, self.passphrase, files)
            else:
                FakeBackup(target).add(SHARED, "ChatStorage.sqlite", b"chats")
            progress(50.0)
            progress(100.0)

        monkeypatch.setattr(iphone, "_list", listing)
        monkeypatch.setattr(iphone, "_will_encrypt", will_encrypt)
        monkeypatch.setattr(iphone, "_change_password", change_password)
        monkeypatch.setattr(iphone, "_backup", backup)


@pytest.fixture
def no_passphrase_env(monkeypatch):
    monkeypatch.delenv("WHATFERRY_BACKUP_PASSPHRASE", raising=False)
    monkeypatch.delenv("WHATFERRY_BACKUP_ROOT", raising=False)


def answers(monkeypatch, *typed):
    it = iter(typed)
    monkeypatch.setattr("getpass.getpass", lambda prompt="": next(it))


def test_backup_lands_in_whatferrys_folder_and_is_listed(monkeypatch, private_home, capsys, no_passphrase_env):
    phone = Phone(monkeypatch)
    answers(monkeypatch, PASS)
    assert main(["ios", "backup"]) == 0
    out = capsys.readouterr().out
    folder = private_home / "backups" / UDID
    assert f"Backed up: {folder}" in out and f"whatferry ios inspect {UDID}" in out
    assert "100%" in out
    assert phone.autopair == [True]  # a backup may ask the phone to trust this computer
    assert phone.backups == [Call(private_home / "backups", UDID, False, PASS, False)]
    assert [p.name for p, _ in list_backups([private_home / "backups"])] == [UDID]
    monkeypatch.setenv("WHATFERRY_BACKUP_ROOT", str(private_home / "backups"))  # not this computer's own
    assert main(["ios", "backups"]) == 0
    assert f"{UDID}  " in capsys.readouterr().out


def test_folders_are_private(monkeypatch, private_home, no_passphrase_env):
    Phone(monkeypatch)
    iphone.backup(iphone.find(), PASS)
    if hasattr(__import__("os"), "geteuid"):
        assert (private_home / "backups").stat().st_mode & 0o777 == 0o700
        assert private_home.stat().st_mode & 0o777 == 0o700


def test_full_starts_over(monkeypatch, private_home, no_passphrase_env):
    phone = Phone(monkeypatch)
    answers(monkeypatch, PASS)
    assert main(["ios", "backup", "--full"]) == 0
    assert phone.backups[0].full


def test_encryption_is_turned_on_with_a_passphrase_typed_twice(monkeypatch, private_home, capsys,
                                                                 no_passphrase_env):
    phone = Phone(monkeypatch, encrypts=False)
    answers(monkeypatch, "one", "two", PASS, PASS)
    assert main(["ios", "backup"]) == 0
    captured = capsys.readouterr()
    assert "don't match" in captured.err
    assert phone.passwords == [PASS]
    assert "Encrypt local backup' ticked" in captured.out
    assert phone.backups[0].passphrase == PASS


def test_no_passphrase_leaves_encryption_off(monkeypatch, capsys, no_passphrase_env):
    phone = Phone(monkeypatch, encrypts=False)
    answers(monkeypatch, "", "", "")
    assert main(["ios", "backup"]) == 1
    assert "encryption left off" in capsys.readouterr().err
    assert phone.passwords == [] and phone.backups == []


def test_a_wrong_passphrase_is_reported_and_the_backup_kept(monkeypatch, private_home, capsys, no_passphrase_env):
    Phone(monkeypatch)
    answers(monkeypatch, "wrong")
    assert main(["ios", "backup"]) == 1
    assert "doesn't open it" in capsys.readouterr().err
    assert (private_home / "backups" / UDID / "Manifest.db").is_file()


def test_an_update_checks_the_passphrase_against_the_last_backup_first(monkeypatch, private_home, capsys,
                                                                       no_passphrase_env):
    phone = Phone(monkeypatch)
    iphone.backup(iphone.find(), PASS)
    answers(monkeypatch, "wrong")
    assert main(["ios", "backup"]) == 1
    assert "doesn't open the last backup" in capsys.readouterr().err
    assert len(phone.backups) == 1  # the second never started


def test_the_passphrase_can_come_from_the_environment(monkeypatch, private_home, no_passphrase_env):
    phone = Phone(monkeypatch)
    monkeypatch.setenv("WHATFERRY_BACKUP_PASSPHRASE", PASS)
    monkeypatch.setattr("getpass.getpass", lambda prompt="": pytest.fail("asked"))
    assert main(["ios", "backup"]) == 0
    assert phone.backups[0].passphrase == PASS


def test_whatsapp_only_goes_next_to_the_full_one_and_never_restores(monkeypatch, private_home, capsys,
                                                                    no_passphrase_env):
    phone = Phone(monkeypatch)
    answers(monkeypatch, PASS, PASS)
    assert main(["ios", "backup"]) == 0
    assert main(["ios", "backup", "--whatsapp-only"]) == 0
    out = capsys.readouterr().out
    only = private_home / "backups" / f"{UDID}-whatsapp"
    assert f"whatferry ios diff <earlier> {only.name}" in out
    assert phone.backups[1].whatsapp_only and phone.backups[1].full
    assert (only / "Manifest.db").is_file() and (private_home / "backups" / UDID / "Manifest.db").is_file()
    assert sorted(p.name for p in (private_home / "backups").iterdir()) == [UDID, only.name]  # no staging left
    with pytest.raises(IphoneError, match="WhatsApp-only backup"):
        restore.backup_udid(only)
    monkeypatch.setenv("WHATFERRY_BACKUP_ROOT", str(private_home / "backups"))  # not this computer's own
    assert main(["ios", "backups"]) == 0
    assert "WhatsApp only" in capsys.readouterr().out


def test_a_second_whatsapp_only_backup_replaces_the_first(monkeypatch, private_home, no_passphrase_env):
    Phone(monkeypatch)
    phone = iphone.find()
    first = iphone.backup(phone, PASS, whatsapp_only=True)
    (first / "left-over").write_text("x")
    second = iphone.backup(phone, PASS, whatsapp_only=True)
    assert second == first and not (second / "left-over").exists()


def test_finding_the_phone(monkeypatch):
    Phone(monkeypatch, paired=False)
    with pytest.raises(IphoneError, match="tap Trust"):
        iphone.find()
    Phone(monkeypatch, phones=[])
    with pytest.raises(IphoneError, match="no iPhone connected"):
        iphone.find()
    two = [Iphone(UDID, "Test iPhone", "27", True, False), Iphone("OTHER", "x", "27", True, False)]
    Phone(monkeypatch, phones=two)
    with pytest.raises(IphoneError, match="--udid"):
        iphone.find()
    assert iphone.find("other").udid == "OTHER"
    with pytest.raises(IphoneError, match="…ISSING connected"):
        iphone.find("MISSING")


def test_the_phones_refusal_is_passed_on(monkeypatch, no_passphrase_env):
    Phone(monkeypatch)

    async def refuses(*args):
        raise RuntimeError("MBErrorDomain/105")

    monkeypatch.setattr(iphone, "_backup", refuses)
    with pytest.raises(IphoneError, match="could not make the backup: MBErrorDomain/105"):
        iphone.backup(iphone.find(), PASS)


File = namedtuple("File", "domain relative_path device_name", defaults=(None, None, None))


def test_whatsapp_filter():
    app = "/private/var/mobile/Containers/Data/Application/AAAA"
    group = "/private/var/mobile/Containers/Shared/AppGroup/BBBB"
    keep = iphone.whatsapp_filter([app, group])
    # While the phone sends files: by their path on the phone.
    assert keep(File(device_name="/var/mobile/Containers/Data/Application/AAAA/Documents/ChatStorage.sqlite"))
    assert keep(File(device_name=f"{group}/Message/Media/x.jpg"))
    assert not keep(File(device_name="/var/mobile/Containers/Data/Application/AAAAB/Documents/x"))
    assert not keep(File(device_name="/var/mobile/Media/DCIM/100APPLE/IMG_0001.HEIC"))
    assert keep(File(device_name="AppDomainGroup-group.net.whatsapp.WhatsApp.shared-ChatStorage.sqlite"))
    # Afterwards, Manifest.db rows: by domain.
    assert keep(File(domain=SHARED, relative_path="ChatStorage.sqlite"))
    assert keep(File(domain="AppDomain-net.whatsapp.WhatsApp", relative_path="Documents/x"))
    assert not keep(File(domain="HomeDomain", relative_path="Library/SMS/sms.db"))
    assert not keep(File(domain="AppDomainPlugin-net.whatsapp.WhatsApp.Intents", relative_path="x"))
    # The containers unknown: every payload is kept, the pruning removes the rest.
    assert iphone.whatsapp_filter([])(File(device_name="/var/mobile/Media/DCIM/IMG.HEIC"))


def test_pruning_decrypts_into_the_private_folder(private_home):
    with iphone._PrivateTempfile.NamedTemporaryFile(suffix=".sqlite3") as f:
        Path(f.name).write_bytes(b"manifest")  # opened again by name, as the pruning does
        assert Path(f.name).parent == workdir.private_temp()
    assert not Path(f.name).exists()


def test_a_copy_without_room_stops_before_it_starts(tmp_path, monkeypatch):
    source = FakeBackup(tmp_path / "source").folder
    usage = namedtuple("usage", "total used free")
    monkeypatch.setattr(shutil, "disk_usage", lambda _: usage(10, 10, 1))
    with pytest.raises(WriteError, match="needs .* GB and only"):
        backup_writer.clone_folder(source, tmp_path / "out" / "copy", platform="win32")
    assert not (tmp_path / "out" / "copy").exists()


@pytest.mark.parametrize("platform", ["win32", "linux"])
def test_a_copy_where_nothing_clones_is_whole(tmp_path, platform):
    fake = FakeBackup(tmp_path / "source")
    fake.add(SHARED, "ChatStorage.sqlite", b"chats")
    backup_writer.clone_folder(fake.folder, tmp_path / "copy", platform=platform)
    assert sorted(p.relative_to(tmp_path / "copy") for p in (tmp_path / "copy").rglob("*")) == \
        sorted(p.relative_to(fake.folder) for p in fake.folder.rglob("*"))


# The wizard's "Back up now"

def test_wizard_status_says_whether_the_phone_encrypts(monkeypatch, private_home):
    Phone(monkeypatch, encrypts=False)
    status = Wizard(private_home).iphone_status()
    assert status["encrypts"] is False and status["phones"][0]["udid"] == UDID
    Phone(monkeypatch, phones=[])
    assert Wizard(private_home).iphone_status() == {"phones": [], "encrypts": None, "error": None}


def test_wizard_backup_turns_encryption_on_and_lists_the_result(monkeypatch, private_home):
    phone = Phone(monkeypatch, encrypts=False)
    wizard = Wizard(private_home)
    with pytest.raises(StepError, match="don't match"):
        wizard.backup_iphone(PASS, "other")
    assert phone.passwords == []
    seen = []
    made = wizard.backup_iphone(PASS, PASS, UDID, seen.append)
    assert made == {"folder": str(private_home / "backups" / UDID), "id": UDID, "phone": "Test iPhone", "turned_on": True}
    assert phone.passwords == [PASS] and seen == [50.0, 100.0]
    # Encryption on now: the second passphrase isn't asked for.
    assert not wizard.backup_iphone(PASS, None)["turned_on"]


def test_wizard_hides_whatsapp_only_backups(monkeypatch, private_home):
    Phone(monkeypatch)
    phone = iphone.find()
    iphone.backup(phone, PASS)
    iphone.backup(phone, PASS, whatsapp_only=True)
    monkeypatch.setenv("WHATFERRY_BACKUP_ROOT", str(private_home / "backups"))
    assert [b["id"] for b in Wizard(private_home).ios_backups()["backups"]] == [UDID]


def test_page_backs_up_with_progress(monkeypatch, server):  # noqa: F811
    Phone(monkeypatch)
    assert request(server, "GET", "/api/ios/phone")[2]["encrypts"] is True
    result = run(server, "/api/ios/backup", {"passphrase": PASS})
    assert result["status"] == "done" and result["progress"] == 100.0
    assert result["result"]["id"] == UDID
