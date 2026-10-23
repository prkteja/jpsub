"""Web server: pushes subtitle lines over a WebSocket and answers dictionary lookups."""
import asyncio
import json
import time
from collections import deque
from pathlib import Path

from aiohttp import WSMsgType, web

from .dictionary import Dictionary
from .japanese import Analyzer
from .recognizer import Recognizer

WEB = Path(__file__).resolve().parent / "web"
HISTORY_LINES = 500


class Hub:
    """Holds subtitle history and fans events out to connected browsers."""

    def __init__(self, loop):
        self.loop = loop
        self.clients = set()
        self.lines = deque(maxlen=HISTORY_LINES)
        self.status = {"type": "status", "state": "starting", "detail": ""}
        self.analyzer = Analyzer()

    def emit(self, event):
        """Called from the recognizer thread."""
        if event["type"] in ("partial", "final"):
            event = {
                "type": event["type"],
                "line": {
                    "id": event["id"],
                    "t": int(time.time() * 1000),
                    "text": event["text"],
                    "words": self.analyzer.analyze(event["text"]),
                },
            }
        self.loop.call_soon_threadsafe(self.dispatch, event)

    def dispatch(self, event):
        if event["type"] == "final":
            self.lines.append(event["line"])
        elif event["type"] == "status":
            self.status = event
        elif event["type"] == "clear":
            self.lines.clear()
        message = json.dumps(event, ensure_ascii=False)
        for ws in list(self.clients):
            self.loop.create_task(self._send(ws, message))

    async def _send(self, ws, message):
        try:
            await ws.send_str(message)
        except ConnectionError:
            self.clients.discard(ws)


async def websocket(request):
    hub = request.app["hub"]
    recognizer = request.app["recognizer"]
    ws = web.WebSocketResponse(heartbeat=30)
    await ws.prepare(request)
    await ws.send_str(json.dumps({
        "type": "init",
        "lines": list(hub.lines),
        "status": hub.status,
        "paused": recognizer.paused.is_set(),
    }, ensure_ascii=False))
    hub.clients.add(ws)
    try:
        async for message in ws:
            if message.type != WSMsgType.TEXT:
                continue
            command = json.loads(message.data)
            if command.get("type") == "pause":
                if command.get("value"):
                    recognizer.paused.set()
                else:
                    recognizer.paused.clear()
                hub.dispatch({"type": "paused", "value": recognizer.paused.is_set()})
            elif command.get("type") == "clear":
                hub.dispatch({"type": "clear"})
    finally:
        hub.clients.discard(ws)
    return ws


async def lookup(request):
    q = request.query
    lemma = q.get("lemma", "").strip()
    if not lemma:
        raise web.HTTPBadRequest(text="lemma is required")
    entries = request.app["dictionary"].lookup(
        lemma,
        normalized=q.get("normalized", ""),
        surface=q.get("surface", ""),
        reading=q.get("reading", ""),
        pos=q.get("pos", ""),
    )
    return web.json_response({"lemma": lemma, "entries": entries})


async def index(request):
    return web.FileResponse(WEB / "index.html")


async def overlay(request):
    return web.FileResponse(WEB / "overlay.html")


async def start_recognizer(app):
    hub = Hub(asyncio.get_running_loop())
    app["hub"] = hub
    app["recognizer"] = Recognizer(hub.emit, **app["recognizer_options"])
    app["recognizer"].start()
    yield
    app["recognizer"].stop()


def create_app(recognizer_options):
    app = web.Application()
    app["recognizer_options"] = recognizer_options
    app["dictionary"] = Dictionary()
    app.cleanup_ctx.append(start_recognizer)
    app.router.add_get("/", index)
    app.router.add_get("/overlay", overlay)
    app.router.add_get("/ws", websocket)
    app.router.add_get("/api/lookup", lookup)
    app.router.add_static("/static", WEB)
    return app
