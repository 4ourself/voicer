"""Settings: categories on the left, items on the right. Every change applies immediately."""
from __future__ import annotations

from audio import devices as dev

from ..canvas import Rect, fit
from ..widgets import ListState, button, slider
from .base import BaseScreen


class Item:
    def __init__(self, kind, label, desc, get=None, set=None, options=None, lo=0, hi=1, step=1, fmt=None, press=None):
        self.kind, self.label, self.desc = kind, label, desc
        self.get, self.set, self.options = get, set, options
        self.lo, self.hi, self.step = lo, hi, step
        self.fmt = fmt or (lambda v: str(v))
        self.press = press


class SettingsScreen(BaseScreen):
    TITLE = "SETTINGS"
    CATS = ("Audio", "Devices", "Performance", "Interface", "Config")

    def __init__(self, app):
        super().__init__(app)
        self.cat = ListState()
        self.items_sel = ListState()
        self.in_items = False

    # ------------------------------------------------------------------ item definitions
    def _items(self, cat: str) -> list[Item]:
        if cat == "Config":
            from .configitems import config_items
            return config_items(self.app)
        ctl, app, cfg, eng = self.ctl, self.app, self.app.cfg, self.ctl.engine
        pct = lambda v: f"{v * 100:.0f}%"  # noqa: E731

        def toggle_item(label, desc, key, after=None, invert=False):
            def setter(v):
                cfg.set(key, (not v) if invert else v)
                if after:
                    after()
            return Item("toggle", label, desc, lambda: (not cfg.get(key)) if invert else bool(cfg.get(key)), setter)

        def choice_item(label, desc, key, options, after=None):
            def setter(v):
                cfg.set(key, v)
                if after:
                    after()
            return Item("choice", label, desc, lambda: cfg.get(key), setter, options=options)

        def restart_audio(msg="Restarting audio..."):
            app.notify("info", msg)
            app.bg(eng.start)

        def device_btn(role):
            return Item("button", role.capitalize(), f"Choose the {role} device (opens the device list).",
                        get=lambda: (eng.health[role]["name"] or eng.health[role]["state"]),
                        press=lambda: self._open_devices(role))

        def mk_slider(label, desc, getter, setter, lo, hi, step, fmt):
            return Item("slider", label, desc, getter, setter, lo=lo, hi=hi, step=step, fmt=fmt)

        if cat == "Audio":
            return [
                Item("toggle", "Hear Output", "Send your processed voice to the monitor device so you hear yourself.",
                     lambda: ctl.hear_output, lambda v: eng.set_hear_output(v)),
                Item("toggle", "Effects Bypass", "Voice passes through unchanged (no effects).",
                     lambda: ctl.bypass, lambda v: eng.set_bypass(v)),
                mk_slider("Voice volume", "Master level of your processed voice in the final mix.",
                          lambda: eng.mixer.voice_volume, lambda v: eng.set_volume("voice", v), 0, 2, 0.05, pct),
                mk_slider("Monitor volume", "How loud the final mix is in YOUR headphones (Hear Output).",
                          lambda: eng.monitor_volume, lambda v: eng.set_volume("monitor", v), 0, 2, 0.05, pct),
                Item("toggle", "Mono output", "Mix the output down to mono (some voice apps prefer it).",
                     lambda: eng.output_mono, lambda v: eng.set_output_mono(v)),
            ]
        if cat == "Devices":
            names = ["auto"] + (dev.hostapi_names() if not self._no_backend() else [])
            return [device_btn("input"), device_btn("output"), device_btn("monitor"),
                    Item("button", "Refresh devices", "Re-scan hardware (briefly restarts audio).",
                         get=lambda: "", press=lambda: (app.notify("info", "Refreshing devices..."), app.bg(ctl.refresh_devices))),
                    choice_item("Audio system", "Windows audio API. WASAPI = lowest latency. Re-pick devices after changing.",
                                "audio.host_api", names, after=lambda: (app.notify("warn", "Audio system changed - check Devices"),
                                                                       restart_audio()))]
        if cat == "Performance":
            ms = lambda: round(cfg.get("audio.block_size") / cfg.get("audio.sample_rate") * 1000)  # noqa: E731

            def set_buf(v):
                cfg.set("audio.block_size", int(int(v.split()[0]) * cfg.get("audio.sample_rate") / 1000))
                restart_audio()

            def set_jit(v):
                cfg.set("audio.jitter_blocks", int(v))
                restart_audio()
            return [
                Item("choice", "Audio buffer", "Smaller = lower latency but needs a faster PC. 10 ms is ideal.",
                     lambda: f"{ms()} ms", set_buf, options=["10 ms", "20 ms", "30 ms", "40 ms"]),
                Item("choice", "Safety buffer", "Blocks of slack between mic and output clocks. Raise if crackling.",
                     lambda: str(cfg.get("audio.jitter_blocks")), set_jit, options=["1", "2", "3", "4"]),
                Item("choice", "Output channels", "Stereo or mono final mix.", lambda: "Mono" if eng.output_mono else "Stereo",
                     lambda v: eng.set_output_mono(v == "Mono"), options=["Stereo", "Mono"]),
                Item("info", "Sample rate", "Fixed engine rate; all processing runs at this rate.",
                     lambda: f"{cfg.get('audio.sample_rate')} Hz"),
                Item("info", "Keyboard events", "Operating-system key hook (event driven, no polling).", lambda: "automatic"),
                Item("info", "Estimated latency", "Mic -> output, including the pitch window when pitch is active.",
                     lambda: f"~{eng.latency_ms():.0f} ms"),
            ]
        return [
            choice_item("Characters", "Unicode box drawing, or plain ASCII for old consoles.", "ui.charset",
                        ["auto", "unicode", "ascii"], app.rebuild_theme),
            choice_item("Refresh rate", "UI frames per second (takes effect next launch). Audio is unaffected.", "ui.fps",
                        [20, 30, 60]),
            toggle_item("Waveform display", "Live input waveform on the dashboard.", "ui.waveform"),
        ]

    def _no_backend(self) -> bool:
        try:
            dev.hostapi_names()
            return False
        except dev.AudioBackendError:
            return True

    def _open_devices(self, role):
        from .devices import DevicesScreen
        s = DevicesScreen(self.app)
        s.role = {"input": 0, "output": 1, "monitor": 2}[role]
        self.app.push(s)

    # ------------------------------------------------------------------ draw
    def draw(self, cv, r: Rect):
        th = self.th
        lw = 18 if r.w >= 60 else 14
        inner = cv.box(Rect(r.x, r.y, lw, r.h), th, self.TITLE, not self.in_items)
        self.cat.clamp(len(self.CATS))
        for i, c in enumerate(self.CATS):
            y = inner.y + i
            if y >= inner.bottom:
                break
            foc = i == self.cat.idx
            if foc:
                cv.fill(Rect(inner.x, y, inner.w, 1), " ", th.sel if not self.in_items else th.sel_dim)
            cv.put(inner.x + 1, y, (th.g.cur if foc else " ") + " " + c,
                   (th.sel if not self.in_items else th.sel_dim) if foc else th.text)
        cname = self.CATS[self.cat.idx]
        ir = cv.box(Rect(r.x + lw + 1, r.y, r.w - lw - 1, r.h), th, cname.upper(), self.in_items)
        items = self._items(cname)
        self.items_sel.clamp(len(items))
        desc_h = 2 if ir.h >= 8 else 0
        list_h = ir.h - desc_h
        first, last = self.items_sel.window(len(items), list_h)
        labw = min(26, ir.w // 2)
        for row, i in enumerate(range(first, last)):
            it, y = items[i], ir.y + row
            foc = self.in_items and i == self.items_sel.idx
            base = th.sel if foc else th.text
            if foc:
                cv.fill(Rect(ir.x, y, ir.w, 1), " ", th.sel)
            cv.put(ir.x + 1, y, th.g.cur if foc else " ", base)
            cv.put(ir.x + 3, y, fit(it.label, labw - 3), base)
            self._value(cv, th, it, ir.x + labw + 2, y, ir.right - (ir.x + labw + 2) - 1, foc)
        if desc_h:
            cv.hline(ir.x + 1, ir.bottom - 2, ir.w - 2, th.g.h, th.faint)
            it = items[self.items_sel.idx]
            cv.put(ir.x + 1, ir.bottom - 1, fit(it.desc, ir.w - 2), th.dim)

    def _value(self, cv, th, it: Item, x: int, y: int, w: int, foc: bool):
        base = th.sel if foc else th.text
        v = it.get() if it.get else None
        if it.kind == "toggle":
            txt = (th.g.dot + " ON") if v else (th.g.ring + " OFF")
            cv.put(x, y, txt, th.sel if foc else (th.on if v else th.off))
        elif it.kind == "choice":
            cv.put(x, y, f"{th.g.left} {v} {th.g.right}" if foc else f"  {v}", base)
        elif it.kind == "slider":
            sw = max(6, min(22, w - 9))
            frac = (v - it.lo) / (it.hi - it.lo)
            if foc:
                pos = int(round(max(0, min(1, frac)) * (sw - 1)))
                cv.put(x, y, th.g.slider * pos + th.g.thumb + th.g.track * (sw - pos - 1), th.sel)
            else:
                slider(cv, th, x, y, sw, frac, False, True)
            cv.put(x + sw + 1, y, it.fmt(v), th.sel if foc else th.bold)
        elif it.kind == "button":
            cv.put(x, y, fit(str(v), max(4, w - 12)), base)
            cv.put(x + min(len(str(v)), max(4, w - 12)) + 2, y, th.g.right, th.sel if foc else th.accent_s)
        else:
            cv.put(x, y, fit(str(v), w), th.sel if foc else th.dim)

    # ------------------------------------------------------------------ keys
    def on_key(self, key) -> bool:
        """Categories: Up/Down, Enter or Right opens. Items: Up/Down, Left/Right change, Enter toggles /
        activates. Backspace: items -> categories -> home."""
        n = key.name
        app = self.app
        if not self.in_items:
            if n in ("up", "down"):
                self.cat.move(-1 if n == "up" else 1, len(self.CATS), wrap=True)
                self.items_sel = ListState()
            elif n in ("enter", "right"):
                self.in_items = True
            else:
                return False
            return True
        items = self._items(self.CATS[self.cat.idx])
        self.items_sel.clamp(len(items))
        it = items[self.items_sel.idx]
        if n in ("up", "down"):
            self.items_sel.move(-1 if n == "up" else 1, len(items), wrap=True)
        elif n == "backspace":
            self.in_items = False
        elif n in ("left", "right"):
            sign = 1 if n == "right" else -1
            if it.kind == "toggle":
                it.set(not it.get())
            elif it.kind == "choice":
                opts = it.options
                cur = it.get()
                i = opts.index(cur) if cur in opts else 0
                it.set(opts[(i + sign) % len(opts)])
            elif it.kind == "slider":
                span = (it.hi - it.lo) / it.step
                v = it.get() + sign * it.step * app.accel(span)
                v = round((v - it.lo) / it.step) * it.step + it.lo
                it.set(max(it.lo, min(it.hi, round(v, 6))))
        elif n == "enter":
            if it.kind == "toggle":
                it.set(not it.get())
            elif it.kind == "choice":
                opts = it.options
                cur = it.get()
                it.set(opts[((opts.index(cur) if cur in opts else 0) + 1) % len(opts)])
            elif it.kind == "button" and it.press:
                it.press()
        else:
            return False
        return True
