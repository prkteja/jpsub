import argparse
import os
import shutil
import subprocess
import sys
import webbrowser
from pathlib import Path

from . import __version__, assets, paths

# Package names for the external programs jpsub runs.
_INSTALL_HINTS = {
    "parec": "Fedora: pulseaudio-utils · Debian/Ubuntu: pulseaudio-utils · Arch: libpulse",
    "ffmpeg": "Fedora (RPM Fusion), Debian/Ubuntu and Arch: ffmpeg",
}


def _restore_library_path():
    """Undo the packaged build's library path so child programs use system libraries.

    PyInstaller points LD_LIBRARY_PATH at its bundled libraries; programs
    started from here (parec, ffmpeg, the GTK overlay, the browser) must not
    pick those up. Libraries this process already loaded are unaffected.
    """
    if not getattr(sys, "frozen", False):
        return
    original = os.environ.pop("LD_LIBRARY_PATH_ORIG", None)
    if original:
        os.environ["LD_LIBRARY_PATH"] = original
    else:
        os.environ.pop("LD_LIBRARY_PATH", None)


def _require(program):
    if not shutil.which(program):
        sys.exit(f"jpsub needs `{program}`, which is not installed.\n"
                 f"  Package: {_INSTALL_HINTS[program]}")


def overlay_command(url):
    # The window uses the system's GTK bindings, so it runs under the system
    # Python rather than the one jpsub runs on (or is bundled with).
    python = os.environ.get("JPSUB_PYTHON", "/usr/bin/python3")
    return [python, str(Path(__file__).with_name("overlay.py")), "--url", url]


def start_overlay(url):
    try:
        return subprocess.Popen(overlay_command(url))
    except FileNotFoundError as error:
        print(f"Could not start the floating window: {error.filename} not found "
              "(set JPSUB_PYTHON to a Python 3 that has PyGObject).", file=sys.stderr)
        return None


def main():
    parser = argparse.ArgumentParser(
        prog="jpsub", description="Live Japanese subtitles with furigana and word lookup."
    )
    parser.add_argument("--version", action="version", version=f"jpsub {__version__}")
    parser.add_argument("--overlay", action="store_true",
                        help="also show the floating subtitle window")
    parser.add_argument("--overlay-only", action="store_true",
                        help="only open the floating window, for a jpsub that is already running")
    parser.add_argument("--open", action="store_true", help="open the full page in your browser")
    parser.add_argument("--source", help="PipeWire/PulseAudio source to capture "
                        "(default: whatever is playing on the default output; "
                        "list sources with `pactl list short sources`)")
    parser.add_argument("--file", help="transcribe an audio or video file instead of live audio")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--threads", type=int, default=2, help="CPU threads for speech recognition")
    parser.add_argument("--data-dir", help=f"where models and the dictionary are kept "
                        f"(default: {paths.data_dir()})")
    parser.add_argument("--setup", action="store_true",
                        help="download the models and dictionary, then exit")
    parser.add_argument("--yes", "-y", action="store_true",
                        help="download without asking on first run")
    args = parser.parse_args()

    _restore_library_path()
    if args.data_dir:
        os.environ["JPSUB_DATA_DIR"] = str(Path(args.data_dir).expanduser().resolve())
    url = f"http://{args.host}:{args.port}"

    if args.overlay_only:
        process = start_overlay(url)
        sys.exit(process.wait() if process else 1)

    try:
        if not assets.ensure(assume_yes=args.yes):
            sys.exit(1)
    except (RuntimeError, OSError) as error:
        sys.exit(f"Setup failed: {error}\nRun jpsub again to resume the download.")
    except KeyboardInterrupt:
        sys.exit("\nDownload interrupted; run jpsub again to resume it.")
    if args.setup:
        return

    _require("ffmpeg" if args.file else "parec")

    from aiohttp import web

    from .server import create_app

    app = create_app({"source": args.source, "file": args.file, "threads": args.threads})
    print(f"jpsub {__version__} is running at {url} (Ctrl-C to stop)")
    if args.open:
        webbrowser.open(url)
    if args.overlay:
        async def overlay_window(app):
            process = start_overlay(url)
            yield
            if process:
                process.terminate()

        app.cleanup_ctx.append(overlay_window)
    web.run_app(app, host=args.host, port=args.port, print=None)


if __name__ == "__main__":
    main()
