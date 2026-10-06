"""Terminal UI tests: diff-render correctness (pyte), key-driven flows, Windows key decoding (fake msvcrt)
and a real pty run of main.py."""
import os
import sys
import time


import numpy as np
import pytest

from tests import fake_sd

SR = 48000
pyte = pytest.importorskip("pyte")


class FakeTerm:
    def __init__(self, w, h):
        self.w, self.h = w, h

    def size(self):
        return self.w, self.h

    def write(self, s):
        pass

    def read_keys(self, t=0):
        return []

    def drain_input(self):
        pass


@pytest.fixture
def rig(tmp_path, monkeypatch):
    monkeypatch.setitem(sys.modules, "sounddevice", fake_sd)
    monkeypatch.setenv("VOICER_DATA", str(tmp_path))
    from audio.engine import AudioEngine
    from config import ConfigManager
    from controller import Controller
    from ui.app import App

    cfg = ConfigManager(tmp_path / "config.json")
    cfg.first_run = False
    cfg.set("audio.output_device", "Fake Cable")
    eng = AudioEngine(cfg)
    ctl = Controller(cfg, eng)
    term = FakeTerm(80, 24)
    app = App(ctl, term)
    app.boot.done = True
    app.splash = False                 # tests start on the menu, not the title screen
    eng.start()
    yield app
    ctl.shutdown()


def press(app, *names):
    from ui.keys import Key
    app.ignore_keys_until = 0
    for n in names:
        key = Key("char", n) if len(n) == 1 else (Key("space", " ") if n == "space" else Key(n))
        app.handle_key(key)
    app.update()


def frame(app):
    app.update()
    app.render()
    return app.cv.text_lines()


# ------------------------------------------------------------------ diff renderer
def test_diff_render_matches_canvas(rig):
    """The incremental escape sequences written by App.render(), fed to a real terminal emulator,
    must reproduce the canvas exactly - across page changes and a resize."""
    app = rig
    screen = pyte.Screen(80, 24)
    stream = pyte.Stream(screen)
    written = []
    app.term.write = lambda s: (written.append(s), stream.feed(s))
    sizes = []
    for step in range(40):
        if step == 5:
            app.goto("voice"); press(app, "down", "right")
        if step == 10:
            app.goto("settings"); press(app, "enter", "down")
        if step == 15:
            app.goto("help")
        if step == 20:
            app.goto("voice"); press(app, "down", "enter")
        if step == 25:
            press(app, "backspace"); app.goto("home")
        if step == 30:
            app.term.w, app.term.h = 100, 30      # resize -> forced full repaint
            screen.resize(30, 100)
        n = sum(map(len, written))
        app.update()
        app.render()
        sizes.append(sum(map(len, written)) - n)
        got = [l.rstrip() for l in screen.display]
        want = [l.rstrip() for l in app.cv.text_lines()]
        assert got == want, f"step {step}\n" + "\n".join(got) + "\n---\n" + "\n".join(want)
    # steady state frames are tiny (diff), not full repaints
    assert min(sizes[1:5]) < 300


def test_unchanged_frame_emits_nothing(rig):
    app = rig
    app.term.write = lambda s: None
    app.goto("settings")
    app.update(); app.render()
    app.draw()
    assert app.scr.flush(app.cv, app.theme) == ""


# ------------------------------------------------------------------ slider / effect flows
def test_slider_live_update_no_engine_restart(rig):
    app = rig
    eng = app.ctl.engine
    epoch = eng._epoch
    app.goto("voice")
    press(app, "down", "right")                       # Pitch row -> its settings page
    assert type(app.current).__name__ == "EffectScreen"
    press(app, "enter")                               # Status row: toggle
    assert app.ctl.effect("pitch").enabled
    press(app, "down", *["right"] * 5)                # Semitones slider
    assert app.ctl.effect("pitch").get("semitones") > 0
    press(app, "left")
    press(app, "down", "down", "enter")               # Window -> RESET
    assert app.ctl.effect("pitch").get("semitones") == 0
    assert eng._epoch == epoch and eng.running        # streams were never rebuilt
    press(app, "backspace")
    assert type(app.current).__name__ == "VoiceScreen"


def test_bypass_and_hear_output_rows(rig):
    app = rig
    app.goto("voice")
    press(app, *["down"] * 6, "enter")                # Effects Bypass row
    assert app.ctl.bypass
    press(app, "enter")
    assert not app.ctl.bypass
    press(app, "down", "enter")                       # Hear Output row
    assert app.ctl.hear_output
    press(app, "enter")
    assert not app.ctl.hear_output


def test_enter_toggles_effect_on_dashboard(rig):
    app = rig
    app.goto("voice")
    press(app, "down", "enter")
    assert app.ctl.effect("pitch").enabled
    press(app, "enter")
    assert not app.ctl.effect("pitch").enabled


def test_presets_apply(rig):
    app = rig
    app.goto("voice")
    press(app, *["down"] * 8, "enter")                # Presets row
    assert type(app.current).__name__ == "PresetsScreen"
    press(app, "down", "down", "down", "enter")       # [save row], Normal, Deep, High Voice
    assert app.ctl.effect("pitch").enabled
    press(app, "backspace")
    assert type(app.current).__name__ == "VoiceScreen"


def test_no_key_hints_on_screen(rig):
    """The UI shows no key legend anywhere (controls: arrows / Enter / Backspace)."""
    app = rig
    banned = ("ESC", "SPACE", "ENTER", "BACKSPACE", "F1", "Navigate", "Select  ", "Toggle")
    for page in ["home", "voice", "settings", "help"]:
        app.goto(page)
        text = "\n".join(frame(app))
        assert not any(b in text for b in banned), (page, text)


def test_backspace_navigation_and_quit(rig):
    app = rig
    app.goto("voice")
    press(app, "backspace")
    assert app.page == "home"
    press(app, "backspace")
    assert app.modal is not None                      # quit confirmation
    press(app, "backspace")                           # = No
    assert app.modal is None and not app.quit_requested
    press(app, "backspace", "left", "enter")
    assert app.quit_requested


# ------------------------------------------------------------------ rendering robustness
@pytest.mark.parametrize("size", [(80, 24), (120, 40), (60, 20), (40, 12), (30, 8)])
def test_every_screen_renders_at_every_size(rig, size):
    from ui.screens.devices import DevicesScreen
    from ui.screens.effect import EffectScreen
    from ui.screens.presets import PresetsScreen
    app = rig
    app.term.w, app.term.h = size
    for page in ["home", "voice", "settings", "help"]:
        app.goto(page)
        for keys in [(), ("down",), ("enter",), ("right",), ("backspace",)]:
            press(app, *keys)
            lines = frame(app)
            assert len(lines) == size[1] and all(len(l) == size[0] for l in lines)
            if app.modal:
                press(app, "backspace")
    for name in ("volume", "pitch", "eq", "distortion", "reverb", "echo"):
        app.goto("voice"); app.push(EffectScreen(app, name)); frame(app)
    for scr in (PresetsScreen(app), DevicesScreen(app), DevicesScreen(app, True)):
        app.goto("voice"); app.push(scr); frame(app)


def test_ascii_fallback_has_no_non_ascii(rig):
    app = rig
    app.cfg.set("ui.charset", "ascii")
    app.cfg.set("ui.colors", "mono")
    app.rebuild_theme()
    for page in ["home", "voice", "settings", "help"]:
        app.goto(page)
        text = "\n".join(frame(app))
        assert all(ord(c) < 128 for c in text), page


# ------------------------------------------------------------------ Windows input decoding (fake msvcrt)
def test_decode_windows_keys():
    from ui.keys import decode_windows

    def run(seq):
        q = list(seq)
        return [str(k) for k in decode_windows(lambda: q.pop(0), lambda: bool(q))]
    assert run("\xe0H\xe0P\xe0K\xe0M") == ["up", "down", "left", "right"]
    assert run("\x00;\x00<") == ["f1", "f2"]
    assert run("a \r\x1b\t\x08") == ["a", "space", "enter", "esc", "tab", "backspace"]
    assert run("\x00\x0f") == ["backtab"]
    assert run("\xe0S\xe0I\xe0Q") == ["delete", "pgup", "pgdn"]
    assert run("\x03") == ["ctrl+c"]


def test_parse_ansi():
    from ui.keys import parse_ansi
    keys, rest = parse_ansi("\x1b[A\x1b[B\x1b[1;5C\x1bOQ x\x1b[3~")
    assert [str(k) for k in keys][:2] == ["up", "down"] and rest == ""
    assert "f2" in [str(k) for k in keys] and "delete" in [str(k) for k in keys]
    assert parse_ansi("\x1b")[1] == "\x1b"


# ------------------------------------------------------------------ real pty run
@pytest.mark.skipif(os.name == "nt", reason="pty is POSIX only")
def test_pty_full_run(tmp_path):
    import pty
    import select
    import struct
    import fcntl
    import termios
    import subprocess

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env = dict(os.environ, VOICER_DATA=str(tmp_path), TERM="xterm-256color", PYTHONPATH=root)
    master, slave = pty.openpty()
    fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 24, 80, 0, 0))
    p = subprocess.Popen([sys.executable, os.path.join(root, "main.py"), "--fake-audio"], cwd=root, env=env,
                         stdin=slave, stdout=slave, stderr=slave, close_fds=True)
    os.close(slave)
    screen = pyte.Screen(80, 24)
    stream = pyte.ByteStream(screen)
    raw = bytearray()

    def pump(sec):
        end = time.time() + sec
        while time.time() < end:
            r, _, _ = select.select([master], [], [], 0.05)
            if r:
                try:
                    d = os.read(master, 65536)
                except OSError:
                    return
                raw.extend(d)
                stream.feed(d)

    def send(s, wait=0.4):
        os.write(master, s.encode())
        pump(wait)

    try:
        pump(1.5)
        text = "\n".join(screen.display)
        assert "voicer" in text, text
        assert "PRESS ENTER" in text and "FIRST RUN SETUP" not in text      # the logo waits; no setup yet
        send("\r", 0.8)                                # Enter on the title screen -> first-run setup
        text = "\n".join(screen.display)
        assert "FIRST RUN SETUP" in text, text
        send("\x1b[B", 0.3)                            # down to [FINISH SETUP]
        send("\r", 0.8)                                # Enter: start audio (virtual cable preselected)
        send("\r", 0.6)                                # Voice Changer from the boot menu
        text = "\n".join(screen.display)
        assert "EFFECTS" in text and "LIVE AUDIO" in text, text
        send("\x1b[B", 0.3)                            # down to Pitch
        send("\x1b[C", 0.4)                            # right: its page
        send("\x1b[B", 0.2)                            # Semitones
        send("\x1b[C" * 3, 0.5)
        text = "\n".join(screen.display)
        assert "+3 st" in text, text
        send("\x7f\x7f", 0.5)                         # Backspace x2 -> home
        send("\x1b[B\r", 0.5)                         # Settings
        assert "SETTINGS" in "\n".join(screen.display)
        send("\x7f\x7f", 0.5)                         # back, back -> quit dialog
        assert "QUIT" in "\n".join(screen.display).upper()
        send("\x1b[D\r", 0.3)                         # choose QUIT, Enter
        p.wait(timeout=8)
        pump(0.3)
    finally:
        if p.poll() is None:
            p.kill()
    assert p.returncode == 0
    assert b"\x1b[?1049l" in raw and b"\x1b[?25h" in raw       # alt screen left, cursor restored
    assert not os.path.exists(tmp_path / "ui_error.log"), "a frame/key handler raised (swallowed by the loop)"
    assert os.path.exists(tmp_path / "config.json")
    import json
    cfg = json.load(open(tmp_path / "config.json"))
    assert cfg["effects"]["pitch"]["enabled"] is True          # persisted on exit
