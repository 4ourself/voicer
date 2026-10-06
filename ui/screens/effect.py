"""Effect detail panel: live sliders for every parameter of one effect."""
from __future__ import annotations

from ..canvas import Rect, fit
from ..widgets import ListState, button, db_text, fmt_value, meter, slider, toggle, waveform
from .base import BaseScreen

INFO = {
    "volume": "Level of your voice. Gain adds or removes dB, Volume is the final percentage.",
    "pitch": "Real pitch shifting (speed unchanged). Smaller window = lower latency, more warble.",
    "eq": "Bass < 120 Hz, mid ~1 kHz, treble > 5 kHz. High-pass removes rumble, low-pass removes hiss.",
    "distortion": "Soft-clip overdrive. Raise Drive for grit, lower Level to compensate, Mix blends dry/wet.",
    "reverb": "Room reflections. Room = tail length, Damping = how dull the tail is, Mix = amount.",
    "echo": "Repeating delay. Feedback = number of repeats. Minimum delay is 50 ms (metallic at short settings).",
}


class EffectScreen(BaseScreen):
    def __init__(self, app, name: str):
        super().__init__(app)
        self.name = name
        self.sel = ListState()

    @property
    def fx(self):
        return self.ctl.effect(self.name)

    def _n(self):
        return len(self.fx.params) + 2            # [STATUS] + params + [RESET]

    def draw(self, cv, r: Rect):
        th, fx = self.th, self.fx
        if r.w >= 84:
            lw = int(r.w * 0.58)
            self._controls(cv, Rect(r.x, r.y, lw, r.h))
            self._side(cv, Rect(r.x + lw + 1, r.y, r.w - lw - 1, r.h))
        else:
            ch = r.h - (4 if r.h >= 20 else 0)
            self._controls(cv, Rect(r.x, r.y, r.w, ch))
            if r.h >= 20:
                self._side(cv, Rect(r.x, r.y + ch, r.w, r.h - ch), tiny=True)

    def _controls(self, cv, rect: Rect):
        th, fx, ctl = self.th, self.fx, self.ctl
        inner = cv.box(rect, th, fx.label.upper(), True)
        y = inner.y
        foc = self.sel.idx == 0
        self.sel.clamp(self._n())
        if foc:
            cv.fill(Rect(inner.x + 1, y, inner.w - 2, 1), " ", th.sel)
        cv.put(inner.x + 2, y, (th.g.cur + " " if foc else "  ") + "Status", th.sel if foc else th.dim)
        if foc:
            cv.put(inner.x + 14, y, (th.g.dot + " ENABLED") if fx.enabled else (th.g.ring + " DISABLED"), th.sel)
        else:
            toggle(cv, th, inner.x + 14, y, fx.enabled, "ENABLED", "DISABLED")
        if ctl.bypass:
            cv.put(inner.x + 30, y, "(global bypass is ON)", th.sel if foc else th.warn)
        y += 2
        n = len(fx.params)
        per = 3 if inner.h - 3 >= 3 * n + 2 else 2
        self.sel.clamp(self._n())
        for i, p in enumerate(fx.params):
            if y + 1 >= inner.bottom:
                break
            foc = self.sel.idx == i + 1
            v = fx.get(p.key)
            line = Rect(inner.x + 1, y, inner.w - 2, 1)
            if foc:
                cv.fill(line, " ", th.sel)
            cv.put(inner.x + 2, y, (th.g.cur + " " if foc else "  ") + p.label, th.sel if foc else th.text)
            vt = fmt_value(v, p.unit, p.step)
            cv.put(inner.right - 2 - len(vt), y, vt, th.sel if foc else th.bold)
            lo, hi = fmt_value(p.min, p.unit, p.step).strip(), fmt_value(p.max, p.unit, p.step).strip()
            sx = inner.x + 3 + len(lo) + 1
            sw = inner.right - 2 - len(hi) - 1 - sx
            cv.put(inner.x + 3, y + 1, lo, th.dim)
            slider(cv, th, sx, y + 1, sw, (v - p.min) / (p.max - p.min), foc, fx.enabled)
            cv.put(sx + sw + 1, y + 1, hi, th.dim)
            y += per
        if y < inner.bottom:
            button(cv, th, inner.x + 3, min(y, inner.bottom - 1), "RESET", self.sel.idx == n + 1)

    def _side(self, cv, rect: Rect, tiny: bool = False):
        th, ctl, m = self.th, self.ctl, self.app.meters
        inner = cv.box(rect, th, "LIVE")
        bw = max(4, inner.w - 20)
        y = inner.y
        for label, key in (("INPUT", "in"), ("OUTPUT", "out")):
            if y >= inner.bottom:
                break
            cv.put(inner.x + 1, y, label, th.dim)
            meter(cv, th, inner.x + 9, y, bw, m.level(key), m.peak(key))
            cv.put(inner.x + 10 + bw, y, db_text(m.level(key)), th.text)
            y += 1
        if tiny:
            return
        y += 1
        wh = max(0, min(7, inner.bottom - y - 6))
        if wh >= 3 and self.app.cfg.get("ui.waveform"):
            waveform(cv, th, Rect(inner.x + 1, y, inner.w - 2, wh), ctl.engine.wave_in.latest(max(64, inner.w * 6)))
            y += wh + 1
        text = INFO.get(self.name, "")
        if self.name == "pitch":
            text += f" Adds ~{self.fx.get('window_ms') / 2:.0f} ms latency."
        words, line = text.split(), ""
        for wd in words + [None]:
            if wd is None or len(line) + len(wd) + 1 > inner.w - 2:
                if y < inner.bottom:
                    cv.put(inner.x + 1, y, line, th.dim)
                y, line = y + 1, wd or ""
            else:
                line = (line + " " + wd).strip()

    def on_key(self, key) -> bool:
        """Up/Down: Status, each parameter, Reset. Left/Right adjust a slider live. Enter toggles / resets."""
        n = key.name
        ctl, app, fx = self.ctl, self.app, self.fx
        np_ = len(fx.params)
        if n in ("up", "down"):
            self.sel.move(-1 if n == "up" else 1, self._n(), wrap=True)
        elif n in ("left", "right") and 1 <= self.sel.idx <= np_:
            p = fx.params[self.sel.idx - 1]
            steps = (1 if n == "right" else -1) * app.accel((p.max - p.min) / p.step)
            _, newly = ctl.adjust(self.name, p.key, steps)
            if newly:
                app.notify("ok", f"{fx.label} enabled")
        elif n == "enter":
            if self.sel.idx == np_ + 1:
                ctl.reset_effect(self.name)
                app.notify("ok", f"{fx.label} reset")
            elif self.sel.idx == 0:
                ctl.toggle_effect(self.name)
        else:
            return False
        return True
