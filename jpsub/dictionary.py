"""JMdict lookup backed by SQLite.

jpsub builds the database on first run (see assets.py). To build it by hand:
python -m jpsub.dictionary SOURCE, where SOURCE is a jmdict-simplified
"jmdict-eng" .json file or the .json.zip it is released as.
"""
import json
import sqlite3
import sys
import zipfile
from pathlib import Path

from . import paths
from .japanese import has_kanji

# Sudachi part of speech -> JMdict part-of-speech tag prefixes.
_POS = {
    "動詞": ("v",),
    "形容詞": ("adj-i", "adj-ix"),
    "形状詞": ("adj-na", "adj-no", "adj-t"),
    "名詞": ("n", "num"),
    "代名詞": ("pn",),
    "副詞": ("adv",),
    "助詞": ("prt",),
    "助動詞": ("aux", "cop"),
    "接続詞": ("conj",),
    "感動詞": ("int",),
    "連体詞": ("adj-pn",),
    "接尾辞": ("suf", "n-suf", "ctr"),
    "接頭辞": ("pref", "n-pref"),
}


def _read_source(source):
    source = Path(source)
    if zipfile.is_zipfile(source):
        with zipfile.ZipFile(source) as archive:
            (name,) = [n for n in archive.namelist() if n.endswith(".json")]
            return json.loads(archive.read(name))
    return json.loads(source.read_text(encoding="utf-8"))


def build(source, db_path):
    data = _read_source(source)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = db_path.with_suffix(".tmp")
    tmp.unlink(missing_ok=True)
    db = sqlite3.connect(tmp)
    db.executescript(
        "CREATE TABLE entry(id INTEGER PRIMARY KEY, data TEXT);"
        "CREATE TABLE form(text TEXT, entry_id INTEGER);"
        "CREATE TABLE tag(code TEXT PRIMARY KEY, label TEXT);"
    )
    db.executemany("INSERT INTO tag VALUES (?, ?)", data["tags"].items())
    for word in data["words"]:
        entry = {
            # "sK" marks search-only spellings that should not be displayed.
            "kanji": [k["text"] for k in word["kanji"] if "sK" not in k["tags"]],
            "kana": [k["text"] for k in word["kana"] if "sk" not in k["tags"]],
            "common": any(f["common"] for f in word["kanji"] + word["kana"]),
            "senses": [
                {
                    "pos": s["partOfSpeech"],
                    "gloss": [g["text"] for g in s["gloss"]],
                    "tags": s["misc"] + s["field"] + s["dialect"],
                    "info": s["info"],
                }
                for s in word["sense"]
            ],
        }
        entry_id = int(word["id"])
        db.execute(
            "INSERT INTO entry VALUES (?, ?)",
            (entry_id, json.dumps(entry, ensure_ascii=False)),
        )
        forms = {f["text"] for f in word["kanji"] + word["kana"]}
        db.executemany("INSERT INTO form VALUES (?, ?)", [(f, entry_id) for f in forms])
    db.execute("CREATE INDEX form_text ON form(text)")
    db.commit()
    db.close()
    tmp.replace(db_path)
    return len(data["words"])


def _pos_matches(code, prefixes):
    return any(
        code == p or code.startswith(p + "-") or (p == "v" and code.startswith("v"))
        for p in prefixes
    )


class Dictionary:
    def __init__(self, db_path=None):
        db_path = db_path or paths.dictionary_path()
        self._db = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, check_same_thread=False)
        self._tags = dict(self._db.execute("SELECT code, label FROM tag"))

    def _entries(self, text):
        rows = self._db.execute(
            "SELECT e.id, e.data FROM form f JOIN entry e ON e.id = f.entry_id WHERE f.text = ?",
            (text,),
        )
        return [(entry_id, json.loads(data)) for entry_id, data in rows]

    def lookup(self, lemma, normalized="", surface="", reading="", pos="", limit=8):
        """Return entries for a word, best match first.

        `normalized` is the tokenizer's standard spelling (居る for いる), which
        picks the right entry among homophones. `reading` should only be given
        for uninflected words, where it is the reading of the lemma itself.
        """
        prefixes = _POS.get(pos, ())
        scored = {}
        for key, weight in ((lemma, 40), (normalized, 30), (surface, 10)):
            if not key:
                continue
            for entry_id, entry in self._entries(key):
                if entry_id in scored:
                    continue
                score = weight
                if entry["common"]:
                    score += 25
                if normalized and has_kanji(normalized) and normalized in entry["kanji"]:
                    score += 60 if lemma in entry["kana"] else 20
                if reading and reading in entry["kana"]:
                    score += 20
                if any(_pos_matches(c, prefixes) for s in entry["senses"] for c in s["pos"]):
                    score += 30
                if not has_kanji(key):
                    first = entry["senses"][0] if entry["senses"] else {"tags": []}
                    if not entry["kanji"] or "uk" in first["tags"]:
                        score += 15
                scored[entry_id] = (score, entry)
        ranked = sorted(scored.values(), key=lambda pair: -pair[0])[:limit]
        return [self._present(entry) for _, entry in ranked]

    def _present(self, entry):
        label = lambda code: self._tags.get(code, code)
        return {
            "kanji": entry["kanji"],
            "kana": entry["kana"],
            "common": entry["common"],
            "senses": [
                {
                    "pos": [label(c) for c in s["pos"]],
                    "gloss": s["gloss"],
                    "tags": [label(c) for c in s["tags"]],
                    "info": s["info"],
                }
                for s in entry["senses"]
            ],
        }


if __name__ == "__main__":
    count = build(sys.argv[1], paths.dictionary_path())
    print(f"Built {paths.dictionary_path()} with {count} entries")
