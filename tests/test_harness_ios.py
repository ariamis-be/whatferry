"""Stage 2 without an iPhone: reading WDA's screen, the three automations, and the fall back to a pause."""

import asyncio
from contextlib import asynccontextmanager

import pytest

from harness import config, ios_flows, ios_ui, scenarios
from harness.ios_ui import Screen, ScreenUnknown
from harness.report import Run
from harness.scenarios import Context, Step
from test_harness import SECRETS, Phone, sent  # noqa: F401 - fixture

SOURCE = """<?xml version="1.0" encoding="UTF-8"?>
<AppiumAUT><XCUIElementTypeApplication type="XCUIElementTypeApplication" name="WhatsApp" label="WhatsApp" visible="true">
  <XCUIElementTypeButton type="XCUIElementTypeButton" name="Settings" label="Settings" visible="true"/>
  <XCUIElementTypeButton type="XCUIElementTypeButton" name="Hidden" label="Add account" visible="false"/>
  <XCUIElementTypeTextField type="XCUIElementTypeTextField" value="+1" visible="true"/>
  <XCUIElementTypeTextField type="XCUIElementTypeTextField" value="phone number" visible="true"/>
</XCUIElementTypeApplication></AppiumAUT>"""


class Client:
    """Stands in for pymobiledevice3's WdaServiceClient: serves screens, records what was done."""

    def __init__(self, *sources):
        self.sources, self.session_id, self.done = list(sources), "s1", []

    async def get_source(self, session_id=None):
        return self.sources.pop(0) if len(self.sources) > 1 else self.sources[0]

    async def find_element(self, using, value, session_id=None):
        self.done.append(("find", using, value))
        return "e1"

    async def click(self, element_id, session_id=None):
        self.done.append(("click", element_id))

    async def _request_json(self, method, path, payload=None):
        self.done.append((method, path.rsplit("/", 1)[-1], payload and payload.get("text")))
        return {}

    async def send_keys(self, text, session_id=None):
        self.done.append(("keys", text))

    async def start_session(self, bundle_id=None):
        self.done.append(("launch", bundle_id))

    async def get_screenshot(self, session_id=None):
        return b"png"


def clock():
    t = iter(range(10_000))
    return lambda: next(t)


async def nap(_):
    pass


def screen(*sources):
    return Screen(Client(*sources), log=lambda m: None, clock=clock(), sleep=nap)


def test_elements_are_matched_whole_by_label_or_name_when_visible():
    found = ios_ui.elements(SOURCE)
    assert [e.type for e in found][:3] == ["AppiumAUT", "XCUIElementTypeApplication", "XCUIElementTypeButton"]
    assert ios_ui._matches("settings", found[2])
    assert not ios_ui._matches("Sett", found[2])  # whole label, not a part
    assert not ios_ui._matches("Add account", found[3])  # not visible
    assert ios_ui.elements("not xml") == []


def test_predicates_quote_the_pattern():
    assert ios_ui._predicate("Don't Allow") == \
        "(label MATCHES[c] 'Don\\'t Allow' OR name MATCHES[c] 'Don\\'t Allow') AND visible == 1"


def test_tap_waits_then_taps_by_predicate():
    s = screen("<a/>", SOURCE)
    asyncio.run(s.tap("Settings"))
    assert s.client.done == [("find", "predicate string", ios_ui._predicate("Settings")), ("click", "e1")]


def test_a_screen_that_doesnt_come_is_unknown():
    s = screen(SOURCE)
    with pytest.raises(ScreenUnknown, match="waited 5s for “Chats”"):
        asyncio.run(s.wait("Chats", timeout=5))
    assert asyncio.run(screen(SOURCE).which({"a": "Chats", "b": "Settings"})) == "b"


def test_fill_types_into_the_nth_field():
    s = screen(SOURCE)
    asyncio.run(s.fill(1, "470000000"))
    assert ("find", "class chain", "**/XCUIElementTypeTextField[`visible == 1`][2]") in s.client.done
    assert ("POST", "value", "470000000") in s.client.done
    with pytest.raises(ScreenUnknown, match="at least 3 text fields"):
        asyncio.run(s.fill(2, "x"))


# The automations, against a screen that shows whatever they ask for

class Scripted:
    """Every screen the flow waits for is there; records taps and typing."""

    def __init__(self, which=()):
        self.done, self.which_answers = [], list(which)

    async def launch(self, bundle):
        self.done.append(("launch", bundle))

    async def tap(self, pattern, timeout=30):
        self.done.append(("tap", pattern))

    async def tap_if(self, pattern):
        self.done.append(("tap_if", pattern))
        return False

    async def wait(self, pattern, timeout=30):
        self.done.append(("wait", pattern))

    async def which(self, patterns, timeout=30):
        return self.which_answers.pop(0)

    async def fill(self, index, text, kind="XCUIElementTypeTextField"):
        self.done.append(("fill", index, text))

    async def type(self, text):
        self.done.append(("type", text))

    async def screenshot(self):
        return b"png"


@pytest.fixture
def kit(tmp_path):
    path = tmp_path / "secrets.toml"
    path.write_text(SECRETS + '\n[ios_automation]\nwda_app = "~/wda/Runner.app"\n')
    path.chmod(0o600)
    return config.load(path, tmp_path / "kit-home")


@pytest.fixture
def ctx(kit):
    c = Context(kit, Run.new(kit.runs, "test"), {"b_on": "android"})
    c._android, c._iphone = Phone(), Phone()
    return c


def test_add_b_types_the_number_and_the_code_from_the_pixel(ctx):
    s, asked = Scripted(), []

    def code(android, since):
        asked.append(since)
        return "482913"

    asyncio.run(ios_flows.add_b(s, ctx, code))
    assert ("fill", 0, "+32") in s.done and ("fill", 1, "470000000") in s.done
    assert ("type", "482913") in s.done and ("fill", 0, "B") in s.done
    assert asked and s.done[-1] == ("wait", ios_flows.CHAT_LIST)


def test_add_b_without_a_code_stops(ctx):
    with pytest.raises(ScreenUnknown, match="no WhatsApp code"):
        asyncio.run(ios_flows.add_b(Scripted(), ctx, lambda android, since: None))


def test_after_restore_answers_the_panes_but_never_the_apple_account(ctx):
    s = Scripted(which=["pane", "pane", "home"])
    asyncio.run(ios_flows.after_restore(s, ctx))
    assert [d for d in s.done if d == ("tap", ios_flows.SPRINGBOARD_PANES)] == [("tap", ios_flows.SPRINGBOARD_PANES)] * 2
    assert ("launch", ios_flows.WHATSAPP) in s.done and ("tap", ios_flows.b_label("+32 470 00 00 00")) in s.done
    with pytest.raises(ScreenUnknown, match="Apple Account"):
        asyncio.run(ios_flows.after_restore(Scripted(which=["pane", "person"]), ctx))


def test_remove_b_picks_b_by_name_or_last_digits(ctx):
    s = Scripted()
    asyncio.run(ios_flows.remove_b(s, ctx))
    assert ("tap", "B|.*0000.*") in s.done


# The runner: taps first, a pause when they stop

def screen_for(monkeypatch, fake=None, fails=None):
    @asynccontextmanager
    async def open_screen(c):
        if fails:
            raise fails
        yield fake

    monkeypatch.setattr(scenarios, "open_screen", open_screen)


def test_stage_two_taps_instead_of_pausing(ctx, monkeypatch, sent):  # noqa: F811
    tapped = []

    async def auto(s, c, wait_for_code):
        tapped.append(s)

    screen_for(monkeypatch, fake=Scripted())
    steps = [Step("tap", manual="Tap it.", auto=auto), Step("after", lambda c: None)]
    assert scenarios.execute(ctx, steps) == scenarios.PASSED
    assert tapped and ctx.run.steps["tap"]["by"] == "harness"
    assert [t for t, _ in sent] == ["whatferry harness: passed"]


def test_taps_that_stop_hand_over_to_a_person(ctx, monkeypatch, sent):  # noqa: F811
    async def auto(s, c, wait_for_code):
        raise ScreenUnknown("waited 30s for “Add account” on the iPhone")

    screen_for(monkeypatch, fake=Scripted())
    steps = [Step("tap", manual="Tap it.", auto=auto)]
    assert scenarios.execute(ctx, steps) == scenarios.PAUSED
    assert "Tap it." in sent[0][1] and "taps stopped: waited 30s for “Add account”" in sent[0][1]
    assert any(p.name.endswith("tap-iphone-stopped.png") for p in (ctx.run.folder / "screenshots").iterdir())
    # The person does it; resume goes on.
    assert scenarios.execute(ctx, steps, resuming=True) == scenarios.PASSED
    assert ctx.run.steps["tap"]["by"] == "person"


def test_no_webdriveragent_is_a_pause_too(ctx, monkeypatch, sent):  # noqa: F811
    async def auto(s, c, wait_for_code):
        raise AssertionError("never reached")

    screen_for(monkeypatch, fails=ios_ui.UiUnavailable("pymobiledevice3's tunnel isn't running"))
    assert scenarios.execute(ctx, [Step("tap", manual="Tap it.", auto=auto)]) == scenarios.PAUSED
    assert "tunnel isn't running" in sent[0][1]


def test_stage_one_never_opens_a_screen(ctx, monkeypatch, sent):  # noqa: F811
    ctx.kit.ios_automation.enabled = False
    screen_for(monkeypatch, fails=AssertionError("opened"))
    assert scenarios.execute(ctx, [Step("tap", manual="Tap it.", auto=ios_flows.remove_b)]) == scenarios.PAUSED
    assert "taps stopped" not in sent[0][1]


def test_the_kits_stage_two_settings(kit, tmp_path):
    assert kit.taps_iphone and kit.ios_automation.wda_app.name == "Runner.app"
    assert "~" not in str(kit.ios_automation.wda_app)
    assert kit.ios_automation.runner == ios_ui.WDA_RUNNER
    path = tmp_path / "bad.toml"
    path.write_text(SECRETS + '\n[ios_automation]\nwda = "x"\n')
    path.chmod(0o600)
    with pytest.raises(config.KitError, match="unknown \\[ios_automation\\] settings: wda"):
        config.load(path)
    path.write_text(SECRETS)
    assert not config.load(path).taps_iphone


def test_every_iphone_pause_has_its_taps():
    manual = [s for s in scenarios.A2I + scenarios.I2A if s.manual]
    assert [s.name for s in manual] == ["a2i.iphone_remove_b", "a2i.iphone_add_b", "a2i.iphone_after_restore"]
    assert all(s.auto for s in manual)
