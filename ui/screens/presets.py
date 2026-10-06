"""Preset browser: apply built-in / custom presets instantly, save the current setup as a custom one."""
from __future__ import annotations

from effects.presets import BUILTIN

from ..canvas import Rect, fit
from ..modals import Confirm, Prompt
from ..widgets import ListState, scrollbar
from .base import BaseScreen


class PresetsScreen(BaseScreen):
    def __init__(self, app):
        super().__init__(app)
        self.sel = ListState()

    def _names(self):
        return self.ctl.preset_names()

    def draw(self, cv, r: Rect):
        th, ctl = self.th, self.ctl
        names = self._names()
        lw = min(34, r.w) if r.w >= 70 else r.w
        inner = cv.box(Rect(r.x, r.y, lw, r.h), th, "PRESETS", True)
        total = len(names) + 1
        self.sel.clamp(total)
        first, last = self.sel.window(total, inner.h)
        for row, i in enumerate(range(first, last)):
            y, foc = inner.y + row, i == self.sel.idx
            if foc:
                cv.fill(Rect(inner.x, y, inner.w, 1), " ", th.sel)
            if i == 0:
                cv.put(inner.x + 1, y, (th.g.cur if foc else " ") + " + Save current setup", th.sel if foc else th.accent_b)
                continue
            name, builtin = names[i - 1]
            cv.put(inner.x + 1, y, (th.g.cur if foc else " ") + " " + fit(name, inner.w - 14), th.sel if foc else th.text)
            if not builtin:
                cv.put(inner.right - 9, y, "(custom)", th.sel if foc else th.accent_s)
        scrollbar(cv, th, inner.right - 1, inner.y, inner.h, first, last, total)
        if r.w >= 70 and self.sel.idx > 0:
            self._preview(cv, Rect(r.x + lw + 1, r.y, r.w - lw - 1, r.h), names[self.sel.idx - 1][0])

    def _spec(self, name):
        user = self.ctl.config.get("presets") or {}
        return BUILTIN[name] if name in BUILTIN else user.get(name, {})

    def _preview(self, cv, rect: Rect, name: str):
        th = self.th
        inner = cv.box(rect, th, f"PREVIEW  -  {name}")
        spec = self._spec(name)
        y = inner.y
        on = [(e, spec[e.name]) for e in self.ctl.chain if spec.get(e.name, {}).get("enabled")]
        if not on or (len(on) == 1 and on[0][0].name == "volume" and name == "Normal"):
            cv.put(inner.x + 1, y, "All effects off - your natural voice.", th.dim)
            return
        for e, d in on:
            if y >= inner.bottom:
                break
            cv.put(inner.x + 1, y, th.g.dot, th.on)
            cv.put(inner.x + 3, y, e.label, th.bold)
            y += 1
            for p in e.params:
                v = d.get("params", {}).get(p.key, p.default)
                if y >= inner.bottom:
                    break
                if abs(v - p.default) > 1e-9:
                    cv.put(inner.x + 5, y, f"{p.label:<11} {v:g}{p.unit}", th.dim)
                    y += 1

    def on_key(self, key) -> bool:
        """Row 0 = save the current setup as a new preset; then the presets.
        Up/Down move, Enter applies, Right on a custom preset deletes it (with confirmation)."""
        n = key.name
        names = self._names()
        total = len(names) + 1
        if n in ("up", "down"):
            self.sel.move(-1 if n == "up" else 1, total, wrap=True)
        elif n == "enter":
            if self.sel.idx == 0:
                self._save()
            else:
                name = names[self.sel.idx - 1][0]
                self.ctl.apply_preset(name)
                self.app.notify("ok", f"Preset applied: {name}")
        elif n == "right" and self.sel.idx > 0:
            name, builtin = names[self.sel.idx - 1]
            if builtin:
                self.app.notify("warn", "Built-in presets cannot be deleted")
            else:
                self.app.open_modal(Confirm("DELETE PRESET", f"Delete '{name}'?", "DELETE", "KEEP",
                                            on_yes=lambda: self.ctl.delete_preset(name)))
        else:
            return False
        return True

    def _save(self):
        def ok(name):
            self.ctl.save_preset(name)
            self.app.notify("ok", f"Saved preset '{name}'")
        self.app.open_modal(Prompt("SAVE CURRENT AS PRESET", "Preset name:", "Custom", ok,
                                   lambda v: "Name required" if not v.strip() else
                                   "Name is a built-in preset" if v.strip() in BUILTIN else ""))
