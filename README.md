# jpsub

Live Japanese subtitles for whatever is playing on your Linux desktop, with
furigana and a click-to-look-up dictionary. Built for watching Japanese video
while learning the language. Speech recognition runs entirely on your own
machine: no account, no cloud service, no audio leaves the computer.

- **Subtitles from any app:** captures the audio your speakers are playing
  (browser, mpv, games), so it works with any video source.
- **Furigana or romaji** over every word, always, on hover, or hidden.
- **Click a word for its meaning:** conjugated forms are looked up by their
  dictionary form (食べられなかった → 食べる), and the attached endings
  (られる, ない, た) can be looked up one by one.
- **Floating subtitle window** that sits above fullscreen video, with a pop-up
  dictionary. Clicks outside the subtitles go to the video underneath.
- **Full page view** in the browser with scrollable history, and saved words
  you can export to Anki.

## Requirements

- Linux on x86-64 with glibc 2.28 or newer (Ubuntu 20.04+, Debian 10+,
  Fedora, Arch, RHEL 8+).
- PipeWire or PulseAudio, with `parec` (package `pulseaudio-utils` on
  Fedora/Debian/Ubuntu, `libpulse` on Arch).
- For the floating window: GTK 3, WebKitGTK 4.1, PyGObject for the system
  Python, and gtk-layer-shell to float above fullscreen windows on Wayland.
  `install.sh` prints the exact packages for your distribution if any are
  missing.
- About 600 MB of disk space and a few CPU cores. No GPU needed.

## Install

Download `jpsub-<version>-linux-x86_64.tar.gz` from the releases page, then:

```sh
tar -xzf jpsub-*-linux-x86_64.tar.gz
cd jpsub-*-linux-x86_64
./install.sh            # installs to ~/.local/bin/jpsub
```

To install system-wide instead, use `sudo PREFIX=/usr/local ./install.sh`.

## First run

```sh
jpsub --overlay
```

The first time, jpsub asks before downloading what it needs (about 250 MB):
the SenseVoice speech model, a voice activity detector, and the JMdict
dictionary. These are kept in `~/.local/share/jpsub`. Downloads resume if
interrupted, and every file is checked against a fixed checksum.

To download without the prompt, for example in a script, run `jpsub --setup --yes`.

## Use

```sh
jpsub --overlay     # floating subtitle window over your video
jpsub --open        # the full page in your browser (http://127.0.0.1:8765)
```

Play something in Japanese; subtitles appear as people speak.

**Floating window.** Click a word for the pop-up dictionary; click it again, or
move the pointer away, to close it. The text holds still while the pointer is
over it, so the word you are reaching for doesn't move. Hover the bar for
controls: pause, readings (always / on hover / off), hiragana or romaji, text
size, background opacity, top or bottom of the screen, and close.

**Full page.** Scroll back through everything said. Click a word for its
dictionary entry, star entries to save them, and export saved words as a
tab-separated file for Anki from the Saved tab. Space pauses and resumes.

### Options

| Option | |
|---|---|
| `--overlay` | Also open the floating subtitle window. |
| `--overlay-only` | Open just the floating window, for a jpsub that is already running. |
| `--open` | Open the full page in your browser. |
| `--source NAME` | Capture a specific audio source, such as a microphone (`pactl list short sources` lists them). The default is whatever the default output is playing. |
| `--file PATH` | Transcribe an audio or video file at playback speed (needs `ffmpeg`). |
| `--port N` | Port for the local web server (default 8765). It only listens on 127.0.0.1. |
| `--threads N` | CPU threads for speech recognition (default 2). |
| `--data-dir DIR` | Keep models and the dictionary somewhere else (also `JPSUB_DATA_DIR`). |
| `--setup` | Download the models and dictionary, then exit. |
| `--yes` | Download without asking. |

### Window placement on Wayland compositors

The floating window is a layer-shell surface with the namespace `jpsub` on
the overlay layer. If your compositor draws shadows or blur behind overlay
surfaces, exclude it.


On desktops without layer-shell (GNOME, X11) it falls back to a borderless
always-on-top window.

## Uninstall

```sh
./install.sh --uninstall       # from the extracted release folder
rm -rf ~/.local/share/jpsub    # downloaded models, dictionary and window settings
```

## Accuracy and limits

On read-aloud Japanese test audio (FLEURS), the speech model gets about 93% of
characters right and transcribes a 12-second phrase in about a quarter of a
second on a laptop CPU. Expect more mistakes with fast, overlapping or noisy
speech such as anime or variety shows.

- Mistakes are usually the wrong kanji for names and rare words. Treat an
  unfamiliar word in the subtitles with some suspicion.
- Furigana for counters can be wrong (三十分 gets さんじゅうふん).
- Most personal names have no dictionary entry; the full page links to Jisho
  for anything not found.
- A speaker who never pauses produces one long line that settles at the pause.

## Building from source

Needs [uv](https://docs.astral.sh/uv/) and git.

```sh
git clone <this repository> && cd jpsub
./setup.sh      # Python environment, then the models and dictionary
./run.sh --overlay
```

`./run.sh` takes the same options as the binary. To build the binary and the
release tarball into `dist/`:

```sh
./build.sh
```

The binary bundles Python and all libraries, but uses the system's C++
runtime, so it runs on any distribution at least as new as glibc 2.28.

### How it works

| Step | Tool | Code |
|---|---|---|
| Capture system audio | `parec` | `jpsub/recognizer.py` |
| Split speech into phrases | Silero VAD | `jpsub/recognizer.py` |
| Speech to text | SenseVoice small via sherpa-onnx | `jpsub/recognizer.py` |
| Words, readings, dictionary forms, romaji | Sudachi | `jpsub/japanese.py` |
| Definitions | JMdict in SQLite | `jpsub/dictionary.py` |
| Web server and live updates | aiohttp, WebSocket | `jpsub/server.py`, `jpsub/web/` |
| Floating window | GTK 3, gtk-layer-shell, WebKitGTK | `jpsub/overlay.py` |
| First-run downloads | | `jpsub/assets.py` |

`bench/` holds the comparison of five speech models that led to choosing
SenseVoice (see `bench/bench.py`).

## License

MIT for jpsub itself. The dictionary and speech models are downloaded from
their publishers on first run and keep their own licenses; see
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). Dictionary data is from
JMdict by the Electronic Dictionary Research and Development Group, used under
CC BY-SA 4.0.
