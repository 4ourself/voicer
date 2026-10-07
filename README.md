# Voicer

Real-time voice changer for Windows 10 and 11. It runs in the terminal, takes your microphone, applies effects and
sends the result to a virtual microphone cable. Discord, games and OBS hear the changed voice.

The soundboard is a separate project, Soundpad. Both can use the same cable at the same time.

![Title screen](docs/screenshots/11_title_screen_logo_glow.png)

## Install

Needs Windows 10 or 11 and Python 3.10 or newer ([python.org](https://www.python.org/downloads/), tick
"Add python.exe to PATH").

1. Download the repository (Code, Download ZIP) and unpack it.
2. Double-click **run.bat**.

`run.bat` creates a private `.venv` folder once, installs the libraries only if they are missing, and starts
`main.py`. A normal launch downloads nothing.

Manual start: `pip install -r requirements.txt`, then `python main.py`. Use Windows Terminal, at least 80x24.

## Setup

1. Install a virtual cable, for example [VB-Cable](https://vb-audio.com/Cable/).
2. Start Voicer, press Enter on the title screen. The first run opens a setup screen.
3. Set **Output** to `CABLE Input`, check Microphone and Monitor, choose **FINISH SETUP**.
4. In Discord, OBS or the game choose `CABLE Output` as the microphone. Turn off automatic input sensitivity.

Never use `CABLE Output` as Voicer's own microphone.

![Devices](docs/screenshots/10_devices.png)

| Device | Meaning |
|--------|---------|
| Microphone | your real microphone |
| Output | the virtual cable (`CABLE Input`) |
| Monitor | your headphones, for Hear Output |

## Controls

| Key | Action |
|-----|--------|
| Up / Down | move |
| Left / Right | change a value, Right opens an effect page |
| Enter | switch on or off, confirm |
| Backspace | go back |

Hold Left or Right to change sliders faster.

## Voice screen

Effects on the left, live levels and waveform on the right, devices and latency at the bottom.
Enter switches an effect, Right opens its settings.

![Voice screen](docs/screenshots/02_voice_dashboard.png)

- **Effects Bypass**: your voice passes through unchanged.
- **Hear Output**: you hear the processed voice in the Monitor device.

## Effects

Chain order: volume, pitch, EQ, distortion, reverb, echo. All change live without restarting the audio.

| Effect | Settings |
|--------|----------|
| Volume | 0 to 200 percent, gain -24 to +24 dB |
| Pitch | -12 to +12 semitones, window 20 to 80 ms |
| EQ | bass, mid, treble +-18 dB, high-pass 0 to 1000 Hz, low-pass 1 to 20 kHz |
| Distortion | drive, level, mix |
| Reverb | room, damping, mix |
| Echo | delay 50 to 1000 ms, feedback, mix |

<img src="docs/screenshots/03_effect_pitch.png" width="49%"> <img src="docs/screenshots/04_effect_distortion.png" width="49%">

Pitch does not change the speed of your voice. Latency is about half the window (around 20 ms by default).

## Presets

Normal, Deep Voice, High Voice, Chipmunk, Radio, Robot, Distorted, Cave, Demon. You can save your own with
**+ Save current setup**. Right on your own preset deletes it.

![Presets](docs/screenshots/05_presets.png)

## Settings

Audio, devices, performance (buffer 10 to 40 ms, sample rate, channels), interface and config.

<img src="docs/screenshots/06_settings_audio.png" width="49%"> <img src="docs/screenshots/07_settings_performance.png" width="49%">

## Help and signal check

**Signal check** follows your voice through the chain and says where it stops: microphone silent, wrong
device, output not open, an effect that failed, buffer underruns.

<img src="docs/screenshots/08_help_overview.png" width="49%"> <img src="docs/screenshots/09_help_signal_check.png" width="49%">

## Customize

In the main menu. Everything applies at once and is saved.

![Main menu](docs/screenshots/14_main_menu_has_customize.png)

![Customize](docs/screenshots/16_customize_colors.png)

### Colors

Main color and volume graph colors can be a solid color, a gradient of 2 to 4 colors, or animated rainbow.
Controls: hue, saturation, brightness, RGB, hex and alpha.

<img src="docs/screenshots/17_editor_solid_color.png" width="49%"> <img src="docs/screenshots/18_editor_gradient.png" width="49%">
<img src="docs/screenshots/21_editor_graph_gradient.png" width="49%"> <img src="docs/screenshots/23_editor_rainbow.png" width="49%">
<img src="docs/screenshots/20_custom_gradient_ui_and_graph.png" width="49%"> <img src="docs/screenshots/22_rainbow_mode.png" width="49%">

### Backdrop and blur

| Backdrop | Result |
|----------|--------|
| terminal | nothing is painted, the Windows Terminal blur stays (default) |
| glass | your color is laid over the blur, alpha sets how much of the blur shows |
| custom | solid painted background, hides the blur |

A terminal cannot mix a cell color with the desktop, so `glass` uses shade characters to let the blur show
between them. If gradients look banded, set Color mode to `true`.

<img src="docs/screenshots/glass_backdrop_gradient.png" width="49%"> <img src="docs/screenshots/glass_backdrop_alpha_editor.png" width="49%">
<img src="docs/screenshots/19_editor_alpha_see_through.png" width="49%"> <img src="docs/screenshots/24_backdrop_gradient_with_alpha.png" width="49%">
<img src="docs/screenshots/25_editor_backdrop.png" width="49%">

The screenshots have no real blur behind them.

### Layout

Graph position and menu position: left, center or right. Borders: rounded or square.

<img src="docs/screenshots/26_graph_left.png" width="49%"> <img src="docs/screenshots/27_graph_center.png" width="49%">
<img src="docs/screenshots/28_menu_right.png" width="49%"> <img src="docs/screenshots/30_customize_layout.png" width="49%">

### Animation

Tab animation: none (default), fade, line, slide, wipe, dissolve, curtain, blinds, random. It only affects
the screen, never the audio.

![Animation settings](docs/screenshots/31_customize_animation.png)

<details>
<summary>Animation frames</summary>

<img src="docs/screenshots/35_animation_fade.png" width="49%"> <img src="docs/screenshots/36_animation_line.png" width="49%">
<img src="docs/screenshots/37_animation_slide.png" width="49%"> <img src="docs/screenshots/38_animation_wipe.png" width="49%">
<img src="docs/screenshots/39_animation_dissolve.png" width="49%"> <img src="docs/screenshots/40_animation_curtain.png" width="49%">
<img src="docs/screenshots/41_animation_blinds.png" width="49%">

</details>

### Logo

Title screen on or off, logo glow: sometimes, always or off.

<img src="docs/screenshots/12_title_screen_gradient.png" width="49%"> <img src="docs/screenshots/13_title_screen_rainbow.png" width="49%">
<img src="docs/screenshots/15_title_screen_80x24.png" width="49%"> <img src="docs/screenshots/32_customize_logo.png" width="49%">

### Config export and import

Customize > Config. Export saves your look and settings to one JSON file, import loads it. Voicer and Soundpad
share the format, so a look made in one works in the other. Audio devices, effects and presets are never
included.

<img src="docs/screenshots/33_customize_config_import_export.png" width="49%"> <img src="docs/screenshots/34_export_config_prompt.png" width="49%">

## Use with Soundpad

Select the same cable as Output in both programs. Windows mixes the two, so Discord hears your voice and your
sounds. Sounds never pass through the voice effects.

## Privacy

- Audio is processed in memory only. Nothing is recorded or stored.
- No network code, no telemetry, no update check. Only `pip` downloads the libraries, once.
- No keyboard hook. Keys are read only inside its own window.
- It writes only to its `data` folder and to files you export.

## Command line

```
python main.py                 start
python main.py --list-devices  list audio devices and exit
```

`VOICER_DATA` changes the data folder.

## Tests

```
pip install -r requirements-dev.txt
python -m pytest -q tests
```

Tests use a fake audio backend, no sound hardware needed.

## License

MIT, see [LICENSE](LICENSE). The logo uses the "Bloody" FIGlet font.
