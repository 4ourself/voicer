# Voicer

A real-time voice changer for Windows 10 and 11 that runs in a terminal window. Your microphone goes through a
chain of effects and out to a virtual microphone cable, so Discord, games or OBS hear the changed voice. You can
also send the processed voice to your headphones to hear yourself.

Voicer is only the voice changer. The soundboard is a separate project, [Soundpad](../soundpad_GIT), and the two
can run side by side on the same cable.

![Voicer title screen](docs/screenshots/11_title_screen_logo_glow.png)

![Voice screen](docs/screenshots/02_voice_dashboard.png)

## Contents

- [Install and run](#install-and-run)
- [First start and the virtual cable](#first-start-and-the-virtual-cable)
- [Controls](#controls)
- [Effects](#effects)
- [Presets](#presets)
- [Screens](#screens)
- [Customize](#customize)
- [Config files](#config-files)
- [Using it with Soundpad](#using-it-with-soundpad)
- [Privacy and safety](#privacy-and-safety)
- [Command line](#command-line)
- [Data files](#data-files)
- [How it works](#how-it-works)
- [Tests](#tests)
- [License](#license)

## Install and run

You need Windows 10 or 11 and Python 3.10 or newer ([python.org](https://www.python.org/downloads/), tick
"Add python.exe to PATH" in the installer).

Download the repository (Code, then Download ZIP, or `git clone`), then double-click **run.bat**.

What `run.bat` does:

1. Finds Python.
2. Creates a private environment in the `.venv` folder next to it (once). Nothing is installed system-wide.
3. Checks that the libraries are present. Only if one is missing it runs `pip install -r requirements.txt`.
   A normal launch downloads nothing.
4. Starts `main.py`.

Manual start, if you prefer:

```
pip install -r requirements.txt
python main.py
```

Use Windows Terminal if you can (the default terminal on Windows 11). The window must be at least 80 by 24
characters. Truecolor is detected automatically; other consoles fall back to 256 or 16 colors.

Libraries: numpy, scipy and sounddevice. Their licenses are their own.

## First start and the virtual cable

1. Install a virtual cable such as [VB-Cable](https://vb-audio.com/Cable/).
2. Start Voicer and press Enter on the title screen. On the very first run a setup screen opens. Pick
   **Output** = `CABLE Input` (it is preselected if found), check the Microphone and Monitor, then go to
   **FINISH SETUP** and press Enter.
3. In Discord (or the game, or OBS) choose `CABLE Output` as the input device and turn off
   "Automatic input sensitivity".
4. Never use `CABLE Output` as Voicer's microphone. That would feed the cable back into itself.

![Device list](docs/screenshots/10_devices.png)

| Device     | What it is |
|------------|------------|
| Microphone | your real microphone |
| Output     | the virtual cable, for example `CABLE Input` |
| Monitor    | your headphones, used by "Hear Output" |

The device screen is also available from the Voice screen and from Settings > Devices. Unplugged devices are
reconnected automatically.

## Controls

Only a few keys are used everywhere.

| Key | Action |
|-----|--------|
| Up / Down | move |
| Left / Right | adjust a slider or choice, open an effect's page with Right |
| Enter | toggle or activate |
| Backspace | go back, from the home menu it asks to quit |

Holding Left or Right speeds up sliders the longer you hold. In text fields Backspace deletes characters.

## Effects

All effects work live while you talk. Parameters change in place, the audio never restarts. The chain order is
volume, pitch, EQ, distortion, reverb, echo.

On the Voice screen, Enter switches the focused effect on or off and Right opens its parameter page. On that page
Left and Right change the selected value, Enter on **Reset** puts the defaults back.

| Effect | Parameters |
|--------|------------|
| Volume | Volume 0 to 200 percent, Gain -24 to +24 dB |
| Pitch | Semitones -12 to +12, Window 20 to 80 ms |
| EQ | Bass, Mid, Treble (each -18 to +18 dB), High-pass 0 to 1000 Hz, Low-pass 1 to 20 kHz |
| Distortion | Drive 0 to 40 dB, Level -24 to +6 dB, Mix 0 to 100 percent |
| Reverb | Room, Damping, Mix (each 0 to 100 percent) |
| Echo | Delay 50 to 1000 ms, Feedback 0 to 90 percent, Mix 0 to 100 percent |

![Pitch page](docs/screenshots/03_effect_pitch.png)
![Distortion page](docs/screenshots/04_effect_distortion.png)

Pitch is a real pitch shifter that does not change the speed of your voice and does not resample. Two read
heads sweep through a short delay line and are crossfaded, which costs about half the window in latency
(around 20 ms with the default 40 ms). A smaller window is faster but sounds rougher.

Two switches on the Voice screen:

- **Effects Bypass**: your voice goes through unchanged. Only the voice chain is bypassed.
- **Hear Output**: sends the processed voice to the Monitor device so you can hear yourself.

## Presets

Open **Presets** from the Voice screen. Enter applies one. The built-in ones are Normal, Deep Voice, High Voice,
Chipmunk, Radio, Robot, Distorted, Cave and Demon. **+ Save current setup** stores the current effects under a
name you type. Right on one of your own presets deletes it after a confirmation, built-in ones cannot be deleted.

![Presets](docs/screenshots/05_presets.png)

## Screens

**Title screen and home menu.** The logo glows from time to time. Press Enter to reach the menu: Voice Changer,
Customize, Settings, Help & diagnostics, Exit. Before the menu is usable the home screen shows the start-up
steps with their state.

![Main menu](docs/screenshots/14_main_menu_has_customize.png)

**Voice.** The main screen. The left side lists the effects with their main value and on/off state, followed by
Effects Bypass, Hear Output, Presets and Devices. The LIVE AUDIO panel shows input, output and monitor levels
and a waveform of your microphone. The SYSTEM panel shows the three devices, whether the voice is processed or
bypassed, hear output and the estimated latency.

![Voice screen](docs/screenshots/02_voice_dashboard.png)

**Settings.**

- Audio: Hear Output, Effects Bypass, voice volume, monitor volume, mono output.
- Devices: Microphone, Output, Monitor, refresh devices, audio system (WASAPI by default).
- Performance: audio buffer (10 to 40 ms), safety buffer, output channels, sample rate, estimated latency.
- Interface: characters (unicode or ASCII), refresh rate, waveform display.
- Config: export and import, see below.

![Settings audio](docs/screenshots/06_settings_audio.png)
![Settings performance](docs/screenshots/07_settings_performance.png)

**Help.** Overview explains the setup. **Signal check** follows your voice through the chain and says where it
stops: microphone not open or silent, input is a virtual cable, Output not open or a normal device instead of a
cable, Output silent, Monitor missing, voice volume at 0, an effect that crashed and was disabled, buffer
underruns. The event log lists what happened since the start.

![Help overview](docs/screenshots/08_help_overview.png)
![Signal check](docs/screenshots/09_help_signal_check.png)

## Customize

Customize is in the main menu and in the header. Everything applies immediately and is saved.

![Customize](docs/screenshots/16_customize_colors.png)

**Colors**

- **Main color**: the color of focus bars, titles and borders. The editor has three columns. Controls on the
  left (mode, color stops, hue, saturation, brightness, red, green, blue, hex, alpha, reset), a color field and
  hue strip in the middle, and a live example on the right. Modes are Solid, Gradient (2 to 4 colors) and
  Rainbow (animated, with a speed).
- **Main color preset**: cyan, green, magenta, amber, blue or custom.
- **Volume graph colors**: meters and waveform. Same editor plus Zones (the default green, yellow, red).
- **Backdrop** and **Backdrop color**: see the note on alpha below.
- **Reset colors** and **Color mode** (auto, true, 256, 16, mono).

![Solid color editor](docs/screenshots/17_editor_solid_color.png)
![Gradient editor](docs/screenshots/18_editor_gradient.png)
![Graph colors](docs/screenshots/21_editor_graph_gradient.png)
![Rainbow editor](docs/screenshots/23_editor_rainbow.png)

A UI with a gradient and a gradient volume graph, and rainbow mode:

![Gradient UI](docs/screenshots/20_custom_gradient_ui_and_graph.png)
![Rainbow UI](docs/screenshots/22_rainbow_mode.png)

**About alpha.** A terminal cannot show your desktop through single characters, so alpha cannot be real
transparency per cell. Alpha mixes a color with the **Backdrop**. With Backdrop set to `terminal` (default) that
is the terminal's own background, assumed to be near black. With `custom` you paint a solid color or a vertical
gradient, the app fills its background with it, and alpha blends against that. If you want real see-through,
use Windows Terminal's own opacity or acrylic setting and keep Backdrop on `terminal`.

![Alpha in the editor](docs/screenshots/19_editor_alpha_see_through.png)
![Custom backdrop](docs/screenshots/24_backdrop_gradient_with_alpha.png)
![Backdrop editor](docs/screenshots/25_editor_backdrop.png)

**Layout**

- Graph position: left, center or right (center needs about 110 columns, otherwise it falls back to right).
- Menu position: left, center or right.
- Borders: rounded (default) or square.

![Graph left](docs/screenshots/26_graph_left.png)
![Graph center](docs/screenshots/27_graph_center.png)
![Menu right](docs/screenshots/28_menu_right.png)
![Layout page](docs/screenshots/30_customize_layout.png)

**Animation.** Tab animation: none (default), fade, line, slide, wipe, dissolve, curtain, blinds or random, with
speed fast, normal or slow. Choosing one plays it once. Animations only touch the screen, never the audio.

![Animation page](docs/screenshots/31_customize_animation.png)

<details>
<summary>Animation frames</summary>

![fade](docs/screenshots/35_animation_fade.png)
![line](docs/screenshots/36_animation_line.png)
![slide](docs/screenshots/37_animation_slide.png)
![wipe](docs/screenshots/38_animation_wipe.png)
![dissolve](docs/screenshots/39_animation_dissolve.png)
![curtain](docs/screenshots/40_animation_curtain.png)
![blinds](docs/screenshots/41_animation_blinds.png)

</details>

**Logo.** Title screen on or off, and logo glow: sometimes (default), always or off.

![Logo with a gradient](docs/screenshots/12_title_screen_gradient.png)
![Logo with rainbow](docs/screenshots/13_title_screen_rainbow.png)
![Title screen at 80x24](docs/screenshots/15_title_screen_80x24.png)
![Logo page](docs/screenshots/32_customize_logo.png)

## Config files

Customize > Config (also Settings > Config) has **Export config** and **Import config**. Export writes your
colors and settings to one JSON file, import reads one and applies it right away. Voicer and Soundpad use the
same format, so a look made in one can be imported in the other. The default file name is
`voicer-soundpad-config.json` in your user folder, so moving a look between the programs is Enter, Enter.

![Config page](docs/screenshots/33_customize_config_import_export.png)
![Export prompt](docs/screenshots/34_export_config_prompt.png)

Included: colors, layout, borders, animation, title screen and logo, characters, refresh rate, audio buffers and
each program's own tuning (volumes, hear output, mono output, bypass).

Never included: audio devices (microphone, output, monitor), the audio system, effect settings and presets.
Importing never changes your devices. Settings the other program does not have are skipped, and every value is
checked before it is stored, so a damaged or hand-edited file cannot break the app. A plain `data/config.json`
can be imported as well.

## Using it with Soundpad

Both programs can write to the same virtual cable. Windows mixes the streams, so Discord hears your voice from
Voicer and your sounds from Soundpad. Sounds never pass through Voicer's effects. Select the same cable as
Output in both and do not use the cable's recording side (`CABLE Output`) as the input of either.

## Privacy and safety

- Voicer processes your microphone in memory. It does not record or store audio.
- There is no network code in the program. It does not send anything anywhere, has no telemetry and no update
  check. You can verify this: `grep -r "socket\|urllib\|http\|subprocess" .` finds nothing in the program code.
- It does not install a keyboard hook and does not read your keys outside its own window.
- The only places it writes to are its own `data` folder (settings, effect values and presets) and files you
  export.
- The one network use is `pip` downloading the libraries from PyPI, once, in `run.bat` or when you install them
  yourself.

## Command line

```
python main.py                 start the interface
python main.py --list-devices  print all audio devices and exit
```

The environment variable `VOICER_DATA` moves the data folder.

## Data files

Created in `data/` next to the program (ignored by git): `config.json` with settings, devices, current effect
values and your presets.

## How it works

```
microphone -> VoiceProcessor (volume > pitch > EQ > distortion > reverb > echo) -> ring buffer
ring buffer -> Mixer (voice volume, soft limiter) -> Output (virtual cable)
                                                  -> ring buffer -> Monitor (Hear Output)
```

```
main.py  config.py  controller.py     entry point, settings file, what the UI talks to
configfile.py                         config export and import
audio/                                engine, capture, processor, mixer, output, devices, ring buffers, meters, diagnostics
effects/                              volume, pitch, eq, distortion, reverb, echo, presets
ui/                                   terminal renderer, theme, colors, animations, widgets, dialogs, screens
tests/                                automated tests
```

- Audio callbacks use 10 ms blocks and only light numpy work. A watchdog reconnects lost devices.
- Output and monitor run on separate device clocks. They are bridged by jitter-buffered ring buffers, so the
  delay stays bounded.
- The interface runs at 30 frames per second through a diff renderer and never touches audio buffers, so a slow
  terminal cannot cause crackling.

## Tests

```
pip install -r requirements-dev.txt
python -m pytest -q tests
```

The tests use a fake audio backend, so they need no sound hardware. They cannot cover real devices or the Windows
console; those were only run by hand.

## License

MIT, see [LICENSE](LICENSE). The logo is set in the "Bloody" FIGlet font.
