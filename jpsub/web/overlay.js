"use strict";
// Floating subtitle bar with a popup dictionary. Runs inside the native overlay
// window (jpsub/overlay.py), and also in a normal browser tab for testing.

const $ = (id) => document.getElementById(id);
const native = window.webkit?.messageHandlers?.jpsub;
const tell = (message) => native && native.postMessage(message);
if (!native) document.body.classList.add("browser");

const VISIBLE_LINES = 2;
const POPUP_ENTRIES = 3;
const POPUP_SENSES = 4;
const LEAVE_DELAY = 700; // ms the pointer may be away before the popup closes

function load(key, fallback) {
  try {
    const value = localStorage.getItem("jpsub.overlay." + key);
    return value === null ? fallback : JSON.parse(value);
  } catch {
    return fallback;
  }
}
function save(key, value) {
  try {
    localStorage.setItem("jpsub.overlay." + key, JSON.stringify(value));
  } catch {
    /* storage unavailable; settings just won't persist */
  }
}

// ---------- settings ----------

let fontSize = load("fontSize", 1.7);
let furigana = load("furigana", "on");
let position = load("position", "bottom");
let opacity = load("opacity", 85); // background opacity, percent
let script = load("script", "kana"); // readings in "kana" or "romaji"

function applySettings() {
  document.documentElement.style.setProperty("--fs", fontSize + "rem");
  document.documentElement.style.setProperty("--opacity", opacity / 100);
  $("opacity").value = opacity;
  document.body.dataset.furigana = furigana;
  document.body.dataset.script = script;
  $("script").textContent = script === "kana" ? "あ" : "a";
  document.body.dataset.position = position;
}
applySettings();
tell({ type: "position", value: position });

$("smaller").onclick = () => resize(-0.15);
$("larger").onclick = () => resize(0.15);
function resize(delta) {
  fontSize = Math.min(3.2, Math.max(1, Math.round((fontSize + delta) * 100) / 100));
  save("fontSize", fontSize);
  applySettings();
}
$("opacity").oninput = (e) => {
  opacity = Number(e.target.value);
  save("opacity", opacity);
  applySettings();
};
$("script").onclick = () => {
  closePopup();
  script = script === "kana" ? "romaji" : "kana";
  save("script", script);
  applySettings();
};
$("furigana").onclick = () => {
  furigana = { on: "hover", hover: "off", off: "on" }[furigana];
  save("furigana", furigana);
  applySettings();
};
$("position").onclick = () => {
  closePopup();
  position = position === "bottom" ? "top" : "bottom";
  save("position", position);
  applySettings();
  tell({ type: "position", value: position });
};
$("close").onclick = () => (native ? tell({ type: "close" }) : window.close());

// ---------- subtitle lines ----------

const bar = $("bar");
const linesEl = $("lines");
const popup = $("popup");
const words = new WeakMap();
let finals = [];
let partial = null;
let status = "starting";
let paused = false;
let hovering = false;
let dirty = false;
let selected = null;

// While the pointer is over the overlay the text stays put, so the word you
// are reaching for does not move; updates are applied once you leave.
const frozen = () => hovering || !popup.hidden;

function render() {
  if (frozen()) {
    dirty = true;
    return;
  }
  dirty = false;
  const shown = finals.slice(-VISIBLE_LINES).map((line) => ({ line, cls: "line old" }));
  if (partial && partial.words.length) shown.push({ line: partial, cls: "line partial" });
  const visible = shown.slice(-VISIBLE_LINES);
  if (visible.length && !visible[visible.length - 1].cls.includes("partial")) {
    visible[visible.length - 1].cls = "line";
  }
  linesEl.replaceChildren();
  for (const { line, cls } of visible) {
    const div = el("div", cls);
    renderLine(div, line, words);
    linesEl.append(div);
  }
  const notes = {
    offline: "Disconnected — is jpsub running?",
    error: "Audio capture problem",
    ended: "File finished",
  };
  const note = notes[status] || (paused ? "Paused" : "");
  if (!visible.length) {
    linesEl.append(el("div", "line note", note || "Waiting for Japanese audio…"));
  }
  $("status").textContent = visible.length ? note : "";
  $("pause").textContent = paused ? "▶" : "⏸";
  document.body.classList.toggle("idle", !visible.length);
}

// ---------- popup dictionary ----------

let lookupSerial = 0;

function closePopup() {
  lookupSerial++;
  popup.hidden = true;
  popup.replaceChildren();
  if (selected) selected.classList.remove("selected");
  selected = null;
  if (dirty) render();
  reportRegion();
}

async function openPopup(span, part) {
  const info = words.get(span);
  if (!info) return;
  if (selected && selected !== span) selected.classList.remove("selected");
  selected = span;
  span.classList.add("selected");
  const serial = ++lookupSerial;
  const { word } = info;
  let entries = [];
  let failed = false;
  try {
    entries = await fetchEntries(word, part);
  } catch {
    failed = true;
  }
  if (serial !== lookupSerial) return;

  popup.replaceChildren(...renderHeard(word, part, (p) => openPopup(span, p)));
  if (failed) {
    popup.append(el("p", "hint", "Lookup failed — is jpsub still running?"));
  } else if (!entries.length) {
    popup.append(el("p", "hint", "No dictionary entry found. It may be a name, or a mis-heard word."));
  }
  for (const entry of entries.slice(0, POPUP_ENTRIES)) {
    const wrap = el("div", "entry");
    const head = el("div", "entry-head");
    head.append(el("span", "headword", entry.kanji[0] || entry.kana[0]));
    if (entry.kanji.length) head.append(el("span", "reading", entry.kana[0]));
    if (entry.common) head.append(el("span", "badge", "common"));
    wrap.append(head, renderSenses(entry, POPUP_SENSES));
    const extra = entry.senses.length - POPUP_SENSES;
    if (extra > 0) wrap.append(el("div", "more-senses", `+${extra} more in the full page`));
    popup.append(wrap);
  }
  popup.hidden = false;
  popup.scrollTop = 0;
  placePopup(span);
}

function placePopup(span) {
  const gap = 8;
  const barRect = bar.getBoundingClientRect();
  const wordRect = span.getBoundingClientRect();
  const width = popup.offsetWidth;
  const center = wordRect.left + wordRect.width / 2;
  const left = Math.max(4, Math.min(window.innerWidth - width - 4, center - width / 2));
  popup.style.left = left + "px";
  if (position === "bottom") {
    popup.style.top = "";
    popup.style.bottom = window.innerHeight - barRect.top + gap + "px";
    popup.style.maxHeight = Math.max(120, barRect.top - gap - 4) + "px";
  } else {
    popup.style.bottom = "";
    popup.style.top = barRect.bottom + gap + "px";
    popup.style.maxHeight = Math.max(120, window.innerHeight - barRect.bottom - gap - 4) + "px";
  }
  reportRegion();
}

linesEl.addEventListener("click", (e) => {
  const span = e.target.closest(".w");
  if (!span) return;
  if (span === selected) closePopup();
  else openPopup(span);
});

// ---------- pointer tracking ----------

const IDLE_DELAY = 3000; // ms the text stays frozen after the pointer last moved
let leaveTimer = null;
let idleTimer = null;
let outsideWindow = false; // set by the native window, which sees the pointer leave reliably
let lastPoint = "";

function pointerActive() {
  document.body.classList.add("pointer");
  clearTimeout(leaveTimer);
  clearTimeout(idleTimer);
  hovering = true;
  // A pointer parked on the bar should not hold the subtitles back.
  idleTimer = setTimeout(() => {
    hovering = false;
    if (popup.hidden && dirty) render();
  }, IDLE_DELAY);
}

function pointerLeft() {
  document.body.classList.remove("pointer");
  if (!hovering && popup.hidden) return;
  clearTimeout(leaveTimer);
  clearTimeout(idleTimer);
  leaveTimer = setTimeout(() => {
    hovering = false;
    if (!popup.hidden) closePopup();
    else if (dirty) render();
  }, LEAVE_DELAY);
}

// The window is larger than the bar, so the pointer can leave the bar without
// leaving the page: decide by what is under it, not by mouseleave alone.
document.addEventListener("mousemove", (e) => {
  // Redrawing the text makes the browser replay a mousemove at the old
  // position; only real movement counts.
  const point = e.screenX + "," + e.screenY;
  if (point === lastPoint || outsideWindow) return;
  lastPoint = point;
  if (e.target.closest && e.target.closest("#bar, #popup")) pointerActive();
  else pointerLeft();
});
document.documentElement.addEventListener("mouseleave", pointerLeft);

// Called by the native window on pointer enter and leave.
window.pointerInWindow = (inside) => {
  outsideWindow = !inside;
  lastPoint = "";
  if (!inside) pointerLeft();
};

// ---------- click-through region ----------

// The native window is larger than what is drawn. Report the drawn rectangles
// so clicks everywhere else go to the video underneath.
let lastRegion = "";
function reportRegion() {
  const rects = [bar, popup]
    .filter((node) => !node.hidden)
    .map((node) => {
      const r = node.getBoundingClientRect();
      return [Math.floor(r.left), Math.floor(r.top), Math.ceil(r.width) + 1, Math.ceil(r.height) + 1];
    });
  if (!popup.hidden && rects.length === 2) {
    // Bridge the gap between bar and popup so the pointer can cross it.
    const [b, p] = rects;
    const top = Math.min(b[1] + b[3], p[1] + p[3]);
    const bottom = Math.max(b[1], p[1]);
    if (bottom > top) rects.push([p[0], top, p[2], bottom - top]);
  }
  const encoded = JSON.stringify(rects);
  if (encoded === lastRegion) return;
  lastRegion = encoded;
  tell({ type: "region", rects });
}
new ResizeObserver(reportRegion).observe(bar);
new ResizeObserver(reportRegion).observe(popup);
window.addEventListener("resize", reportRegion);

// ---------- connection ----------

let socket = null;

function connect() {
  socket = new WebSocket(`ws://${location.host}/ws`);
  socket.onmessage = (message) => {
    const event = JSON.parse(message.data);
    if (event.type === "init") {
      finals = event.lines.slice(-VISIBLE_LINES);
      partial = null;
      paused = event.paused;
      status = event.status.state;
    } else if (event.type === "partial") {
      partial = event.line;
    } else if (event.type === "final") {
      partial = null;
      finals.push(event.line);
      finals = finals.slice(-VISIBLE_LINES);
    } else if (event.type === "status") {
      status = event.state;
    } else if (event.type === "paused") {
      paused = event.value;
      if (paused) partial = null;
    } else if (event.type === "clear") {
      finals = [];
      partial = null;
    }
    render();
  };
  socket.onclose = () => {
    status = "offline";
    render();
    setTimeout(connect, 1500);
  };
}
$("pause").onclick = () => {
  if (socket && socket.readyState === WebSocket.OPEN) {
    socket.send(JSON.stringify({ type: "pause", value: !paused }));
  }
};

render();
reportRegion();
connect();
