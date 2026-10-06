"""Boot sequence run on a background thread so the boot screen can animate.
Order: config -> devices -> audio engine -> READY."""
from __future__ import annotations

from audio import devices as dev


def run_boot(app) -> None:
    ctl, b = app.ctl, app.boot

    def step(name, fn):
        b.status[name] = "run"
        try:
            status, detail = fn()
        except Exception as e:  # noqa: BLE001
            status, detail = "bad", str(e)[:70]
        b.status[name], b.detail[name] = status, detail

    step("config", lambda: ("ok", "first run" if ctl.config.first_run else "loaded"))

    def devices():
        api = dev.preferred_hostapi(ctl.config.get("audio.host_api"))
        n_in, n_out = len(dev.list_devices("input", api)), len(dev.list_devices("output", api))
        return "ok", f"{api}: {n_in} in / {n_out} out"
    step("devices", devices)

    def engine():
        if ctl.config.first_run:
            return "warn", "waiting for first-run setup"
        ctl.engine.start()
        return ("ok", "") if ctl.engine.running else ("bad", "output device unavailable")
    step("engine", engine)

    b.done = True
    if ctl.config.first_run:
        app.pending_setup = True        # the UI thread opens the setup once the title screen has been left
