#!/usr/bin/python3
"""Floating subtitle window: shows the jpsub overlay page above other windows.

Runs with the system Python (it needs the system GTK bindings, not the project
environment). On Wayland compositors with layer-shell support (niri, sway,
Hyprland, KDE) the window sits on the overlay layer, above fullscreen video,
and never takes keyboard focus. Elsewhere it falls back to a borderless
always-on-top window.
"""
import argparse
import json
import signal
import sys
from pathlib import Path

MISSING = """The floating window needs PyGObject, GTK 3 and WebKitGTK 4.1 for the
system Python ({python}), plus gtk-layer-shell to float above fullscreen video.

  Fedora:        sudo dnf install python3-gobject gtk3 webkit2gtk4.1 gtk-layer-shell
  Debian/Ubuntu: sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-3.0 \\
                     gir1.2-webkit2-4.1 gir1.2-gtklayershell-0.1
  Arch:          sudo pacman -S python-gobject python-cairo gtk3 webkit2gtk-4.1 gtk-layer-shell

({error})"""

try:
    import cairo
    import gi

    gi.require_version("Gdk", "3.0")
    gi.require_version("Gtk", "3.0")
    gi.require_version("WebKit2", "4.1")
    from gi.repository import Gdk, GLib, Gtk, WebKit2
except (ImportError, ValueError) as error:
    sys.exit(MISSING.format(python=sys.executable, error=error))

try:
    gi.require_version("GtkLayerShell", "0.1")
    from gi.repository import GtkLayerShell
except (ImportError, ValueError):
    GtkLayerShell = None  # falls back to an ordinary always-on-top window

WAITING_PAGE = """
<body style="margin:0;height:100vh;display:flex;align-items:flex-end;justify-content:center;
             background:transparent;font:14px system-ui,sans-serif;color:#a3aab6">
  <div style="background:rgba(16,18,22,.86);border-radius:12px;padding:10px 18px">
    Waiting for jpsub to start…
  </div>
</body>
"""


class Overlay:
    def __init__(self, args):
        self.args = args
        self.url = args.url.rstrip("/") + "/overlay"
        self.layered = GtkLayerShell is not None and GtkLayerShell.is_supported()

        self.window = Gtk.Window(title="jpsub")
        self.window.set_decorated(False)
        self.window.set_app_paintable(True)
        visual = self.window.get_screen().get_rgba_visual()
        if visual:
            self.window.set_visual(visual)

        monitor = Gdk.Display.get_default().get_monitor(0).get_geometry()
        width = min(args.width, monitor.width - 16)
        height = min(args.height, monitor.height - 2 * args.margin)
        self.window.set_default_size(width, height)
        self.window.set_size_request(width, height)

        if self.layered:
            GtkLayerShell.init_for_window(self.window)
            GtkLayerShell.set_namespace(self.window, "jpsub")
            GtkLayerShell.set_layer(self.window, GtkLayerShell.Layer.OVERLAY)
            GtkLayerShell.set_keyboard_mode(self.window, GtkLayerShell.KeyboardMode.NONE)
        else:
            self.window.set_keep_above(True)
            self.window.set_accept_focus(False)
            self.window.set_skip_taskbar_hint(True)
        self.set_position("bottom")

        # A persistent profile keeps the overlay's font size and position.
        data = Path(GLib.get_user_data_dir()) / "jpsub" / "overlay"
        cache = Path(GLib.get_user_cache_dir()) / "jpsub" / "overlay"
        manager = WebKit2.WebsiteDataManager(
            base_data_directory=str(data), base_cache_directory=str(cache)
        )
        context = WebKit2.WebContext.new_with_website_data_manager(manager)
        content = WebKit2.UserContentManager()
        content.register_script_message_handler("jpsub")
        content.connect("script-message-received::jpsub", self.on_message)
        self.view = WebKit2.WebView(web_context=context, user_content_manager=content)
        self.view.set_background_color(Gdk.RGBA(0, 0, 0, 0))
        if args.debug:
            self.view.get_settings().set_enable_write_console_messages_to_stdout(True)
        self.view.connect("load-failed", self.on_load_failed)
        self.view.connect("context-menu", lambda *_: True)
        # The page cannot tell when the pointer moves onto the click-through
        # area, because that is still inside the web view.
        self.view.connect("enter-notify-event", self.on_pointer, "true")
        self.view.connect("leave-notify-event", self.on_pointer, "false")
        self.window.add(self.view)

        self.window.connect("destroy", Gtk.main_quit)
        self.window.show_all()
        self.view.load_uri(self.url)

    def set_position(self, position):
        top = position == "top"
        if self.layered:
            for edge, on in ((GtkLayerShell.Edge.TOP, top), (GtkLayerShell.Edge.BOTTOM, not top)):
                GtkLayerShell.set_anchor(self.window, edge, on)
                GtkLayerShell.set_margin(self.window, edge, self.args.margin if on else 0)
        else:
            monitor = Gdk.Display.get_default().get_monitor(0).get_geometry()
            width, height = self.window.get_size_request()
            y = self.args.margin if top else monitor.height - height - self.args.margin
            self.window.move(monitor.x + (monitor.width - width) // 2, monitor.y + y)

    def set_click_region(self, rects):
        """Only the drawn parts of the window take clicks; the rest passes through."""
        region = cairo.Region([cairo.RectangleInt(*map(int, rect)) for rect in rects])
        self.window.input_shape_combine_region(region)

    def on_message(self, _manager, result):
        message = json.loads(result.get_js_value().to_json(0))
        if self.args.debug:
            print("page:", message, flush=True)
        kind = message.get("type")
        if kind == "region":
            self.set_click_region(message["rects"])
        elif kind == "position":
            self.set_position(message["value"])
        elif kind == "close":
            self.window.destroy()

    def on_pointer(self, _view, _event, inside):
        self.view.evaluate_javascript(
            f"window.pointerInWindow && pointerInWindow({inside})",
            -1, None, None, None, None, None,
        )
        return False

    def on_load_failed(self, _view, _event, uri, _error):
        if uri != self.url:
            return False
        # jpsub is not running yet: say so and keep trying.
        self.window.input_shape_combine_region(None)
        self.view.load_html(WAITING_PAGE, "about:blank")
        GLib.timeout_add_seconds(2, self.retry)
        return True

    def retry(self):
        self.view.load_uri(self.url)
        return False


def main():
    parser = argparse.ArgumentParser(description="Floating jpsub subtitle window.")
    parser.add_argument("--url", default="http://127.0.0.1:8765", help="where jpsub is running")
    parser.add_argument("--width", type=int, default=1000, help="maximum subtitle width in pixels")
    parser.add_argument("--height", type=int, default=560,
                        help="room for subtitles plus the dictionary popup")
    parser.add_argument("--margin", type=int, default=48, help="gap from the screen edge")
    parser.add_argument("--debug", action="store_true", help="print messages and console output from the page")
    args = parser.parse_args()

    Overlay(args)
    try:
        gi.require_version("GLibUnix", "2.0")
        from gi.repository import GLibUnix
        signal_add = GLibUnix.signal_add
    except (ValueError, ImportError):  # older GLib bindings
        signal_add = GLib.unix_signal_add
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal_add(GLib.PRIORITY_DEFAULT, sig, Gtk.main_quit)
    Gtk.main()


if __name__ == "__main__":
    main()
