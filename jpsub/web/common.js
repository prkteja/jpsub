"use strict";
// Shared by the full page (app.js) and the floating overlay (overlay.js).

const el = (tag, className, text) => {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
};

const POS_LABELS = {
  動詞: "verb", 形容詞: "i-adjective", 形状詞: "na-adjective", 名詞: "noun", 代名詞: "pronoun",
  副詞: "adverb", 助詞: "particle", 助動詞: "auxiliary", 接続詞: "conjunction",
  感動詞: "interjection", 連体詞: "pre-noun adjectival", 接尾辞: "suffix", 接頭辞: "prefix",
};

// Fill `container` with a line's words; clickable ones are recorded in `registry`
// (a WeakMap from element to {word, line}).
function renderLine(container, line, registry) {
  container.replaceChildren();
  for (const word of line.words) {
    if (word.x) {
      container.append(word.s);
      continue;
    }
    const span = el("span", "w");
    span.tabIndex = 0;
    // Both reading styles are rendered; the stylesheet shows one of them
    // depending on body[data-script].
    const kana = el("span", "kana");
    for (const [text, reading] of word.f) {
      if (reading) {
        const ruby = el("ruby");
        ruby.append(text, el("rt", "", reading));
        kana.append(ruby);
      } else {
        kana.append(text);
      }
    }
    span.append(kana);
    if (word.ro) {
      span.classList.add("has-romaji");
      // The wrapper is what gets shown and hidden: WebKitGTK does not accept
      // "display: ruby", so the <ruby> itself must keep its default display.
      const romaji = el("span", "romaji");
      const ruby = el("ruby");
      ruby.append(word.s, el("rt", "", word.ro));
      romaji.append(ruby);
      span.append(romaji);
    }
    registry.set(span, { word, line });
    container.append(span);
  }
}

// Dictionary entries for a word, or for one of its parts (an attached ending).
async function fetchEntries(word, part) {
  const target = part || word;
  const params = new URLSearchParams({ lemma: target.l, pos: target.p, surface: target.s });
  if (!part) {
    params.set("normalized", word.n);
    // The reading belongs to the surface form, so it only identifies the
    // dictionary entry when the word is not inflected.
    if (word.s === word.l) params.set("reading", word.r);
  }
  const response = await fetch("/api/lookup?" + params);
  if (!response.ok) throw new Error(response.statusText);
  return (await response.json()).entries;
}

// The "heard → dictionary form · part of speech" line plus buttons for each part.
function renderHeard(word, part, onPart) {
  const nodes = [];
  const heard = el("p", "heard");
  heard.append(el("b", "", word.s));
  if (word.s !== word.l) heard.append(" → " + word.l);
  heard.append(" · " + (POS_LABELS[word.p] || word.p));
  nodes.push(heard);
  if (word.parts) {
    const parts = el("div", "parts");
    word.parts.forEach((p, i) => {
      const button = el("button", "", p.s === p.l ? p.s : `${p.s} (${p.l})`);
      button.type = "button";
      if ((part || word.parts[0]) === p) button.classList.add("active");
      button.onclick = () => onPart(i === 0 ? undefined : p);
      parts.append(button);
    });
    nodes.push(parts);
  }
  return nodes;
}

// Numbered senses; `limit` truncates long entries.
function renderSenses(entry, limit) {
  const list = el("ol", "senses");
  let lastPos = "";
  for (const sense of entry.senses.slice(0, limit || entry.senses.length)) {
    const item = el("li");
    const pos = sense.pos.join(", ");
    if (pos && pos !== lastPos) item.append(el("span", "pos", pos));
    lastPos = pos;
    item.append(sense.gloss.join("; "));
    const notes = [...sense.tags, ...sense.info];
    if (notes.length) item.append(el("span", "note", " — " + notes.join("; ")));
    list.append(item);
  }
  return list;
}
