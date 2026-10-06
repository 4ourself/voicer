"""Voice Changer dashboard: effect list with live mini-sliders, meters, waveform, device + state panels."""
from __future__ import annotations

from ..canvas import Rect, fit
from ..widgets import (ListState, db_text, dot, fmt_value, meter, slider, toggle, waveform, scrollbar)
from .base import BaseScreen

CONTROLS = ("bypass", "hear", "presets", "devices")


class VoiceScreen(BaseScreen):
    def __init__(self, app):
        super().__init__(app)
        self.sel = ListState()

    # ----------------------------------------------------------- items
    def n_items(self) -> int:
        return len(self.ctl.chain) + len(CONTROLS)

    def item(self, i: int):
        fx = self.ctl.chain
        return ("fx", fx[i]) if i < len(fx) else ("ctl", CONTROLS[i - len(fx)])

    # ----------------------------------------------------------- drawing
    def draw(self, cv, r: Rect):
        w, h = r.w, r.h
        wide, mid = w >= 96 and h >= 20, w >= 70 and h >= 15
        pos = self.app.graph_position()          # where the LIVE AUDIO graph panel sits: left | center | right
        if (wide or mid) and pos == "center" and w >= 110:
            lw, sw = 40, 30                      # effects | live audio | system
            self._effects_panel(cv, Rect(r.x, r.y, lw, h))
            self._live_panel(cv, Rect(r.x + lw + 1, r.y, w - lw - sw - 2, h))
            self._system_panel(cv, Rect(r.right - sw, r.y, sw, h))
        elif wide or mid:
            lw = 46 if wide else 40
            gw = w - lw - 1
            ex, gx = (r.x + gw + 1, r.x) if pos == "left" else (r.x, r.x + lw + 1)
            self._effects_panel(cv, Rect(ex, r.y, lw, r.h))
            right = Rect(gx, r.y, gw, r.h)
            sys_h = 9 if (wide and h >= 24) else 7
            if right.h >= 8 + sys_h:
                self._live_panel(cv, Rect(right.x, right.y, right.w, right.h - sys_h))
                self._system_panel(cv, Rect(right.x, right.bottom - sys_h, right.w, sys_h))
            else:
                self._live_panel(cv, right)
        else:
            lh = min(self.n_items() + 2, max(5, r.h - 5))
            self._effects_panel(cv, Rect(r.x, r.y, w, lh))
            if r.h - lh >= 4:
                self._live_panel(cv, Rect(r.x, r.y + lh, w, r.h - lh), compact=True)

    def _effects_panel(self, cv, rect: Rect):
        th, ctl = self.th, self.ctl
        inner = cv.box(rect, th, "EFFECTS", True)
        n = self.n_items()
        show_sep = inner.h >= n + 1
        display = list(range(n))
        if show_sep:
            display.insert(len(ctl.chain), -1)
        self.sel.clamp(n)
        fidx = self.sel.idx + (1 if show_sep and self.sel.idx >= len(ctl.chain) else 0)
        tmp = ListState()
        tmp.idx, tmp.top = fidx, getattr(self, "_top", 0)
        first, last = tmp.window(len(display), inner.h)
        self._top = tmp.top
        for row, di in enumerate(display[first:last]):
            y = inner.y + row
            if di == -1:
                cv.hline(inner.x + 1, y, inner.w - 2, th.g.h, th.faint)
                continue
            foc = di == self.sel.idx
            self._row(cv, Rect(inner.x, y, inner.w - (1 if len(display) > inner.h else 0), 1), di, foc)
        scrollbar(cv, th, inner.right - 1, inner.y, inner.h, first, last, len(display))

    def _row(self, cv, r: Rect, i: int, foc: bool):
        th, ctl = self.th, self.ctl
        kind, obj = self.item(i)
        base = th.sel if foc else th.text
        if foc:
            cv.fill(r, " ", th.sel)
        cv.put(r.x + 1, r.y, th.g.cur if foc else " ", base)
        if kind == "fx":
            e = obj
            on = e.enabled and not ctl.bypass
            if foc:
                cv.put(r.x + 3, r.y, (th.g.dot + " ON " if e.enabled else th.g.ring + " OFF"), th.sel)
            else:
                toggle(cv, th, r.x + 3, r.y, e.enabled)
            cv.put(r.x + 9, r.y, e.label, base if e.enabled or foc else th.dim)
            p = e.primary_param
            v = e.get(p.key)
            vt = fmt_value(v, p.unit, p.step)
            vw = 9
            cv.put(r.right - vw, r.y, vt.rjust(vw - 1), th.sel if foc else (th.bold if e.enabled else th.dim))
            sx, sw = r.x + 9 + 15, r.w - (9 + 15) - vw - 1
            if sw >= 6:
                if foc:
                    pos = int(round((v - p.min) / (p.max - p.min) * (sw - 1)))
                    cv.put(sx, r.y, th.g.slider * pos + th.g.thumb + th.g.track * (sw - pos - 1), th.sel)
                else:
                    slider(cv, th, sx, r.y, sw, (v - p.min) / (p.max - p.min), False, e.enabled)
        else:
            if obj == "bypass":
                if foc:
                    cv.put(r.x + 3, r.y, th.g.dot + " ON " if ctl.bypass else th.g.ring + " OFF", th.sel)
                else:
                    toggle(cv, th, r.x + 3, r.y, ctl.bypass)
                cv.put(r.x + 9, r.y, "Effects Bypass", base)
                if ctl.bypass:
                    cv.put(r.x + 9 + 15, r.y, fit("voice passes unchanged", r.w - 26), th.sel if foc else th.warn)
            elif obj == "hear":
                if foc:
                    cv.put(r.x + 3, r.y, th.g.dot + " ON " if ctl.hear_output else th.g.ring + " OFF", th.sel)
                else:
                    toggle(cv, th, r.x + 3, r.y, ctl.hear_output)
                cv.put(r.x + 9, r.y, "Hear Output", base)
            elif obj == "presets":
                cv.put(r.x + 3, r.y, th.g.right + "  ", base)
                cv.put(r.x + 9, r.y, "Presets", base)
                cv.put(r.x + 9 + 15, r.y, f"{len(ctl.preset_names())} available", th.sel if foc else th.dim)
            elif obj == "devices":
                cv.put(r.x + 3, r.y, th.g.right + "  ", base)
                cv.put(r.x + 9, r.y, "Devices", base)

    def _live_panel(self, cv, rect: Rect, compact: bool = False):
        th, ctl, m = self.th, self.ctl, self.app.meters
        inner = cv.box(rect, th, "LIVE AUDIO")
        if inner.h < 1:
            return
        lab = 9
        bw = max(4, inner.w - lab - 11)
        rows = [("MIC", "in", ctl.engine.health["input"]), ("OUTPUT", "out", ctl.engine.health["output"]),
                ("MONITOR", "mon", ctl.engine.health["monitor"])]
        y = inner.y
        for label, key, hs in rows:
            if y >= inner.bottom:
                break
            if key == "mon" and inner.h < 6:
                continue
            cv.put(inner.x + 1, y, label, th.dim)
            if hs["state"] in ("ok",) and (key != "mon" or ctl.hear_output):
                meter(cv, th, inner.x + lab, y, bw, m.level(key), m.peak(key))
                cv.put(inner.x + lab + bw + 1, y, db_text(m.level(key)), th.text)
            else:
                txt = "DISCONNECTED" if hs["state"] == "disconnected" else ("HEAR OUTPUT OFF" if key == "mon" and hs["state"] == "ok" else "OFF")
                cv.put(inner.x + lab, y, txt, th.err if hs["state"] == "disconnected" else th.off)
            y += 1
        # summary line at the bottom, waveform in between
        sum_y = inner.bottom - 1
        wf_top, wf_h = y + 1, sum_y - (y + 1) - (1 if inner.h > 9 else 0)
        if wf_h >= 3 and self.cfg_waveform():
            cv.put(inner.x + 1, y, "INPUT", th.dim)
            waveform(cv, th, Rect(inner.x + 1, wf_top, inner.w - 2, wf_h), ctl.engine.wave_in.latest(max(64, inner.w * 6)))
        if inner.h >= 6 and sum_y > y:
            vol, pitch = ctl.effect("volume"), ctl.effect("pitch")
            on = lambda e: e.enabled and not ctl.bypass  # noqa: E731
            st = (f"PITCH {pitch.get('semitones'):+.0f} st" if on(pitch) and abs(pitch.get("semitones")) > 0 else "PITCH off")
            gain = f"GAIN {vol.get('gain_db'):+.0f}dB  VOL {vol.get('volume'):.0f}%" if on(vol) else "GAIN +0dB  VOL 100%"
            cv.put(inner.x + 1, sum_y, fit(f"{st}  {gain}", inner.w - 2), th.bold)

    def cfg_waveform(self) -> bool:
        return bool(self.app.cfg.get("ui.waveform"))

    def _system_panel(self, cv, rect: Rect):
        th, ctl = self.th, self.ctl
        inner = cv.box(rect, th, "SYSTEM")
        hs = ctl.engine.health
        two = inner.w >= 56
        y = inner.y
        names = (("INPUT", "input"), ("OUTPUT", "output"), ("MONITOR", "monitor"))
        colw = inner.w // 2 if two else inner.w
        for label, role in names:
            h = hs[role]
            cv.put(inner.x + 1, y, label, th.dim)
            st = {"ok": "ok", "disconnected": "bad", "disabled": "off", "init": "off"}[h["state"]]
            dot(cv, th, inner.x + 9, y, st)
            txt = h["name"] or ("DISCONNECTED" if st == "bad" else "disabled" if st == "off" else "default")
            if st == "bad":
                txt = "DISCONNECTED" + (f" ({h['error']})" if h["error"] else "")
            cv.put(inner.x + 11, y, fit(txt, colw - 12), th.err if st == "bad" else th.text)
            y += 1
        states = [("VOICE", "off" if ctl.bypass else "ok", "BYPASSED" if ctl.bypass else "PROCESSING"),
                  ("HEAR OUTPUT", "ok" if ctl.hear_output else "off", "ON" if ctl.hear_output else "OFF"),
                  ("LATENCY", "ok", f"~{ctl.engine.latency_ms():.0f} ms")]
        if two:
            y2 = inner.y
            for label, st, txt in states:
                if y2 >= inner.bottom:
                    break
                x0 = inner.x + colw + 1
                cv.put(x0, y2, label, th.dim)
                dot(cv, th, x0 + 13, y2, st if label != "VOICE" or not ctl.bypass else "warn")
                cv.put(x0 + 15, y2, fit(txt, colw - 17), th.text)
                y2 += 1
        else:
            for label, st, txt in states:
                if y >= inner.bottom:
                    break
                cv.put(inner.x + 1, y, label, th.dim)
                dot(cv, th, inner.x + 13, y, st)
                cv.put(inner.x + 15, y, fit(txt, inner.w - 16), th.text)
                y += 1

    # ----------------------------------------------------------- input
    def on_key(self, key) -> bool:
        """Up/Down move, Enter toggles (effects, bypass, hear output) or opens (presets, devices),
        Right opens the focused effect's settings page. Backspace (global) goes back."""
        n = key.name
        ctl, app = self.ctl, self.app
        if n in ("up", "down"):
            self.sel.move(-1 if n == "up" else 1, self.n_items(), wrap=True)
            return True
        kind, obj = self.item(self.sel.idx)
        if n == "right" and kind == "fx":
            from .effect import EffectScreen
            app.push(EffectScreen(app, obj.name))
            return True
        if n == "enter":
            if kind == "fx":
                ctl.toggle_effect(obj.name)
            elif obj == "bypass":
                app.toggle_bypass()
            elif obj == "hear":
                app.toggle_hear()
            elif obj == "presets":
                app.open_presets()
            elif obj == "devices":
                app.open_devices()
            return True
        return False
