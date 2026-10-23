"use strict";

const $ = (id) => document.getElementById(id);
// ---------- settings (kept in this browser) ----------

function load(key, fallback) {
  try {
    const value = localStorage.getItem("jpsub." + key);
    return value === null ? fallback : JSON.parse(value);
  } catch {
    return fallback;
  }
}
function save(key, value) {
  try {
    localStorage.setItem("jpsub." + key, JSON.stringify(value));
  } catch {
    /* storage unavailable; settings just won't persist */
  }
}

let fontSize = load("fontSize", 2);
let saved = load("saved", []);

function applyFontSize() {
  document.documentElement.style.setProperty("--fs", fontSize + "rem");
}
function applyFurigana(mode) {
  document.body.dataset.furigana = mode;
  $("furigana").value = mode;
}
function applyScript(script) {
  document.body.dataset.script = script;
  $("script").value = script;
}
applyFontSize();
applyFurigana(load("furigana", "on"));
applyScript(load("script", "kana"));

$("script").onchange = (e) => {
  applyScript(e.target.value);
  save("script", e.target.value);
};

$("furigana").onchange = (e) => {
  applyFurigana(e.target.value);
  save("furigana", e.target.value);
};
$("smaller").onclick = () => resize(-0.2);
$("larger").onclick = () => resize(0.2);
function resize(delta) {
  fontSize = Math.min(4, Math.max(1, Math.round((fontSize + delta) * 10) / 10));
  applyFontSize();
  save("fontSize", fontSize);
}

// ---------- transcript ----------

const transcript = $("transcript");
const linesEl = $("lines");
const partialEl = $("partial");
const words = new WeakMap(); // word element -> {word, line}
let selected = null;
let following = true;

function addLine(line) {
  const div = el("div", "line");
  renderLine(div, line, words);
  linesEl.append(div);
}

function scrollToLive() {
  transcript.scrollTop = transcript.scrollHeight;
}
function afterUpdate() {
  $("empty").hidden = linesEl.childElementCount > 0 || partialEl.childElementCount > 0;
  if (following) scrollToLive();
}
transcript.addEventListener("scroll", () => {
  following = transcript.scrollHeight - transcript.scrollTop - transcript.clientHeight < 80;
  $("jump").hidden = following;
});
$("jump").onclick = () => {
  following = true;
  scrollToLive();
};

function pick(span) {
  const info = words.get(span);
  if (!info) return;
  if (selected) selected.classList.remove("selected");
  selected = span;
  span.classList.add("selected");
  showTab("lookup");
  lookup(info.word, info.line.text);
}
transcript.addEventListener("click", (e) => {
  const span = e.target.closest(".w");
  if (span) pick(span);
});
transcript.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && e.target.classList.contains("w")) pick(e.target);
});

// ---------- connection ----------

let socket = null;
let paused = false;

function setStatus(state, detail) {
  const labels = {
    starting: "Starting…",
    listening: "Listening",
    paused: "Paused",
    ended: "File finished",
    error: detail || "Audio capture problem",
    offline: "Disconnected — is jpsub running?",
  };
  const shown = paused && state === "listening" ? "paused" : state;
  $("dot").className = "dot " + (shown === "offline" || shown === "error" ? "error" : shown);
  $("status").textContent = labels[shown] || shown;
}
let lastState = "starting";
let lastDetail = "";
function refreshStatus() {
  setStatus(lastState, lastDetail);
  $("pause").textContent = paused ? "Resume" : "Pause";
}

function connect() {
  socket = new WebSocket(`ws://${location.host}/ws`);
  socket.onmessage = (message) => {
    const event = JSON.parse(message.data);
    if (event.type === "init") {
      linesEl.replaceChildren();
      partialEl.replaceChildren();
      event.lines.forEach(addLine);
      paused = event.paused;
      lastState = event.status.state;
      lastDetail = event.status.detail;
      refreshStatus();
    } else if (event.type === "partial") {
      renderLine(partialEl, event.line, words);
    } else if (event.type === "final") {
      partialEl.replaceChildren();
      addLine(event.line);
    } else if (event.type === "status") {
      lastState = event.state;
      lastDetail = event.detail;
      refreshStatus();
    } else if (event.type === "paused") {
      paused = event.value;
      if (paused) partialEl.replaceChildren();
      refreshStatus();
    } else if (event.type === "clear") {
      linesEl.replaceChildren();
      partialEl.replaceChildren();
    }
    afterUpdate();
  };
  socket.onclose = () => {
    setStatus("offline");
    setTimeout(connect, 1500);
  };
}
function send(command) {
  if (socket && socket.readyState === WebSocket.OPEN) socket.send(JSON.stringify(command));
}

$("pause").onclick = () => send({ type: "pause", value: !paused });
$("clear").onclick = () => send({ type: "clear" });
document.addEventListener("keydown", (e) => {
  if (e.code === "Space" && !e.target.closest("button, select, input, .w")) {
    e.preventDefault();
    send({ type: "pause", value: !paused });
  }
});

// ---------- lookup panel ----------

function showTab(name) {
  for (const tab of ["lookup", "saved"]) {
    $(tab).hidden = tab !== name;
    $("tab-" + tab).classList.toggle("active", tab === name);
  }
  if (name === "saved") renderSaved();
}
$("tab-lookup").onclick = () => showTab("lookup");
$("tab-saved").onclick = () => showTab("saved");

let lookupSerial = 0;

async function lookup(word, sentence, part) {
  const target = part || word;
  const serial = ++lookupSerial;
  const pane = $("lookup");
  let entries = [];
  let failed = false;
  try {
    entries = await fetchEntries(word, part);
  } catch {
    failed = true;
  }
  if (serial !== lookupSerial) return;

  pane.replaceChildren();
  pane.scrollTop = 0;
  pane.append(...renderHeard(word, part, (p) => lookup(word, sentence, p)));

  if (failed) {
    pane.append(el("p", "hint", "Lookup failed — is jpsub still running?"));
    return;
  }
  if (!entries.length) {
    pane.append(el("p", "hint", "No dictionary entry found. It may be a name, or a mis-heard word."));
  }
  for (const entry of entries) pane.append(renderEntry(entry, sentence));

  const more = el("a", "more", `Search “${target.l}” on Jisho ↗`);
  more.href = "https://jisho.org/search/" + encodeURIComponent(target.l);
  more.target = "_blank";
  more.rel = "noopener";
  pane.append(more);
}

function renderEntry(entry, sentence) {
  const wrap = el("div", "entry");
  const head = el("div", "entry-head");
  const headword = entry.kanji[0] || entry.kana[0];
  head.append(el("span", "headword", headword));
  if (entry.kanji.length) head.append(el("span", "reading", entry.kana[0]));
  if (entry.common) head.append(el("span", "badge", "common"));

  const key = headword + "|" + entry.kana[0];
  const star = el("button", "star");
  star.type = "button";
  const paint = () => {
    const on = saved.some((item) => item.key === key);
    star.textContent = on ? "★" : "☆";
    star.classList.toggle("on", on);
    star.title = on ? "Remove from saved words" : "Save this word";
  };
  star.onclick = () => {
    if (saved.some((item) => item.key === key)) {
      saved = saved.filter((item) => item.key !== key);
    } else {
      saved.push({
        key,
        word: headword,
        reading: entry.kana[0],
        meaning: entry.senses.slice(0, 3).map((s) => s.gloss.join(", ")).join("; "),
        sentence,
      });
    }
    save("saved", saved);
    paint();
    updateSavedCount();
  };
  paint();
  head.append(star);
  wrap.append(head);

  const others = [...entry.kanji.slice(1), ...entry.kana.slice(1)];
  if (others.length) wrap.append(el("div", "alt", "Also: " + others.join("、")));

  wrap.append(renderSenses(entry));
  return wrap;
}

// ---------- saved words ----------

function updateSavedCount() {
  $("saved-count").textContent = saved.length ? `(${saved.length})` : "";
}
updateSavedCount();

function renderSaved() {
  const pane = $("saved");
  pane.replaceChildren();
  if (!saved.length) {
    pane.append(el("p", "hint", "Star a word in the Lookup tab to keep it here."));
    return;
  }
  const actions = el("div", "saved-actions");
  const exportButton = el("button", "", "Export for Anki (TSV)");
  exportButton.type = "button";
  exportButton.onclick = exportSaved;
  actions.append(exportButton);
  pane.append(actions);

  for (const item of [...saved].reverse()) {
    const row = el("div", "saved-item");
    row.append(el("span", "saved-word", item.word));
    row.append(el("span", "saved-meaning", `${item.reading} — ${item.meaning}`));
    const remove = el("button", "", "×");
    remove.type = "button";
    remove.title = "Remove";
    remove.onclick = () => {
      saved = saved.filter((other) => other.key !== item.key);
      save("saved", saved);
      updateSavedCount();
      renderSaved();
    };
    row.append(remove);
    pane.append(row);
  }
}

function exportSaved() {
  const clean = (text) => String(text || "").replace(/[\t\n]/g, " ");
  const rows = saved.map((item) =>
    [item.word, item.reading, item.meaning, item.sentence].map(clean).join("\t")
  );
  const blob = new Blob([rows.join("\n") + "\n"], { type: "text/tab-separated-values" });
  const link = el("a");
  link.href = URL.createObjectURL(blob);
  link.download = "jpsub-words.tsv";
  link.click();
  URL.revokeObjectURL(link.href);
}

connect();
