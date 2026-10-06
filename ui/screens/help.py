"""Help: key reference, live signal check (where does the audio stop?), event log."""
from __future__ import annotations

import time

from ..canvas import Rect, fit
from .base import BaseScreen

PAGES = ("Overview", "Signal check", "Event log")


def wrap(text: str, width: int) -> list[str]:
    out, line = [], ""
    for wd in text.split():
        if len(line) + len(wd) + 1 > width:
            out.append(line)
            line = wd
        else:
            line = (line + " " + wd).strip()
    return out + ([line] if line else [])


class HelpScreen(BaseScreen):
    def __init__(self, app):
        super().__init__(app)
        self.page = 0
        self.scroll = 0

    def draw(self, cv, r: Rect):
        th = self.th
        title = "   ".join(f"[{p}]" if i == self.page else f" {p} " for i, p in enumerate(PAGES))
        inner = cv.box(r, th, "HELP", True)
        # page tabs
        x = inner.x + 1
        for i, p in enumerate(PAGES):
            x += cv.put(x, inner.y, f" {p} ", th.tab_on if i == self.page else th.tab_off) + 1
        body = Rect(inner.x + 1, inner.y + 2, inner.w - 2, inner.h - 2)
        [self._keys, self._checks, self._log][self.page](cv, body)

    def _keys(self, cv, r: Rect):
        th = self.th
        rows = [
            ("SIGNAL PATH", None),
            ("", "MIC > effects (volume, pitch, EQ, distortion, reverb, echo) > MIXER"),
            ("", "                                                        |"),
            ("", "                          OUTPUT (virtual cable > Discord)  +  MONITOR (you)"),
            ("", "Effects Bypass turns the effects off; Hear Output sends your voice to the monitor."),
            ("", "Soundpad is a separate program: run it next to voicer."),
        ]
        self.scroll = max(0, min(self.scroll, max(0, len(rows) - r.h)))
        for row, (k, d) in enumerate(rows[self.scroll:self.scroll + r.h]):
            x, y = r.x, r.y + row
            if d is None:
                cv.put(x, y, k, th.title)
            else:
                cv.put(x, y, k, th.key)
                cv.put(x + (14 if k else 0), y, fit(d, r.w - 16), th.text if k else th.dim)
        if len(rows) > r.h:
            from ..widgets import scrollbar
            scrollbar(cv, th, r.right, r.y, r.h, self.scroll, self.scroll + r.h, len(rows))

    def _checks(self, cv, r: Rect):
        th = self.th
        y = r.y
        for lvl, msg in self.ctl.checks():
            icon, st = {"ok": ("OK  ", th.ok), "warn": ("WARN", th.warn), "bad": ("FAIL", th.err)}[lvl]
            for i, ln in enumerate(wrap(msg, r.w - 7)):
                if y >= r.bottom:
                    return
                if i == 0:
                    cv.put(r.x, y, icon, st)
                cv.put(r.x + 6, y, ln, th.text)
                y += 1
        if y + 1 < r.bottom:
            cv.put(r.x, y + 1, "Discord: set Input Device to 'CABLE Output', turn off Automatic Input Sensitivity.", th.dim)

    def _log(self, cv, r: Rect):
        th = self.th
        log = list(self.app.log)[-r.h:]
        if not log:
            cv.put(r.x, r.y, "No events yet.", th.dim)
        for i, (t, lvl, msg) in enumerate(log):
            st = {"error": th.err, "warn": th.warn, "ok": th.ok, "sound": th.sound}.get(lvl, th.text)
            cv.put(r.x, r.y + i, time.strftime("%H:%M:%S", time.localtime(t)), th.faint)
            cv.put(r.x + 9, r.y + i, fit(msg, r.w - 9), st)

    def on_key(self, key) -> bool:
        if key.name in ("up", "down") and self.page == 0:
            self.scroll = max(0, self.scroll + (1 if key.name == "down" else -1))
        elif key.name in ("left",):
            self.page = (self.page - 1) % len(PAGES); self.scroll = 0
        elif key.name in ("right",):
            self.page = (self.page + 1) % len(PAGES); self.scroll = 0
        else:
            return False
        return True
